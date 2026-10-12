"""HiddenBench-derived scenario references for unrestricted business-task generation.

The grouping and query hints are our adaptations, not an official taxonomy.
Source IDs refer to https://huggingface.co/datasets/YuxuanLi1225/HiddenBench
Paper: https://arxiv.org/html/2505.11556v4
"""
from __future__ import annotations

SAMPLING_VERSION = "hiddenbench_scenarios_v5_english_free_cycle_suggestion"
SCENARIOS = (('evacuation', 'Evacuation and shelter', 'Coordinate evacuation and accommodation with distributed risk and resource information.', 'Choose evacuation destinations, shelters or safe accommodation plans.', (1, 2, 3, 19, 25, 41)), ('transport_rescue', 'Transport and emergency rescue', 'Coordinate capacity, access, receiving requirements and timing for transport or rescue.', 'Choose routes, destinations, rescue plans or supply delivery plans.', (9, 10, 28, 32, 38, 39, 40, 55)), ('event_organization', 'Events and venue selection', 'Combine participant needs, venue conditions and organizational resources.', 'Choose venues, event arrangements or feasible relocation plans.', (11, 14, 23, 44, 50, 58, 63)), ('research_fieldwork', 'Research and field operations', 'Combine research needs, facility capabilities and environmental information.', 'Choose field camps, research facilities, equipment locations or work plans.', (17, 18, 27, 31, 45, 49, 53, 54, 57)), ('asset_protection', 'Asset protection and disaster recovery', 'Coordinate preservation, transfer and recovery of physical or digital assets.', 'Choose storage sites, transfer plans, backup facilities or recovery arrangements.', (15, 16, 24, 26, 36, 56)), ('investigation', 'Investigation, localization and cause identification', 'Combine distributed records and observations to check explanations, targets or investigation plans.', 'Evaluate explanations, locate targets or select investigation arrangements.', (4, 8, 13, 47, 48, 60, 61, 64, 65)), ('personnel_selection', 'Recruitment and personnel selection', 'Combine distributed qualifications, experience and assessment records.', 'Choose job candidates or evaluate appointment requirements.', (5, 6)), ('business_selection', 'Business partnerships and transactions', 'Combine partnership terms, capabilities and transaction information across departments.', 'Choose suppliers, service providers, partners or transaction plans.', (7, 30, 59, 62)))

def reference_scenarios() -> list[dict[str, str]]:
    """Return all eight frameworks as optional inspiration, never a whitelist."""
    return [{'name': name, 'description': description, 'query_hints': hints}
            for _, name, description, hints, _ in SCENARIOS]


def select_scenario(task_number: int) -> dict:
    """Cycle an optional starting point, while keeping all references and free choice."""
    if type(task_number) is not int or task_number < 1:
        raise ValueError("task number must be a positive integer")
    references = reference_scenarios()
    slot = (task_number - 1) % len(references)
    return {'version': SAMPLING_VERSION, 'mode': 'free', 'scenario_id': None,
            'references': references, 'slot': slot + 1,
            'suggestion': dict(references[slot])}


def scenario_counts(states: list[dict]) -> dict:
    counts = {item[0]: {"attempts": 0, "accepted": 0} for item in SCENARIOS}
    counts.update(free={"attempts": 0, "accepted": 0},
                  legacy_unclassified={"attempts": 0, "accepted": 0})
    for state in states:
        selection = state.get("scenario_selection")
        key = (selection["scenario_id"] if selection["mode"] == "guided" else "free") if selection else "legacy_unclassified"
        bucket = counts.setdefault(key, {"attempts": 0, "accepted": 0})
        bucket["attempts"] += 1
        bucket["accepted"] += int(state.get("status") == "accepted")
    return counts
