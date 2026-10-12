"""Compact business goals for the generation prompt, without task rules."""
from __future__ import annotations

import re
import json
from pathlib import Path


def _english_summary(ontology: dict) -> str:
    """Extract a decision goal and requested quantity, not eligibility rules.

    Recognize output verbs with a definite object rather than every occurrence
    of 'report'. Sentence boundaries exclude decimal points. Unsupported long
    decision forms fall back to the supplied title, without inventing a goal.
    """
    problem = re.sub(r'\s+', ' ', ontology['problem']).strip()
    boundary = r'[:;]|\.(?=\s|$)'
    decision = re.split(boundary, problem, maxsplit=1)[0]
    decision = re.split(
        r'\s+(?:by\s+(?:evaluating|assessing|verifying|checking)|based on whether|'
        r'(?:that|who|which)\s+(?:satisfies|satisfy|meets|meet)|'
        r'qualifies under|satisfies|satisfy|meets|meet)\b',
        decision, maxsplit=1, flags=re.I)[0].rstrip(' ,')
    if re.match(r'^(?:Determine|Evaluate) whether exactly one\b', decision, re.I):
        decision += ' qualifies'
    if ontology.get('title') and (len(decision.split()) > 45 or re.fullmatch(
            r'(?:Determine|Evaluate) whether exactly one candidate qualifies', decision, re.I)):
        decision = ontology['title'].strip()

    # Treat output verbs as instructions only when they have an explicit object.
    output = re.search(
        r'\b(?:report|calculate|compute|determine)\s+(?:and\s+report\s+)?'
        r'((?:its|their|the|that|this)\s+.+)', problem, re.I)
    if output:
        quantity = re.split(boundary, output[1], maxsplit=1)[0]
        quantity = re.split(
            r',\s*(?:calculated|computed|defined|obtained|which|where)\b|'
            r'\s+(?:calculated|computed|piecewise)\b|'
            r'\s+as\s+(?=[^;:.]*\b(?:plus|minus|multiplied|divided)\b)|'
            r'\s+by\s+(?:taking|summing|adding|subtracting|multiplying|dividing|applying)\b',
            quantity, maxsplit=1, flags=re.I)[0].rstrip(' ,')
        if quantity and not decision.casefold().endswith(quantity.casefold()):
            decision += '; report ' + quantity
    return decision


def recent_task_summaries(output_root: Path, task_id: str) -> list[dict[str, str]]:
    """Use all completed tasks until tasks 1–5 exist, then nearest lower eight."""
    previous = {}
    for checkpoint in (output_root / "candidates").glob("attempt_*/checkpoint.json"):
        state = json.loads(checkpoint.read_text(encoding="utf-8"))
        if state.get("status") == "accepted":
            number = int(state["task_id"].removeprefix("task_"))
            previous[number] = checkpoint.parent / "ontology.json"
    numbers = sorted(previous)
    if set(range(1, 6)).issubset(previous):
        current = int(task_id.removeprefix("task_"))
        numbers = [number for number in numbers if number < current][-8:]
    return [scenario_summary(json.loads(previous[number].read_text(encoding="utf-8")))
            for number in numbers]


def scenario_summary(ontology: dict) -> dict[str, str]:
    problem = ontology["problem"].strip()
    if not re.search(r'[\u3400-\u9fff]', problem):
        return {"domain": ontology["domain"], "problem": _english_summary(ontology)}
    # Use the candidate type when the question embeds conditions in its subject.
    if problem.startswith("判断是否存在"):
        decision = f"判断是否存在合格的{ontology['candidate_type']}"
        transition = "若存在"
    else:
        decision = re.split(r"[：:；;，,。]", problem, maxsplit=1)[0]
        transition_match = re.search(r"若([^，,；;。]+)[，,]", problem)
        transition = f"若{transition_match.group(1)}" if transition_match else ""

    # Keep the requested business result, not its arithmetic instructions.
    reports = re.findall(r"报告([^。；;]+)", problem)
    if reports:
        result = reports[-1].strip("，,。 ")
        summary = "，".join(part for part in (decision, transition, f"报告{result}") if part)
    else:
        summary = decision
    return {"domain": ontology["domain"], "problem": summary}
