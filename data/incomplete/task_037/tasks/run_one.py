from __future__ import annotations
import json
import re
from typing import Any
COMMUNICATION_ROLE_NAMES = []
GOLD = {'conclusion': 'Select', 'numeric_result': 48.0}
POSITIVE_CONCLUSION = 'Select'
NEGATIVE_CONCLUSION = 'Do not select'
NUMERIC_PRECISION = 1
PUBLIC_ROLES = [{'role_name': 'Chief marine archaeologist (ARCH)', 'responsibility': 'Maintains archaeological survey compliance and artifact catalog records', 'role_abbreviation': 'ARCH'}, {'role_name': 'Subsea operations director (SUB)', 'responsibility': 'Maintains deep-water positioning telemetry, benthic disturbance data, and underwater robotics records', 'role_abbreviation': 'SUB'}, {'role_name': 'Artifact conservation director (CONS)', 'responsibility': 'Maintains artifact salinity stabilization, chemical bath chemistry, and primary desalinization records', 'role_abbreviation': 'CONS'}, {'role_name': 'Naval architecture safety surveyor (SAFE)', 'responsibility': 'Maintains topside rigging, heavy lifting gear verification, and hoist safety margin records', 'role_abbreviation': 'SAFE'}, {'role_name': 'Offshore staging and transit manager (LOG)', 'responsibility': 'Maintains dockside quayside clearance certifications and quarantine holding tank records', 'role_abbreviation': 'LOG'}, {'role_name': 'Marine hull and cargo underwriter (INSR)', 'responsibility': 'Maintains salvage syndicate risk indemnification and heritage asset commercial insurance records', 'role_abbreviation': 'INSR'}]
ROLE_KEY_PREFIXES = {'Chief marine archaeologist (ARCH)': 'ARCH-', 'Subsea operations director (SUB)': 'SUB-', 'Artifact conservation director (CONS)': 'CONS-', 'Naval architecture safety surveyor (SAFE)': 'SAFE-', 'Offshore staging and transit manager (LOG)': 'LOG-', 'Marine hull and cargo underwriter (INSR)': 'INSR-'}
ROLE_VALID_KEYS = {'Chief marine archaeologist (ARCH)': ['ARCH-DATING-FZE', 'ARCH-DATING-BZ7', 'ARCH-DATING-NO0', 'ARCH-HERIT-UIN', 'ARCH-HERIT-UN9', 'ARCH-HERIT-BI8', 'ARCH-HERIT-XWG'], 'Subsea operations director (SUB)': ['SUB-ROV-3DQ', 'SUB-ROV-Z3Q', 'SUB-ROV-YSZ', 'SUB-THRUST-FXA', 'SUB-THRUST-HAH', 'SUB-THRUST-6X6'], 'Artifact conservation director (CONS)': ['CONS-OXID-3P9', 'CONS-OXID-FCA', 'CONS-OXID-CDG', 'CONS-STABIL-333', 'CONS-STABIL-1HO', 'CONS-STABIL-PSG'], 'Naval architecture safety surveyor (SAFE)': ['SAFE-RIG-2CL', 'SAFE-RIG-7K4', 'SAFE-RIG-WHE', 'SAFE-CABLE-7AP', 'SAFE-CABLE-4IC', 'SAFE-CABLE-KHK'], 'Offshore staging and transit manager (LOG)': ['LOG-BERTH-3F8', 'LOG-BERTH-NEB', 'LOG-BERTH-HMG', 'LOG-DOCK-HFZ', 'LOG-DOCK-OZO', 'LOG-DOCK-ZQ7'], 'Marine hull and cargo underwriter (INSR)': ['INSR-RISK-M3K', 'INSR-RISK-BBR', 'INSR-RISK-L84', 'INSR-DEDUCT-2OP', 'INSR-DEDUCT-90F', 'INSR-DEDUCT-0B7']}
RECORD_REPLY_KEYS = {'ARCH-HERIT-XWG': ['ARCH-HERIT-XWG'], 'ARCH-HERIT-UIN': ['ARCH-HERIT-UIN'], 'ARCH-HERIT-UN9': ['ARCH-HERIT-UN9'], 'SUB-ROV-3DQ': ['SUB-ROV-3DQ'], 'SUB-ROV-YSZ': ['SUB-ROV-YSZ'], 'SUB-ROV-Z3Q': ['SUB-ROV-Z3Q'], 'CONS-STABIL-333': ['CONS-STABIL-333'], 'CONS-STABIL-1HO': ['CONS-STABIL-1HO'], 'CONS-STABIL-PSG': ['CONS-STABIL-PSG'], 'SAFE-RIG-WHE': ['SAFE-RIG-WHE'], 'SAFE-RIG-2CL': ['SAFE-RIG-2CL'], 'SAFE-RIG-7K4': ['SAFE-RIG-7K4'], 'LOG-DOCK-HFZ': ['LOG-DOCK-HFZ'], 'LOG-DOCK-OZO': ['LOG-DOCK-OZO'], 'LOG-DOCK-ZQ7': ['LOG-DOCK-ZQ7'], 'INSR-RISK-L84': ['INSR-RISK-L84'], 'INSR-RISK-BBR': ['INSR-RISK-BBR'], 'INSR-RISK-M3K': ['INSR-RISK-M3K'], 'ARCH-DATING-FZE': ['ARCH-DATING-FZE'], 'ARCH-DATING-NO0': ['ARCH-DATING-NO0'], 'ARCH-DATING-BZ7': ['ARCH-DATING-BZ7'], 'SUB-THRUST-HAH': ['SUB-THRUST-HAH'], 'SUB-THRUST-FXA': ['SUB-THRUST-FXA'], 'SUB-THRUST-6X6': ['SUB-THRUST-6X6'], 'CONS-OXID-FCA': ['CONS-OXID-FCA'], 'CONS-OXID-3P9': ['CONS-OXID-3P9'], 'CONS-OXID-CDG': ['CONS-OXID-CDG'], 'SAFE-CABLE-7AP': ['SAFE-CABLE-7AP'], 'SAFE-CABLE-4IC': ['SAFE-CABLE-4IC'], 'SAFE-CABLE-KHK': ['SAFE-CABLE-KHK'], 'LOG-BERTH-3F8': ['LOG-BERTH-3F8'], 'LOG-BERTH-NEB': ['LOG-BERTH-NEB'], 'LOG-BERTH-HMG': ['LOG-BERTH-HMG'], 'INSR-DEDUCT-90F': ['INSR-DEDUCT-90F'], 'INSR-DEDUCT-2OP': ['INSR-DEDUCT-2OP'], 'INSR-DEDUCT-0B7': ['INSR-DEDUCT-0B7'], 'ARCH-HERIT-BI8': ['ARCH-HERIT-BI8']}
REQUIRED_KEYS = ['ARCH-HERIT-UIN', 'ARCH-HERIT-XWG', 'CONS-STABIL-333', 'CONS-STABIL-PSG', 'LOG-DOCK-HFZ', 'SAFE-RIG-WHE', 'SUB-ROV-3DQ']
DISTRACTOR_KEYS = ['INSR-DEDUCT-0B7', 'INSR-DEDUCT-2OP', 'INSR-DEDUCT-90F', 'INSR-RISK-BBR', 'INSR-RISK-L84', 'INSR-RISK-M3K']
SETTING = 'incomplete'

def runtime_defaults() -> dict[str, Any]:
    return {
        "setting": SETTING,
        "communication_role_names": list(COMMUNICATION_ROLE_NAMES),
        "finalize_ideal_round": 3,
        "max_turns": 6,
    }

FINALIZE_IDEAL_ROUND = runtime_defaults()["finalize_ideal_round"]
DEFAULT_MAX_TURNS = runtime_defaults()["max_turns"]
ERROR_INJECTION = {'enabled': False, 'role_name': 'Chief marine archaeologist (ARCH)', 'target_key': 'ARCH-HERIT-XWG', 'alternate_key': 'ARCH-HERIT-BI8', 'target_context': 'operational production environment', 'alternate_context': 'simulation test environment'}
INCOMPLETE_INJECTION = {'record_id': 'rec_subsea_operations_A', 'role_id': 'subsea_operations', 'candidate_id': 'A', 'key': 'SUB-ROV-3DQ', 'boolean_predicate_id': 'A_acoustic_beacon_enabled', 'boolean_label': 'Acoustic positioning beacon system enablement', 'hidden_predicate_id': 'A_acoustic_positioning_accuracy', 'threshold_label': 'Acoustic positioning accuracy', 'threshold_aliases': ['Seabed localization error', 'Target tracking positioning error'], 'threshold_value': 8, 'threshold_unit': 'cm', 'partial_record_text': 'SUB-ROV-3DQ: Robotic benthic claw recovery plan.Robotic benthic claw recovery plan: Acoustic positioning beacon system enablement = true .Source: Telemetry pre-dive commissioning checklist; Scope: Ultra-short baseline acoustic transceiver array; Measurement: Operational readiness state of seabed acoustic positioning beacons.Robotic benthic claw recovery plan: Maximum benthic sediment disturbance radius = 18 m.Source: Hydrodynamic benthic dispersion model; Scope: Artifact lifting touchdown and excavation boundary; Measurement: Maximum lateral radius of suspended seabed sediment deposition.', 'alternative_outputs': [{'conclusion': 'Do not select', 'numeric_result': None, 'qualified_candidate_id': None}], 'disclosure_mode': 'upper_bound', 'disclosure_version': 'truthful_bounds_v3_domain_bounds', 'disclosure_bounds': {'lower': None, 'upper': 40}, 'coarse_statement': 'Acoustic positioning accuracy is at most 40 cm.', 'role_name': 'Subsea operations director (SUB)', 'candidate_name': 'Robotic benthic claw recovery plan', 'other_candidate_names': ['Pressurized subsea cradle retrieval plan', 'Atmospheric diving suit rigging plan'], 'context_value': None, 'other_context_values': [], 'language': 'en'}
INCOMPLETE_FOLLOWUP_RECORDS = [{'key': 'ARCH-HERIT-XWG', 'role': 'Chief marine archaeologist (ARCH)', 'candidate': 'Robotic benthic claw recovery plan', 'context': 'operational production environment', 'fields': [{'id': 'unesco_compliance', 'label': 'UNESCO underwater cultural heritage treaty compliance', 'aliases': ['Treaty compliance', 'UNESCO convention compliance']}]}, {'key': 'ARCH-HERIT-UIN', 'role': 'Chief marine archaeologist (ARCH)', 'candidate': 'Pressurized subsea cradle retrieval plan', 'context': 'operational production environment', 'fields': [{'id': 'unesco_compliance', 'label': 'UNESCO underwater cultural heritage treaty compliance', 'aliases': ['Treaty compliance', 'UNESCO convention compliance']}]}, {'key': 'ARCH-HERIT-UN9', 'role': 'Chief marine archaeologist (ARCH)', 'candidate': 'Atmospheric diving suit rigging plan', 'context': 'operational production environment', 'fields': [{'id': 'unesco_compliance', 'label': 'UNESCO underwater cultural heritage treaty compliance', 'aliases': ['Treaty compliance', 'UNESCO convention compliance']}]}, {'key': 'SUB-ROV-3DQ', 'role': 'Subsea operations director (SUB)', 'candidate': 'Robotic benthic claw recovery plan', 'context': '', 'fields': [{'id': 'acoustic_beacon_enabled', 'label': 'Acoustic positioning beacon system enablement', 'aliases': ['Transponder array active', 'USBL positioning status']}, {'id': 'acoustic_positioning_accuracy', 'label': 'Acoustic positioning accuracy', 'aliases': ['Seabed localization error', 'Target tracking positioning error']}, {'id': 'benthic_sediment_disturbance_radius', 'label': 'Maximum benthic sediment disturbance radius', 'aliases': ['Sediment plume radius', 'Seafloor disturbance zone']}]}, {'key': 'SUB-ROV-YSZ', 'role': 'Subsea operations director (SUB)', 'candidate': 'Pressurized subsea cradle retrieval plan', 'context': '', 'fields': [{'id': 'acoustic_beacon_enabled', 'label': 'Acoustic positioning beacon system enablement', 'aliases': ['Transponder array active', 'USBL positioning status']}, {'id': 'acoustic_positioning_accuracy', 'label': 'Acoustic positioning accuracy', 'aliases': ['Seabed localization error', 'Target tracking positioning error']}, {'id': 'benthic_sediment_disturbance_radius', 'label': 'Maximum benthic sediment disturbance radius', 'aliases': ['Sediment plume radius', 'Seafloor disturbance zone']}]}, {'key': 'SUB-ROV-Z3Q', 'role': 'Subsea operations director (SUB)', 'candidate': 'Atmospheric diving suit rigging plan', 'context': '', 'fields': [{'id': 'acoustic_beacon_enabled', 'label': 'Acoustic positioning beacon system enablement', 'aliases': ['Transponder array active', 'USBL positioning status']}, {'id': 'acoustic_positioning_accuracy', 'label': 'Acoustic positioning accuracy', 'aliases': ['Seabed localization error', 'Target tracking positioning error']}, {'id': 'benthic_sediment_disturbance_radius', 'label': 'Maximum benthic sediment disturbance radius', 'aliases': ['Sediment plume radius', 'Seafloor disturbance zone']}]}, {'key': 'CONS-STABIL-333', 'role': 'Artifact conservation director (CONS)', 'candidate': 'Robotic benthic claw recovery plan', 'context': '', 'fields': [{'id': 'salinity_variance', 'label': 'Preservation bath salinity variance', 'aliases': ['Salinity fluctuation limit', 'Bath salinity variance']}, {'id': 'primary_desalinization_dwell_time', 'label': 'Primary desalinization dwell time', 'aliases': ['Shipboard desalinization duration', 'Primary bath holding time']}]}, {'key': 'CONS-STABIL-1HO', 'role': 'Artifact conservation director (CONS)', 'candidate': 'Pressurized subsea cradle retrieval plan', 'context': '', 'fields': [{'id': 'salinity_variance', 'label': 'Preservation bath salinity variance', 'aliases': ['Salinity fluctuation limit', 'Bath salinity variance']}, {'id': 'primary_desalinization_dwell_time', 'label': 'Primary desalinization dwell time', 'aliases': ['Shipboard desalinization duration', 'Primary bath holding time']}]}, {'key': 'CONS-STABIL-PSG', 'role': 'Artifact conservation director (CONS)', 'candidate': 'Atmospheric diving suit rigging plan', 'context': '', 'fields': [{'id': 'salinity_variance', 'label': 'Preservation bath salinity variance', 'aliases': ['Salinity fluctuation limit', 'Bath salinity variance']}, {'id': 'primary_desalinization_dwell_time', 'label': 'Primary desalinization dwell time', 'aliases': ['Shipboard desalinization duration', 'Primary bath holding time']}]}, {'key': 'SAFE-RIG-WHE', 'role': 'Naval architecture safety surveyor (SAFE)', 'candidate': 'Robotic benthic claw recovery plan', 'context': '', 'fields': [{'id': 'hoist_winch_safety_margin', 'label': 'Hoist winch dynamic load safety margin', 'aliases': ['Lifting safety margin', 'Winch load reserve']}]}, {'key': 'SAFE-RIG-2CL', 'role': 'Naval architecture safety surveyor (SAFE)', 'candidate': 'Pressurized subsea cradle retrieval plan', 'context': '', 'fields': [{'id': 'hoist_winch_safety_margin', 'label': 'Hoist winch dynamic load safety margin', 'aliases': ['Lifting safety margin', 'Winch load reserve']}]}, {'key': 'SAFE-RIG-7K4', 'role': 'Naval architecture safety surveyor (SAFE)', 'candidate': 'Atmospheric diving suit rigging plan', 'context': '', 'fields': [{'id': 'hoist_winch_safety_margin', 'label': 'Hoist winch dynamic load safety margin', 'aliases': ['Lifting safety margin', 'Winch load reserve']}]}, {'key': 'LOG-DOCK-HFZ', 'role': 'Offshore staging and transit manager (LOG)', 'candidate': 'Robotic benthic claw recovery plan', 'context': '', 'fields': [{'id': 'quayside_transfer_certified', 'label': 'Climate-controlled quayside transfer certification', 'aliases': ['Quayside transfer clearance', 'Port cold-chain custody certificate']}, {'id': 'quarantine_tank_dwell_time', 'label': 'Quayside quarantine tank dwell time', 'aliases': ['Quayside buffer holding duration', 'Quarantine tank stabilization time']}]}, {'key': 'LOG-DOCK-OZO', 'role': 'Offshore staging and transit manager (LOG)', 'candidate': 'Pressurized subsea cradle retrieval plan', 'context': '', 'fields': [{'id': 'quayside_transfer_certified', 'label': 'Climate-controlled quayside transfer certification', 'aliases': ['Quayside transfer clearance', 'Port cold-chain custody certificate']}, {'id': 'quarantine_tank_dwell_time', 'label': 'Quayside quarantine tank dwell time', 'aliases': ['Quayside buffer holding duration', 'Quarantine tank stabilization time']}]}, {'key': 'LOG-DOCK-ZQ7', 'role': 'Offshore staging and transit manager (LOG)', 'candidate': 'Atmospheric diving suit rigging plan', 'context': '', 'fields': [{'id': 'quayside_transfer_certified', 'label': 'Climate-controlled quayside transfer certification', 'aliases': ['Quayside transfer clearance', 'Port cold-chain custody certificate']}, {'id': 'quarantine_tank_dwell_time', 'label': 'Quayside quarantine tank dwell time', 'aliases': ['Quayside buffer holding duration', 'Quarantine tank stabilization time']}]}, {'key': 'INSR-RISK-L84', 'role': 'Marine hull and cargo underwriter (INSR)', 'candidate': 'Robotic benthic claw recovery plan', 'context': '', 'fields': [{'id': 'syndicate_salvage_coverage', 'label': 'Expedition casualty indemnification limit', 'aliases': ['Salvage casualty insurance limit', 'Syndicate coverage limit']}]}, {'key': 'INSR-RISK-BBR', 'role': 'Marine hull and cargo underwriter (INSR)', 'candidate': 'Pressurized subsea cradle retrieval plan', 'context': '', 'fields': [{'id': 'syndicate_salvage_coverage', 'label': 'Expedition casualty indemnification limit', 'aliases': ['Salvage casualty insurance limit', 'Syndicate coverage limit']}]}, {'key': 'INSR-RISK-M3K', 'role': 'Marine hull and cargo underwriter (INSR)', 'candidate': 'Atmospheric diving suit rigging plan', 'context': '', 'fields': [{'id': 'syndicate_salvage_coverage', 'label': 'Expedition casualty indemnification limit', 'aliases': ['Salvage casualty insurance limit', 'Syndicate coverage limit']}]}, {'key': 'ARCH-DATING-FZE', 'role': 'Chief marine archaeologist (ARCH)', 'candidate': 'Robotic benthic claw recovery plan', 'context': '', 'fields': [{'id': 'supplemental_marine_archaeology', 'label': 'Sample carbon calibration confidence', 'aliases': []}]}, {'key': 'ARCH-DATING-NO0', 'role': 'Chief marine archaeologist (ARCH)', 'candidate': 'Pressurized subsea cradle retrieval plan', 'context': '', 'fields': [{'id': 'supplemental_marine_archaeology', 'label': 'Sample carbon calibration confidence', 'aliases': []}]}, {'key': 'ARCH-DATING-BZ7', 'role': 'Chief marine archaeologist (ARCH)', 'candidate': 'Atmospheric diving suit rigging plan', 'context': '', 'fields': [{'id': 'supplemental_marine_archaeology', 'label': 'Sample carbon calibration confidence', 'aliases': []}]}, {'key': 'SUB-THRUST-HAH', 'role': 'Subsea operations director (SUB)', 'candidate': 'Robotic benthic claw recovery plan', 'context': '', 'fields': [{'id': 'supplemental_subsea_operations', 'label': 'Auxiliary thruster output', 'aliases': []}]}, {'key': 'SUB-THRUST-FXA', 'role': 'Subsea operations director (SUB)', 'candidate': 'Pressurized subsea cradle retrieval plan', 'context': '', 'fields': [{'id': 'supplemental_subsea_operations', 'label': 'Auxiliary thruster output', 'aliases': []}]}, {'key': 'SUB-THRUST-6X6', 'role': 'Subsea operations director (SUB)', 'candidate': 'Atmospheric diving suit rigging plan', 'context': '', 'fields': [{'id': 'supplemental_subsea_operations', 'label': 'Auxiliary thruster output', 'aliases': []}]}, {'key': 'CONS-OXID-FCA', 'role': 'Artifact conservation director (CONS)', 'candidate': 'Robotic benthic claw recovery plan', 'context': '', 'fields': [{'id': 'supplemental_environmental_control', 'label': 'Deoxygenation tank concentration', 'aliases': []}]}, {'key': 'CONS-OXID-3P9', 'role': 'Artifact conservation director (CONS)', 'candidate': 'Pressurized subsea cradle retrieval plan', 'context': '', 'fields': [{'id': 'supplemental_environmental_control', 'label': 'Deoxygenation tank concentration', 'aliases': []}]}, {'key': 'CONS-OXID-CDG', 'role': 'Artifact conservation director (CONS)', 'candidate': 'Atmospheric diving suit rigging plan', 'context': '', 'fields': [{'id': 'supplemental_environmental_control', 'label': 'Deoxygenation tank concentration', 'aliases': []}]}, {'key': 'SAFE-CABLE-7AP', 'role': 'Naval architecture safety surveyor (SAFE)', 'candidate': 'Robotic benthic claw recovery plan', 'context': '', 'fields': [{'id': 'supplemental_maritime_safety', 'label': 'Umbilical armor bend fatigue limit', 'aliases': []}]}, {'key': 'SAFE-CABLE-4IC', 'role': 'Naval architecture safety surveyor (SAFE)', 'candidate': 'Pressurized subsea cradle retrieval plan', 'context': '', 'fields': [{'id': 'supplemental_maritime_safety', 'label': 'Umbilical armor bend fatigue limit', 'aliases': []}]}, {'key': 'SAFE-CABLE-KHK', 'role': 'Naval architecture safety surveyor (SAFE)', 'candidate': 'Atmospheric diving suit rigging plan', 'context': '', 'fields': [{'id': 'supplemental_maritime_safety', 'label': 'Umbilical armor bend fatigue limit', 'aliases': []}]}, {'key': 'LOG-BERTH-3F8', 'role': 'Offshore staging and transit manager (LOG)', 'candidate': 'Robotic benthic claw recovery plan', 'context': '', 'fields': [{'id': 'supplemental_staging_logistics', 'label': 'Low-tide draft clearance', 'aliases': []}]}, {'key': 'LOG-BERTH-NEB', 'role': 'Offshore staging and transit manager (LOG)', 'candidate': 'Pressurized subsea cradle retrieval plan', 'context': '', 'fields': [{'id': 'supplemental_staging_logistics', 'label': 'Low-tide draft clearance', 'aliases': []}]}, {'key': 'LOG-BERTH-HMG', 'role': 'Offshore staging and transit manager (LOG)', 'candidate': 'Atmospheric diving suit rigging plan', 'context': '', 'fields': [{'id': 'supplemental_staging_logistics', 'label': 'Low-tide draft clearance', 'aliases': []}]}, {'key': 'INSR-DEDUCT-90F', 'role': 'Marine hull and cargo underwriter (INSR)', 'candidate': 'Robotic benthic claw recovery plan', 'context': '', 'fields': [{'id': 'supplemental_insurance_underwriting', 'label': 'Equipment policy deductible', 'aliases': []}]}, {'key': 'INSR-DEDUCT-2OP', 'role': 'Marine hull and cargo underwriter (INSR)', 'candidate': 'Pressurized subsea cradle retrieval plan', 'context': '', 'fields': [{'id': 'supplemental_insurance_underwriting', 'label': 'Equipment policy deductible', 'aliases': []}]}, {'key': 'INSR-DEDUCT-0B7', 'role': 'Marine hull and cargo underwriter (INSR)', 'candidate': 'Atmospheric diving suit rigging plan', 'context': '', 'fields': [{'id': 'supplemental_insurance_underwriting', 'label': 'Equipment policy deductible', 'aliases': []}]}, {'key': 'ARCH-HERIT-BI8', 'role': 'Chief marine archaeologist (ARCH)', 'candidate': 'Robotic benthic claw recovery plan', 'context': 'simulation test environment', 'fields': [{'id': 'unesco_compliance', 'label': 'UNESCO underwater cultural heritage treaty compliance', 'aliases': ['Treaty compliance', 'UNESCO convention compliance']}]}]
KEY_PATTERN = re.compile(r"^[A-Z]+-[A-Z]+-[A-Z0-9]{3}$")
REPLY_KEY_PATTERN = re.compile(r"(?<![A-Z0-9])[A-Z]+-[A-Z]+-[A-Z0-9]{3}(?![A-Z0-9])", re.IGNORECASE)
ROLE_REPLY_MAX_ATTEMPTS = 3
TASK_QUERY = 'Determine whether exactly one candidate salvage plan satisfies all of the following conditions: UNESCO underwater cultural heritage treaty compliance is true in the operational production environment; the acoustic positioning beacon system is enabled and acoustic positioning accuracy is at most 15 cm; maximum benthic sediment disturbance radius is at most 20 m; preservation bath salinity variance is at most 0.5 PSU; hoist winch dynamic load safety margin is at least 25 %; and climate-controlled quayside transfer certification is true. If so, select the plan and calculate its mean stabilization immersion duration in h by finding the arithmetic mean of its primary desalinization dwell time and quayside quarantine tank dwell time. Otherwise, do not select any salvage plan and report null for the numeric result.\n\nNumeric calculation rule: Compute only for the unique eligible candidate: ([Primary desalinization dwell time] + [Quayside quarantine tank dwell time]) / 2 (arithmetic mean). Result unit: h. Round only the final result to 1 decimal places (ties to even). If no candidate qualifies, numeric_result is null.\n\nCandidates and records to verify:\n- Atmospheric diving suit rigging plan：ARCH-HERIT-UN9、SUB-ROV-Z3Q、CONS-STABIL-PSG、SAFE-RIG-7K4、LOG-DOCK-ZQ7、INSR-RISK-M3K\n- Pressurized subsea cradle retrieval plan：ARCH-HERIT-UIN、SUB-ROV-YSZ、CONS-STABIL-1HO、SAFE-RIG-2CL、LOG-DOCK-OZO、INSR-RISK-BBR\n- Robotic benthic claw recovery plan：ARCH-HERIT-XWG、SUB-ROV-3DQ、CONS-STABIL-333、SAFE-RIG-WHE、LOG-DOCK-HFZ、INSR-RISK-L84'
TASK_CONTEXT = 'Deep-sea cultural artifact recovery operations require rigorous multidisciplinary review to safeguard submerged heritage sites, ensure operational safety, and preserve fragile historical materials during salvage and transfer. Candidate salvage plans must be vetted against strict international heritage standards, acoustic positioning tolerances, environmental disturbance limits, shipboard preservation controls, heavy lift dynamics, and quayside containment safeguards.'

"""Parse one model message without treating trailing generation noise as an action."""
import json
import re
from typing import Any


def parse_json_message(content: Any, *, trace: dict[str, Any] | None = None) -> dict[str, Any]:
    if trace is not None:
        trace.clear()
        trace.update(policy="first_complete_object", raw_response=content, recovered=False)
    if not isinstance(content, str):
        raise ValueError("model response must be text")
    text = content.strip().lstrip("\ufeff").strip()
    # Parse the first complete object; never recover a nested fragment.
    try:
        value, end = json.JSONDecoder().raw_decode(text)
        start = 0
    except json.JSONDecodeError:
        if text.startswith(("{", "[", '"')):
            raise
        opening = re.search(r"[\{\[]", text)
        if opening is None:
            raise
        start = opening.start()
        value, consumed = json.JSONDecoder().raw_decode(text[start:])
        end = start + consumed
    if not isinstance(value, dict):
        raise ValueError("model response must be a JSON object")
    prefix, suffix = text[:start], text[end:]
    if trace is not None:
        trace.update(recovered=bool(prefix.strip() or suffix.strip()),
                     ignored_prefix=prefix, ignored_suffix=suffix)
    return value


def expand_question_keys(questions):
    expanded = []
    for question in questions:
        if not isinstance(question, dict):
            expanded.append(question)
            continue
        text = question.get("question")
        keys = list(dict.fromkeys(REPLY_KEY_PATTERN.findall(text))) if isinstance(text, str) else []
        for key in keys or [None]:
            expanded.append(dict(question, key=key))
    return expanded


def validate_question(question, *, role_name, semantic_enabled=False):
    if not isinstance(question, dict) or not isinstance(question.get("question"), str) or not question["question"].strip():
        raise ValueError("question must contain natural-language text")
    if role_name not in ROLE_KEY_PREFIXES:
        raise ValueError("unknown Role")
    key = question.get("key")
    authorized = semantic_enabled if key is None else (
        isinstance(key, str) and key in ROLE_VALID_KEYS[role_name] and key in question["question"])
    return {"authorized": bool(authorized)}

def recovery_key_match(answer: str) -> str | None:
    target = ERROR_INJECTION.get("target_key")
    if not target:
        return None
    def contains(key: str) -> bool:
        return bool(re.search(r"(?<![A-Z0-9-])" + re.escape(key) + r"(?![A-Z0-9-])", answer, re.IGNORECASE))
    if contains(target):
        return "full_key"
    parts = target.split("-")
    alias = parts[0] + "-" + parts[-1]
    matches = [key for key in ROLE_VALID_KEYS.get(ERROR_INJECTION.get("role_name"), [])
               if key.split("-")[0] + "-" + key.split("-")[-1] == alias]
    if matches == [target] and contains(alias):
        return "abbreviated_key"
    return None

def communication_metrics(transcript: list[dict[str, Any]]) -> dict[str, Any]:
    key_query_rounds: dict[str, int] = {}
    key_query_counts: dict[str, int] = {}
    queried_roles: set[str] = set()
    mismatch_round: int | None = None
    recovery_query_sent = False
    recovery_query_turn: int | None = None
    target_key_returned = False
    recovery_turn: int | None = None
    recovery_method: str | None = None
    recovery_reference: str | None = None
    target_key_query_turn: int | None = None
    finalized_before_recovery = False
    for event in transcript:
        turn = int(event.get("turn", len(transcript)))
        action = event.get("main_agent_action", {})
        if (
            ERROR_INJECTION.get("enabled")
            and action.get("action") == "finalize"
            and not target_key_returned
        ):
            finalized_before_recovery = True
        if action.get("action") != "ask_role_agents": continue
        for answer in event.get("role_answers", []):
            role_name = answer.get("role_agent")
            if role_name: queried_roles.add(role_name)
            if (
                ERROR_INJECTION.get("enabled") and mismatch_round is not None and turn > mismatch_round
                and role_name == ERROR_INJECTION.get("role_name")
                and answer.get("question", {}).get("key") == ERROR_INJECTION.get("target_key")
                and "role_trace" in answer
                and recovery_key_match(str(answer.get("answer", ""))) is not None
            ):
                target_key_query_turn = target_key_query_turn or turn
            if (
                ERROR_INJECTION.get("enabled")
                and role_name == ERROR_INJECTION.get("role_name")
                and answer.get("question", {}).get("key") == ERROR_INJECTION.get("alternate_key")
                and "role_trace" in answer
            ):
                mismatch_round = mismatch_round or turn
        for message in action.get("messages", []):
            for question in message.get("questions", []):
                key = question.get("key")
                if (
                    ERROR_INJECTION.get("enabled")
                    and resolve_role_name(message.get("role_agent")) == ERROR_INJECTION.get("role_name")
                    and (key is None or key == ERROR_INJECTION.get("target_key"))
                    and mismatch_round is not None
                    and turn > mismatch_round
                ):
                    recovery_query_sent = True
                    recovery_query_turn = recovery_query_turn or turn
                if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key): continue
                key_query_rounds.setdefault(key, turn)
                key_query_counts[key] = key_query_counts.get(key, 0) + 1
        if recovery_query_sent and not target_key_returned and mismatch_round is not None and turn > mismatch_round:
            for answer in event.get("role_answers", []):
                question = answer.get("question", {})
                if (
                    answer.get("role_agent") == ERROR_INJECTION.get("role_name")
                    and (question.get("key") is None or question.get("key") == ERROR_INJECTION.get("target_key"))
                    and "role_trace" in answer
                    and recovery_key_match(str(answer.get("answer", ""))) is not None
                ):
                    target_key_returned = True
                    recovery_reference = recovery_key_match(str(answer.get("answer", "")))
                    recovery_turn = turn
                    recovery_method = "keyless_query" if question.get("key") is None else "target_key_query"
                    break
    queried = set(key_query_counts)
    required = set(REQUIRED_KEYS)
    relevant = queried & required
    return {
        "required_key_recall":len(relevant)/len(required) if required else 1.0,
        "required_key_precision":len(relevant)/len(queried) if queried else 0.0,
        "key_query_rounds":key_query_rounds,
        "key_query_counts":key_query_counts,
        "duplicate_key_queries":sum(max(0, count-1) for count in key_query_counts.values()),
        "distractor_key_queries":sum(key_query_counts.get(key, 0) for key in DISTRACTOR_KEYS),
        "distractor_key_query_rate":sum(key_query_counts.get(key, 0) for key in DISTRACTOR_KEYS)/sum(key_query_counts.values()) if key_query_counts else 0.0,
        "turns_to_finalize":len(transcript),
        "mismatch_key_queried":mismatch_round is not None,
        "mismatch_key_turn":mismatch_round,
        "recovery_query_sent":recovery_query_sent,
        "recovery_query_turn":recovery_query_turn,
        "target_key_returned":target_key_returned,
        "recovery_turn":recovery_turn,
        "recovery_method":recovery_method,
        "target_key_query_turn":target_key_query_turn,
        "recovery_key_match":recovery_reference,
        "recovery_metrics_version":"keyed_and_keyless_v3",
        "recovery_latency":recovery_turn - mismatch_round if recovery_turn is not None and mismatch_round is not None else None,
        "finalized_before_recovery":finalized_before_recovery,
    }

def main_system_prompt() -> str:
    role_text = "\n".join(f"- {item['role_name']}: {item['responsibility']}" for item in PUBLIC_ROLES)
    ask_example = json.dumps({"action":"ask_role_agents","messages":[{"role_agent":"Role name","questions":[{"id":"Q1","question":"Please provide the record for ABC-DATA-A1B using the supplied key."}]}]}, ensure_ascii=False)
    final_example = json.dumps({"action":"finalize","conclusion":"Exactly: " + POSITIVE_CONCLUSION + " or " + NEGATIVE_CONCLUSION,"numeric_result":None}, ensure_ascii=False).replace('"numeric_result": null', '"numeric_result": null/number')
    communication_protocol = ('You may output {"action":"wait"} to advance one logical turn. An empty observation {"observations":[]} means no new visible messages; it does not imply receipt, processing or any future reply.' if SETTING in {'missed', 'mixed'} else '')
    followup = ('For keyless follow-ups, name the candidate in full and the metric explicitly, or request that candidate\'s complete records. A unique previously queried record can be checked directly; otherwise supply a full key and metric when asked to clarify. Explicit directory requests return the complete directory.' if SETTING == 'incomplete' else
                'Authorized keyless follow-ups may name the candidate and metric or request complete records. A role may retrieve facts, request clarification or return a directory. If given a directory, select a valid key to obtain facts.' if SETTING == 'mixed' else
                'Authorized keyless questions return that role\'s complete directory. Choose a key from the directory to obtain concrete facts.')
    return "\n\n".join([
        'You are the Main Agent. Integrate information from independent role agents and make the final decision. Communicate in English.',
        'You cannot see private role information directly. Obtain it only by explicitly messaging the role agents.',
        'Key protocol:\n1. Candidate names and record keys are supplied in the task. Initial access requires a valid key; authorized later follow-ups are the exception.\n'
        '2. Keys use ROLE-BUSINESS-XXX: role abbreviation, business abbreviation and three random alphanumeric characters. Use complete supplied keys; do not invent them.\n'
        '3. Send each key to its owning business role. Use valid keys supplied by roles for subsequent checks.\n'
        '4. Do not output a separate key field. Put the complete key in question text; the system extracts it and checks ownership. Separate different keys into individual questions, preferably one record per question.\n'
        '5. After a successful keyed query to a role, keyless natural-language follow-ups to that role are authorized starting from the next turn.\n6. ' + followup,
        'Available independent role agents:\n\n' + role_text,
        'To ask questions, output only JSON in this form:\n\n' + ask_example,
        *([communication_protocol] if communication_protocol else []),
        'Final answer format (output only valid JSON):\n\n' + final_example,
        'Use exactly one of these conclusion labels: ' + POSITIVE_CONCLUSION + ' or ' + NEGATIVE_CONCLUSION + '. '
        'Do not append a candidate name, explanation or other text. null/number means choose one, not literal syntax. '
        'For a positive conclusion provide the computed number; for a negative conclusion use null. Do not include units or explanations in numeric_result.',
    ])


"""Conservative English evidence rules shared by standalone generated runtimes.

This is attribution of explicit statements, not arbitrary semantic entailment.
Unsupported or conflicting statements remain unknown; no model calls are made.
"""
import re
from decimal import Decimal

_RECOVERY_NUMBER = r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?'
_RECOVERY_UNCERTAIN = r"\b(?:unknown|uncertain|unclear|may(?!\s+\d{1,4}\b)|might|could|should|would|must|expected|possibly|whether|cannot|unable|unconfirmed|approximately|about|around|roughly|estimated|not confirmed|not known|not established)\b"
_RECOVERY_NEGATIVE = r'\b(?:not|no|never|false|invalid|blocked|failed|denied|unavailable|unapproved|revoked|inactive|disabled|noncompliant)\b'


def evidence_text(text):
    text = text.replace('’', "'").replace('−', '-').replace('‑', '-')
    text = re.sub(r"\bcan't\b", 'cannot', text, flags=re.I)
    text = re.sub(r"n't\b", ' not', text, flags=re.I)
    text = re.sub(r'(?<![\w.,])[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d,]|\.\d)',
                  lambda m: m[0].replace(',', ''), text)
    return text


def evidence_phrase(text, phrase):
    if not phrase:
        return False
    return bool(re.search(r'(?<!\w)' + re.escape(phrase).replace(r'\ ', r'\s+') + r'(?!\w)', text, re.I))


def evidence_nonasserted(text):
    """Questions, hypotheses and unconfirmed claims are not returned facts."""
    return bool('?' in text or re.search(_RECOVERY_UNCERTAIN, text, re.I)
                or re.search(r'\b(?:if|unless|assuming|suppose|supposing|hypothetically)\b', text, re.I)
                or re.search(r'\b(?:do|does|did|has|have|had)\s+not\s+(?:confirm|verify|establish)(?:ed)?\b', text, re.I))


def evidence_clauses(text):
    # Preserve questions and uncertainty when splitting assertions.
    sentences = re.split(r'[。\n]|\.(?!\d)|(?<=[!?])\s+', text)
    clauses = []
    for sentence in sentences:
        if evidence_nonasserted(sentence):
            clauses.append(sentence)
        else:
            # Split conjunctions between assertions, never inside metric labels.
            predicate = r'\b(?:is|are|was|were|has|have|had|holds?|received|maintains?|equals?)\b|[:=]'
            parts = re.split(r'([;；]|,?\s+\b(?:but|and)\b\s+(?![+-]?\d))', sentence, flags=re.I)
            current = parts[0]
            for separator, following in zip(parts[1::2], parts[2::2]):
                continuation = re.match(r'(?:it|its|this|that|(?:the\s+)?status)\b', following, re.I)
                split = not continuation and (not re.search(r'\band\b', separator, re.I) or
                        re.search(predicate, current, re.I) and re.search(predicate, following, re.I))
                if split:
                    clauses.append(current)
                    current = following
                else:
                    current += separator + following
            clauses.append(current)
    return clauses


def evidence_scope(answer, question, profile):
    for target in [profile.get('candidate', ''), profile.get('target_context', '')]:
        if target and re.search(r'\b(?:not|outside|excluding|except)(?:\s+(?:for|the))?\s+' + re.escape(target) + r'(?!\w)', answer, re.I):
            return 'not_returned'
    candidates = profile.get('other_candidates', [])
    contexts = profile.get('other_contexts', [profile.get('alternate_context', '')])
    if any(evidence_phrase(answer, c) for c in [*candidates, *contexts] if c):
        target_also_present = evidence_phrase(answer, profile.get('candidate', '')) and (
            not profile.get('target_context') or evidence_phrase(answer, profile['target_context']))
        return 'unknown' if target_also_present else 'not_returned'
    combined = question.get('question', '') + '\n' + answer
    target_key = profile.get('target_key', '')
    if target_key and (question.get('key') == target_key or evidence_phrase(combined, target_key)):
        return 'eligible'
    if evidence_phrase(combined, profile.get('candidate', '')) and (
            not profile.get('target_context') or evidence_phrase(combined, profile['target_context'])):
        return 'eligible'
    return 'unknown'


def evidence_unit_pattern(unit):
    # Unit names may inflect; canonical symbols remain case-sensitive.
    groups = [('h', 'hour', 'hours'), ('min', 'minute', 'minutes'), ('s', 'second', 'seconds'),
              ('kg', 'kilogram', 'kilograms'), ('m', 'meter', 'meters', 'metre', 'metres'),
              ('%', 'percent', 'per cent'), ('instances', 'instance'), ('items', 'item'),
              ('people', 'person', 'persons'), ('days', 'day')]
    for group in groups:
        if unit in group:
            canonical, *words = group
            if canonical in {'instances', 'items', 'people', 'days'}:
                words.append(canonical)
                canonical = None
            parts = ([re.escape(canonical)] if canonical else []) + ['(?i:' + re.escape(w) + ')' for w in words]
            if unit == '%': parts.append('％')
            return '(?:' + '|'.join(sorted(parts, key=len, reverse=True)) + ')'
    if re.fullmatch(r'[a-z]{3,}', unit) and unit not in {'mol', 'rad', 'kat', 'lux'}:
        singular = unit
        if unit.endswith('ies'):
            singular = unit[:-3] + 'y'
        elif re.search(r'(?:ch|sh|ss|x|z)es$', unit):
            singular = unit[:-2]
        elif unit.endswith('s') and not unit.endswith(('ss', 'us', 'is')):
            singular = unit[:-1]
        plural = (singular[:-1] + 'ies' if re.search(r'[^aeiou]y$', singular) else
                  singular + 'es' if re.search(r'(?:s|x|z|ch|sh)$', singular) else singular + 's')
        return '(?i:' + '|'.join(re.escape(w) for w in sorted({unit, singular, plural}, key=len, reverse=True)) + ')'
    return re.escape(unit)


def evidence_measurements(text, unit):
    text = evidence_text(text)
    text = re.sub(r'(?<=\d)[-–—](?=\d)', ' to ', text)
    suffix = (r'(?:\s+(?:1|(?i:dimensionless)))?' if unit == '1'
              else r'\s*' + evidence_unit_pattern(unit))
    pattern = r'(?<![A-Za-z0-9_.,+\-])(' + _RECOVERY_NUMBER + r')' + suffix + r'(?![A-Za-z0-9_/%]|\.\d|,\d)'
    return text, list(re.finditer(pattern, text))


def evidence_exact_measurement(text, match):
    before, after = text[max(0, match.start()-60):match.start()], text[match.end():match.end()+45]
    if evidence_nonasserted(text):
        return False
    if re.search(r'(?:\b(?:under|over|below|above|less than|more than|at most|at least|up to|between|to|and|not|no more than|no less than)|不超过|不低于|小于等于|大于等于|小于|大于|至少|至多|最多|最少|低于|高于|介于|至|到|[<>≤≥～~–—])\s*$', before, re.I):
        return False
    if re.search(r'\d\s*[-–—]\s*$', before):
        return False
    if re.match(r'\s*(?:\b(?:maximum|minimum|max|min)\b|\bor (?:less|more|lower|higher)\b|\b(?:to|through)\s+[+-]?\d|[-–—~～]\s*\d)', after, re.I):
        return False
    return True


def english_exact_value(answer, value, unit):
    for clause in evidence_clauses(evidence_text(answer)):
        text, matches = evidence_measurements(clause, unit)
        if any(Decimal(m[1]) == Decimal(str(value)) and evidence_exact_measurement(text, m) for m in matches):
            return True
    return False


def numeric_evidence(answer, question, profile, fact):
    answer = evidence_text(answer)
    scope = evidence_scope(answer, question, profile)
    if scope != 'eligible':
        return scope
    labels = [fact.get('label', ''), *fact.get('aliases', [])]
    states = set()
    for clause in evidence_clauses(answer):
        # Bind each value to its asserted metric; nearby numbers are not evidence.
        if not any(evidence_phrase(clause, label) for label in labels if label):
            continue
        if evidence_nonasserted(clause) or re.search(r'\b(?:catalog|directory)\b', clause, re.I):
            continue
        # Leave ambiguous multi-metric clauses unscored.
        others = profile.get('facts', profile.get('numeric', []) + profile.get('boolean', []))
        if any(other.get('topic') != fact.get('topic') and any(evidence_phrase(clause, label) for label in
               [other.get('label', ''), *other.get('aliases', [])] if label) for other in others):
            continue
        text, matches = evidence_measurements(clause, fact.get('unit', ''))
        for m in matches:
            if evidence_exact_measurement(text, m) and not re.search(_RECOVERY_NEGATIVE, text[:m.start()], re.I):
                states.add(Decimal(m[1]) == Decimal(str(fact['value'])))
    if len(states) != 1:
        return 'unknown'
    return 'returned' if states.pop() else 'not_returned'


def _evidence_predicate(text):
    text = re.sub(r'\b(?:is|are|was|were|has|have|had|been|the|a|an|already)\b', ' ', text.casefold())
    return re.sub(r'\s+', ' ', text).strip(' .:')


_BOOLEAN_PREDICATE = r'\b(?:enabled|issued|approved|valid|clear|ready|open|active|completed|available|installed|registered|signed|granted|confirmed|verified|operational|compliant|meets|passed|released|equipped|connected|running|accepted)\b'


def _boolean_labels(label):
    """Allow a participle before or after its noun phrase, preserving its words."""
    phrase = _evidence_predicate(label)
    variants = [phrase]
    words = phrase.split()
    if len(words) > 1 and re.fullmatch(_BOOLEAN_PREDICATE, words[-1]):
        variants.append(' '.join([words[-1], *words[:-1]]))
    return variants


def _boolean_clauses(answer):
    for clause in evidence_clauses(answer):
        if evidence_nonasserted(clause):
            yield clause
            continue
        # Keep status continuations attached so their negation is not discarded.
        yield from re.split(
            r',(?!\s*(?:but|and|is|are|was|were|has|have|had|which|that|it|its|status|not|no|false|true|yes|confirmed)\b)\s*',
            clause, flags=re.I)


def boolean_evidence(answer, question, profile):
    answer = evidence_text(answer)
    scope = evidence_scope(answer, question, profile)
    if scope != 'eligible':
        return scope
    labels = [variant for label in [profile['label'], *profile.get('aliases', [])]
              for variant in _boolean_labels(label)]
    primary = _boolean_labels(profile['label'])
    states = set()
    for clause in _boolean_clauses(answer):
        plain = _evidence_predicate(clause)
        no_negative = _evidence_predicate(re.sub(_RECOVERY_NEGATIVE, ' ', clause, flags=re.I))
        if not any(evidence_phrase(plain, _evidence_predicate(label)) or evidence_phrase(no_negative, _evidence_predicate(label)) for label in labels if label):
            continue
        if evidence_nonasserted(clause) or re.search(r'\b(?:catalog|directory)\b', clause, re.I):
            continue
        remainder = clause
        for label in sorted(labels, key=len, reverse=True):
            remainder = re.sub(re.escape(label), '', remainder, flags=re.I)
        negative = bool(re.search(_RECOVERY_NEGATIVE, remainder, re.I))
        explicit = bool(re.search(r'\b(?:true|yes|false|no)\b', remainder, re.I))
        label_match = any(evidence_phrase(no_negative, label) for label in primary)
        affirmative = label_match and bool(re.search(_BOOLEAN_PREDICATE, profile['label'], re.I))
        # Directory entries and requests are not assertions.
        for label in primary:
            escaped = re.escape(label).replace(r'\ ', r'\s+')
            affirmative |= bool(re.search(r'\b(?:holds?|received|obtained|secured)\s+(?:valid\s+)?' + escaped + r'(?!\w)', no_negative, re.I))
            affirmative |= bool(re.search(r'(?<!\w)' + escaped + r'\s+(?:' + _BOOLEAN_PREDICATE + r')(?!\w)', no_negative, re.I))
            affirmative |= bool(re.search(r'\b(?:valid|approved|confirmed|verified)\s+' + escaped + r'(?!\w)', no_negative, re.I))
        # Do not transfer negation between unrelated metrics.
        opposites = {'disabled':'enabled', 'unavailable':'available', 'invalid':'valid',
                     'closed':'open', 'inactive':'active', 'blocked':'clear', 'revoked':'granted'}
        opposite = False
        for denied, affirmed in opposites.items():
            if re.search(r'\b' + denied + r'\b', clause, re.I):
                rewritten = re.sub(r'\b' + denied + r'\b', affirmed, clause, flags=re.I)
                opposite |= any(evidence_phrase(_evidence_predicate(rewritten), label) for label in primary)
        bare_boolean = bool(explicit and re.fullmatch(r'(?:status\s*[:=]?\s*)?(?:true|yes|false|no)',
                                                       _evidence_predicate(remainder), re.I))
        if affirmative or label_match and (negative or explicit) or opposite or bare_boolean:
            states.add(not (negative or opposite))
    if len(states) != 1:
        return 'unknown'
    return 'returned' if states.pop() == profile['value'] else 'not_returned'


def recovery_number_present(answer, value):
    """Literal numeric occurrence, independent of unit, metric, scope or wording."""
    text = re.sub(r'(?<![A-Z0-9])[A-Z]{2,10}-[A-Z]{2,10}-[A-Z0-9]{3}(?![A-Z0-9])', '', answer, flags=re.I)
    text = evidence_text(text)
    text = re.sub(r'(?<=\d)[-–—](?=\d)', ' to ', text)
    pattern = r'(?<![A-Za-z0-9_.,+\-])(' + _RECOVERY_NUMBER + r')(?![0-9_]|\.\d|,\d)'
    return any(Decimal(m[1]) == Decimal(str(value)) for m in re.finditer(pattern, text))




import os
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from openai import OpenAI


def load_project_env() -> None:
    for parent in Path(__file__).resolve().parents:
        env_path = parent / ".env"
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        break


load_project_env()
MAIN_AGENT_API_KEY = os.getenv("MAIN_AGENT_API_KEY", os.getenv("OPENROUTER_API_KEY", ""))
MAIN_AGENT_MODEL_NAME = os.getenv("MAIN_AGENT_MODEL_NAME", "openai/gpt-5.5")
MAIN_AGENT_BASE_URL = os.getenv("MAIN_AGENT_BASE_URL", "https://openrouter.ai/api/v1")
ROLE_AGENT_API_KEY = os.getenv("ROLE_AGENT_API_KEY", os.getenv("OPENROUTER_API_KEY", ""))
ROLE_AGENT_MODEL_NAME = "deepseek/deepseek-v4-flash-0731"
ROLE_AGENT_BASE_URL = os.getenv("ROLE_AGENT_BASE_URL", "https://openrouter.ai/api/v1")
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "medium")
ROLE_REASONING_EFFORT = "low"
ROLE_MAX_TOKENS = 8192
LLM_REASONING_EXCLUDE = os.getenv("LLM_REASONING_EXCLUDE", "1") != "0"
MAIN_AGENT_ROLE_ORDER_SEED = os.getenv("MAIN_AGENT_ROLE_ORDER_SEED")
AGENT_DIR = str(Path(__file__).resolve().parent.parent / "role_agents")


def print_key_trace(title: str, content: Any = "") -> None:
    print(f"\n========== {title} ==========\n", flush=True)
    if content != "":
        print(str(content), flush=True)


def format_metric_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    if value is None:
        return "None"
    return str(value)


def format_llm_config() -> str:
    return "\n".join([
        f"main_agent_llm: {MAIN_AGENT_MODEL_NAME}",
        f"role_agent_llm: {ROLE_AGENT_MODEL_NAME}",
        f"reasoning_effort: {LLM_REASONING_EFFORT}",
        f"role_reasoning_effort: {ROLE_REASONING_EFFORT}",
    ])


def format_available_roles(role_agents: Dict[str, Any]) -> str:
    lines = []
    for role_name, role in role_agents.items():
        key_prefix = ROLE_KEY_PREFIXES.get(role_name, "")
        lines.append(f"- {role_name}（Key 格式：{key_prefix}业务缩写-XXX）：{role.config['abstract']}")
    return "\n".join(lines)


def format_evaluation_summary(evaluation: Dict[str, Any]) -> str:
    conclusion = evaluation.get("conclusion_evaluation", {})
    communication = evaluation.get("communication_evaluation", {})
    fields = [
        ("ground_truth_conclusion", conclusion.get("ground_truth_conclusion")),
        ("ground_truth_numeric_result", conclusion.get("ground_truth_numeric_result")),
        ("final_conclusion", conclusion.get("final_conclusion")),
        ("parsed_numeric_result", conclusion.get("parsed_numeric_result")),
        ("conclusion_correct", conclusion.get("conclusion_correct")),
        ("numeric_result_correct", conclusion.get("numeric_result_correct")),
        ("turns_to_finalize", communication.get("turns_to_finalize")),
        ("total_role_agent_queries", communication.get("total_role_agent_queries")),
        ("total_questions", communication.get("total_questions")),
        ("duplicate_key_queries", communication.get("duplicate_key_queries")),
    ]
    return "\n".join(f"{name}: {format_metric_value(value)}" for name, value in fields)


def format_key_metrics(evaluation: Dict[str, Any]) -> str:
    communication = evaluation.get("communication_evaluation", {})
    correctness = int(bool(evaluation.get("joint_correctness")))
    turns = communication.get("turns_to_finalize")
    lines = [
        f"正确率: {correctness}",
        f"完成轮数: {format_metric_value(turns)} / {communication.get('max_turns', DEFAULT_MAX_TURNS)}（理想：{communication.get('finalize_ideal_round', FINALIZE_IDEAL_ROUND)}）",
    ]
    if SETTING in {"incomplete", "mixed"}:
        lines.append(f"阈值补齐: {communication.get('incomplete_threshold_returned', False)}；补齐轮次: {communication.get('incomplete_recovery_turn')}；补救成功: {communication.get('incomplete_recovery_success')}")
    if SETTING in {"missed", "mixed"}:
        lines.append(f"忽略: {communication.get('neglect_ignored_count', 0)}；交付: {communication.get('neglect_delivered_count', 0)}；待答: {communication.get('neglect_pending_count', 0)}")
    if SETTING not in {"misaligned", "mixed"}:
        return "\n".join(lines)

    if communication.get("error_recovery_status") == "unknown":
        lines.append("Recovery result: UNKNOWN (evidence cannot be classified; excluded from recovery rates)")
        return "\n".join(lines)

    mismatch_queried = bool(communication.get("mismatch_key_queried"))
    mismatch_turn = communication.get("mismatch_key_turn")
    recovery_query_sent = bool(communication.get("recovery_query_sent"))
    recovery_query_turn = communication.get("recovery_query_turn")
    target_key_returned = bool(communication.get("error_fact_returned", communication.get("target_key_returned")))
    recovery_turn = communication.get("recovery_turn")
    finalized_early = bool(communication.get("finalized_before_recovery"))

    def turn_suffix(turn: Any) -> str:
        return f"（第{turn}轮）" if isinstance(turn, int) else ""

    lines.extend(["", "恢复链路："])
    if not mismatch_queried:
        lines.extend([
            f"✗ 未访问错配 key：{ERROR_INJECTION.get('alternate_key')}",
            "— 未触发补救询问",
            "— Role 未返回目标 key",
            "— 未进入恢复流程",
            "",
            "恢复延迟：N/A",
            "恢复结果：NOT_TRIGGERED（Main 未访问错配 key）",
        ])
        return "\n".join(lines)

    lines.append(
        f"✓ 已访问错配 key：{ERROR_INJECTION.get('alternate_key')}{turn_suffix(mismatch_turn)}"
    )
    lines.append(
        ("✓ 已发起补救询问" if recovery_query_sent else "✗ 未发起补救询问")
        + turn_suffix(recovery_query_turn)
    )
    lines.append(
        (
            f"✓ Role 已返回目标事实（对应 key）：{ERROR_INJECTION.get('target_key')}"
            if target_key_returned
            else f"✗ Role 未返回目标事实（对应 key）：{ERROR_INJECTION.get('target_key')}"
        )
        + turn_suffix(recovery_turn)
    )
    lines.append("✗ 已在恢复前提前 finalize" if finalized_early else "✓ 未在恢复前提前 finalize")
    if target_key_returned:
        lines.append("✓ 恢复后最终答案正确" if correctness else "✗ 恢复后最终答案错误")
    else:
        lines.append("— 尚未完成恢复，无法判断恢复后答案")

    recovery_latency = communication.get("recovery_latency")
    recovery_method = communication.get("recovery_method")
    if recovery_method:
        target_query_turn = communication.get("target_key_query_turn")
        if recovery_method == "keyless_query" and isinstance(target_query_turn, int) and isinstance(recovery_turn, int) and target_query_turn > recovery_turn:
            method_label = "无 key 获取目录 → 正确 key 查询"
            lines.append(f"取得目标 key：第{recovery_turn}轮")
            lines.append(f"正确 key 查询取得答复：第{target_query_turn}轮")
            recovery_latency = target_query_turn - mismatch_turn if isinstance(mismatch_turn, int) else recovery_latency
        else:
            method_label = {"keyless_query": "无 key 补充询问", "target_key_query": "目标 key 纠正查询"}.get(recovery_method, recovery_method)
        lines.append(f"补救方式：{method_label}")
    if communication.get("recovery_success"):
        status = "SUCCESS"
    elif finalized_early:
        status = "FINALIZED_EARLY"
    elif not recovery_query_sent:
        status = "RECOVERY_NOT_REQUESTED"
    elif not target_key_returned:
        status = "TARGET_NOT_RETURNED"
    else:
        status = "RECOVERED_BUT_WRONG"
    lines.extend([
        "",
        f"恢复延迟：{recovery_latency}轮" if isinstance(recovery_latency, int) else "恢复延迟：N/A",
        f"恢复结果：{status}",
    ])
    return "\n".join(lines)


def format_role_messages(action: Dict[str, Any], role_answers: List[Dict[str, Any]]) -> str:
    requested = {
        (message.get("role_agent"), question.get("id"), question.get("key")): question.get("question")
        for message in action.get("messages", [])
        for question in message.get("questions", [])
    }
    blocks = []
    for item in role_answers:
        question = item.get("question", {})
        identity = (item.get("role_agent"), question.get("id"), question.get("key"))
        blocks.append("\n".join([
            f"role_agent: {item.get('role_agent')}",
            f"question_id: {question.get('id')}",
            f"key: {question.get('key')}",
            f"question: {requested.get(identity, question.get('question'))}",
            f"answer: {item.get('answer')}",
        ]))
    return "\n\n".join(blocks)


def parse_numeric_result(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        match = re.search(r"[-+]?\d+(?:\.\d+)?", value.strip())
        if not match:
            return None
        number = float(match.group(0))
    else:
        return None
    rounded = round(number, NUMERIC_PRECISION)
    return int(rounded) if NUMERIC_PRECISION == 0 else rounded


def compute_conclusion_correctness(final_result: Dict[str, Any]) -> Dict[str, Any]:
    parsed = parse_numeric_result(final_result.get("numeric_result"))
    expected = parse_numeric_result(GOLD["numeric_result"])
    conclusion_correct = int(final_result.get("conclusion") == GOLD["conclusion"])
    numeric_correct = int(parsed == expected)
    return {
        "ground_truth_conclusion": GOLD["conclusion"],
        "ground_truth_numeric_result": GOLD["numeric_result"],
        "final_conclusion": final_result.get("conclusion"),
        "numeric_result_raw": final_result.get("numeric_result"),
        "parsed_numeric_result": parsed,
        "conclusion_correct": conclusion_correct,
        "numeric_result_correct": numeric_correct,
        "conclusion_correctness": int(conclusion_correct and numeric_correct),
    }


def format_role_user_message(question: Dict[str, Any]) -> str:
    question_id = str(question.get("id") or "Q")
    text = str(question["question"]).strip()
    return f"{question_id}: {text}"


"""Deterministic follow-up routing; metadata contains no hidden values or target flags."""
import re


def build_followup_records(task):
    roles = {r['role_id']: r['name'] for r in task['roles']}
    candidates = {c['candidate_id']: c['name'] for c in task['candidates']}
    topics = {t['topic_id']: t for group in ('topics', 'distractor_topics', 'supplemental_topics')
              for t in task.get(group, [])}
    observations = {o['observation_id']: o for o in task['observations']}
    records = []
    for record in task['records']:
        fields = []
        for oid in record['observation_ids']:
            tid = observations[oid]['topic_id']
            topic = topics.get(tid, {})
            if topic.get('label'):
                fields.append({'id': tid, 'label': topic['label'], 'aliases': topic.get('aliases', [])})
        records.append(dict(key=task['routing']['record_keys'][record['record_id']],
                            role=roles[record['owner_role_id']], candidate=candidates[record['candidate_id']],
                            context=(record.get('context') or {}).get('value', ''), fields=fields))
    return records


class IncompleteFollowupResolver:
    VERSION = 'rule_followup_v2_english'
    CLARIFY = 'The record and metric cannot be uniquely identified. Put the complete record key and the metric to verify in your question.'

    def __init__(self, records):
        self.records = records
        self.reset()

    def reset(self):
        self.seen = {}
        self.events = []

    def observe(self, role, key, turn):
        if key is not None:
            self.seen.setdefault((role, key), turn)

    @staticmethod
    def normalize(text):
        return re.sub(r'\s+', ' ', text).strip().casefold().replace('’', "'").replace('‑', '-').replace('–', '-')

    @classmethod
    def mentions(cls, text, phrase):
        phrase = cls.normalize(phrase)
        if re.search(r'[\u3400-\u9fff]', phrase):
            return phrase.replace(' ', '') in text.replace(' ', '')
        return bool(re.search(r'(?<![\w])' + re.escape(phrase) + r'(?![\w])', text))

    def resolve(self, role, text, turn):
        text = self.normalize(text)
        available = [r for r in self.records if r['role'] == role]
        if re.search(r'目录|索引列表|key列表|\b(?:catalog(?:ue)?s?|director(?:y|ies)|(?:key|index)\s+lists?)\b', text):
            result = dict(status='catalog', key=None, fields=[])
        else:
            # Match the full role catalog before restricting to previously queried records.
            names = {r['candidate'] for r in available if self.mentions(text, r['candidate'])}
            contexts = {r['context'] for r in available if r['context'] and self.mentions(text, r['context'])}
            fields = {f['id'] for r in available for f in r['fields']
                      if any(self.mentions(text, a) for a in [f['label'], *f['aliases']] if a)}
            full = bool(re.search(r'完整(?:资料|信息|内容|记录)|全部(?:资料|信息|内容)|详细资料|\b(?:complete|full|all|detailed)\s+(?:(?:the|your|available)\s+)*(?:records?|information|details|data)\b', text))
            matches = [r for r in available
                       if self.seen.get((role, r['key']), turn) < turn
                       and r['candidate'] in names
                       and (not contexts or r['context'] in contexts)
                       and (fields <= {f['id'] for f in r['fields']} if fields else full)]
            # Ambiguous references require a key; do not infer pronouns or fuzzy matches.
            unique = len(names) == 1 and len(contexts) <= 1 and len(matches) == 1 and (fields or full)
            result = dict(status='resolved' if unique else 'clarify',
                          key=matches[0]['key'] if unique else None, fields=sorted(fields), full=full)
        self.events.append(dict(turn=turn, role_agent=role, question=text, **result))
        return result

    def catalog(self, role):
        return 'Complete record directory (supply a key to obtain facts):\n' + '\n'.join(
            r['key'] + '：' + r['candidate'] + ('；' + r['context'] if r['context'] else '')
            + '; Metrics: ' + '、'.join(f['label'] for f in r['fields'])
            for r in self.records if r['role'] == role)

    def metrics(self):
        return dict(incomplete_followup_protocol=self.VERSION,
                    incomplete_keyless_followup_count=len(self.events),
                    incomplete_rule_resolved_count=sum(e['status'] == 'resolved' for e in self.events),
                    incomplete_clarification_count=sum(e['status'] == 'clarify' for e in self.events),
                    incomplete_followup_routing=list(self.events))


"""Self-contained Incomplete policy embedded only in generated Incomplete run_one.py files."""
import re


class IncompletePolicy:
    def __init__(self, profile):
        self.profile = profile
        self.reset()

    def reset(self):
        self.omitted_at_turn = None
        self.followup_at_turn = None
        self.recovered_at_turn = None

    def mode(self, role_name, question, turn):
        if role_name != self.profile['role_name'] or question.get('key') != self.profile['key']:
            return None
        if self.recovered_at_turn is not None:
            return None
        # Any valid later query of the same record can recover the omitted value.
        if self.omitted_at_turn is not None and turn > self.omitted_at_turn:
            if self.followup_at_turn is None:
                self.followup_at_turn = turn
            return 'incomplete_recovery'
        return 'incomplete_partial'

    def request_options(self, mode, full_system_message):
        profile = self.profile
        coarse = profile.get('disclosure_mode', 'omission') != 'omission'
        if mode == 'incomplete_partial':
            system = (
                f"You are {profile['role_name']}. For this request use only the business record below. "
                "Respond in English in one or two connected sentences, retaining the key, candidate, material scope and facts. "
                "Do not add metrics, infer facts or assert that the overall plan qualifies. "
                "Do not say information is incomplete, unavailable or requires follow-up, and do not recommend another question. "
            )
            if coarse:
                system += (
                    "Include the supplied coarse metric statement, retaining its numbers, units and bound wording. "
                    "Bounds are not exact values. Do not treat endpoints as actual values or infer narrower bounds, even when asked for an exact value. "
                )
            system += "\n\n" + profile['partial_record_text']
            if coarse:
                system += "\n" + profile['coarse_statement']
            system += '\n\nOutput only valid JSON: {"answer":"Answer text"}.'
        else:
            system = (full_system_message + "\n\nFor this request, give the complete specified record, explicitly stating "
                      + profile['threshold_label'] + " as its original numeric value and unit. Use Arabic numerals, not just a compliance judgment.")
            if coarse:
                system += (" Introduce the exact finding naturally with 'After careful verification'. "
                           "The exact number must come from the true private record, not a previous bound or interval endpoint. "
                           "Do not merely repeat the earlier coarse range.")
        return {'system_override': system, 'response_validator': None}

    def validate_answer(self, mode, answer):
        if mode == 'incomplete_partial':
            return None
        return (None if recovery_number_present(answer, self.profile['threshold_value'])
                else 'incomplete_threshold_not_returned')

    def observe(self, mode, turn, answer=None):
        if mode == 'incomplete_partial' and self.omitted_at_turn is None:
            self.omitted_at_turn = turn
        elif mode == 'incomplete_recovery' and answer is not None:
            if self.validate_answer(mode, answer) is None:
                self.recovered_at_turn = turn

    def observe_keyless(self, role_name, question, turn, answer=None):
        """Measure accepted search replies without changing their runtime protocol."""
        if (role_name != self.profile['role_name'] or question.get('key') is not None
                or self.omitted_at_turn is None or turn <= self.omitted_at_turn
                or self.recovered_at_turn is not None):
            return
        # Recovery uses numeric occurrence only, without wording, scope or unit checks.
        # Observe only accepted replies; identifiers are excluded by validate_answer.
        if answer is not None and self.validate_answer("incomplete_recovery", answer) is None:
            if self.followup_at_turn is None:
                self.followup_at_turn = turn
            self.recovered_at_turn = turn

    def metrics(self, *, correct, finalized):
        triggered = self.omitted_at_turn is not None
        recovered = self.recovered_at_turn is not None
        return {
            'incomplete_omission_triggered': triggered,
            'incomplete_omission_turn': self.omitted_at_turn,
            'incomplete_followup_sent': self.followup_at_turn is not None,
            'incomplete_followup_turn': self.followup_at_turn,
            'incomplete_threshold_returned': recovered,
            'incomplete_recovery_turn': self.recovered_at_turn,
            'incomplete_recovery_latency': self.recovered_at_turn - self.omitted_at_turn if recovered else None,
            'finalized_before_incomplete_recovery': bool(finalized and triggered and not recovered),
            'incomplete_recovery_success': bool(recovered) if triggered else None,
        }


def exact_value_present(answer, profile):
    """Compatibility name: count the target numeric value, including within bounds."""
    return recovery_number_present(answer, profile['threshold_value'])


def incomplete_numeric_metrics(profile, transcript, communication, *, correct, finalized):
    """Measure later accepted replies only; never alter interaction policy state.

    User-defined numeric-occurrence rule: no unit, polarity, metric or scope gate.
    Only later accepted replies from the affected role are eligible.
    """
    omitted = communication.get('incomplete_omission_turn')
    followup = communication.get('incomplete_followup_turn')
    recovered = None
    for event in transcript:
        turn = event['turn']
        if omitted is None or turn <= omitted:
            continue
        for reply in event.get('role_answers', []) + event.get('delivered_role_answers', []):
            if (reply.get('role_agent') != profile['role_name']
                    or 'role_trace' not in reply
                    or reply.get('protocol_error') or 'role_validation_trace' in reply):
                continue
            if exact_value_present(reply.get('answer', ''), profile):
                recovered = turn if recovered is None else min(recovered, turn)
    if recovered is not None:
        followup = recovered if followup is None else min(followup, recovered)
    status = 'returned' if recovered is not None else 'not_returned'
    return {
        'incomplete_recovery_status': status,
        'incomplete_omission_triggered': omitted is not None,
        'incomplete_omission_turn': omitted,
        'incomplete_followup_sent': followup is not None,
        'incomplete_followup_turn': followup,
        'incomplete_threshold_returned': recovered is not None,
        'incomplete_recovery_turn': recovered,
        'incomplete_recovery_latency': recovered - omitted if recovered is not None else None,
        'finalized_before_incomplete_recovery': bool(finalized and omitted is not None and recovered is None),
        'incomplete_recovery_success': bool(recovered is not None) if omitted is not None else None,
        'incomplete_statistics_version': 'numeric_occurrence_v4',
    }


class RoleAgent:
    def __init__(self, config: Dict[str, Any], client: OpenAI, model: str = ROLE_AGENT_MODEL_NAME):
        self.config = config
        self.client = client
        self.model = model
        self.system_message = self._build_system_message()
        self.reset_history()

    def reset_history(self) -> None:
        self.messages = [{"role": "system", "content": self.system_message}]

    def _build_system_message(self) -> str:
        private_blocks = []
        for index, point in enumerate(self.config["information_points"]):
            content = "\n\n".join(
                line for line in str(point["content"]).splitlines() if line.strip()
            )
            private_blocks.append(f"{index + 1}. {point['title']}：\n\n{content}")
        private = "\n\n".join(private_blocks)
        return (
            f"{self.config['system_message']}\n\n"
            f"Your private information:\n\n{private}\n\n"
            "Output only a valid JSON object: {\"answer\":\"Answer text\"}。"
        )

    def answer_with_trace(
        self, question: str, *, allowed_keys: set[str], response_mode: str,
        system_override: str | None = None, response_validator: Any = None,
    ) -> Dict[str, Any]:
        user_message = {"role": "user", "content": question}
        attempts = []
        for _ in range(ROLE_REPLY_MAX_ATTEMPTS):
            # Keep rejected replies in the audit trace, outside model conversation history.
            messages = [*self.messages, user_message]
            if system_override is not None:
                messages[0] = {"role": "system", "content": system_override}
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, temperature=0.1,
                max_tokens=ROLE_MAX_TOKENS,
                response_format={"type": "json_object"},
                extra_body={"reasoning": {"effort": ROLE_REASONING_EFFORT, "exclude": LLM_REASONING_EXCLUDE}},
            )
            finish_reason = getattr(response.choices[0], "finish_reason", None)
            response_message = {"role": "assistant", "content": response.choices[0].message.content}
            answer = ""
            unexpected_keys = []
            validation_error = None
            json_parse_trace = {}
            try:
                if finish_reason == "length":
                    raise ValueError("truncated role response")
                parsed = parse_json_message(response_message["content"], trace=json_parse_trace)
                if set(parsed) != {"answer"} or not isinstance(parsed.get("answer"), str) or not parsed["answer"].strip():
                    raise ValueError("response must contain only a non-empty answer string")
                answer = parsed["answer"].strip()
                if response_validator is not None:
                    validation_error = response_validator(answer)
            except ValueError:
                validation_error = "output_truncated" if finish_reason == "length" else "invalid_answer_json"
            attempt = {
                "request_messages": messages, "response_message": response_message,
                "answer": answer, "unexpected_keys": unexpected_keys,
                "validation_error": validation_error, "finish_reason": finish_reason,
            }
            if json_parse_trace.get("recovered"):
                attempt["json_parse"] = json_parse_trace
            attempts.append(attempt)
            if validation_error is None:
                history_response = ({"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)}
                                    if json_parse_trace.get("recovered") else response_message)
                self.messages.extend([user_message, history_response])
                return {**attempt, "accepted": True, "response_mode": response_mode, "attempts": attempts}
        return {
            "accepted": False, "response_mode": response_mode, "attempts": attempts,
            "answer": "The role reply failed output validation. Please query again.",
        }

def load_role_agent_configs(agent_dir: str = AGENT_DIR) -> Dict[str, Dict[str, Any]]:
    root = Path(agent_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"Missing role_agents directory: {root}")
    configs: Dict[str, Dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        config = json.loads(path.read_text(encoding="utf-8"))
        configs[config["role_agent_name"]] = config
    return configs


def build_role_agents(
    client: OpenAI, agent_dir: str = AGENT_DIR,
    model: str = ROLE_AGENT_MODEL_NAME,
) -> Dict[str, RoleAgent]:
    configs = load_role_agent_configs(agent_dir)
    if not configs:
        raise ValueError(f"Empty role_agents directory: {agent_dir}")
    return {name: RoleAgent(config, client, model) for name, config in configs.items()}


def resolve_role_name(role_name, role_names=None):
    """Resolve unique full names, Chinese names, or abbreviations without guessing."""
    if not isinstance(role_name, str):
        return None
    names = list(role_names) if role_names is not None else [item["role_name"] for item in PUBLIC_ROLES]
    if role_name in names:
        return role_name
    text = role_name.strip().replace("(", "（").replace(")", "）")
    matches = set()
    for name in names:
        normalized = name.strip().replace("(", "（").replace(")", "）")
        aliases = {normalized}
        parts = re.fullmatch(r"(.+?)（([^（）]+)）", normalized)
        if parts:
            aliases.update(part.strip() for part in parts.groups())
        if text in aliases:
            matches.add(name)
    return next(iter(matches)) if len(matches) == 1 else role_name


"""Ignore each selected role's first contact; a later contact responds normally."""
import copy


class NeglectPolicy:
    def __init__(self, role_names):
        self.roles = {name: {"state": "uncontacted", "pending": {}}
                      for name in role_names}
        self.events = []

    def contact(self, role, questions, turn):
        """Called once per role/turn with only authorized questions.

        Pending questions are tracked for metrics only, never auto-delivered.
        On retry, the caller answers the current questions normally.
        """
        state = self.roles.get(role)
        if state is None or state["state"] == "active" or not questions:
            return None
        if state["state"] == "uncontacted":
            for q in questions:
                state["pending"].setdefault(q.get("key") or q["question"], copy.deepcopy(q))
            state.update(state="ignored", first_turn=turn)
            self.events.append({"kind": "neglect_ignored", "turn": turn, "role_agent": role})
            return ""
        if turn <= state["first_turn"]:
            return ""
        state.update(state="active", pending={})
        self.events.append({"kind": "neglect_delivered", "turn": turn, "role_agent": role})
        return None

    def metrics(self):
        # Keep legacy counters at zero for compatible result readers.
        return {**{kind + "_count": sum(e["kind"] == kind for e in self.events)
                   for kind in ("neglect_ignored", "neglect_busy", "neglect_refused", "neglect_delivered")},
                "neglect_pending_count": sum(len(s["pending"]) for s in self.roles.values())}

"""Direct-access main loop, embedded in standalone runtimes."""

def run_direct(self, task):
    self._semantic_enabled_roles = set()
    self.empty_observation_count = 0
    self.neglect_policy = NeglectPolicy(self.runtime_config['communication_role_names'])
    self.communication_events = self.neglect_policy.events
    self.delivered_messages = []
    if self.incomplete_policy:
        self.incomplete_policy.reset()
        self.followup_resolver.reset()
    for role in self.role_agents.values():
        role.reset_history()
    self.messages = [{'role': 'system', 'content': self.system_message}, {'role': 'user', 'content': task}]
    transcript = []
    consecutive_errors = 0

    def answer(role, question):
        result, _ = self._answer_question(role, question)
        return dict(result, role_agent=role, question=dict(question))

    def publish(replies):
        for reply in replies:
            if reply.pop('authorized_exact', False):
                self._semantic_enabled_roles.add(reply['role_agent'])
        if replies:
            self.messages.append({'role': 'user', 'content': '\n'.join(
                r['role_agent'] + '：' + r['answer'] for r in replies)})

    for turn in range(1, self.max_turns + 1):
        self.current_turn = turn
        event = {'turn': turn, 'role_answers': []}
        try:
            action = self._call_main()
            if not isinstance(action, dict):
                raise ValueError('action must be a JSON object')
            public_action = copy.deepcopy(action)
            kind = action.get('action')
            if kind == 'finalize':
                if action.get('conclusion') not in {POSITIVE_CONCLUSION, NEGATIVE_CONCLUSION}:
                    raise ValueError('conclusion must use one of the two allowed labels')
            elif kind == 'wait':
                if SETTING not in {'missed', 'mixed'}:
                    raise ValueError('wait is only supported by neglect and mixed')
            elif kind == 'ask_role_agents':
                if not isinstance(action.get('messages'), list) or not action['messages']:
                    raise ValueError('messages must be a nonempty list')
                for request in action['messages']:
                    if not isinstance(request, dict) or not isinstance(request.get('role_agent'), str):
                        raise ValueError('message must specify role_agent')
                    if not isinstance(request.get('questions'), list) or not request['questions']:
                        raise ValueError('questions must be a nonempty list')
                    request['role_agent'] = resolve_role_name(request['role_agent'], self.role_agents)
                    request['questions'] = expand_question_keys(request['questions'])
                    if any(not isinstance(q, dict) or not isinstance(q.get('question'), str) or not q['question'].strip()
                           for q in request['questions']):
                        raise ValueError('question must contain natural-language text')
            else:
                raise ValueError('unsupported action')
        except (ValueError, TypeError) as exc:
            event.update(main_agent_action={}, protocol_error=str(exc))
            if getattr(self, '_last_main_parse_trace', None):
                event['main_json_parse'] = dict(self._last_main_parse_trace)
            transcript.append(event)
            self.messages.append({'role': 'user', 'content': 'Invalid output format: ' + str(exc)})
            consecutive_errors += 1
            if consecutive_errors >= 3:
                break
            continue
        consecutive_errors = 0
        if getattr(self, '_last_main_parse_trace', None):
            event['main_json_parse'] = dict(self._last_main_parse_trace)
        event['main_agent_action'] = action
        transcript.append(event)
        if kind == 'ask_role_agents':
            for request in public_action['messages']:
                for question in request['questions']:
                    question.pop('key', None)
        self.messages.append({'role': 'assistant', 'content': json.dumps(public_action, ensure_ascii=False)})
        if kind == 'finalize':
            return self._result({'conclusion': action['conclusion'], 'numeric_result': action.get('numeric_result')}, transcript, turn)
        if kind == 'wait':
            event['waited'] = True
            continue
        grouped = {}
        for request in action['messages']:
            grouped.setdefault(request['role_agent'], []).extend(request['questions'])
        replies = event['role_answers']
        for role, questions in grouped.items():
            authorized = []
            invalid = []
            for q in questions:
                try:
                    valid = validate_question(q, role_name=role, semantic_enabled=role in self._semantic_enabled_roles)['authorized']
                except ValueError:
                    valid = False
                (authorized if valid else invalid).append(q)
            replies.extend(answer(role, q) for q in invalid)
            response = self.neglect_policy.contact(role, authorized, turn)
            if response is None:
                replies.extend(answer(role, q) for q in authorized)
            else:
                event.setdefault('deferred_role_requests', []).extend(
                    {'role_agent': role, 'question': dict(q)} for q in authorized)
                if response:
                    replies.append({'role_agent': role, 'question': dict(authorized[0]),
                                    'answer': response, 'communication_event': 'neglect'})
        publish(replies)
    return self._result({'conclusion': None, 'numeric_result': None}, transcript, None)


class MainAgent:
    def __init__(
        self, client: OpenAI, role_agents: Dict[str, RoleAgent],
        model: str = MAIN_AGENT_MODEL_NAME, max_turns: int | None = None,
    ):
        self.client = client
        self.role_agents = role_agents
        self.model = model
        self.runtime_config = runtime_defaults()
        self.max_turns = max_turns if max_turns is not None else int(os.getenv("MAX_TURNS", str(self.runtime_config["max_turns"])))
        self.runtime_config["max_turns"] = self.max_turns
        self.neglect_policy = NeglectPolicy(self.runtime_config["communication_role_names"])
        self.delivered_messages = []
        self.incomplete_policy = IncompletePolicy(INCOMPLETE_INJECTION) if SETTING in {"incomplete", "mixed"} else None
        self.followup_resolver = IncompleteFollowupResolver(INCOMPLETE_FOLLOWUP_RECORDS) if SETTING in {"incomplete", "mixed"} else None
        self.current_turn = 0
        self.communication_events = []
        self.empty_observation_count = 0
        self.messages: List[Dict[str, str]] = []
        self.system_message = self._build_system_message()
        self._semantic_enabled_roles: set[str] = set()

    def _build_system_message(self) -> str:
        if MAIN_AGENT_ROLE_ORDER_SEED is None:
            return main_system_prompt()
        roles = list(PUBLIC_ROLES)
        random.Random(MAIN_AGENT_ROLE_ORDER_SEED).shuffle(roles)
        role_text = "\n".join(
            f"- {item['role_name']}: {item['responsibility']}"
            for item in roles
        )
        return main_system_prompt().replace(
            "\n".join(
                f"- {item['role_name']}: {item['responsibility']}"
                for item in PUBLIC_ROLES
            ),
            role_text,
        )

    def _call_main(self) -> Dict[str, Any]:
        if SETTING in {"missed", "mixed"} and self.messages[-1]["role"] == "assistant":
            self.messages.append({"role": "user", "content": '{"observations":[]}'})
            self.empty_observation_count += 1
        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            temperature=0.1,
            response_format={"type": "json_object"},
            extra_body={"reasoning": {"effort": LLM_REASONING_EFFORT, "exclude": LLM_REASONING_EXCLUDE}},
        )
        self._last_main_parse_trace = {}
        return parse_json_message(response.choices[0].message.content, trace=self._last_main_parse_trace)

    def _answer_question(
        self, role_name: str, question: Dict[str, Any],
    ) -> tuple[Dict[str, Any], bool]:
        role_name = resolve_role_name(role_name, self.role_agents)
        role = self.role_agents.get(role_name)
        if role is None:
            return {"answer": f"Error: unknown role {role_name}。"}, False
        try:
            normalized = validate_question(
                question, role_name=role_name,
                semantic_enabled=role_name in self._semantic_enabled_roles,
            )
        except ValueError as error:
            return {"answer": f"Invalid query: {error}"}, False
        if not normalized["authorized"]:
            return {"answer": "The key is invalid, belongs to another role, or keyless follow-up is not yet authorized. Include a complete key for this role in question text, without a separate key field."}, False
        key = question.get("key")
        role_question = dict(question)
        binding = None
        if (self.followup_resolver and key is None
                and (SETTING != "mixed" or role_name == INCOMPLETE_INJECTION["role_name"])):
            binding = self.followup_resolver.resolve(role_name, question['question'], self.current_turn)
            if binding['status'] != 'resolved':
                answer = (self.followup_resolver.catalog(role_name) if binding['status'] == 'catalog'
                          else self.followup_resolver.CLARIFY)
                return {"answer": answer, "followup_binding": binding}, False
            key = binding['key']
            # Resolve keys only for role requests; preserve the main question in transcripts.
            role_question = dict(question, key=key, question=question['question'] + ' (System-linked record: ' + key + ')')
        allowed_keys = set(RECORD_REPLY_KEYS[key] if key is not None else ROLE_VALID_KEYS[role_name])
        unrelated_field = False
        if binding and key == INCOMPLETE_INJECTION['key']:
            hidden_topic = INCOMPLETE_INJECTION['hidden_predicate_id'].removeprefix(INCOMPLETE_INJECTION['candidate_id'] + '_')
            unrelated_field = not binding['full'] and hidden_topic not in binding['fields'] and self.incomplete_policy.recovered_at_turn is None
        disclosure_mode = ('incomplete_partial' if unrelated_field else self.incomplete_policy.mode(role_name, role_question, self.current_turn)) if self.incomplete_policy else None
        if binding:
            binding['recovery_requested'] = disclosure_mode == 'incomplete_recovery'
        options = self.incomplete_policy.request_options(disclosure_mode, role.system_message) if disclosure_mode else {}
        trace = role.answer_with_trace(
            format_role_user_message(role_question), allowed_keys=allowed_keys,
            response_mode=disclosure_mode or ("exact" if key is not None else "search"),
            **options,
        )
        if not trace["accepted"]:
            return {
                "answer": trace["answer"], "role_validation_trace": trace,
                "protocol_error": "role_reply_scope_violation",
                **({"followup_binding": binding} if binding else {}),
            }, False
        if disclosure_mode:
            self.incomplete_policy.observe(disclosure_mode, self.current_turn, trace["answer"])
        if self.followup_resolver:
            self.followup_resolver.observe(role_name, key, self.current_turn)
        return {
            "answer": trace["answer"], "role_trace": trace,
            "authorized_exact": question.get("key") is not None,
            **({"followup_binding": binding} if binding else {}),
        }, False

    def _communication_evaluation(
        self, transcript: List[Dict[str, Any]], final_turn: int | None,
    ) -> Dict[str, Any]:
        metrics = communication_metrics(transcript)
        total_questions = sum(
            len(message.get("questions", []))
            for event in transcript
            for message in event.get("main_agent_action", {}).get("messages", [])
        )
        ideal = max(1, self.runtime_config["finalize_ideal_round"])
        turns = final_turn if final_turn is not None else len(transcript)
        return {
            **metrics,
            "total_role_agent_queries": total_questions,
            "total_questions": total_questions,
            "finalize_ideal_round": self.runtime_config["finalize_ideal_round"],
            "max_turns": self.max_turns,
            "wait_turns": sum(bool(event.get("waited")) for event in transcript),
            "empty_observation_count": self.empty_observation_count,
            **self.neglect_policy.metrics(),
            "delivered_reply_count": len(self.delivered_messages),
            "pending_reply_count": self.neglect_policy.metrics()["neglect_pending_count"],
            "efficiency": min(1.0, ideal / turns) if final_turn else 0.0,
        }

    def _result(
        self, final: Dict[str, Any], transcript: List[Dict[str, Any]], final_turn: int | None,
    ) -> Dict[str, Any]:
        conclusion = compute_conclusion_correctness(final)
        communication = self._communication_evaluation(transcript, final_turn)
        communication["recovery_success"] = (
            recovery_success(communication, conclusion["conclusion_correctness"] == 1)
            if ERROR_INJECTION.get("enabled") else None
        )
        if self.incomplete_policy:
            communication.update(self.followup_resolver.metrics())
            communication.update(self.incomplete_policy.metrics(
                correct=conclusion["conclusion_correctness"] == 1, finalized=final_turn is not None,
            ))
            communication.update(incomplete_numeric_metrics(
                INCOMPLETE_INJECTION, transcript, communication,
                correct=conclusion["conclusion_correctness"] == 1, finalized=final_turn is not None,
            ))
        return {
            "final_result": final,
            "evaluation": {
                "conclusion_correct": conclusion["conclusion_correct"],
                "numeric_result_correct": conclusion["numeric_result_correct"],
                "joint_correctness": conclusion["conclusion_correctness"],
                "conclusion_evaluation": conclusion,
                "communication_evaluation": communication,
            },
            "transcript": transcript,
            "runtime_config": dict(self.runtime_config),
            "collaboration_state": {
                "neglect_roles": self.neglect_policy.roles,
                "delivered_messages": list(self.delivered_messages),
                "communication_events": list(self.communication_events),
            },
        }

    run = run_direct


def build_task() -> str:
    return TASK_CONTEXT.strip() + "\n\n" + TASK_QUERY.strip()


def create_timestamped_run_dir(
    root: str | Path, prefix: str, started: datetime | None = None,
) -> Path:
    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    timestamp = (started or datetime.now()).strftime("%m%d_%H%M")
    base_name = f"{prefix}_{timestamp}"
    suffix = 1
    while True:
        name = base_name if suffix == 1 else f"{base_name}_{suffix:02d}"
        candidate = root_path / name
        try:
            candidate.mkdir(exist_ok=False)
            return candidate
        except FileExistsError:
            suffix += 1


def save_single_run_result(
    result: Dict[str, Any], output_root: str | Path | None = None,
) -> Path:
    logs_root = (
        Path(output_root)
        if output_root is not None
        else Path(__file__).resolve().parent.parent / "logs"
    )
    run_dir = create_timestamped_run_dir(logs_root, "single_run")
    result_path = run_dir / "result.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result_path


def main() -> None:
    main_client = OpenAI(base_url=MAIN_AGENT_BASE_URL, api_key=MAIN_AGENT_API_KEY)
    role_client = OpenAI(base_url=ROLE_AGENT_BASE_URL, api_key=ROLE_AGENT_API_KEY)
    role_agents = build_role_agents(role_client)
    agent = MainAgent(main_client, role_agents)
    task = build_task()
    print_key_trace("LLM CONFIG", format_llm_config())
    print_key_trace("AVAILABLE ROLES", format_available_roles(role_agents))
    print_key_trace("TASK QUERY", task)
    result = agent.run(task)
    result_path = save_single_run_result(result)
    summary_title = "MISALIGNED RECOVERY SUMMARY" if SETTING in {"misaligned", "mixed"} else "TASK SUMMARY"
    print_key_trace(summary_title, format_key_metrics(result["evaluation"]))
    print_key_trace("RESULT SAVED", result_path)


if __name__ == "__main__":
    main()
