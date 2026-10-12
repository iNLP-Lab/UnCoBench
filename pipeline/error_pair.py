from __future__ import annotations

import copy
import itertools
import random
from typing import Any

from key_routing import assign_record_keys
from context_binding import validate_context_templates
from task_solver import _evaluate_complete, gold_assignment
from task_types import (
    ERROR_TYPES, GEOGRAPHY_CATALOG, GEOGRAPHY_VALID_VALUES, TASK_SCHEMA_VERSION, validate_task_graph,
)


def _counterfactual_values(
    task: dict[str, Any], record: dict[str, Any], *, seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    observation_by_id = {item["observation_id"]: item for item in task["observations"]}
    predicate_by_id = {item["predicate_id"]: item for item in task["predicates"]}
    observations = [
        observation_by_id[item] for item in record["observation_ids"]
        if observation_by_id[item].get("predicate_id") in predicate_by_id
    ]
    if not observations:
        raise ValueError("Error target record must contain formal facts")
    combinations = list(itertools.product(*(
        predicate_by_id[item["predicate_id"]]["domain"] for item in observations
    )))
    random.Random(f"{task['task_id']}:{seed}:{record['record_id']}:counterfactual").shuffle(combinations)
    full = gold_assignment(task)
    for values in combinations:
        replacements = {
            item["predicate_id"]: value for item, value in zip(observations, values)
        }
        if all(full[predicate_id] == value for predicate_id, value in replacements.items()):
            continue
        assignment = dict(full)
        assignment.update(replacements)
        output = _evaluate_complete(task, assignment)
        if output is not None and output != task["gold"]:
            return replacements, output
    raise ValueError("target record has no consequential alternate snapshot")


def has_consequential_alternate(
    task: dict[str, Any], record: dict[str, Any], *, seed: int,
) -> bool:
    try:
        _counterfactual_values(task, record, seed=seed)
    except ValueError:
        return False
    return True


def _context(
    spec: dict[str, Any], value: str, *, geography_level: str | None = None,
) -> dict[str, Any]:
    return {
        "error_type": spec["error_type"],
        "dimension_label": spec["dimension_label"],
        "value": value,
        "geography_level": geography_level,
    }


def _refresh_required_key_rounds(task: dict[str, Any]) -> None:
    keys = task["routing"]["record_keys"]
    task["routing"]["required_key_ideal_rounds"] = {
        keys[r]: 1 for r in task["routing"]["required_record_ids"]
    }


def prepare_reliable_pair(
    task: dict[str, Any], spec: dict[str, Any], *, seed: int, routing_mode: str | None = None,
) -> dict[str, Any]:
    if routing_mode is None:
        routing_mode = "cross_business" if seed % 2 == 0 else "same_business"
    if routing_mode not in {"same_business", "cross_business"}:
        raise ValueError("unsupported Error routing_mode")
    cross_business = routing_mode == "cross_business"
    if spec.get("error_type") not in ERROR_TYPES:
        raise ValueError("unsupported error_type for Error pair")
    target_value = spec.get("target_context")
    alternate_value = spec.get("alternate_context")
    query_requirement = spec.get("query_requirement")
    if (
        not all(isinstance(item, str) and item.strip() for item in (
            target_value, alternate_value, query_requirement,
        ))
        or target_value not in query_requirement
        or alternate_value in query_requirement
    ):
        raise ValueError("Error pair query_requirement must name only the target context")
    if spec.get("error_type") == "geographic":
        target_level = spec.get("target_geography_level")
        alternate_level = spec.get("alternate_geography_level")
        if (
            target_level not in {"country", "province", "city"}
            or alternate_level not in {"country", "province", "city"}
            or target_level != alternate_level
        ):
            raise ValueError("geographic Error pair requires matching target and alternate levels")
        if (
            spec.get("target_context") not in GEOGRAPHY_VALID_VALUES[target_level]
            or spec.get("alternate_context") not in GEOGRAPHY_VALID_VALUES[alternate_level]
        ):
            raise ValueError("geographic Error contexts must match their declared catalog level")
    else:
        target_level = alternate_level = None
    reliable = copy.deepcopy(task)
    reliable["schema_version"] = TASK_SCHEMA_VERSION
    record_by_id = {item["record_id"]: item for item in reliable["records"]}
    target = record_by_id.get(spec["target_record_id"])
    if target is None or target["record_id"] not in reliable["routing"]["required_record_ids"]:
        raise ValueError("Error target must be a required record")
    role_by_id = {item["role_id"]: item for item in reliable["roles"]}
    if role_by_id[target["owner_role_id"]]["kind"] in {"candidate_holder", "router", "distractor"}:
        raise ValueError("Error target must be a formal downstream Role record")
    plan = reliable.get('intervention_plan')
    if plan and target['record_id'] != plan['error_record_id']:
        raise ValueError('Error spec must use the jointly selected record')
    replacements, counterfactual = _counterfactual_values(reliable, target, seed=seed)
    topic_ids = {item['topic_id'] for item in reliable['observations']
                 if item['observation_id'] in target['observation_ids']}
    validate_context_templates(spec.get('context_templates', {}),
                               [topic for topic in reliable['topics'] if topic['topic_id'] in topic_ids],
                               spec['target_context'], spec['alternate_context'])

    for record in reliable["records"]:
        if record["owner_role_id"] != target["owner_role_id"]:
            continue
        if record.get("record_type") == "supplemental":
            continue
        if role_by_id[record["owner_role_id"]]["kind"] in {"candidate_holder", "router"}:
            continue
        record["record_family_id"] = (
            f"{record['owner_role_id']}:{record['business_abbreviation']}:{record['candidate_id']}"
        )
        record["context"] = _context(
            spec, spec["target_context"], geography_level=target_level,
        )
        business_title = role_by_id[target["owner_role_id"]]["business_title"]
        record["business_title"] = f"{spec['target_context']}·{business_title}" if cross_business else business_title

    observation_by_id = {item["observation_id"]: item for item in reliable["observations"]}
    alternate_id = f"{target['record_id']}_alternate"
    if alternate_id in record_by_id:
        raise ValueError("duplicate alternate record_id")
    affected_role = role_by_id[target["owner_role_id"]]
    secondary_code = affected_role["secondary_business"]["business_abbreviation"] if cross_business else target["business_abbreviation"]
    secondary_title = f"{spec['alternate_context']}·{affected_role['business_title']}" if cross_business else target["business_title"]
    removed = [r for r in reliable["records"] if cross_business and r["owner_role_id"] == target["owner_role_id"] and r.get("record_type") == "supplemental"]
    removed_ids = {r["record_id"] for r in removed}
    removed_observations = {o for r in removed for o in r["observation_ids"]}
    reliable["records"] = [r for r in reliable["records"] if r["record_id"] not in removed_ids]
    reliable["observations"] = [o for o in reliable["observations"] if o["observation_id"] not in removed_observations]
    if cross_business:
        reliable["supplemental_topics"] = [t for t in reliable["supplemental_topics"] if t["topic_id"] != f"supplemental_{target['owner_role_id']}"]
    catalog = [r for r in reliable["routing"]["catalog_only_record_ids"] if r not in removed_ids]
    if cross_business:
        affected_role["secondary_business"] = {"business_abbreviation": secondary_code, "title": secondary_title}
    for primary in [r for r in reliable["records"] if r["owner_role_id"] == target["owner_role_id"] and r.get("record_type") != "supplemental" and (cross_business or r["record_id"] == target["record_id"])]:
        alternate_observation_ids = []
        for observation_id in primary["observation_ids"]:
            source = observation_by_id[observation_id]
            alternate = copy.deepcopy(source)
            alternate["observation_id"] = f"alt_{observation_id}"
            alternate["observation_type"] = "alternate_snapshot"
            alternate["source_predicate_id"] = source.get("predicate_id")
            alternate["predicate_id"] = None
            if primary["record_id"] == target["record_id"] and source.get("predicate_id") in replacements:
                alternate["claimed_value"] = replacements[source["predicate_id"]]
            reliable["observations"].append(alternate)
            alternate_observation_ids.append(alternate["observation_id"])
        sibling_id = f"{primary['record_id']}_alternate"
        reliable["records"].append({
            "record_id": sibling_id, "record_type": "alternate_snapshot",
            "owner_role_id": primary["owner_role_id"], "candidate_id": primary["candidate_id"],
            "business_abbreviation": secondary_code, "business_title": secondary_title,
            "observation_ids": alternate_observation_ids,
            "record_family_id": primary["record_family_id"],
            "context": _context(spec, spec["alternate_context"], geography_level=alternate_level),
        })
        catalog.append(sibling_id)
    reliable["routing"]["record_keys"] = assign_record_keys(
        task_id=reliable["task_id"], records=reliable["records"], roles=reliable["roles"],
    )
    reliable["routing"]["catalog_only_record_ids"] = catalog
    reliable["setting"] = "reliable"
    reliable["target_context"] = {
        "error_type": spec["error_type"],
        "dimension_label": spec["dimension_label"],
        "value": spec["target_context"],
        "geography_level": target_level,
        "query_requirement": spec["query_requirement"],
        "affected_role_id": target["owner_role_id"],
    }
    reliable["error_pair"] = {
        "context_templates": copy.deepcopy(spec.get('context_templates', {})),
        "error_type": spec["error_type"],
        "affected_role_id": target["owner_role_id"],
        "routing_mode": routing_mode,
        "affected_candidate_id": target["candidate_id"],
        "target_record_id": target["record_id"],
        "alternate_record_id": alternate_id,
        "target_context": spec["target_context"],
        "alternate_context": spec["alternate_context"],
        "counterfactual_output": counterfactual,
        "target_business_abbreviation": target["business_abbreviation"],
        "alternate_business_abbreviation": secondary_code,
    }
    reliable["error_pair"].update({
        "target_key": reliable["routing"]["record_keys"][target["record_id"]],
        "alternate_key": reliable["routing"]["record_keys"][alternate_id],
    })
    _refresh_required_key_rounds(reliable)
    from runtime_settings import apply_budget
    return validate_task_graph(apply_budget(reliable))


def derive_error_task(reliable: dict[str, Any]) -> dict[str, Any]:
    error = copy.deepcopy(reliable)
    pair = error["error_pair"]
    target_id = pair["target_record_id"]
    alternate_id = pair["alternate_record_id"]
    matching_routes = [
        item for item in error["routing"]["candidate_records"]
        if target_id in item["record_ids"]
    ]
    if len(matching_routes) != 1:
        raise ValueError("target record must appear in exactly one public candidate directory")
    route = matching_routes[0]
    route["record_ids"] = [
        alternate_id if item == target_id else item for item in route["record_ids"]
    ]
    error["routing"]["catalog_only_record_ids"] = [
        target_id if item == alternate_id else item
        for item in error["routing"]["catalog_only_record_ids"]
    ]
    error["routing"]["required_record_ids"] = [
        alternate_id if item == target_id else item
        for item in error["routing"]["required_record_ids"]
    ]
    error["setting"] = "misaligned"
    _refresh_required_key_rounds(error)
    from runtime_settings import apply_budget
    return validate_task_graph(apply_budget(error))
