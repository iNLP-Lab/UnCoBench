from __future__ import annotations

import ast
import copy
import re
from typing import Any


OPERATOR_ALIASES = {
    "==": "eq", "=": "eq", "eq": "eq", "equals": "eq", "equal": "eq",
    "!=": "neq", "<>": "neq", "ne": "neq", "neq": "neq",
    ">": "gt", "gt": "gt",
    ">=": "gte", "gte": "gte", "ge": "gte",
    "<": "lt", "lt": "lt",
    "<=": "lte", "lte": "lte", "le": "lte",
}


def _first(source: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = source.get(name)
        if value is not None:
            return value
    return None


def _canonical_id(value: Any, *, prefix: str, index: int) -> str:
    text = re.sub(r"[^a-z0-9_]+", "_", str(value or "").strip().lower()).strip("_")
    if not text or not text[0].isalpha():
        text = f"{prefix}_{text}" if text else f"{prefix}_{index}"
    return text


def _candidate_name(candidate: Any) -> Any:
    if not isinstance(candidate, dict):
        return candidate
    return _first(candidate, "name", "label", "candidate_name", "title")


def _finite_domain(value: Any, *, threshold: Any = None) -> Any:
    if not isinstance(value, str):
        return value
    try:
        parsed = ast.literal_eval(value.strip())
    except (ValueError, SyntaxError):
        return value
    if not isinstance(parsed, (list, tuple)):
        return value
    domain = list(parsed)
    if (
        len(domain) == 2
        and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in domain)
        and isinstance(threshold, (int, float))
        and not isinstance(threshold, bool)
        and min(domain) < threshold < max(domain)
    ):
        domain.append(threshold)
        domain.sort()
    return domain


def canonicalize_ontology(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize only unambiguous representation differences in model output."""
    if not isinstance(raw, dict):
        return raw
    result = copy.deepcopy(raw)

    scenario = _first(raw, "scenario", "scene")
    if isinstance(scenario, dict):
        scenario_title = _first(scenario, "title", "label", "name")
        scenario_problem = _first(scenario, "problem", "description", "question")
    else:
        scenario_title = scenario_problem = scenario
    title = _first(raw, "title") or scenario_title
    problem = _first(raw, "problem", "question") or scenario_problem
    if title is not None:
        result["title"] = title
    if problem is not None:
        result["problem"] = problem

    candidates = _first(raw, "candidate_names", "candidate_labels", "candidates")
    if isinstance(candidates, list):
        result["candidate_names"] = [_candidate_name(item) for item in candidates]

    roles = raw.get("roles")
    if isinstance(roles, list):
        normalized_roles = []
        for index, source in enumerate(roles, start=1):
            role = copy.deepcopy(source)
            if isinstance(role, dict):
                role["role_id"] = _canonical_id(role.get("role_id"), prefix="role", index=index)
            normalized_roles.append(role)
        result["roles"] = normalized_roles

    topics = _first(raw, "topics", "formal_topics", "condition_topics")
    topic_id_map: dict[str, str] = {}
    if isinstance(topics, list):
        normalized_topics = []
        for index, source in enumerate(topics, start=1):
            topic = copy.deepcopy(source)
            if not isinstance(topic, dict):
                normalized_topics.append(topic)
                continue
            old_id = str(topic.get("topic_id", ""))
            new_id = _canonical_id(old_id, prefix="topic", index=index)
            topic_id_map[old_id] = new_id
            topic["topic_id"] = new_id
            if "operator" in topic:
                topic["operator"] = OPERATOR_ALIASES.get(str(topic["operator"]).strip().lower(), topic["operator"])
            topic["domain"] = _finite_domain(topic.get("domain"), threshold=topic.get("threshold"))
            normalized_topics.append(topic)
        result["topics"] = normalized_topics

    distractors = raw.get("distractor_topics")
    if isinstance(distractors, list):
        normalized_distractors = []
        for index, source in enumerate(distractors, start=1):
            topic = copy.deepcopy(source)
            if isinstance(topic, dict):
                topic["topic_id"] = _canonical_id(topic.get("topic_id"), prefix="dtopic", index=index)
            normalized_distractors.append(topic)
        result["distractor_topics"] = normalized_distractors

    numeric_rule = raw.get("numeric_rule")
    if isinstance(numeric_rule, list) and len(numeric_rule) == 1:
        numeric_rule = numeric_rule[0]
    if isinstance(numeric_rule, dict):
        normalized_rule = copy.deepcopy(numeric_rule)
        old_topic_id = str(normalized_rule.get("topic_id", ""))
        if old_topic_id in topic_id_map:
            normalized_rule["topic_id"] = topic_id_map[old_topic_id]
        if isinstance(normalized_rule.get("topic_ids"), list):
            normalized_rule["topic_ids"] = [topic_id_map.get(str(item), item) for item in normalized_rule["topic_ids"]]
        result["numeric_rule"] = normalized_rule
    pair = result.get("incomplete_condition")
    if isinstance(pair, dict):
        for field in ("boolean_topic_id", "threshold_topic_id"):
            if field in pair:
                pair[field] = topic_id_map.get(str(pair[field]), pair[field])
    return result
