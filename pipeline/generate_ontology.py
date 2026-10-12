from __future__ import annotations

from pathlib import Path
import copy
from typing import Any, Callable

from normalize_ontology import canonicalize_ontology
from task_types import validate_ontology
from numeric_rules import OPERATIONS
from scenario_catalog import reference_scenarios
from incomplete_setting import validate_incomplete_ontology


HERE = Path(__file__).resolve().parent


def generate_ontology(
    generate: Callable[[dict[str, Any]], dict[str, Any]], *, seed: int,
    repair: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    require_incomplete: bool = False,
    expected_language: str | None = None,
    recent_scenarios: list[dict[str, Any]] | None = None,
    requested_operation: str | None = None,
    scenario_references: list[dict[str, str]] | None = None,
    scenario_suggestion: dict[str, str] | None = None,
) -> dict[str, Any]:
    if requested_operation is not None and requested_operation not in OPERATIONS:
        raise ValueError("unsupported requested_operation")
    if scenario_references is None:
        scenario_references = reference_scenarios()
    if scenario_suggestion is None:
        scenario_suggestion = reference_scenarios()[0]
    request = {
        "recent_scenarios": recent_scenarios or [],
        "scenario_references": copy.deepcopy(scenario_references),
        "scenario_suggestion": copy.deepcopy(scenario_suggestion),
        "seed": seed, "candidate_count": 3, "role_count_range": [5, 7],
        "distractor_role_count_range": [1, 2], "condition_topic_count_range": [5, 7],
        "condition_role_count_min": 4,
        "language": "en",
        "requirements": [
            "Write all natural-language fields in English; retain JSON keys and IDs.",
            "Design an idiomatic English scenario directly, with coherent locale, jurisdiction, unambiguous dates, explicit currency and canonical case-sensitive units. Use distinctive full candidate names and natural metric aliases; preserve boolean polarity.",
            "Generate only business semantics, roles, finite-domain topics, evidence contexts, conditions and numeric meaning.",
            "Use 5–7 business roles, 5–7 atomic conditions across at least four distinct roles, and 1–2 independent distractor roles.",
            "Do not generate candidate truth values, Gold, role kind, keys, routing IDs, noisy data or records.",
            "Every role needs an independent secondary_business with a distinct abbreviation, meaningful title and numeric/boolean topic containing label, value_type, domain, unit and evidence_context.",
            "Each topic needs source, scope and measurement evidence contexts; numeric topics require units.",
            "Choose the business goal first; vary selection, service acceptance, execution, admission and existence decisions. Labels must directly answer the question.",
            "recent_scenarios is history to avoid, not examples to continue. Change concrete situations, goals and requested results, not merely names, numbers or synonyms.",
            "Few-shot examples illustrate fields, types and structural relationships only. Do not copy their domain, goal, candidates, roles, metrics or condition combinations.",
            f"You are actively encouraged to create scenarios beyond the eight references and to explore coherent cross-domain scenarios. Seek fresh business goals, decision objects and operational contexts, especially when familiar themes recur in recent_scenarios. The suggestion '{scenario_suggestion['name']}' and all eight references remain optional inspirations that you may use for a substantively different task. References are not a whitelist or mandatory quota. Preserve the structural and business contract.",
        ],
    }
    request["allowed_numeric_operations"] = list(OPERATIONS)
    if requested_operation is not None:
        request["requested_operation"] = requested_operation
        request["requirements"].append(f"numeric_rule.operation must be {requested_operation}; design its business meaning without changing the operation.")
    if require_incomplete:
        request["condition_topic_count_range"] = [5, 7]
        request["requirements"].append(
            "Provide incomplete_condition linking a boolean_topic_id and threshold_topic_id owned by the same role/capability. "
            "Both are formal AND conditions: the boolean is eq true for presence/enabling only, the other is an independent numeric threshold. "
            "Vary business domains; do not put numeric compliance into the boolean definition."
        )
    def validate(value):
        if expected_language == 'en':
            from language_contract import require_english
            require_english(value)
        ontology = validate_ontology(canonicalize_ontology(value))
        if requested_operation is not None and ontology["numeric_rule"]["operation"] != requested_operation:
            raise ValueError(f"numeric_rule.operation must be {requested_operation}")
        validate_incomplete_ontology(ontology, required=require_incomplete)
        if expected_language == 'en':
            ontology['language'] = 'en'
        return ontology

    raw = generate(request)
    try:
        return validate(raw)
    except ValueError as initial_error:
        if repair is None:
            raise
        repair_request = {
            "seed": seed,
            "requested_operation": requested_operation,
            "validation_error": str(initial_error),
            "invalid_ontology": raw,
            "instruction": "Preserve the task semantics and repair the structure to satisfy the Ontology contract. Write natural-language fields in English.",
            "recent_scenarios": copy.deepcopy(request["recent_scenarios"]),
            "generation_requirements": list(request["requirements"]),
        }
        repair_request["scenario_references"] = copy.deepcopy(request["scenario_references"])
        repair_request["scenario_suggestion"] = copy.deepcopy(request["scenario_suggestion"])
        repaired = repair(repair_request)
        try:
            return validate(repaired)
        except ValueError as repair_error:
            raise ValueError(
                f"ontology repair failed: initial={initial_error}; repair={repair_error}"
            ) from repair_error
