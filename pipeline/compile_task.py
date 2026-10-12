from __future__ import annotations

import random
import copy
from typing import Any

from key_routing import assign_record_keys
from business_catalog import add_secondary_businesses, role_display_name
from task_solver import _matches
from task_types import TASK_SCHEMA_VERSION, validate_ontology, validate_task_graph


def _owner_for_capability(ontology: dict[str, Any], capability: str) -> dict[str, Any]:
    matches = [role for role in ontology["roles"] if capability in role["capabilities"]]
    if len(matches) != 1:
        raise ValueError(f"capability must map to exactly one role: {capability}")
    return matches[0]


def _pick_values(topic: dict[str, Any], rng: random.Random) -> tuple[Any, Any]:
    satisfying = [value for value in topic["domain"] if _matches(value, topic["operator"], topic["threshold"])]
    failing = [value for value in topic["domain"] if not _matches(value, topic["operator"], topic["threshold"])]
    if not satisfying or not failing:
        raise ValueError(f"condition topic cannot express both truth values: {topic['topic_id']}")
    return rng.choice(satisfying), rng.choice(failing)


def _assign_decoy_values(
    distractor: dict[str, Any], candidates: list[dict[str, Any]],
    *, rng: random.Random, positive: bool, gold_candidate_id: str | None,
) -> dict[str, Any]:
    domain = list(distractor["domain"])
    if distractor["value_type"] == "boolean":
        preferred = True
    elif distractor["preference"] == "higher":
        preferred = max(domain)
    else:
        preferred = min(domain)
    alternatives = [value for value in domain if value != preferred]
    preferred_candidates = [item for item in candidates if not positive or item["candidate_id"] != gold_candidate_id]
    preferred_candidate = rng.choice(preferred_candidates)
    return {
        candidate["candidate_id"]: preferred if candidate == preferred_candidate else rng.choice(alternatives)
        for candidate in candidates
    }


def _build_records(
    *, task_id: str, seed: int, roles: list[dict[str, Any]], candidates: list[dict[str, Any]],
    observations: list[dict[str, Any]], positive: bool, gold_candidate_id: str | None,
    constraints: list[dict[str, Any]], numeric_topic_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    role_by_id = {role["role_id"]: role for role in roles}
    records: list[dict[str, Any]] = []
    record_by_role_candidate: dict[tuple[str, str], dict[str, Any]] = {}
    for role in roles:
        for candidate in candidates:
            candidate_id = candidate["candidate_id"]
            owned = [
                item for item in observations
                if item.get("reporter_role_id") == role["role_id"]
                and item.get("candidate_id") == candidate_id
            ]
            if not owned:
                continue
            record = {
                "record_id": f"rec_{role['role_id']}_{candidate_id}",
                "owner_role_id": role["role_id"], "candidate_id": candidate_id,
                "business_abbreviation": role["business_abbreviation"],
                "observation_ids": [item["observation_id"] for item in owned],
            }
            records.append(record)
            record_by_role_candidate[(role["role_id"], candidate_id)] = record
    routes: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        final_records = [record for record in records if record["candidate_id"] == candidate_id]
        routes.append({
            "candidate_id": candidate_id,
            "record_ids": [record["record_id"] for record in final_records],
            "distractor_record_ids": [record["record_id"] for record in final_records
                if role_by_id[record["owner_role_id"]]["kind"] == "distractor"],
        })
    random.Random(f"{task_id}:{seed}:candidate-order").shuffle(routes)
    record_keys = assign_record_keys(task_id=task_id, records=records, roles=roles)
    observation_by_id = {item["observation_id"]: item for item in observations}
    condition_topic_ids = {item["topic_id"] for item in constraints}
    required_record_ids: list[str] = []
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        candidate_facts = [
            item for item in observations
            if item.get("candidate_id") == candidate_id and item.get("observation_type") == "fact"
        ]
        failed_topics = [
            condition for condition in constraints
            if not _matches(
                next(item["claimed_value"] for item in candidate_facts if item["topic_id"] == condition["topic_id"]),
                condition["operator"], condition["threshold"],
            )
        ]
        needed_topics = (
            condition_topic_ids | numeric_topic_ids
            if positive and candidate_id == gold_candidate_id
            else {failed_topics[0]["topic_id"]}
        )
        for role in roles:
            record = record_by_role_candidate.get((role["role_id"], candidate_id))
            if record and any(observation_by_id[item]["topic_id"] in needed_topics for item in record["observation_ids"]):
                required_record_ids.append(record["record_id"])
    required_record_ids = list(dict.fromkeys(required_record_ids))
    return records, {
        "mode": "direct", "candidate_records": routes, "record_keys": record_keys,
        "required_record_ids": required_record_ids,
        "required_key_ideal_rounds": {record_keys[r]: 1 for r in required_record_ids},
        "finalize_ideal_round": 2,
    }


def compile_task(
    ontology: dict[str, Any], *, task_id: str, seed: int, positive: bool,
) -> dict[str, Any]:
    ontology = validate_ontology(ontology)
    rng = random.Random(seed)
    condition_topics = [topic for topic in ontology["topics"] if "operator" in topic]
    numeric_topic_ids = set(ontology["numeric_rule"]["topic_ids"])
    condition_capabilities = {topic["owner_capability"] for topic in condition_topics}
    numeric_capabilities = {
        topic["owner_capability"] for topic in ontology["topics"] if topic["topic_id"] in numeric_topic_ids
    }
    distractor_capabilities = {topic["owner_capability"] for topic in ontology.get("distractor_topics", [])}
    roles: list[dict[str, Any]] = []
    for source in ontology["roles"]:
        capabilities = set(source["capabilities"])
        if capabilities & condition_capabilities:
            kind = "decision"
        elif capabilities & numeric_capabilities:
            kind = "decision" if positive else "output"
        elif capabilities & distractor_capabilities:
            kind = "distractor"
        else:
            raise ValueError(f"Role has no compiled benchmark function: {source['role_id']}")
        roles.append({
            "role_id": source["role_id"], "name": role_display_name(source),
            "responsibility": source["responsibility"], "kind": kind,
            "role_abbreviation": source["role_abbreviation"],
            "business_abbreviation": source["business_abbreviation"],
            "business_title": source.get("business_title", source["responsibility"]),
            "secondary_business": copy.deepcopy(source["secondary_business"]),
        })
    candidates = [
        {"candidate_id": chr(ord("A") + index), "name": name}
        for index, name in enumerate(ontology["candidate_names"])
    ]
    gold_candidate_id = candidates[0]["candidate_id"] if positive else None
    truth_by_candidate = {
        candidate["candidate_id"]: {topic["topic_id"]: True for topic in condition_topics}
        for candidate in candidates
    }
    owner_conditions: dict[str, list[dict[str, Any]]] = {}
    for topic in condition_topics:
        owner = _owner_for_capability(ontology, topic["owner_capability"])["role_id"]
        owner_conditions.setdefault(owner, []).append(topic)
    decision_roles = sorted(owner_conditions)
    compound = ontology.get("incomplete_condition")
    if compound:
        threshold_id = compound["threshold_topic_id"]
        paired_role = next(role_id for role_id, topics in owner_conditions.items()
                           if any(topic["topic_id"] == threshold_id for topic in topics))
        # Keep the presence fact true; failure comes from its numeric condition.
        owner_conditions[paired_role].sort(key=lambda topic: topic["topic_id"] != threshold_id)
        # Negative tasks must also include a candidate failing only this threshold.
        decision_roles = [paired_role, *[role_id for role_id in decision_roles if role_id != paired_role]]
    if positive:
        for index, role_id in enumerate(decision_roles):
            candidate_id = candidates[1 + index % 2]["candidate_id"]
            truth_by_candidate[candidate_id][owner_conditions[role_id][0]["topic_id"]] = False
    else:
        for index, candidate in enumerate(candidates):
            role_id = decision_roles[index % len(decision_roles)]
            truth_by_candidate[candidate["candidate_id"]][owner_conditions[role_id][0]["topic_id"]] = False
    predicates: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        for topic in ontology["topics"]:
            owner = _owner_for_capability(ontology, topic["owner_capability"])["role_id"]
            if "operator" in topic:
                satisfying, failing = _pick_values(topic, rng)
                value = satisfying if truth_by_candidate[candidate_id][topic["topic_id"]] else failing
            else:
                value = rng.choice(topic["domain"])
            predicate_id = f"{candidate_id}_{topic['topic_id']}"
            predicates.append({
                "predicate_id": predicate_id, "candidate_id": candidate_id,
                "topic_id": topic["topic_id"], "domain": list(topic["domain"]),
                "gold_value": value, "owner_role_id": owner,
            })
            observations.append({
                "observation_id": f"obs_{predicate_id}", "observation_type": "fact",
                "predicate_id": predicate_id, "reporter_role_id": owner,
                "candidate_id": candidate_id, "topic_id": topic["topic_id"],
                "claimed_value": value, "handoff_topics": [],
            })
    for distractor in ontology.get("distractor_topics", []):
        owner = _owner_for_capability(ontology, distractor["owner_capability"])["role_id"]
        assigned_values = _assign_decoy_values(
            distractor, candidates, rng=rng, positive=positive, gold_candidate_id=gold_candidate_id,
        )
        for candidate in candidates:
            observations.append({
                "observation_id": f"obs_{candidate['candidate_id']}_{distractor['topic_id']}",
                "observation_type": "distractor", "predicate_id": None,
                "reporter_role_id": owner, "candidate_id": candidate["candidate_id"],
                "topic_id": distractor["topic_id"], "claimed_value": assigned_values[candidate["candidate_id"]],
                "handoff_topics": [],
            })
    constraints = [
        {"constraint_id": f"condition_{topic['topic_id']}", "topic_id": topic["topic_id"], "operator": topic["operator"], "threshold": topic["threshold"]}
        for topic in condition_topics
    ]
    records, routing = _build_records(
        task_id=task_id, seed=seed, roles=roles, candidates=candidates, observations=observations,
        positive=positive, gold_candidate_id=gold_candidate_id,
        constraints=constraints, numeric_topic_ids=numeric_topic_ids,
    )
    task = {
        "schema_version": TASK_SCHEMA_VERSION, "task_id": task_id, "seed": seed,
        "scenario": {
            "title": ontology["title"], "domain": ontology["domain"], "problem": ontology["problem"],
            "question": ontology["problem"], "positive_label": ontology["positive_label"],
            "negative_label": ontology["negative_label"], "candidate_type": ontology["candidate_type"],
        },
        "roles": roles, "candidates": candidates,
        "topics": [{key: value for key, value in topic.items() if key in {"topic_id", "label", "aliases", "value_type", "domain", "unit", "evidence_context"}} for topic in ontology["topics"]],
        "distractor_topics": ontology.get("distractor_topics", []),
        "predicates": predicates, "constraints": constraints,
        "numeric_rule": dict(ontology["numeric_rule"]), "observations": observations,
        "records": records, "routing": routing, "gold": None,
    }
    if ontology.get("language"):
        task["language"] = ontology["language"]
    if compound:
        task["incomplete_condition"] = copy.deepcopy(compound)
    role_by_id = {role["role_id"]: role for role in roles}
    for record in records:
        record["business_title"] = role_by_id[record["owner_role_id"]]["business_title"]
    add_secondary_businesses(task)
    task["routing"]["required_key_ideal_rounds"] = {
        task["routing"]["record_keys"][record_id]: 1
        for record_id in task["routing"]["required_record_ids"]
    }
    from runtime_settings import apply_budget
    return validate_task_graph(apply_budget(task))
