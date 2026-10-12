from __future__ import annotations

import json
import re
import random
from typing import Any, Callable


GRADER_VERSION = "conclusion_label_v3_english_exact"


def build_full_information_prompt(
    task: dict[str, Any], rendered: dict[str, Any], *, ordering_seed: int,
) -> str:
    rng = random.Random(ordering_seed)
    roles = list(rendered["model_view"]["role_agents"])
    rng.shuffle(roles)
    role_blocks = []
    for role in roles:
        information = list(role["information"])
        rng.shuffle(information)
        lines = []
        for item in information:
            lines.append(item["text"])
            if item.get("handoff_text"):
                lines.append(item["handoff_text"])
        role_blocks.append(f"【{role['role_name']}】\n" + "\n".join(f"- {line}" for line in lines))
    topic_labels = {item["topic_id"]: item["label"] for item in task["topics"]}
    operator_labels = {"eq": "equals", "neq": "does not equal", "lte": "at most", "lt": "less than", "gte": "at least", "gt": "greater than"}
    constraints = "\n".join(
        f"- {topic_labels[item['topic_id']]} {operator_labels.get(item['operator'], item['operator'])} {item['threshold']}"
        for item in task["constraints"]
    )
    return (
        f"{rendered['main']['task_context']}\n\n"
        f"Task: {rendered['main']['query']}\n\n"
        f"Decision conditions:\n{constraints}\n\n"
        "All information held by every role is provided below, including business records that may not affect the formal decision.\n\n"
        + "\n\n".join(role_blocks)
        + f"\n\nconclusion must be exactly one of these two strings: {json.dumps(task['scenario']['positive_label'], ensure_ascii=False)} or {json.dumps(task['scenario']['negative_label'], ensure_ascii=False)}。"
        + "Do not append candidate names, explanations or other text to conclusion."
        + "\nOutput only JSON: {\"conclusion\": \"one of the two labels above\", \"numeric_result\": number or null}"
    )


def _normalize_conclusion(task: dict[str, Any], value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().casefold()
    positive = str(task["scenario"]["positive_label"])
    negative = str(task["scenario"]["negative_label"])
    def pattern(label):
        escaped = re.escape(label.casefold())
        return (r"(?<!\w)" + escaped + r"(?!\w)"
                if re.search(r"[A-Za-z]", label) and not re.search(r"[\u3400-\u9fff]", label) else escaped)
    if task.get('language') == 'en':
        # Match runtime answer labels exactly, including case and no extra prose.
        return value if value in (positive, negative) else None
    negative_present = bool(re.search(pattern(negative), text))
    without_negative = re.sub(pattern(negative), "", text)
    positive_present = bool(re.search(pattern(positive), without_negative))
    if negative_present == positive_present:
        return None
    return negative if negative_present else positive


def _correct(task: dict[str, Any], answer: dict[str, Any]) -> bool:
    gold = task["gold"]
    if _normalize_conclusion(task, answer.get("conclusion")) != gold["conclusion"]:
        return False
    if gold["numeric_result"] is None:
        return answer.get("numeric_result") is None
    value = answer.get("numeric_result")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    precision = int(task["numeric_rule"].get("precision", 0))
    return round(float(value), precision) == round(float(gold["numeric_result"]), precision)


def regrade_full_information_report(
    task: dict[str, Any], report: dict[str, Any], *, required_runs: int | None = None,
) -> dict[str, Any]:
    results = report.get("results", [])
    for result in results:
        response = result.get("response")
        result["correct"] = isinstance(response, dict) and _correct(task, response)
    correct_runs = sum(bool(item.get("correct")) for item in results)
    runs = int(report.get("runs", len(results)))
    required = runs if required_runs is None else int(required_runs)
    report.update({
        "grader_version": GRADER_VERSION,
        "required_correct": required,
        "correct_runs": correct_runs,
        "executed_runs": len(results),
        "accuracy": correct_runs / len(results) if results else 0.0,
        "accepted": (
            required > 0
            and runs == required
            and len(results) == required
            and correct_runs == required
        ),
    })
    return report


def qualify_full_information(
    task: dict[str, Any], rendered: dict[str, Any],
    answer: Callable[[str], dict[str, Any]], *, model: str, runs: int = 3,
) -> dict[str, Any]:
    results = []
    for index in range(runs):
        ordering_seed = int(task.get("seed", 0)) * 100 + index
        prompt = build_full_information_prompt(task, rendered, ordering_seed=ordering_seed)
        response = answer(prompt)
        correct = _correct(task, response)
        results.append({
            "run": index + 1, "ordering_seed": ordering_seed,
            "prompt": prompt, "response": response, "correct": correct,
        })
        if not correct:
            break
    report = {
        "model": model, "runs": runs, "required_correct": runs,
        "stopped_early": len(results) < runs,
        "task_schema_version": task.get("schema_version"),
        "results": results,
    }
    return regrade_full_information_report(task, report, required_runs=runs)
