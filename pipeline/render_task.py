from __future__ import annotations

import copy
import re
from numeric_rules import describe_numeric_rule
from typing import Any, Callable
from context_binding import resolved_evidence_context, validate_record_context


def _role_groups(task: dict[str, Any], role: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = {item["candidate_id"]: item["name"] for item in task["candidates"]}
    topic_records = {
        item["topic_id"]: item
        for item in [*task.get("topics", []), *task.get("distractor_topics", []), *task.get("supplemental_topics", [])]
    }
    observation_by_id = {item["observation_id"]: item for item in task["observations"]}
    groups: list[dict[str, Any]] = []
    for record in task["records"]:
        if record["owner_role_id"] != role["role_id"]:
            continue
        facts = []
        for observation_id in record["observation_ids"]:
            observation = observation_by_id[observation_id]
            topic = topic_records[observation["topic_id"]]
            facts.append({
                "observation_type": observation["observation_type"],
                "topic_label": topic["label"],
                "aliases": list(topic.get("aliases", [])),
                "value": observation["claimed_value"],
                "unit": topic.get("unit", ""),
                "evidence_context": resolved_evidence_context(task, record, topic),
            })
        groups.append({
            "observation_type": "candidate_record",
            "candidate_name": candidates[record["candidate_id"]],
            "facts": facts,
            "business_title": record.get("business_title", role["responsibility"]),
            "context": copy.deepcopy(record.get("context")),
            "record_id": record["record_id"],
            "observation_ids": list(record["observation_ids"]),
        })
    return groups


def _render_payload(task: dict[str, Any], role: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "role",
        "scenario": task["scenario"],
        "role": {key: role[key] for key in ("role_id", "name", "responsibility")},
        "information_groups": [
            {key: value for key, value in group.items() if key not in {"record_id", "observation_ids"}}
            for group in _role_groups(task, role)
        ],
    }


DIRECTORY_MARKER = "\n\nCandidates and records to verify:\n"


def _record_text(task, record, natural_text):
    return f"{task['routing']['record_keys'][record['record_id']]}：{natural_text.strip()}"


def update_public_directory(task, main):
    names = {c["candidate_id"]: c["name"] for c in task["candidates"]}
    keys = task["routing"]["record_keys"]
    listing = "\n".join("- " + names[e["candidate_id"]] + "：" + "、".join(keys[r] for r in e["record_ids"])
                        for e in task["routing"]["candidate_records"])
    main["query"] = main["query"].split(DIRECTORY_MARKER, 1)[0] + DIRECTORY_MARKER + listing
    return main


def render_task(
    task: dict[str, Any], renderer: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    main_payload = {
        "kind": "main", "scenario": task["scenario"],
        "topics": task["topics"], "constraints": task["constraints"],
        "numeric_rule": task["numeric_rule"],
        "numeric_rule_description": describe_numeric_rule(task["numeric_rule"], task["topics"]),
    }
    if task.get("incomplete_condition"):
        labels = {topic["topic_id"]: topic["label"] for topic in task["topics"]}
        main_payload["compound_condition"] = {
            field: labels[topic_id] for field, topic_id in task["incomplete_condition"].items()
        }
    if task.get("target_context"):
        main_payload["target_context"] = copy.deepcopy(task["target_context"])
        affected_topics = {
            item["topic_id"] for item in task["predicates"]
            if item["owner_role_id"] == task["target_context"]["affected_role_id"]
        }
        main_payload["target_context"]["affected_topic_labels"] = [
            item["label"] for item in task["topics"] if item["topic_id"] in affected_topics
        ]
    main = renderer(main_payload)
    if set(main) != {"task_context", "query"}:
        raise ValueError("main rendering must contain task_context and query")
    if any(not isinstance(main[field], str) or not main[field].strip() for field in ("task_context", "query")):
        raise ValueError("main rendering must contain non-empty background and query")
    context = task.get("target_context", {})
    if context and context["value"] not in main["query"]:
        raise ValueError("main query must integrate the target context into the relevant condition or numeric operand")
    requirement = context.get("query_requirement", "").strip()
    if requirement and re.search(r"(?:^|[。！？.!?\n])\s*" + re.escape(requirement), main["query"]):
        raise ValueError("main query must integrate the target context instead of listing a standalone requirement")
    main["query"] += "\n\nNumeric calculation rule: " + main_payload["numeric_rule_description"]
    rendered_roles: list[dict[str, Any]] = []
    model_roles: list[dict[str, Any]] = []
    record_by_id = {item["record_id"]: item for item in task["records"]}
    for role in task["roles"]:
        groups = _role_groups(task, role)
        result = renderer(_render_payload(task, role))
        if set(result) != {"system_context", "information"} or not isinstance(result["information"], list):
            raise ValueError("role rendering has invalid fields")
        if not isinstance(result["system_context"], str) or not result["system_context"].strip():
            raise ValueError("role rendering system_context must be non-empty")
        if len(result["information"]) != len(groups):
            raise ValueError("role rendering must return one item per information group")
        natural_texts: list[str] = []
        for information in result["information"]:
            if not isinstance(information, dict):
                raise ValueError("role rendering information items must be objects")
            text = information.get("text")
            handoff_text = information.get("handoff_text", "")
            if not isinstance(text, str) or not text.strip() or not isinstance(handoff_text, str):
                raise ValueError("role rendering information text must be non-empty strings")
            natural_texts.append(text)
        rendered_records: list[dict[str, Any]] = []
        for group, natural_text in zip(groups, natural_texts):
            record = record_by_id[group["record_id"]]
            validate_record_context(task, record, natural_text)
            text = _record_text(task, record, natural_text)
            rendered_records.append({
                "record_id": record["record_id"],
                "key": task["routing"]["record_keys"][record["record_id"]],
                "candidate_id": record["candidate_id"],
                "natural_text": natural_text.strip(),
                "text": text,
                "observation_ids": list(group["observation_ids"]),
            })
        aggregate_text = "\n".join(item["text"] for item in rendered_records)
        information = [{"text": aggregate_text, "handoff_text": ""}]
        rendered_role = {
            "role_id": role["role_id"], "role_name": role["name"],
            "system_context": result["system_context"],
            "information": information, "records": rendered_records,
        }
        rendered_roles.append(rendered_role)
        model_roles.append({
            "role_name": role["name"], "responsibility": role["responsibility"],
            "system_context": result["system_context"], "information": information,
        })
    update_public_directory(task, main)
    return {
        "task_id": task["task_id"], "main": main, "roles": rendered_roles,
        "model_view": {"main": main, "role_agents": model_roles},
    }


def reroute_rendered_task(task, rendered):
    """Reuse private prose and replace only the public candidate directory."""
    result = copy.deepcopy(rendered)
    update_public_directory(task, result["main"])
    result["model_view"]["main"] = copy.deepcopy(result["main"])
    return result
