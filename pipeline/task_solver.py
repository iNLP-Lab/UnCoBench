from __future__ import annotations

import itertools
import math
from fractions import Fraction
from numeric_rules import OPERATIONS
from typing import Any


def _matches(value: Any, operator: str, threshold: Any) -> bool:
    if operator == "eq":
        return value == threshold
    if operator == "neq":
        return value != threshold
    if operator == "gt":
        return value > threshold
    if operator == "gte":
        return value >= threshold
    if operator == "lt":
        return value < threshold
    if operator == "lte":
        return value <= threshold
    raise ValueError(f"unsupported operator: {operator}")


def _numeric_result(task: dict[str, Any], candidate_id: str, assignment: dict[str, Any]) -> int | float:
    rule = task["numeric_rule"]
    topic_ids = rule.get("topic_ids") or [rule["topic_id"]]
    values = [assignment[f"{candidate_id}_{topic_id}"] for topic_id in topic_ids]
    operation = rule["operation"]
    if operation in OPERATIONS:
        # Preserve exact decimal values and round only the final result.
        values = [Fraction(str(value)) for value in values]
    if operation == "identity":
        result = values[0]
    elif operation == "sum":
        result = sum(values)
    elif operation == "average":
        result = sum(values) / len(values)
    elif operation == "min":
        result = min(values)
    elif operation == "max":
        result = max(values)
    elif operation == "difference":
        result = values[0] - values[1]
    elif operation == "product":
        result = math.prod(values)
    elif operation == "weighted_sum":
        result = sum(value * Fraction(str(weight)) for value, weight in zip(values, rule["weights"]))
    elif operation == "sum_minus":
        split = len(values) - rule["subtract_count"]
        result = sum(values[:split]) - sum(values[split:])
    elif operation == "piecewise":
        total = sum(values)
        if total < 0:
            raise ValueError("piecewise total must be nonnegative")
        lower = 0
        charges = []
        for tier in rule["tiers"]:
            upper = None if tier["upper_bound"] is None else Fraction(str(tier["upper_bound"]))
            quantity = max(0, (total if upper is None else min(total, upper)) - lower)
            charges.append(quantity * Fraction(str(tier["rate"])))
            if upper is None or total <= upper:
                break
            lower = upper
        result = sum(charges)
    elif operation == "ratio":
        if values[1] == 0:
            raise ValueError("numeric ratio denominator cannot be zero")
        result = values[0] / values[1]
    elif operation == "percentage_change":
        if values[1] == 0:
            raise ValueError("percentage change baseline cannot be zero")
        result = (values[0] - values[1]) / values[1] * 100
    else:
        raise ValueError(f"unsupported numeric operation: {operation}")
    if isinstance(result, bool) or not isinstance(result, (int, float, Fraction)) or not math.isfinite(float(result)):
        raise ValueError("numeric result must be finite")
    precision = int(rule.get("precision", 0))
    rounded = round(result, precision)
    return int(rounded) if precision == 0 else float(rounded)


def _evaluate_complete(task: dict[str, Any], assignment: dict[str, Any]) -> dict[str, Any] | None:
    qualified: list[str] = []
    for candidate in task["candidates"]:
        candidate_id = candidate["candidate_id"]
        if all(
            _matches(
                assignment[f"{candidate_id}_{condition['topic_id']}"],
                condition["operator"],
                condition["threshold"],
            )
            for condition in task["constraints"]
        ):
            qualified.append(candidate_id)
    if len(qualified) > 1:
        return None
    if not qualified:
        return {
            "conclusion": task["scenario"]["negative_label"],
            "numeric_result": None,
            "qualified_candidate_id": None,
        }
    candidate_id = qualified[0]
    return {
        "conclusion": task["scenario"]["positive_label"],
        "numeric_result": _numeric_result(task, candidate_id, assignment),
        "qualified_candidate_id": candidate_id,
    }


def _output_key(output: dict[str, Any]) -> tuple[Any, ...]:
    return output["conclusion"], output["numeric_result"], output["qualified_candidate_id"]


def solve(task: dict[str, Any], assignment: dict[str, Any]) -> dict[str, Any]:
    predicates = {item["predicate_id"]: item for item in task["predicates"]}
    unknown = [predicate_id for predicate_id in predicates if predicate_id not in assignment]
    outputs: dict[tuple[Any, ...], dict[str, Any]] = {}
    ambiguous = 0
    for values in itertools.product(*(predicates[predicate_id]["domain"] for predicate_id in unknown)):
        complete = dict(assignment)
        complete.update(dict(zip(unknown, values)))
        output = _evaluate_complete(task, complete)
        if output is None:
            ambiguous += 1
            continue
        outputs[_output_key(output)] = output
    feasible = list(outputs.values())
    feasible.sort(key=lambda item: repr(_output_key(item)))
    return {
        "feasible_outputs": feasible,
        "unique_output": feasible[0] if len(feasible) == 1 and ambiguous == 0 else None,
        "unresolved_predicates": unknown,
        "ambiguous_completion_count": ambiguous,
    }


def gold_assignment(task: dict[str, Any]) -> dict[str, Any]:
    return {item["predicate_id"]: item["gold_value"] for item in task["predicates"]}


def derive_gold(task: dict[str, Any]) -> dict[str, Any]:
    output = _evaluate_complete(task, gold_assignment(task))
    if output is None:
        raise ValueError("multiple qualified candidates")
    return output


def validate_p1(task: dict[str, Any]) -> dict[str, Any]:
    result = solve(task, gold_assignment(task))
    if result["unique_output"] is None:
        raise ValueError("P1 failed: full information does not produce one valid output")
    return {"valid": True, "predicate": "P1", "unique_output": result["unique_output"]}


def validate_p3(task: dict[str, Any]) -> dict[str, Any]:
    full = gold_assignment(task)
    reports: list[dict[str, Any]] = []
    for role in task["roles"]:
        if role["kind"] != "decision":
            continue
        owned = [item["predicate_id"] for item in task["predicates"] if item["owner_role_id"] == role["role_id"]]
        partial = {predicate_id: value for predicate_id, value in full.items() if predicate_id not in owned}
        result = solve(task, partial)
        possible_count = len(result["feasible_outputs"]) + int(result["ambiguous_completion_count"] > 0)
        if not owned or possible_count < 2:
            raise ValueError(f"P3 failed: decision role is removable: {role['role_id']}")
        reports.append({
            "role_id": role["role_id"],
            "removed_predicate_ids": owned,
            "feasible_outputs": result["feasible_outputs"],
            "has_ambiguous_completion": bool(result["ambiguous_completion_count"]),
        })
    if len(reports) < 2:
        raise ValueError("P3 failed: at least two decision roles are required")
    return {"valid": True, "predicate": "P3", "roles": reports}
