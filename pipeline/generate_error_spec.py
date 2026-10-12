from __future__ import annotations

import hashlib
from typing import Any, Callable

from error_pair import has_consequential_alternate
from task_types import ERROR_TYPES, GEOGRAPHY_CATALOG, GEOGRAPHY_VALID_VALUES, GEOGRAPHY_LEVELS
from context_binding import validate_context_templates


def _eligible_records(task: dict[str, Any], *, seed: int) -> list[dict[str, Any]]:
    role_by_id = {item["role_id"]: item for item in task["roles"]}
    candidate_by_id = {item["candidate_id"]: item["name"] for item in task["candidates"]}
    observation_by_id = {item["observation_id"]: item for item in task["observations"]}
    topic_by_id = {item["topic_id"]: item for item in task["topics"]}
    eligible = []
    for record_id in task["routing"]["required_record_ids"]:
        record = next(item for item in task["records"] if item["record_id"] == record_id)
        role = role_by_id[record["owner_role_id"]]
        if role["kind"] in {"candidate_holder", "router", "distractor"}:
            continue
        if not has_consequential_alternate(task, record, seed=seed):
            continue
        facts = []
        for observation_id in record["observation_ids"]:
            observation = observation_by_id[observation_id]
            if observation.get("predicate_id") is None:
                continue
            topic = topic_by_id[observation["topic_id"]]
            facts.append({
                "topic_id": topic["topic_id"],
                "topic_label": topic["label"],
                "unit": topic.get("unit", ""),
                "evidence_context": topic.get("evidence_context", {}),
            })
        if facts:
            eligible.append({
                "record_id": record_id,
                "role_id": role["role_id"],
                "role_name": role["name"],
                "responsibility": role["responsibility"],
                "candidate_id": record["candidate_id"],
                "candidate_name": candidate_by_id[record["candidate_id"]],
                "business_abbreviation": record["business_abbreviation"],
                "alternate_business_abbreviation": role["secondary_business"]["business_abbreviation"],
                "facts": facts,
            })
    return eligible


def _validated_spec(
    value: dict[str, Any], *, requested_type: str, eligible_ids: set[str],
) -> dict[str, Any]:
    error_type = value.get("error_type")
    if error_type not in ERROR_TYPES:
        raise ValueError(f"unsupported error_type: {error_type}")
    if error_type != requested_type:
        raise ValueError("Error-spec must use the requested error_type")
    target_record_id = value.get("target_record_id")
    if target_record_id not in eligible_ids:
        raise ValueError("Error-spec target_record_id must be an eligible required record")
    for field in ("dimension_label", "target_context", "alternate_context", "query_requirement"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise ValueError(f"Error-spec {field} must be a non-empty string")
    if value["target_context"].strip() == value["alternate_context"].strip():
        raise ValueError("Error-spec contexts must be different")
    if value["target_context"].strip() not in value["query_requirement"]:
        raise ValueError("query_requirement must explicitly contain the target context")
    if value["alternate_context"].strip() in value["query_requirement"]:
        raise ValueError("query_requirement must not reveal the alternate context")
    geography_level = value.get("geography_level")
    if error_type == "geographic":
        target_level = value.get("target_geography_level")
        alternate_level = value.get("alternate_geography_level")
        if (
            target_level not in GEOGRAPHY_LEVELS
            or alternate_level not in GEOGRAPHY_LEVELS
            or target_level != alternate_level
        ):
            raise ValueError("target and alternate geography levels must be the same supported level")
        if geography_level not in {None, target_level}:
            raise ValueError("geography_level conflicts with the two geographic context levels")
        if (
            value["target_context"].strip() not in GEOGRAPHY_VALID_VALUES[target_level]
            or value["alternate_context"].strip() not in GEOGRAPHY_VALID_VALUES[alternate_level]
        ):
            raise ValueError("geographic contexts must come from the declared geography catalog level")
        geography_level = target_level
    elif any(
        value.get(field) is not None
        for field in ("geography_level", "target_geography_level", "alternate_geography_level")
    ):
        raise ValueError("geography levels are only valid for geographic errors")
    return {
        "applicable": True,
        "error_type": error_type,
        "target_record_id": target_record_id,
        "dimension_label": value["dimension_label"].strip(),
        "target_context": value["target_context"].strip(),
        "alternate_context": value["alternate_context"].strip(),
        "geography_level": geography_level,
        "target_geography_level": value.get("target_geography_level"),
        "alternate_geography_level": value.get("alternate_geography_level"),
        "query_requirement": value["query_requirement"].strip(),
        "context_templates": value.get("context_templates", {}),
    }


def generate_error_spec(
    generate: Callable[[dict[str, Any]], dict[str, Any]],
    task: dict[str, Any], *, seed: int,
) -> dict[str, Any]:
    eligible = _eligible_records(task, seed=seed)
    if not eligible:
        raise ValueError("task has no required evidence record eligible for Error injection")
    digest = hashlib.sha256(f"{task['task_id']}:{seed}:error-target".encode("utf-8")).digest()
    selected = eligible[int.from_bytes(digest[:8], "big") % len(eligible)]
    if task.get('intervention_plan'):
        selected = next((r for r in eligible if r['record_id'] == task['intervention_plan']['error_record_id']), None)
        if selected is None:
            raise ValueError('planned Error record is not eligible')
    selected_id = selected["record_id"]
    start = seed % len(ERROR_TYPES)
    ordered_types = ERROR_TYPES[start:] + ERROR_TYPES[:start]
    for requested_type in ordered_types:
        payload = {
            "seed": seed,
            "requested_error_type": requested_type,
            "allowed_error_types": list(ERROR_TYPES),
            "scenario": task["scenario"],
            "eligible_records": [selected],
            "language": "en",
            "requirements": [
                "Design one context mismatch only; do not generate numbers, Gold, keys or routing.",
                "Use English for all natural-language values.",
                "target_context and alternate_context must belong to one semantic dimension.",
                "Geographic contexts must have the same level: country, province or city.",
                "No revision-status or source-provenance mismatches.",
            ],
        }
        if requested_type == "geographic":
            payload["geography_catalog"] = {
                level: list(values) for level, values in GEOGRAPHY_CATALOG.items()
            }
        if requested_type == "measurement_basis":
            payload["requirements"].append(
                "Use intuitive bases: before/after deductions, including/excluding tax, signed-for/dispatched, or explicit timing start points. "
                "Preserve the metric; no normalized capacity, equivalent instances, weighted conversions or simple unit conversions. "
                "Return applicable=false if unsuitable."
            )
        response = generate(payload)
        if not isinstance(response, dict):
            raise ValueError("Error-spec model must return an object")
        error_type = response.get("error_type")
        if error_type not in ERROR_TYPES:
            raise ValueError(f"unsupported error_type: {error_type}")
        if response.get("applicable") is False:
            continue
        spec = _validated_spec(
            response, requested_type=requested_type, eligible_ids={selected_id},
        )
        validate_context_templates(spec['context_templates'], selected['facts'],
                                   spec['target_context'], spec['alternate_context'])
        return spec
    raise ValueError("no allowed Error type is applicable to this task")
