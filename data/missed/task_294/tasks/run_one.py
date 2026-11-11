from __future__ import annotations
import json
import re
from typing import Any
COMMUNICATION_ROLE_NAMES = ['Subsea acoustics specialist (SAS)']
GOLD = {'conclusion': 'Select', 'numeric_result': 72}
POSITIVE_CONCLUSION = 'Select'
NEGATIVE_CONCLUSION = 'Do not select'
NUMERIC_PRECISION = 0
PUBLIC_ROLES = [{'role_name': 'Subsea acoustics specialist (SAS)', 'responsibility': 'Maintains acoustic sonar profiling and sensor calibration records', 'role_abbreviation': 'SAS'}, {'role_name': 'Intervention robotics engineer (IRE)', 'responsibility': 'Maintains subsea crawler tooling certifications and vehicle endurance figures', 'role_abbreviation': 'IRE'}, {'role_name': 'Subsea telemetry systems officer (STS)', 'responsibility': 'Maintains subsea umbilical telemetry latency and optical link records', 'role_abbreviation': 'STS'}, {'role_name': 'Marine environmental compliance officer (ECO)', 'responsibility': 'Maintains benthic habitat clearances and environmental protection permits', 'role_abbreviation': 'ECO'}, {'role_name': 'Offshore safety regulator liaison (OSR)', 'responsibility': 'Maintains national energy regulator safety case and hazard mitigation sign-offs', 'role_abbreviation': 'OSR'}, {'role_name': 'Marine geophysics lead (MGL)', 'responsibility': 'Maintains seabed survey speed rate benchmarks', 'role_abbreviation': 'MGL'}, {'role_name': 'Commercial charter coordinator (CCC)', 'responsibility': 'Maintains vessel availability and vessel day-rate estimates', 'role_abbreviation': 'CCC'}]
ROLE_KEY_PREFIXES = {'Subsea acoustics specialist (SAS)': 'SAS-', 'Intervention robotics engineer (IRE)': 'IRE-', 'Subsea telemetry systems officer (STS)': 'STS-', 'Marine environmental compliance officer (ECO)': 'ECO-', 'Offshore safety regulator liaison (OSR)': 'OSR-', 'Marine geophysics lead (MGL)': 'MGL-', 'Commercial charter coordinator (CCC)': 'CCC-'}
ROLE_VALID_KEYS = {'Subsea acoustics specialist (SAS)': ['SAS-NOISE-71N', 'SAS-NOISE-V8Y', 'SAS-NOISE-QNO', 'SAS-SONAR-H1D', 'SAS-SONAR-O5H', 'SAS-SONAR-A6E'], 'Intervention robotics engineer (IRE)': ['IRE-TOOL-TFK', 'IRE-TOOL-RMQ', 'IRE-TOOL-C9J', 'IRE-DEPTH-4UV', 'IRE-DEPTH-RVA', 'IRE-DEPTH-SE9'], 'Subsea telemetry systems officer (STS)': ['STS-BAND-QTN', 'STS-BAND-8LI', 'STS-BAND-L63', 'STS-COMM-C5Q', 'STS-COMM-5OB', 'STS-COMM-TIH'], 'Marine environmental compliance officer (ECO)': ['ECO-ENV-CS2', 'ECO-ENV-H19', 'ECO-ENV-OKJ', 'ECO-CORAL-PBR', 'ECO-CORAL-FT4', 'ECO-CORAL-50H'], 'Offshore safety regulator liaison (OSR)': ['OSR-EVAC-KPJ', 'OSR-EVAC-IRY', 'OSR-EVAC-323', 'OSR-REG-1BJ', 'OSR-REG-QL1', 'OSR-REG-Z8T'], 'Marine geophysics lead (MGL)': ['MGL-MAG-OAB', 'MGL-MAG-KN7', 'MGL-MAG-WMT', 'MGL-GEO-X25', 'MGL-GEO-4SG', 'MGL-GEO-1K3'], 'Commercial charter coordinator (CCC)': ['CCC-CHAR-GHV', 'CCC-CHAR-MCI', 'CCC-CHAR-U3E', 'CCC-CREW-I81', 'CCC-CREW-60A', 'CCC-CREW-8L0']}
RECORD_REPLY_KEYS = {'SAS-SONAR-A6E': ['SAS-SONAR-A6E'], 'SAS-SONAR-H1D': ['SAS-SONAR-H1D'], 'SAS-SONAR-O5H': ['SAS-SONAR-O5H'], 'IRE-TOOL-TFK': ['IRE-TOOL-TFK'], 'IRE-TOOL-RMQ': ['IRE-TOOL-RMQ'], 'IRE-TOOL-C9J': ['IRE-TOOL-C9J'], 'STS-COMM-5OB': ['STS-COMM-5OB'], 'STS-COMM-C5Q': ['STS-COMM-C5Q'], 'STS-COMM-TIH': ['STS-COMM-TIH'], 'ECO-ENV-H19': ['ECO-ENV-H19'], 'ECO-ENV-OKJ': ['ECO-ENV-OKJ'], 'ECO-ENV-CS2': ['ECO-ENV-CS2'], 'OSR-REG-1BJ': ['OSR-REG-1BJ'], 'OSR-REG-Z8T': ['OSR-REG-Z8T'], 'OSR-REG-QL1': ['OSR-REG-QL1'], 'MGL-GEO-X25': ['MGL-GEO-X25'], 'MGL-GEO-1K3': ['MGL-GEO-1K3'], 'MGL-GEO-4SG': ['MGL-GEO-4SG'], 'CCC-CHAR-GHV': ['CCC-CHAR-GHV'], 'CCC-CHAR-MCI': ['CCC-CHAR-MCI'], 'CCC-CHAR-U3E': ['CCC-CHAR-U3E'], 'SAS-NOISE-QNO': ['SAS-NOISE-QNO'], 'SAS-NOISE-71N': ['SAS-NOISE-71N'], 'SAS-NOISE-V8Y': ['SAS-NOISE-V8Y'], 'STS-BAND-L63': ['STS-BAND-L63'], 'STS-BAND-QTN': ['STS-BAND-QTN'], 'STS-BAND-8LI': ['STS-BAND-8LI'], 'ECO-CORAL-FT4': ['ECO-CORAL-FT4'], 'ECO-CORAL-50H': ['ECO-CORAL-50H'], 'ECO-CORAL-PBR': ['ECO-CORAL-PBR'], 'OSR-EVAC-IRY': ['OSR-EVAC-IRY'], 'OSR-EVAC-323': ['OSR-EVAC-323'], 'OSR-EVAC-KPJ': ['OSR-EVAC-KPJ'], 'MGL-MAG-KN7': ['MGL-MAG-KN7'], 'MGL-MAG-OAB': ['MGL-MAG-OAB'], 'MGL-MAG-WMT': ['MGL-MAG-WMT'], 'CCC-CREW-8L0': ['CCC-CREW-8L0'], 'CCC-CREW-I81': ['CCC-CREW-I81'], 'CCC-CREW-60A': ['CCC-CREW-60A'], 'IRE-DEPTH-RVA': ['IRE-DEPTH-RVA'], 'IRE-DEPTH-SE9': ['IRE-DEPTH-SE9'], 'IRE-DEPTH-4UV': ['IRE-DEPTH-4UV']}
REQUIRED_KEYS = ['ECO-ENV-H19', 'IRE-TOOL-C9J', 'IRE-TOOL-TFK', 'MGL-GEO-X25', 'OSR-REG-1BJ', 'SAS-SONAR-A6E', 'SAS-SONAR-H1D', 'STS-COMM-5OB']
DISTRACTOR_KEYS = ['CCC-CHAR-GHV', 'CCC-CHAR-MCI', 'CCC-CHAR-U3E', 'CCC-CREW-60A', 'CCC-CREW-8L0', 'CCC-CREW-I81']
SETTING = 'missed'

def runtime_defaults() -> dict[str, Any]:
    return {
        "setting": SETTING,
        "communication_role_names": list(COMMUNICATION_ROLE_NAMES),
        "neglect_required_followups": 1,
        "finalize_ideal_round": 3,
        "max_turns": 6,
    }

FINALIZE_IDEAL_ROUND = runtime_defaults()["finalize_ideal_round"]
DEFAULT_MAX_TURNS = runtime_defaults()["max_turns"]
ERROR_INJECTION = {'enabled': False, 'role_name': 'Intervention robotics engineer (IRE)', 'target_key': 'IRE-TOOL-TFK', 'alternate_key': 'IRE-DEPTH-RVA', 'target_context': 'Production release', 'alternate_context': 'Testbed prototype release'}
INCOMPLETE_INJECTION = {}
INCOMPLETE_FOLLOWUP_RECORDS = []
KEY_PATTERN = re.compile(r"^[A-Z]+-[A-Z]+-[A-Z0-9]{3}$")
REPLY_KEY_PATTERN = re.compile(r"(?<![A-Z0-9])[A-Z]+-[A-Z]+-[A-Z0-9]{3}(?![A-Z0-9])", re.IGNORECASE)
ROLE_REPLY_MAX_ATTEMPTS = 3
TASK_QUERY = 'Evaluate the candidate investigation plans to determine whether exactly one plan qualifies for selection. A plan qualifies if it possesses autonomous acoustic leak mapping capability, holds certified pipeline intervention tooling clearance under the Production release deployment version, has an active subsea telemetry system with a remote telemetry latency of at most 120 ms, has obtained marine environmental clearance approval, and holds regulatory safety case sign-off. If exactly one candidate meets all criteria, report "Select" alongside its total deepwater survey work volume in km, computed as its deepwater inspection rate multiplied by its operational seabed endurance assessed under the Production release deployment version; otherwise, report "Do not select".\n\nNumeric calculation rule: Compute only for the unique eligible candidate: [Deepwater inspection rate] * [Operational seabed endurance]. Result unit: km. Round only the final result to 0 decimal places (ties to even). If no candidate qualifies, numeric_result is null.\n\nCandidates and records to verify:\n- Tethered crawler inspection plan：SAS-SONAR-H1D、IRE-TOOL-RMQ、STS-COMM-C5Q、ECO-ENV-OKJ、OSR-REG-Z8T、MGL-GEO-1K3、CCC-CHAR-MCI\n- Autonomous bathymetric survey plan：SAS-SONAR-A6E、IRE-TOOL-TFK、STS-COMM-5OB、ECO-ENV-H19、OSR-REG-1BJ、MGL-GEO-X25、CCC-CHAR-GHV\n- Hybrid ROV acoustic profiling plan：SAS-SONAR-O5H、IRE-TOOL-C9J、STS-COMM-TIH、ECO-ENV-CS2、OSR-REG-QL1、MGL-GEO-4SG、CCC-CHAR-U3E'
TASK_CONTEXT = 'Following a subsea pipeline rupture, an offshore energy forensic review is being conducted to choose a qualified investigation plan for root-cause inspection and seabed forensic logging. To ensure safe and compliant operations in hazardous venting zones, candidate plans are evaluated across technical sensing readiness, tooling compliance under the Production release deployment version, communications network performance, and regulatory authorizations.'

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


"""Reply after a configurable number of later-turn authorized follow-ups."""
import copy


class NeglectPolicy:
    def __init__(self, role_names, required_followups=1):
        if type(required_followups) is not int or required_followups < 1:
            raise ValueError('required_followups must be a positive integer')
        self.required_followups = required_followups
        self.roles = {name: {"state": "uncontacted", "pending": {}, "followups": 0}
                      for name in role_names}
        self.events = []

    def contact(self, role, questions, turn):
        """Called once per role/turn with only authorized questions.

        Pending questions are tracked for metrics only, never auto-delivered.
        Only one contact per distinct later turn counts, regardless of question
        count. Once the threshold is met, answer current questions normally.
        """
        state = self.roles.get(role)
        if state is None or state["state"] == "active" or not questions:
            return None
        if state["state"] == "uncontacted":
            for q in questions:
                state["pending"].setdefault(q.get("key") or q["question"], copy.deepcopy(q))
            state.update(state="ignored", first_turn=turn, last_contact_turn=turn)
            self.events.append({"kind": "neglect_ignored", "turn": turn, "role_agent": role})
            return ""
        if turn <= state["last_contact_turn"]:
            return ""
        state['last_contact_turn'] = turn
        state['followups'] += 1
        if state['followups'] < self.required_followups:
            for q in questions:
                state['pending'].setdefault(q.get('key') or q['question'], copy.deepcopy(q))
            self.events.append({'kind': 'neglect_ignored', 'turn': turn, 'role_agent': role})
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
    self.neglect_policy = NeglectPolicy(self.runtime_config['communication_role_names'],
                                       self.runtime_config.get('neglect_required_followups', 1))
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
