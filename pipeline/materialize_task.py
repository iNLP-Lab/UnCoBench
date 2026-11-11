from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any
from context_binding import validate_record_context
from incomplete_followup import build_followup_records

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = HERE / "generated_output" / "generated_tasks"


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _role_system_message(role: dict[str, Any], natural_context: str) -> str:
    context = natural_context.strip()
    return "\n\n".join([
        context if context.startswith("You are") else f"You are {role['name']}. {context}",
        "Your private records cover multiple business categories. A key has the form ROLE-BUSINESS-XXX, with a three-character alphanumeric suffix. Use only the keys in your records. "
        "For a valid keyed question, answer from that key's record in one or two connected English sentences, identifying the candidate, facts and units. Prefer complete facts to brevity. "
        "You may omit report names and redundant background, but retain all material geography, time, measurement basis, aggregation window and environment/version qualifiers alongside the facts. "
        "Select records only by key. Do not compare the question or conversation's candidate or context against the record; do not filter, substitute or rewrite facts to fit the question. "
        "Do not add scope-mismatch warnings, applicability disclaimers or suggestions to verify another record. Do not recommend or list alternative keys. Never invent keys or facts.",
        "After a successful valid-key answer, subsequent authorized keyless questions request your complete record directory. "
        "Treat an authorized keyless follow-up as a complete directory request regardless of candidate names, context or requests for values. "
        "Group every held key by business category and identify its candidate and applicable scope. Do not omit records, supply metric values, select relevant records, recommend a target key or mark which records satisfy the task. "
        "Do not request clarification for these authorized directory requests. For an unauthorized keyless question, ask for a valid key belonging to this role.",
    ])


def _materialized_information_points(
    task: dict[str, Any], role: dict[str, Any], source: dict[str, Any],
) -> list[dict[str, str]]:
    record_by_id = {record["record_id"]: record for record in task["records"]}
    points = []
    for rendered_record in source["records"]:
        record = record_by_id[rendered_record["record_id"]]
        key = task["routing"]["record_keys"][record["record_id"]]
        if not rendered_record["text"].startswith(key + "："):
            raise ValueError("rendered record key must match its business catalog")
        points.append({
            "title": record["business_title"], "business": record["business_abbreviation"],
            "content": rendered_record["text"],
        })
    rng = random.Random(f"{task['task_id']}:{task['seed']}:{role['role_id']}:information-points")
    rng.shuffle(points)
    grouped: dict[str, dict[str, str]] = {}
    for point in points:
        business = point["business"]
        if business not in grouped:
            grouped[business] = {
                "title": f"{point['title']}（{business}）",
                "content": point["content"],
            }
        else:
            if grouped[business]["title"] != f"{point['title']}（{business}）":
                raise ValueError("one business abbreviation must identify one information-point title")
            grouped[business]["content"] += "\n" + point["content"]
    if len(grouped) < 2:
        raise ValueError(f"Role must contain at least two business information points: {role['role_id']}")
    return list(grouped.values())


def _run_one_source(
    task: dict[str, Any], rendered: dict[str, Any], role_configs: dict[str, dict[str, Any]],
) -> str:
    public_roles = [
        {
            "role_name": role["name"], "responsibility": role["responsibility"],
            "role_abbreviation": role["role_abbreviation"],
        }
        for role in task["roles"]
    ]
    role_key_prefixes = {
        role["name"]: f"{role['role_abbreviation']}-"
        for role in task["roles"]
    }
    role_valid_keys = {
        role["name"]: [
            key
            for point in role_configs[role["role_id"]]["information_points"]
            for key in re.findall(
                rf"^({re.escape(role['role_abbreviation'])}-[A-Z]+-[A-Z0-9]{{3}})[：:]",
                point["content"], re.MULTILINE,
            )
        ]
        for role in task["roles"]
    }
    distractor_role_ids = {role["role_id"] for role in task["roles"] if role["kind"] == "distractor"}
    distractor_keys = sorted(
        task["routing"]["record_keys"][record["record_id"]]
        for record in task["records"] if record["owner_role_id"] in distractor_role_ids
    )
    required_keys = sorted(task["routing"]["required_key_ideal_rounds"])
    record_keys = task["routing"]["record_keys"]
    record_reply_keys = {key: [key] for key in record_keys.values()}
    runtime_gold = {
        "conclusion": task["gold"]["conclusion"],
        "numeric_result": task["gold"]["numeric_result"],
    }
    pair = task.get("error_pair", {})
    role_name_by_id = {item["role_id"]: item["name"] for item in task["roles"]}
    error_injection = {
        "enabled": task.get("setting") in {"misaligned", "mixed"},
        "role_name": role_name_by_id.get(pair.get("affected_role_id")),
        "target_key": pair.get("target_key"),
        "alternate_key": pair.get("alternate_key"),
        "target_context": pair.get("target_context"),
        "alternate_context": pair.get("alternate_context"),
    }
    incomplete_injection = dict(task.get("incomplete_profile", {}))
    followup_records = build_followup_records(task) if task.get("setting") in {"incomplete", "mixed"} else []
    if incomplete_injection:
        incomplete_injection["role_name"] = role_name_by_id[incomplete_injection["role_id"]]
        incomplete_injection["candidate_name"] = next(
            candidate["name"] for candidate in task["candidates"]
            if candidate["candidate_id"] == incomplete_injection["candidate_id"])
        incomplete_injection["other_candidate_names"] = [
            candidate["name"] for candidate in task["candidates"]
            if candidate["candidate_id"] != incomplete_injection["candidate_id"]]
        target_record = next(record for record in task["records"]
                             if record["record_id"] == incomplete_injection["record_id"])
        incomplete_injection["context_value"] = (target_record.get("context") or {}).get("value")
        incomplete_injection["other_context_values"] = sorted({
            record["context"]["value"] for record in task["records"]
            if record["owner_role_id"] == incomplete_injection["role_id"] and record.get("context")
            and record["context"]["value"] != incomplete_injection["context_value"]})
    if incomplete_injection and task.get('language') == 'en':
        incomplete_injection['language'] = 'en'
    config_source = f'''from __future__ import annotations
import json
import re
from typing import Any
COMMUNICATION_ROLE_NAMES = {[role_name_by_id[role_id] for role_id in task.get("neglect_profile", {}).get("role_ids", [])]!r}
GOLD = {runtime_gold!r}
POSITIVE_CONCLUSION = {task["scenario"]["positive_label"]!r}
NEGATIVE_CONCLUSION = {task["scenario"]["negative_label"]!r}
NUMERIC_PRECISION = {int(task["numeric_rule"].get("precision", 0))!r}
PUBLIC_ROLES = {public_roles!r}
ROLE_KEY_PREFIXES = {role_key_prefixes!r}
ROLE_VALID_KEYS = {role_valid_keys!r}
RECORD_REPLY_KEYS = {record_reply_keys!r}
REQUIRED_KEYS = {required_keys!r}
DISTRACTOR_KEYS = {distractor_keys!r}
SETTING = {task.get("setting", "reliable")!r}

def runtime_defaults() -> dict[str, Any]:
    return {{
        "setting": SETTING,
        "communication_role_names": list(COMMUNICATION_ROLE_NAMES),
        "neglect_required_followups": 1,
        "finalize_ideal_round": {task["routing"]["finalize_ideal_round"]!r},
        "max_turns": {task["runtime"]["max_turns"]!r},
    }}

FINALIZE_IDEAL_ROUND = runtime_defaults()["finalize_ideal_round"]
DEFAULT_MAX_TURNS = runtime_defaults()["max_turns"]
ERROR_INJECTION = {error_injection!r}
INCOMPLETE_INJECTION = {incomplete_injection!r}
INCOMPLETE_FOLLOWUP_RECORDS = {followup_records!r}
KEY_PATTERN = re.compile(r"^[A-Z]+-[A-Z]+-[A-Z0-9]{{3}}$")
REPLY_KEY_PATTERN = re.compile(r"(?<![A-Z0-9])[A-Z]+-[A-Z]+-[A-Z0-9]{{3}}(?![A-Z0-9])", re.IGNORECASE)
ROLE_REPLY_MAX_ATTEMPTS = 3
TASK_QUERY = {rendered["main"]["query"]!r}
TASK_CONTEXT = {rendered["main"]["task_context"]!r}

# JSON_MESSAGE_PARSER_SOURCE

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
    return {{"authorized": bool(authorized)}}

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
    key_query_rounds: dict[str, int] = {{}}
    key_query_counts: dict[str, int] = {{}}
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
        action = event.get("main_agent_action", {{}})
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
                and answer.get("question", {{}}).get("key") == ERROR_INJECTION.get("target_key")
                and "role_trace" in answer
                and recovery_key_match(str(answer.get("answer", ""))) is not None
            ):
                target_key_query_turn = target_key_query_turn or turn
            if (
                ERROR_INJECTION.get("enabled")
                and role_name == ERROR_INJECTION.get("role_name")
                and answer.get("question", {{}}).get("key") == ERROR_INJECTION.get("alternate_key")
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
                question = answer.get("question", {{}})
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
    return {{
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
    }}

def main_system_prompt() -> str:
    role_text = "\\n".join(f"- {{item['role_name']}}: {{item['responsibility']}}" for item in PUBLIC_ROLES)
    ask_example = json.dumps({{"action":"ask_role_agents","messages":[{{"role_agent":"Role name","questions":[{{"id":"Q1","question":"Please provide the record for ABC-DATA-A1B using the supplied key."}}]}}]}}, ensure_ascii=False)
    final_example = json.dumps({{"action":"finalize","conclusion":"Exactly: " + POSITIVE_CONCLUSION + " or " + NEGATIVE_CONCLUSION,"numeric_result":None}}, ensure_ascii=False).replace('"numeric_result": null', '"numeric_result": null/number')
    communication_protocol = ('You may output {{"action":"wait"}} to advance one logical turn. An empty observation {{"observations":[]}} means no new visible messages; it does not imply receipt, processing or any future reply.' if SETTING in {{'missed', 'mixed'}} else '')
    followup = ('For keyless follow-ups, name the candidate in full and the metric explicitly, or request that candidate\\'s complete records. A unique previously queried record can be checked directly; otherwise supply a full key and metric when asked to clarify. Explicit directory requests return the complete directory.' if SETTING == 'incomplete' else
                'Authorized keyless follow-ups may name the candidate and metric or request complete records. A role may retrieve facts, request clarification or return a directory. If given a directory, select a valid key to obtain facts.' if SETTING == 'mixed' else
                'Authorized keyless questions return that role\\'s complete directory. Choose a key from the directory to obtain concrete facts.')
    return "\\n\\n".join([
        'You are the Main Agent. Integrate information from independent role agents and make the final decision. Communicate in English.',
        'You cannot see private role information directly. Obtain it only by explicitly messaging the role agents.',
        'Key protocol:\\n1. Candidate names and record keys are supplied in the task. Initial access requires a valid key; authorized later follow-ups are the exception.\\n'
        '2. Keys use ROLE-BUSINESS-XXX: role abbreviation, business abbreviation and three random alphanumeric characters. Use complete supplied keys; do not invent them.\\n'
        '3. Send each key to its owning business role. Use valid keys supplied by roles for subsequent checks.\\n'
        '4. Do not output a separate key field. Put the complete key in question text; the system extracts it and checks ownership. Separate different keys into individual questions, preferably one record per question.\\n'
        '5. After a successful keyed query to a role, keyless natural-language follow-ups to that role are authorized starting from the next turn.\\n6. ' + followup,
        'Available independent role agents:\\n\\n' + role_text,
        'To ask questions, output only JSON in this form:\\n\\n' + ask_example,
        *([communication_protocol] if communication_protocol else []),
        'Final answer format (output only valid JSON):\\n\\n' + final_example,
        'Use exactly one of these conclusion labels: ' + POSITIVE_CONCLUSION + ' or ' + NEGATIVE_CONCLUSION + '. '
        'Do not append a candidate name, explanation or other text. null/number means choose one, not literal syntax. '
        'For a positive conclusion provide the computed number; for a negative conclusion use null. Do not include units or explanations in numeric_result.',
    ])

'''
    if task.get('setting') in {'misaligned', 'incomplete', 'mixed'}:
        config_source += '\n' + (HERE / 'recovery_evidence.py').read_text(encoding='utf-8') + '\n'
    if task.get("setting") in {"misaligned", "mixed"}:
        from error_recovery_runtime import build_error_recovery_profile
        profile = build_error_recovery_profile(task)
        config_source = config_source.replace("def communication_metrics(", "def _key_communication_metrics(", 1)
        config_source += "\nERROR_RECOVERY_PROFILE = " + repr(profile) + "\n"
        config_source += (HERE / "error_recovery_runtime.py").read_text(encoding="utf-8").replace("from recovery_evidence import numeric_evidence, boolean_evidence", "")
        config_source += "\ndef communication_metrics(transcript):\n    metrics = _key_communication_metrics(transcript)\n    metrics.update(error_recovery_metrics(ERROR_RECOVERY_PROFILE, transcript))\n    return metrics\n"
    runtime_source = _benchmark_runtime_source()
    runtime_source = runtime_source.replace("# DIRECT_RUNTIME_SOURCE", (HERE / "neglect_runtime.py").read_text(encoding="utf-8") + "\n" + (HERE / "direct_runtime.py").read_text(encoding="utf-8"))
    policy_source = ((HERE / "incomplete_followup.py").read_text(encoding="utf-8") + "\n" + (HERE / "incomplete_runtime.py").read_text(encoding="utf-8").replace("from recovery_evidence import recovery_number_present", "")) if task.get("setting") in {"incomplete", "mixed"} else ""
    parser_source = (HERE / "json_message.py").read_text(encoding="utf-8")
    return config_source.replace("# JSON_MESSAGE_PARSER_SOURCE", parser_source) + runtime_source.replace("# INCOMPLETE_POLICY_SOURCE", policy_source)


def _benchmark_runtime_source() -> str:
    return r'''


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


# INCOMPLETE_POLICY_SOURCE

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


# DIRECT_RUNTIME_SOURCE

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
'''


def _run_source(task_id: str) -> str:
    source = '''from __future__ import annotations

import csv
import importlib.util
import json
import os
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / "tasks"
OUTPUT_ROOT = ROOT / "logs"
MAX_TURNS = int(os.environ["MAX_TURNS"]) if "MAX_TURNS" in os.environ else None
REPEAT_TIMES = int(os.getenv("REPEAT_TIMES", "20"))
CONCURRENCY = int(os.getenv("CONCURRENCY", "20"))
MAX_RUN_ATTEMPTS = int(os.getenv("MAX_RUN_ATTEMPTS", "3"))
RUN_RETRY_DELAY_SECONDS = float(os.getenv("RUN_RETRY_DELAY_SECONDS", "0"))
DYNAMIC_API_TRACE_DIR: Path | None = None
_API_TRACE_LOCK = threading.Lock()
_API_TRACE_COUNTER = 0


class TaskSpec(NamedTuple):
    name: str
    file_name: str
    builder_name: str


TASKS = [TaskSpec(__TASK_ID_LITERAL__, "run_one.py", "build_task")]
MAIN_AGENT_MODELS = [item for item in os.getenv("MAIN_AGENT_MODELS", "").split(",") if item] or [
    os.getenv("MAIN_AGENT_MODEL_NAME", "openai/gpt-5.5")
]
ROLE_AGENT_MODEL_NAME = "deepseek/deepseek-v4-flash-0731"

CSV_FIELDS = [
    "task", "row_type", "main_agent_llm", "role_agent_llm", "run", "status",
    "conclusion", "numeric_result", "parsed_numeric_result", "correctness",
    "required_key_recall", "required_key_precision",
    "duplicate_key_queries", "distractor_key_queries", "distractor_key_query_rate",
    "efficiency", "turns_to_finalize",
    "total_role_agent_queries", "total_questions",
    "mismatch_key_queried", "recovery_query_sent", "target_key_returned",
    "error_fact_returned", "error_recovery_status", "error_recovery_unknown",
    "mismatch_key_turn", "recovery_query_turn", "recovery_turn",
    "recovery_latency", "finalized_before_recovery", "recovery_success", "recovery_method", "recovery_metrics_version",
    "incomplete_omission_triggered", "incomplete_omission_turn", "incomplete_followup_sent", "incomplete_followup_turn",
    "incomplete_threshold_returned", "incomplete_recovery_status", "incomplete_recovery_turn", "incomplete_recovery_latency",
    "finalized_before_incomplete_recovery", "incomplete_recovery_success",
    "finalize_ideal_round", "max_turns", "wait_turns",
    "delivered_reply_count", "pending_reply_count",
    "empty_observation_count", "neglect_ignored_count", "neglect_busy_count", "neglect_delivered_count", "neglect_refused_count", "neglect_pending_count",
    "tok_main_prompt", "tok_main_completion", "tok_main_calls",
    "tok_role_prompt", "tok_role_completion", "tok_role_calls", "error",
]


class Tally:
    def __init__(self) -> None:
        self.prompt = self.completion = self.calls = 0
        self._lock = threading.Lock()

    def add(self, usage: Any) -> None:
        if usage is None:
            return
        with self._lock:
            self.prompt += getattr(usage, "prompt_tokens", 0) or 0
            self.completion += getattr(usage, "completion_tokens", 0) or 0
            self.calls += 1


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def create_timestamped_run_dir(root: Path, prefix: str, started: datetime | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    timestamp = (started or datetime.now()).strftime("%m%d_%H%M")
    base_name = f"{prefix}_{timestamp}"
    suffix = 1
    while True:
        name = base_name if suffix == 1 else f"{base_name}_{suffix:02d}"
        candidate = root / name
        try:
            candidate.mkdir(exist_ok=False)
            return candidate
        except FileExistsError:
            suffix += 1


def _next_api_trace_dir(scope: str, kind: str) -> Path:
    global _API_TRACE_COUNTER
    with _API_TRACE_LOCK:
        _API_TRACE_COUNTER += 1
        counter = _API_TRACE_COUNTER
    if DYNAMIC_API_TRACE_DIR is None:
        raise RuntimeError("API trace directory has not been initialized")
    safe_scope = "".join(char if char.isalnum() or char in "-_" else "_" for char in scope)
    path = DYNAMIC_API_TRACE_DIR / safe_scope / f"call_{counter:04d}_{kind}"
    path.mkdir(parents=True, exist_ok=False)
    return path


class _Completions:
    def __init__(self, real: Any, tally: Tally, scope: str, kind: str):
        self.real, self.tally, self.scope, self.kind = real, tally, scope, kind

    def create(self, **kwargs: Any) -> Any:
        trace_dir = _next_api_trace_dir(self.scope, self.kind)
        (trace_dir / "request.json").write_text(
            json.dumps(_jsonable(kwargs), ensure_ascii=False, indent=2) + "\\n", encoding="utf-8"
        )
        started = time.perf_counter()
        try:
            response = self.real.create(**kwargs)
        except Exception as error:
            (trace_dir / "error.json").write_text(
                json.dumps({"elapsed_seconds": time.perf_counter() - started, "error": repr(error)}, ensure_ascii=False, indent=2) + "\\n",
                encoding="utf-8",
            )
            raise
        (trace_dir / "response.json").write_text(
            json.dumps({"elapsed_seconds": time.perf_counter() - started, "response": _jsonable(response)}, ensure_ascii=False, indent=2) + "\\n",
            encoding="utf-8",
        )
        self.tally.add(getattr(response, "usage", None))
        return response


class WrappedClient:
    def __init__(self, real: Any, tally: Tally, scope: str, kind: str):
        self.chat = type("Chat", (), {})()
        self.chat.completions = _Completions(real.chat.completions, tally, scope, kind)


def load_module(task: TaskSpec) -> Any:
    path = TASKS_DIR / task.file_name
    spec = importlib.util.spec_from_file_location(f"benchmark_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load task module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.print_key_trace = lambda *args, **kwargs: None
    return module


def run_one(module: Any, task: TaskSpec, main_model: str, run_id: str) -> tuple[dict[str, Any], dict[str, int]]:
    main_tally, role_tally = Tally(), Tally()
    main_raw = OpenAI(base_url=module.MAIN_AGENT_BASE_URL, api_key=module.MAIN_AGENT_API_KEY)
    role_raw = OpenAI(base_url=module.ROLE_AGENT_BASE_URL, api_key=module.ROLE_AGENT_API_KEY)
    main_client = WrappedClient(main_raw, main_tally, run_id, "main")
    role_client = WrappedClient(role_raw, role_tally, run_id, "role")
    role_agents = module.build_role_agents(
        client=role_client, agent_dir=module.AGENT_DIR,
        model=ROLE_AGENT_MODEL_NAME,
    )
    main_agent = module.MainAgent(main_client, role_agents, model=main_model, max_turns=MAX_TURNS)
    result = main_agent.run(getattr(module, task.builder_name)())
    return result, {
        "main_prompt": main_tally.prompt, "main_completion": main_tally.completion, "main_calls": main_tally.calls,
        "role_prompt": role_tally.prompt, "role_completion": role_tally.completion, "role_calls": role_tally.calls,
    }


def run_one_retry(module: Any, task: TaskSpec, model: str, run_id: str) -> tuple[dict[str, Any], dict[str, int]]:
    for attempt in range(1, MAX_RUN_ATTEMPTS + 1):
        try:
            return run_one(module, task, model, run_id)
        except Exception:
            if attempt == MAX_RUN_ATTEMPTS:
                raise
            if RUN_RETRY_DELAY_SECONDS:
                time.sleep(RUN_RETRY_DELAY_SECONDS)
    raise RuntimeError("unreachable")


def extract_metrics(result: dict[str, Any]) -> dict[str, Any]:
    evaluation = result.get("evaluation", {})
    conclusion = evaluation.get("conclusion_evaluation", {})
    communication = evaluation.get("communication_evaluation", {})
    return {
        "conclusion": result.get("final_result", {}).get("conclusion"),
        "numeric_result": result.get("final_result", {}).get("numeric_result"),
        "parsed_numeric_result": conclusion.get("parsed_numeric_result"),
        "correctness": conclusion.get("conclusion_correctness", 0),
        **{field: communication.get(field) for field in (
            "required_key_recall", "required_key_precision",
            "duplicate_key_queries", "distractor_key_queries", "distractor_key_query_rate",
            "efficiency", "turns_to_finalize",
            "total_role_agent_queries", "total_questions",
            "incomplete_omission_triggered", "incomplete_omission_turn", "incomplete_followup_sent", "incomplete_followup_turn",
            "incomplete_threshold_returned", "incomplete_recovery_status", "incomplete_recovery_turn", "incomplete_recovery_latency",
            "finalized_before_incomplete_recovery", "incomplete_recovery_success",
            "finalize_ideal_round", "max_turns", "wait_turns",
            "delivered_reply_count", "pending_reply_count",
            "empty_observation_count", "neglect_ignored_count", "neglect_busy_count", "neglect_delivered_count", "neglect_refused_count", "neglect_pending_count",
            "mismatch_key_queried", "recovery_query_sent", "target_key_returned",
    "error_fact_returned", "error_recovery_status", "error_recovery_unknown",
            "mismatch_key_turn", "recovery_query_turn", "recovery_turn",
            "recovery_latency", "finalized_before_recovery", "recovery_success", "recovery_method", "recovery_metrics_version",
        )},
    }


def _mean(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [row[field] for row in rows if isinstance(row.get(field), (int, float)) and not isinstance(row.get(field), bool)]
    return sum(values) / len(values) if values else None


def write_outputs(output: Path, rows: list[dict[str, Any]]) -> None:
    summaries = []
    for task in TASKS:
        selected = [row for row in rows if row["task"] == task.name]
        summary = {"task": task.name, "row_type": "TASK_MEAN", "run": "", "status": "summary"}
        for field in CSV_FIELDS:
            value = _mean(selected, field)
            if value is not None:
                summary[field] = value
        summaries.append(summary)
    all_rows = rows + summaries
    with (output / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
    core_fields = ["task", "row_type", "main_agent_llm", "correctness", "required_key_recall", "required_key_precision", "efficiency"]
    with (output / "metrics_core.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=core_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)
    (output / "metrics.json").write_text(
        json.dumps({"runs": rows, "summaries": summaries}, ensure_ascii=False, indent=2) + "\\n",
        encoding="utf-8",
    )


def run_model(model: str, modules: dict[str, Any]) -> Path:
    global DYNAMIC_API_TRACE_DIR
    started = datetime.now()
    label = model.replace("/", "_")
    output = create_timestamped_run_dir(OUTPUT_ROOT, f"run_{label}", started)
    DYNAMIC_API_TRACE_DIR = output / "api_traces"
    transcripts = output / "transcripts"
    transcripts.mkdir(parents=True, exist_ok=True)
    jobs = [(task, index) for task in TASKS for index in range(1, REPEAT_TIMES + 1)]
    records: dict[tuple[str, int], dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max(1, CONCURRENCY)) as executor:
        futures = {
            executor.submit(run_one_retry, modules[task.name], task, model, f"{label}:{task.name}:run{index}"): (task, index)
            for task, index in jobs
        }
        for future in as_completed(futures):
            task, index = futures[future]
            try:
                records[(task.name, index)] = {"status": "success", "value": future.result()}
            except Exception as error:
                records[(task.name, index)] = {"status": "failed", "error": repr(error), "trace": traceback.format_exc()}
    rows = []
    for task, index in jobs:
        record = records[(task.name, index)]
        row = {"task": task.name, "row_type": "RUN", "main_agent_llm": model, "role_agent_llm": ROLE_AGENT_MODEL_NAME, "run": index, "status": record["status"]}
        transcript_path = transcripts / f"{label}_{task.name}_run{index}.json"
        if record["status"] == "success":
            result, usage = record["value"]
            row.update(extract_metrics(result))
            row.update({f"tok_{key}": value for key, value in usage.items()})
            transcript_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
        else:
            row["correctness"] = 0
            row["error"] = record["error"]
            transcript_path.with_name(transcript_path.stem + "_ERROR.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8"
            )
        rows.append(row)
    write_outputs(output, rows)
    print(f"wrote {output}", flush=True)
    return output


def main() -> None:
    modules = {task.name: load_module(task) for task in TASKS}
    for model in MAIN_AGENT_MODELS:
        run_model(model, modules)


if __name__ == "__main__":
    main()
'''
    return source.replace("__TASK_ID_LITERAL__", repr(task_id))


def _error_analysis_source() -> str:
    return '''from __future__ import annotations
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent

def resolve_run_dir() -> Path:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1]).expanduser().resolve()
        if not path.is_dir(): raise SystemExit(f"运行目录不存在：{path}")
        return path
    candidates = sorted((ROOT / "logs").glob("run_*"), key=lambda item: item.stat().st_mtime)
    if not candidates: raise SystemExit("尚无运行日志，请先执行 tasks/run.py")
    return candidates[-1]

def main():
    run_dir = resolve_run_dir()
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.is_file(): raise SystemExit(f"缺少指标文件：{metrics_path}")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    transcripts = sorted((run_dir / "transcripts").glob("*.json"))
    failed = [path.name for path in transcripts if path.name.endswith("_ERROR.json")]
    print(json.dumps({
        "run_dir": str(run_dir),
        "summaries": metrics.get("summaries", []),
        "transcript_count": len(transcripts),
        "failed_transcripts": failed,
    }, ensure_ascii=False, indent=2))
if __name__ == "__main__": main()
'''


def materialize_task(
    task: dict[str, Any], rendered: dict[str, Any], *,
    output_root: Path = DEFAULT_OUTPUT_ROOT, overwrite: bool = False,
    runtime_version: str = "legacy",
) -> Path:
    if runtime_version != "legacy":
        raise ValueError("v7 direct tasks do not support legacy controlled extensions")
    from task_types import validate_task_graph
    validate_task_graph(task)
    if task.get('setting') in {'misaligned', 'mixed'}:
        from error_recovery_runtime import build_error_recovery_profile, validate_error_recovery_profile
        validate_error_recovery_profile(build_error_recovery_profile(task))
    records = {record['record_id']: record for record in task['records']}
    for role in rendered['roles']:
        for record in role['records']:
            validate_record_context(task, records[record['record_id']], record['text'])
    task_dir = Path(output_root) / task["task_id"]
    if task_dir.exists():
        if not overwrite:
            raise FileExistsError(f"generated task exists: {task_dir}")
    role_dir, tasks_dir, internal_dir = task_dir / "role_agents", task_dir / "tasks", task_dir / "internal"
    for directory in (role_dir, tasks_dir, internal_dir):
        directory.mkdir(parents=True, exist_ok=True)
    expected_role_files = {f"{role['role_id']}.json" for role in task["roles"]}
    for path in role_dir.glob("*.json"):
        if path.name not in expected_role_files:
            path.unlink()
    rendered_by_id = {item["role_id"]: item for item in rendered["roles"]}
    role_configs: dict[str, dict[str, Any]] = {}
    for role in task["roles"]:
        source = rendered_by_id[role["role_id"]]
        information_points = _materialized_information_points(task, role, source)
        config = {
            "role_agent_name": role["name"],
            "abstract": role["responsibility"],
            "system_message": _role_system_message(role, source["system_context"]),
            "information_points": information_points,

        }
        role_configs[role["role_id"]] = config
        _write_json(role_dir / f"{role['role_id']}.json", config)
    source = _run_one_source(task, rendered, role_configs)
    (tasks_dir / "run_one.py").write_text(source, encoding="utf-8")
    (tasks_dir / "run.py").write_text(
        _run_source(task["task_id"]),
        encoding="utf-8",
    )
    (task_dir / "requirements.txt").write_text("openai>=1.0\n", encoding="utf-8")
    (task_dir / "error_analysis.py").write_text(_error_analysis_source(), encoding="utf-8")
    _write_json(task_dir / "validation_report.json", task["validation"])
    _write_json(internal_dir / "task_graph.json", task)
    _write_json(internal_dir / "rendered_task.json", rendered)
    for path in (tasks_dir / "run_one.py", tasks_dir / "run.py", task_dir / "error_analysis.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    return task_dir
