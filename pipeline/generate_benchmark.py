from __future__ import annotations

import argparse
import inspect
import json
import math
import sys
import os
import tempfile
import threading
import time
import fcntl
from functools import wraps
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from compile_task import compile_task
from error_pair import derive_error_task, prepare_reliable_pair
from generate_error_spec import generate_error_spec
from generate_ontology import generate_ontology
from materialize_task import materialize_task
from pipeline_llm import build_json_caller, load_project_env
from llm_runtime import is_non_retryable_error
from generation_costs import trace_call_ids, summarize_costs
from qualify_full_information import (
    GRADER_VERSION,
    qualify_full_information,
    regrade_full_information_report,
)
from render_task import render_task, reroute_rendered_task
from task_types import TASK_SCHEMA_VERSION
from scenario_history import recent_task_summaries
from scenario_catalog import SAMPLING_VERSION, select_scenario, scenario_counts
from communication_setting import derive_neglect_task
from mixed_setting import select_interventions, derive_mixed_task
from runtime_settings import SETTINGS
from incomplete_setting import (
    INCOMPLETE_DISCLOSURE_LABELS, derive_incomplete_task, incomplete_candidates,
    incomplete_mode_for_task, validate_incomplete_ontology,
)


TASK_COUNT = 1
# Groups run in parallel; stages within each group remain sequential.
GENERATION_WORKERS = 20
# Positive tasks use ceil(count * ratio); the remaining tasks are negative.
POSITIVE_RATIO = 1
START_TASK_NUMBER = 1
GLOBAL_SEED = 2026
GENERATION_MODEL = "google/gemini-3.8-flash"
ONTOLOGY_MODEL = GENERATION_MODEL
ERROR_SPEC_MODEL = ONTOLOGY_MODEL
RENDER_MODEL = GENERATION_MODEL
FULL_INFORMATION_MODEL = "deepseek/deepseek-v4.1-flash"
FULL_INFORMATION_RUNS = 3
MAX_CANDIDATES_PER_TASK = 3
MAX_LLM_ATTEMPTS = 3

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = HERE.parent / "outputs" / "generated"
STAGES = (
    "ontology", "compile", "error_spec", "prepare_reliable_pair", "render",
    "full_information", "derive_error", "derive_neglect", "derive_incomplete", "derive_mixed", "materialize", "accepted",
)


class IncompatibleIncompleteBaselineError(RuntimeError):
    """An existing baseline cannot be augmented without changing its task content."""


class RecoverableGenerationError(RuntimeError):
    """An execution failure that can be retried from the saved candidate stage."""


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        try:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"checkpoint artifact must be a JSON object: {path}")
    return value


def _attempt_number(path: Path) -> int:
    try:
        return int(path.name.rsplit("_", 1)[1])
    except (IndexError, ValueError) as error:
        raise ValueError(f"invalid candidate directory name: {path.name}") from error


def _valid_full_information_report(path: Path) -> bool:
    if not path.is_file():
        return False
    report = _read_json(path)
    # Cached responses must satisfy the current answer-label contract.
    # Recheck acceptance when the saved report used an older grader.
    graph_paths = [path.parent / "reliable_task_graph.json", path.parent / "task_graph.json"]
    for graph_path in graph_paths:
        if graph_path.is_file():
            task = _read_json(graph_path)
            if task.get("language") == "en":
                report = regrade_full_information_report(task, report, required_runs=FULL_INFORMATION_RUNS)
            break
    return bool(
        report.get("accepted") is True
        and report.get("task_schema_version") == TASK_SCHEMA_VERSION
        and report.get("runs") == FULL_INFORMATION_RUNS
        and report.get("required_correct") == FULL_INFORMATION_RUNS
        and report.get("correct_runs") == FULL_INFORMATION_RUNS
        and isinstance(report.get("results"), list)
        and len(report["results"]) == FULL_INFORMATION_RUNS
    )


def _pair_artifacts_complete(output_root: Path, task_id: str) -> bool:
    reliable_dir = output_root / "generated_tasks" / "reliable" / task_id
    error_dir = output_root / "generated_tasks" / "misaligned" / task_id
    neglect_dir = output_root / "generated_tasks" / "missed" / task_id
    reliable_graph_path = reliable_dir / "internal" / "task_graph.json"
    error_graph_path = error_dir / "internal" / "task_graph.json"
    derivation_path = error_dir / "internal" / "error_derivation_report.json"
    incomplete_dir = output_root / "generated_tasks" / "incomplete" / task_id
    mixed_dir = output_root / "generated_tasks" / "mixed" / task_id
    setting_dirs = (reliable_dir, error_dir, neglect_dir, incomplete_dir, mixed_dir)
    required_files = (
        reliable_graph_path,
        error_graph_path,
        derivation_path,
        neglect_dir / "internal" / "task_graph.json",
        neglect_dir / "internal" / "neglect_derivation_report.json",
        incomplete_dir / "internal" / "task_graph.json",
        incomplete_dir / "internal" / "incomplete_derivation_report.json",
        mixed_dir / "internal" / "task_graph.json",
        mixed_dir / "internal" / "mixed_derivation_report.json",
        *[directory / relative_path for directory in setting_dirs for relative_path in (
            "tasks/run_one.py", "tasks/run.py", "internal/rendered_task.json",
            "validation_report.json", "requirements.txt", "error_analysis.py",
        )],
    )
    if not all(path.is_file() for path in required_files):
        return False
    try:
        reliable_graph = _read_json(reliable_graph_path)
        error_graph = _read_json(error_graph_path)
        derivation = _read_json(derivation_path)
        neglect = _read_json(neglect_dir / "internal" / "task_graph.json")
        neglect_report = _read_json(neglect_dir / "internal" / "neglect_derivation_report.json")
        incomplete = _read_json(incomplete_dir / "internal" / "task_graph.json")
        incomplete_report = _read_json(incomplete_dir / "internal" / "incomplete_derivation_report.json")
        mixed = _read_json(mixed_dir / 'internal' / 'task_graph.json')
        mixed_report = _read_json(mixed_dir / 'internal' / 'mixed_derivation_report.json')
        from task_types import validate_task_graph
        for graph in (reliable_graph, error_graph, incomplete, neglect, mixed):
            validate_task_graph(graph)
        return bool(
            mixed.get('setting') == 'mixed'
            and mixed.get('gold') == reliable_graph.get('gold')
            and mixed.get('incomplete_profile') == incomplete.get('incomplete_profile')
            and mixed.get('neglect_profile') == neglect.get('neglect_profile')
            and mixed.get('error_pair') == error_graph.get('error_pair')
            and mixed_report.get('gold_unchanged') is True
            and all(g.get('intervention_plan') == reliable_graph.get('intervention_plan') and g.get('intervention_plan')
                    for g in (error_graph, incomplete, neglect, mixed))
            and all(g.get(field) == reliable_graph.get(field)
                    for g in (error_graph, incomplete, neglect, mixed)
                    for field in ('roles', 'candidates', 'topics', 'constraints', 'predicates',
                                  'records', 'observations', 'numeric_rule', 'gold', 'error_pair'))
            and reliable_graph.get("schema_version") == TASK_SCHEMA_VERSION
            and reliable_graph.get("setting") == "reliable"
            and error_graph.get("schema_version") == TASK_SCHEMA_VERSION
            and error_graph.get("setting") == "misaligned"
            and _valid_full_information_report(
                reliable_dir / "internal" / "full_information_report.json"
            )
            and neglect.get("schema_version") == TASK_SCHEMA_VERSION
            and neglect.get("setting") == "missed"
            and neglect.get("gold") == reliable_graph.get("gold")
            and incomplete.get("schema_version") == TASK_SCHEMA_VERSION
            and incomplete.get("setting") == "incomplete"
            and incomplete.get("gold") == reliable_graph.get("gold")
            and incomplete_report.get("gold_unchanged") is True
            and incomplete_report.get("reliable_full_information", {}).get("accepted") is True
            and neglect_report.get("gold_unchanged") is True
            and neglect_report.get("reliable_full_information", {}).get("accepted") is True
            and all((directory / "role_agents" / f"{role['role_id']}.json").is_file()
                    for directory in setting_dirs for role in reliable_graph["roles"])
            and derivation.get("gold_unchanged") is True
            and derivation.get("reliable_full_information", {}).get("accepted") is True
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _materialize_variant(task: dict[str, Any], rendered: dict[str, Any], *, output_root: Path) -> Path:
    """Backfill a missing setting without rewriting complete sibling runtimes."""
    directory = output_root / task["task_id"]
    required = [directory / relative for relative in (
        "tasks/run_one.py", "tasks/run.py", "internal/task_graph.json", "internal/rendered_task.json",
        "validation_report.json", "requirements.txt", "error_analysis.py",
    )]
    required.extend(directory / "role_agents" / f"{role['role_id']}.json" for role in task["roles"])
    if all(path.is_file() for path in required):
        try:
            if (_read_json(directory / "internal" / "task_graph.json") == task
                    and _read_json(directory / "internal" / "rendered_task.json") == rendered):
                return directory
        except (OSError, ValueError):
            pass
    return materialize_task(task, rendered, output_root=output_root, overwrite=True)


def _infer_stage(candidate_dir: Path, output_root: Path, task_id: str) -> str:
    if not (candidate_dir / "ontology.json").is_file():
        return "ontology"
    if not (candidate_dir / "task_graph.json").is_file():
        return "compile"
    if not (candidate_dir / "error_spec.json").is_file():
        return "error_spec"
    if not (candidate_dir / "reliable_task_graph.json").is_file():
        return "prepare_reliable_pair"
    if not (candidate_dir / "reliable_rendered_task.json").is_file():
        return "render"
    if not _valid_full_information_report(candidate_dir / "full_information_report.json"):
        return "full_information"
    if not (candidate_dir / "error_task_graph.json").is_file():
        return "derive_error"
    if not all((candidate_dir / name).is_file() for name in ("neglect_task_graph.json", "neglect_derivation_report.json")):
        return "derive_neglect"
    if not all((candidate_dir / name).is_file() for name in ("incomplete_task_graph.json", "incomplete_derivation_report.json")):
        return "derive_incomplete"
    if not all((candidate_dir / name).is_file() for name in ('mixed_task_graph.json', 'mixed_derivation_report.json')):
        return 'derive_mixed'
    if not _pair_artifacts_complete(output_root, task_id):
        return "materialize"
    return "accepted"


def _maybe_regrade_full_information_checkpoint(
    state: dict[str, Any], candidate_dir: Path,
) -> dict[str, Any]:
    """Upgrade old false-negative Full Information reports without another API call."""
    if state.get("stage") != "full_information" or state.get("status") != "rejected":
        return state
    task_path = candidate_dir / "reliable_task_graph.json"
    report_path = candidate_dir / "full_information_report.json"
    if not task_path.is_file() or not report_path.is_file():
        return state
    report = _read_json(report_path)
    if report.get("task_schema_version") != TASK_SCHEMA_VERSION:
        state.update({"stage": "full_information", "status": "in_progress", "error": None})
        return state
    if report.get("grader_version") == GRADER_VERSION:
        return state
    task = _read_json(task_path)
    report = regrade_full_information_report(
        task, report, required_runs=FULL_INFORMATION_RUNS,
    )
    _write_json(report_path, report)
    if report["accepted"]:
        state.update({"stage": "derive_error", "status": "in_progress", "error": None})
    return state


def _load_candidate_states(output_root: Path, *, seed: int) -> list[dict[str, Any]]:
    states = []
    for candidate_dir in sorted((output_root / "candidates").glob("attempt_*")):
        if not candidate_dir.is_dir():
            continue
        checkpoint_path = candidate_dir / "checkpoint.json"
        if checkpoint_path.is_file():
            state = _read_json(checkpoint_path)
            state = _maybe_regrade_full_information_checkpoint(state, candidate_dir)
            if state.get("status") == "accepted":
                inferred = _infer_stage(
                    candidate_dir, output_root, str(state.get("task_id") or "task_001"),
                )
                if inferred != "accepted":
                    state.update({"stage": inferred, "status": "in_progress", "error": None})
            if (state.get("stage") in {"derive_neglect", "derive_incomplete", "derive_mixed", "materialize"}
                    and state.get("status") in {"in_progress", "recoverable_error"}):
                inferred = _infer_stage(candidate_dir, output_root, str(state.get("task_id") or "task_001"))
                state.update({"stage": inferred,
                              "status": "accepted" if inferred == "accepted" else "in_progress",
                              "error": None})
            _write_json(checkpoint_path, state)
            state["candidate_dir"] = candidate_dir
            states.append(state)
            continue
        attempt = _attempt_number(candidate_dir)
        task_path = (
            candidate_dir / "reliable_task_graph.json"
            if (candidate_dir / "reliable_task_graph.json").is_file()
            else candidate_dir / "task_graph.json"
        )
        task = _read_json(task_path) if task_path.is_file() else {}
        task_id = str(task.get("task_id") or "task_001")
        stage = _infer_stage(candidate_dir, output_root, task_id)
        rejection_path = candidate_dir / "rejection_report.json"
        rejection = _read_json(rejection_path) if rejection_path.is_file() else None
        if stage == "accepted":
            status = "accepted"
        elif rejection and rejection.get("error_type") == "ValueError":
            status = "rejected"
        elif rejection:
            status = "recoverable_error"
        else:
            status = "in_progress"
        state = {
            "schema_version": TASK_SCHEMA_VERSION,
            "attempt": attempt,
            "seed": int(task.get("seed", seed + attempt - 1)),
            "task_id": task_id,
            "positive": task.get("scenario", {}).get("positive_label") == (task.get("gold") or {}).get("conclusion") if task else True,
            "stage": stage,
            "status": status,
            "error": rejection,
        }
        state = _maybe_regrade_full_information_checkpoint(state, candidate_dir)
        _write_json(checkpoint_path, {key: value for key, value in state.items() if key != "candidate_dir"})
        state["candidate_dir"] = candidate_dir
        states.append(state)
    return states


def _save_checkpoint(state: dict[str, Any]) -> None:
    candidate_dir = Path(state["candidate_dir"])
    serializable = {key: value for key, value in state.items() if key != "candidate_dir"}
    serializable["schema_version"] = TASK_SCHEMA_VERSION
    _write_json(candidate_dir / "checkpoint.json", serializable)


def _accepted_task_dirs(output_root: Path) -> list[Path]:
    root = output_root / "generated_tasks" / "reliable"
    accepted = []
    for path in sorted(root.glob("task_*")):
        if _pair_artifacts_complete(output_root, path.name):
            accepted.append(path)
    return accepted


def _next_task_number(output_root: Path) -> int:
    numbers = []
    for path in (output_root / "generated_tasks" / "reliable").glob("task_*"):
        try:
            numbers.append(int(path.name.rsplit("_", 1)[1]))
        except (IndexError, ValueError):
            continue
    return max(numbers, default=0) + 1


def _pair_summaries(output_root: Path, states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summaries = []
    for state in states:
        if state.get("status") != "accepted":
            continue
        candidate_dir = Path(state["candidate_dir"])
        graph_path = candidate_dir / "error_task_graph.json"
        if not graph_path.is_file():
            continue
        task = _read_json(graph_path)
        pair = task["error_pair"]
        neglect_profile = _read_json(candidate_dir / "neglect_task_graph.json")["neglect_profile"]
        incomplete_profile = _read_json(candidate_dir / "incomplete_task_graph.json")["incomplete_profile"]
        role = next(item for item in task["roles"] if item["role_id"] == pair["affected_role_id"])
        candidate = next(item for item in task["candidates"] if item["candidate_id"] == pair["affected_candidate_id"])
        summaries.append({
            "task_id": task["task_id"],
            "error_type": pair["error_type"],
            "routing_mode": pair.get("routing_mode"),
            "affected_role_id": role["role_id"],
            "affected_role_name": role["name"],
            "affected_candidate_id": candidate["candidate_id"],
            "affected_candidate_name": candidate["name"],
            "target_context": pair["target_context"],
            "alternate_context": pair["alternate_context"],
            "target_business_abbreviation": pair.get("target_business_abbreviation"),
            "alternate_business_abbreviation": pair.get("alternate_business_abbreviation"),
            "reliable_path": str(output_root / "generated_tasks" / "reliable" / task["task_id"]),
            "error_path": str(output_root / "generated_tasks" / "misaligned" / task["task_id"]),
            "neglect_path": str(output_root / "generated_tasks" / "missed" / task["task_id"]),
            "neglect_role_ids": neglect_profile["role_ids"],
            "mixed_path": str(output_root / "generated_tasks" / "mixed" / task["task_id"]),
            "intervention_plan": task["intervention_plan"],
            "incomplete_path": str(output_root / "generated_tasks" / "incomplete" / task["task_id"]),
            "incomplete_role_id": incomplete_profile["role_id"],
            "incomplete_key": incomplete_profile["key"],
            "incomplete_hidden_predicate_id": incomplete_profile["hidden_predicate_id"],
            "incomplete_disclosure_mode": incomplete_profile.get("disclosure_mode", "omission"),
        })
    return summaries


def _print_error_injection(task: dict[str, Any]) -> None:
    pair = task["error_pair"]
    role = next(item for item in task["roles"] if item["role_id"] == pair["affected_role_id"])
    candidate = next(item for item in task["candidates"] if item["candidate_id"] == pair["affected_candidate_id"])
    error_type_labels = {
        "temporal": "时间错配",
        "geographic": "同级地域错配",
        "measurement_basis": "统计口径错配",
        "aggregation_window": "聚合窗口错配",
        "environment_version": "环境/产品版本错配",
    }
    print(
        "\n".join([
            f"[{task['task_id']}] Misaligned注入完成：",
            f"Role Agent：{role['name']}",
            f"候选：{candidate['name']}",
            f"错误类型：{error_type_labels[pair['error_type']]}",
            f"任务目标：{pair['target_context']}",
            f"Coordinator实际提供：{pair['alternate_context']}",
            f"目标key：{pair['target_key']}",
            f"错配key：{pair['alternate_key']}",
        ]),
        flush=True,
    )


def _fresh_output_root(base: Path) -> Path:
    base = Path(base)
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("run_%Y%m%d_%H%M%S")
    candidate = base / stamp
    suffix = 1
    while candidate.exists():
        candidate = base / f"{stamp}_{suffix:02d}"
        suffix += 1
    candidate.mkdir()
    return candidate


def _exclusive_output(function):
    @wraps(function)
    def locked(**kwargs):
        root = Path(kwargs["output_root"])
        root.mkdir(parents=True, exist_ok=True)
        with (root / ".generation.lock").open("a") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("another generator is using this output directory") from error
            try:
                return function(**kwargs)
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
    return locked


@_exclusive_output
def generate_tasks(
    *, count: int, seed: int, candidate_budget: int, output_root: Path,
    ontology_factory: Callable[..., dict[str, Any]],
    renderer: Callable[[dict[str, Any]], dict[str, Any]],
    full_answer: Callable[[dict[str, Any]], Callable[[str], dict[str, Any]]],
    error_spec_factory: Callable[[dict[str, Any], int], dict[str, Any]],
    qualification_model: str,
    positive_ratio: float = POSITIVE_RATIO,
    start_task_number: int = START_TASK_NUMBER,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    workers: int = 1,
) -> list[Path]:
    if type(workers) is not int or workers < 1:
        raise ValueError("workers must be a positive integer")
    if candidate_budget < 0:
        raise ValueError("candidate_budget must be nonnegative")
    if count < 1:
        raise ValueError("count must be at least one")
    if not 0 <= positive_ratio <= 1:
        raise ValueError("positive_ratio must be between 0 and 1")
    if start_task_number < 1:
        raise ValueError("start_task_number must be at least one")
    output_root = Path(output_root)
    if getattr(ontology_factory, "expected_language", None) == "en":
        from language_contract import validate_english_output_root
        validate_english_output_root(output_root)
    for path in [*(output_root / "candidates").glob("attempt_*/*task_graph.json"),
                 *(output_root / "generated_tasks").glob("*/task_*/internal/task_graph.json")]:
        if _read_json(path).get("schema_version") != TASK_SCHEMA_VERSION:
            raise ValueError(f"旧任务与v8 schema不兼容，请使用空输出目录或--fresh：{path}")
    for path in (output_root / "candidates").glob("attempt_*/checkpoint.json"):
        if _read_json(path).get("schema_version") != TASK_SCHEMA_VERSION:
            raise ValueError(f"旧检查点与v8不兼容，请使用空输出目录或--fresh：{path}")
    positive_target = math.ceil(count * positive_ratio)
    labels = [True] * positive_target + [False] * (count - positive_target)
    states = _load_candidate_states(output_root, seed=seed)
    accepted = _accepted_task_dirs(output_root)
    # Resuming must preserve the original positive/negative assignment.
    existing_by_id = {
        path.name: _read_json(path / "internal" / "task_graph.json")["gold"]["numeric_result"] is not None
        for path in accepted
    }
    pending = [state for state in states if state.get("status") in {"in_progress", "recoverable_error"}]
    for state in pending:
        existing_by_id[state["task_id"]] = bool(state["positive"])
    first_number = min([start_task_number] + [int(k.rsplit("_", 1)[1]) for k in existing_by_id])
    # Resume reserved task IDs, including gaps from out-of-order completion.
    task_ids = [f"task_{first_number + i:03d}" for i in range(count)]
    label_by_id = dict(zip(task_ids, labels))
    if any(k in label_by_id and value != label_by_id[k] for k, value in existing_by_id.items()):
        raise ValueError(
            "existing tasks/checkpoints conflict with positive_ratio; "
            "use --fresh or a new --output-root to generate the requested ratio"
        )
    if len({state["task_id"] for state in pending}) != len(pending):
        raise ValueError("multiple pending candidates reserve the same task_id")
    output_root.mkdir(parents=True, exist_ok=True)
    max_attempt = max((int(state["attempt"]) for state in states), default=0)
    new_attempts = 0
    last_progress = None
    events = Queue()
    owner_thread = threading.get_ident()
    stopping = getattr(ontology_factory, "cancel_event", None)
    if not isinstance(stopping, threading.Event):
        stopping = threading.Event()
    running = {}

    def report_progress(state: dict[str, Any] | None = None, *, status: str = "in_progress") -> None:
        nonlocal last_progress
        if threading.get_ident() != owner_thread:
            events.put((dict(state) if state else None, status))
            return
        if progress_callback is None:
            return
        event = {
            "completed": min(len(accepted), count), "total": count,
            "running": len(running), "workers": workers,
            "task_id": state.get("task_id") if state else None,
            "attempt": state.get("attempt") if state else None,
            "stage": state.get("stage") if state else None,
            "status": status,
        }
        if event != last_progress:
            progress_callback(event)
            last_progress = event

    report_progress(status="resuming" if states else "starting")

    def write_manifest(*, run_status: str) -> None:
        current_states = [dict(state) for state in states]
        # Only the coordinator may commit completed groups to the manifest.
        accepted_ids = {path.name for path in accepted}
        for snapshot in current_states:
            if snapshot.get("status") == "accepted" and snapshot["task_id"] not in accepted_ids:
                snapshot["status"] = "in_progress"
        pairs = _pair_summaries(output_root, current_states)
        rejected = [state.get("error") for state in current_states if state.get("status") == "rejected" and state.get("error")]
        recoverable = [state.get("error") for state in current_states if state.get("status") in {"in_progress", "recoverable_error"} and state.get("error")]
        _write_json(output_root / "manifest.json", {
            "settings": list(SETTINGS),
            "requested_count": count,
            "accepted_count": len(accepted),
            "workers": workers,
            "accepted_pair_count": len(pairs),
            "rejected_count": len(rejected),
            "recoverable_count": len(recoverable),
            "candidate_budget_this_run": candidate_budget,
            "new_attempts_this_run": new_attempts,
            "seed": seed,
            "positive_ratio": positive_ratio,
            "start_task_number": start_task_number,
            "positive_target": positive_target,
            "negative_target": count - positive_target,
            "qualification_model": qualification_model,
            "full_information_runs": FULL_INFORMATION_RUNS,
            "run_status": run_status,
            "accepted_tasks": [path.name for path in accepted],
            "pairs": pairs,
            "scenario_counts": scenario_counts(current_states),
            "rejections": rejected,
            "recoverable_errors": recoverable,
        })

    def advance(state: dict[str, Any], stage: str) -> None:
        state.update({"stage": stage, "status": "in_progress", "error": None})
        _save_checkpoint(state)
        report_progress(state)

    def run_candidate(state: dict[str, Any]) -> Path | None:
        candidate_dir = Path(state["candidate_dir"])
        while state["stage"] != "accepted":
            if stopping.is_set():
                state["status"] = "recoverable_error"
                _save_checkpoint(state)
                return None
            stage = str(state["stage"])
            advance(state, stage)
            try:
                if stage == "ontology":
                    ontology_path = candidate_dir / "ontology.json"
                    if ontology_path.is_file():
                        # Reuse saved output if a crash occurred before the checkpoint advanced.
                        ontology = _read_json(ontology_path)
                    else:
                        if state.get("scenario_selection", {}).get("version") != SAMPLING_VERSION:
                            state["scenario_selection"] = select_scenario(int(state["task_id"].rsplit("_", 1)[1]))
                            _save_checkpoint(state)
                        # Pass optional metadata only when the factory accepts it.
                        parameters = inspect.signature(ontology_factory).parameters
                        options = {key: state[key] for key in
                                   ("scenario_selection", "task_id", "generation_context")
                                   if key in parameters and key in state}
                        ontology = ontology_factory(int(state["seed"]), **options)
                    validate_incomplete_ontology(ontology, required=True)
                    if not ontology_path.is_file():
                        _write_json(ontology_path, ontology)
                    advance(state, "compile")
                elif stage == "compile":
                    ontology = _read_json(candidate_dir / "ontology.json")
                    task = compile_task(
                        ontology, task_id=str(state["task_id"]), seed=int(state["seed"]),
                        positive=bool(state["positive"]),
                    )
                    if not incomplete_candidates(task):
                        raise ValueError("compiled task must contain a pivotal bool=true + threshold record")
                    task = select_interventions(task)
                    _write_json(candidate_dir / "task_graph.json", task)
                    _write_json(candidate_dir / "p1_report.json", task["validation"]["p1"])
                    _write_json(candidate_dir / "p3_report.json", task["validation"]["p3"])
                    advance(state, "error_spec")
                elif stage == "error_spec":
                    task = _read_json(candidate_dir / "task_graph.json")
                    spec = error_spec_factory(task, int(state["seed"]))
                    _write_json(candidate_dir / "error_spec.json", spec)
                    advance(state, "prepare_reliable_pair")
                elif stage == "prepare_reliable_pair":
                    task = _read_json(candidate_dir / "task_graph.json")
                    spec = _read_json(candidate_dir / "error_spec.json")
                    reliable = prepare_reliable_pair(task, spec, seed=int(state["seed"]))
                    _write_json(candidate_dir / "reliable_task_graph.json", reliable)
                    advance(state, "render")
                elif stage == "render":
                    task = _read_json(candidate_dir / "reliable_task_graph.json")
                    rendered = render_task(task, renderer)
                    _write_json(candidate_dir / "reliable_rendered_task.json", rendered)
                    advance(state, "full_information")
                elif stage == "full_information":
                    task = _read_json(candidate_dir / "reliable_task_graph.json")
                    rendered = _read_json(candidate_dir / "reliable_rendered_task.json")
                    qualification = qualify_full_information(
                        task, rendered, full_answer(task), model=qualification_model,
                        runs=FULL_INFORMATION_RUNS,
                    )
                    _write_json(candidate_dir / "full_information_report.json", qualification)
                    if not qualification["accepted"]:
                        raise ValueError("Full Information qualification failed")
                    advance(state, "derive_error")
                elif stage == "derive_error":
                    reliable = _read_json(candidate_dir / "reliable_task_graph.json")
                    rendered_reliable = _read_json(candidate_dir / "reliable_rendered_task.json")
                    error_task = derive_error_task(reliable)
                    rendered_error = reroute_rendered_task(error_task, rendered_reliable)
                    qualification = _read_json(candidate_dir / "full_information_report.json")
                    reliable_report_path = (
                        f"../../../reliable/{error_task['task_id']}/internal/"
                        "full_information_report.json"
                    )
                    _write_json(candidate_dir / "error_task_graph.json", error_task)
                    _write_json(candidate_dir / "error_rendered_task.json", rendered_error)
                    _write_json(candidate_dir / "error_derivation_report.json", {
                        "task_id": error_task["task_id"],
                        "gold_unchanged": error_task["gold"] == reliable["gold"],
                        "reliable_full_information": {
                            "report_path": reliable_report_path,
                            "accepted": qualification.get("accepted"),
                            "grader_version": qualification.get("grader_version"),
                            "runs": qualification.get("runs"),
                        },
                        **error_task["error_pair"],
                    })
                    advance(state, "derive_neglect")
                elif stage in {"derive_neglect"}:
                    setting = stage.removeprefix("derive_")
                    reliable = _read_json(candidate_dir / "reliable_task_graph.json")
                    variant = (derive_neglect_task)(reliable)
                    qualification = _read_json(candidate_dir / "full_information_report.json")
                    _write_json(candidate_dir / f"{setting}_task_graph.json", variant)
                    _write_json(candidate_dir / f"{setting}_derivation_report.json", {
                        "task_id": variant["task_id"],
                        "gold_unchanged": variant["gold"] == reliable["gold"],
                        "reliable_full_information": {
                            "report_path": f"../../../reliable/{variant['task_id']}/internal/full_information_report.json",
                            "accepted": qualification.get("accepted"),
                            "grader_version": qualification.get("grader_version"),
                            "runs": qualification.get("runs"),
                        },
                        **variant[setting + "_profile"],
                    })
                    advance(state, "derive_incomplete")
                elif stage == "derive_incomplete":
                    reliable = _read_json(candidate_dir / "reliable_task_graph.json")
                    if not incomplete_candidates(reliable):
                        raise IncompatibleIncompleteBaselineError(
                            "Existing Reliable lacks a pivotal bool+threshold condition. "
                            "Its baseline is preserved; use --fresh to generate comparable five-setting tasks."
                        )
                    incomplete = derive_incomplete_task(reliable, disclosure_mode=incomplete_mode_for_task(reliable['task_id']))
                    qualification = _read_json(candidate_dir / "full_information_report.json")
                    _write_json(candidate_dir / "incomplete_task_graph.json", incomplete)
                    _write_json(candidate_dir / "incomplete_derivation_report.json", {
                        "task_id": incomplete["task_id"], "gold_unchanged": incomplete["gold"] == reliable["gold"],
                        "reliable_full_information": {
                            "report_path": f"../../../reliable/{incomplete['task_id']}/internal/full_information_report.json",
                            "accepted": qualification.get("accepted"), "runs": qualification.get("runs"),
                            "grader_version": qualification.get("grader_version"),
                        },
                        **incomplete["incomplete_profile"],
                    })
                    advance(state, "derive_mixed")
                elif stage == "derive_mixed":
                    reliable = _read_json(candidate_dir / "reliable_task_graph.json")
                    mixed = derive_mixed_task(reliable, disclosure_mode=incomplete_mode_for_task(reliable['task_id']))
                    _write_json(candidate_dir / 'mixed_task_graph.json', mixed)
                    _write_json(candidate_dir / 'mixed_derivation_report.json', {
                        'task_id': mixed['task_id'], 'gold_unchanged': mixed['gold'] == reliable['gold'],
                        'intervention_plan': mixed['intervention_plan'],
                        'error_pair': mixed['error_pair'], 'incomplete_profile': mixed['incomplete_profile'],
                        'neglect_profile': mixed['neglect_profile'],
                    })
                    advance(state, "materialize")
                elif stage == "materialize":
                    reliable = _read_json(candidate_dir / "reliable_task_graph.json")
                    rendered_reliable = _read_json(candidate_dir / "reliable_rendered_task.json")
                    error_task = _read_json(candidate_dir / "error_task_graph.json")
                    rendered_error = _read_json(candidate_dir / "error_rendered_task.json")
                    qualification = _read_json(candidate_dir / "full_information_report.json")
                    reliable_dir = _materialize_variant(
                        reliable, rendered_reliable,
                        output_root=output_root / "generated_tasks" / "reliable",
                    )
                    error_dir = _materialize_variant(
                        error_task, rendered_error,
                        output_root=output_root / "generated_tasks" / "misaligned",
                    )
                    _write_json(reliable_dir / "internal" / "full_information_report.json", qualification)
                    derivation = _read_json(candidate_dir / "error_derivation_report.json")
                    _write_json(error_dir / "internal" / "error_derivation_report.json", derivation)
                    neglect = _read_json(candidate_dir / "neglect_task_graph.json")
                    neglect_dir = _materialize_variant(
                        neglect, rendered_reliable,
                        output_root=output_root / "generated_tasks" / "missed",
                    )
                    _write_json(neglect_dir / "internal" / "neglect_derivation_report.json",
                                _read_json(candidate_dir / "neglect_derivation_report.json"))
                    incomplete = _read_json(candidate_dir / "incomplete_task_graph.json")
                    incomplete_dir = _materialize_variant(
                        incomplete, rendered_reliable,
                        output_root=output_root / "generated_tasks" / "incomplete",
                    )
                    _write_json(incomplete_dir / "internal" / "incomplete_derivation_report.json",
                                _read_json(candidate_dir / "incomplete_derivation_report.json"))
                    mixed = _read_json(candidate_dir / 'mixed_task_graph.json')
                    mixed_dir = _materialize_variant(mixed, rendered_error,
                        output_root=output_root / 'generated_tasks' / 'mixed')
                    _write_json(mixed_dir / 'internal' / 'mixed_derivation_report.json',
                                _read_json(candidate_dir / 'mixed_derivation_report.json'))
                    if not _pair_artifacts_complete(output_root, str(state["task_id"])):
                        raise RuntimeError("Reliable/Error/Incomplete/Missed/Mixed artifacts are incomplete")
                    state.update({"stage": "accepted", "status": "accepted", "error": None})
                    _save_checkpoint(state)
                    return reliable_dir
                else:
                    raise RuntimeError(f"unknown checkpoint stage: {stage}")
            except KeyboardInterrupt:
                error = {"attempt": state["attempt"], "seed": state["seed"], "stage": stage, "error_type": "KeyboardInterrupt", "message": "generation interrupted"}
                state.update({"stage": stage, "status": "recoverable_error", "error": error})
                _save_checkpoint(state)
                report_progress(state, status="interrupted")
                raise
            except ValueError as error:
                rejection = {"attempt": state["attempt"], "seed": state["seed"], "stage": stage, "error_type": type(error).__name__, "message": str(error), "category": "quality_rejection"}
                state.update({"stage": stage, "status": "rejected", "error": rejection})
                _save_checkpoint(state)
                _write_json(candidate_dir / "rejection_report.json", rejection)
                report_progress(state, status="rejected")
                return None
            except Exception as error:
                recoverable = {"attempt": state["attempt"], "seed": state["seed"], "stage": stage, "error_type": type(error).__name__, "message": str(error), "category": "recoverable_execution_error"}
                state.update({"stage": stage, "status": "recoverable_error", "error": recoverable})
                _save_checkpoint(state)
                _write_json(candidate_dir / "recoverable_error_report.json", recoverable)
                report_progress(state, status="recoverable_error")
                message = (
                    str(error) if isinstance(error, IncompatibleIncompleteBaselineError)
                    else f"attempt {state['attempt']} stopped at {stage}; rerun the same command to resume"
                )
                raise RecoverableGenerationError(message) from error
        task_dir = output_root / "generated_tasks" / "reliable" / str(state["task_id"])
        return task_dir if _pair_artifacts_complete(output_root, str(state["task_id"])) else None

    if len(accepted) >= count:
        write_manifest(run_status="complete")
        report_progress(status="complete")
        return accepted[:count]

    resumable = {state["task_id"]: state for state in states
                 if state.get("status") in {"in_progress", "recoverable_error"}}
    completed_ids = {path.name for path in accepted}
    blocked_ids = set()
    failures = []

    def drain_events():
        while True:
            try:
                state, status = events.get_nowait()
            except Empty:
                break
            report_progress(state, status=status)

    def submit(executor, task_id):
        nonlocal new_attempts, max_attempt
        state = resumable.pop(task_id, None)
        if state is None:
            if new_attempts >= candidate_budget:
                return False
            new_attempts += 1
            max_attempt += 1
            candidate_dir = output_root / "candidates" / f"attempt_{max_attempt:04d}"
            candidate_dir.mkdir(parents=True, exist_ok=False)
            state = {"attempt": max_attempt, "seed": seed + max_attempt - 1,
                     "task_id": task_id, "positive": label_by_id[task_id],
                     "stage": "ontology", "status": "in_progress", "error": None,
                     "candidate_dir": candidate_dir}
            states.append(state)
        if state["stage"] == "ontology" and not (Path(state["candidate_dir"]) / "ontology.json").is_file():
            if state.get("scenario_selection", {}).get("version") != SAMPLING_VERSION:
                state["scenario_selection"] = select_scenario(int(state["task_id"].rsplit("_", 1)[1]))
            prepare = getattr(ontology_factory, "prepare_context", None)
            if callable(prepare) and "generation_context" not in state:
                state["generation_context"] = prepare(state)
        _save_checkpoint(state)
        running[executor.submit(run_candidate, state)] = state
        return True

    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="task-generation")
    last_manifest_at = 0.0
    try:
        while True:
            active_ids = {state["task_id"] for state in running.values()}
            for task_id in task_ids:
                if stopping.is_set() or len(running) >= workers:
                    break
                if task_id not in completed_ids | blocked_ids | active_ids:
                    if submit(executor, task_id):
                        active_ids.add(task_id)
            drain_events()
            if time.monotonic() - last_manifest_at >= 2:
                write_manifest(run_status="in_progress")
                last_manifest_at = time.monotonic()
            if not running:
                break
            done, _ = wait(running, timeout=0.2, return_when=FIRST_COMPLETED)
            for future in done:
                state = running.pop(future)
                try:
                    task_dir = future.result()
                except RecoverableGenerationError as error:
                    failures.append(error)
                    blocked_ids.add(state["task_id"])
                    cause = error
                    while cause is not None:
                        if is_non_retryable_error(cause):
                            stopping.set()
                            break
                        cause = cause.__cause__
                    continue
                if task_dir is not None:
                    completed_ids.add(state["task_id"])
                    accepted = sorted(set(accepted) | {task_dir}, key=lambda p: int(p.name.rsplit("_", 1)[1]))
                    _print_error_injection(_read_json(Path(state["candidate_dir"]) / "error_task_graph.json"))
                    report_progress(state, status="accepted")
    except BaseException:
        stopping.set()
        # Let active API calls finish, then stop at a checkpoint boundary.
        executor.shutdown(wait=True, cancel_futures=True)
        accepted = _accepted_task_dirs(output_root)
        drain_events()
        write_manifest(run_status="interrupted")
        report_progress(status="interrupted")
        raise
    finally:
        executor.shutdown(wait=True)
    drain_events()
    status = "complete" if len(accepted) >= count else (
        "recoverable_error" if failures else "candidate_budget_exhausted")
    write_manifest(run_status=status)
    report_progress(status=status)
    if failures:
        raise RecoverableGenerationError(f"{len(failures)} task group(s) paused; rerun to resume. {failures[0]}") from failures[0]
    if len(accepted) < count:
        raise RuntimeError(f"accepted {len(accepted)}/{count} tasks within {candidate_budget} new candidate attempts")
    return accepted[:count]


def _real_dependencies(output_root: Path):
    prompt_dir, trace_dir = HERE / "prompts", output_root / "api_traces"
    cancel_event = threading.Event()
    caller_options = {"trace_dir": trace_dir, "max_attempts": MAX_LLM_ATTEMPTS, "cancel_event": cancel_event}
    ontology_contract = (prompt_dir / "ontology_generation.md").read_text(encoding="utf-8")
    repair_instructions = (prompt_dir / "ontology_repair.md").read_text(encoding="utf-8")
    ontology_call = build_json_caller(model=ONTOLOGY_MODEL, stage="ontology", system_prompt=ontology_contract, **caller_options)
    ontology_repair_call = build_json_caller(
        model=ONTOLOGY_MODEL, stage="ontology_repair",
        system_prompt=repair_instructions + "\n\nFollow the complete output contract and valid example below:\n\n" + ontology_contract,
        **caller_options,
    )
    render_call = build_json_caller(model=RENDER_MODEL, stage="render", system_prompt=(prompt_dir / "task_rendering.md").read_text(encoding="utf-8"), **caller_options)
    error_spec_call = build_json_caller(
        model=ERROR_SPEC_MODEL, stage="error_spec",
        system_prompt=(prompt_dir / "error_spec.md").read_text(encoding="utf-8"),
        **caller_options,
    )
    full_call = build_json_caller(model=FULL_INFORMATION_MODEL, stage="full_information", system_prompt=(prompt_dir / "full_information.md").read_text(encoding="utf-8"), **caller_options)

    def full_answer(_: dict[str, Any]):
        return lambda prompt: full_call({"full_information_prompt": prompt})

    def error_spec_factory(task: dict[str, Any], candidate_seed: int) -> dict[str, Any]:
        from language_contract import require_english
        spec = generate_error_spec(error_spec_call, task, seed=candidate_seed)
        require_english(spec)
        return spec

    from numeric_rules import select_operation

    def prepare_context(state):
        operation_history = []
        for path in sorted((output_root / "candidates").glob("attempt_*/checkpoint.json"))[-10:]:
            previous_state = _read_json(path)
            ontology_path = path.parent / "ontology.json"
            if ontology_path.is_file():
                operation_history.append({"numeric_rule": _read_json(ontology_path)["numeric_rule"]})
            else:
                operation = previous_state.get("generation_context", {}).get("requested_operation")
                if operation:
                    operation_history.append({"numeric_rule": {"operation": operation}})
        return {"recent_scenarios": recent_task_summaries(output_root, state["task_id"]),
                "requested_operation": select_operation(operation_history, int(state["seed"]))}

    def ontology_factory(candidate_seed: int, *, task_id: str | None = None,
                         scenario_selection: dict[str, Any] | None = None,
                         generation_context: dict[str, Any] | None = None) -> dict[str, Any]:
        resolved_task_id = task_id or f"task_{_next_task_number(output_root):03d}"
        selection = (scenario_selection if scenario_selection and scenario_selection.get("version") == SAMPLING_VERSION
                     else select_scenario(int(resolved_task_id.rsplit("_", 1)[1])))
        context = generation_context if generation_context is not None else prepare_context({
            "task_id": resolved_task_id, "seed": candidate_seed,
        })
        ontology = generate_ontology(
            ontology_call, seed=candidate_seed, repair=ontology_repair_call,
            require_incomplete=True, expected_language="en", recent_scenarios=context["recent_scenarios"],
            requested_operation=context["requested_operation"], scenario_references=selection["references"],
            scenario_suggestion=selection["suggestion"],
        )
        from language_contract import require_english
        require_english(ontology)
        ontology["language"] = "en"
        return ontology

    ontology_factory.expected_language = "en"
    ontology_factory.prepare_context = prepare_context
    ontology_factory.cancel_event = cancel_event

    def english_render(payload):
        from language_contract import require_english
        result = render_call(payload)
        require_english(result)
        return result

    return ontology_factory, english_render, full_answer, error_spec_factory


def _print_generation_summary(output_root: Path, *, calls_before: set[str] | None = None,
                              accepted_before: set[str] | None = None) -> None:
    candidate_count = sum(path.is_dir() for path in (output_root / "candidates").glob("attempt_*"))
    accepted_ids = {path.name for path in _accepted_task_dirs(output_root)}
    accepted_count = len(accepted_ids)
    print(f"\n生成统计（含历史续跑）：候选总数 {candidate_count}，验收通过数 {accepted_count}",
          file=sys.stderr, flush=True)
    call_ids = trace_call_ids(output_root)
    scopes = [('累计', call_ids, accepted_count)]
    if calls_before is not None:
        scopes.insert(0, ('本次', call_ids - calls_before, len(accepted_ids - (accepted_before or set()))))
    for label, ids, count in scopes:
        costs = summarize_costs(output_root, ids)
        total = costs['cost_usd']
        average = f'${total / count:.6f}' if count else 'N/A（无验收通过task）'
        incomplete = (f"；费用不完整：{costs['missing_cost_calls']}次调用未返回费用，金额仅为已记录部分"
                      if costs['missing_cost_calls'] else '')
        total_label = '本次运行' if label == '本次' else label
        print(f"{total_label}总花费：${total:.6f} USD；{label}平均每个task：{average}"
              f"（{count}组，五类setting合计为一个task）{incomplete}", file=sys.stderr, flush=True)


def main() -> None:
    global ONTOLOGY_MODEL, ERROR_SPEC_MODEL, RENDER_MODEL, FULL_INFORMATION_MODEL
    load_project_env()
    parser = argparse.ArgumentParser(description="Generate CEG benchmark tasks end to end")
    parser.add_argument("--count", type=int, default=TASK_COUNT)
    parser.add_argument("--workers", type=int, default=GENERATION_WORKERS, help="concurrent task groups; 1 for serial")
    parser.add_argument("--positive-ratio", type=float, default=POSITIVE_RATIO,
                        help="positive task ratio in [0, 1]; positive count is rounded up")
    parser.add_argument("--start-task-number", type=int, default=START_TASK_NUMBER,
                        help="starting task number for a new batch (default: 1)")
    parser.add_argument("--seed", type=int, default=GLOBAL_SEED)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--candidate-budget", type=int)
    parser.add_argument("--fresh", action="store_true", help="start a new timestamped run instead of resuming")
    parser.add_argument("--no-progress", action="store_true", help="disable the generation progress bar")
    parser.add_argument("--generation-model", default=os.getenv("GENERATION_MODEL", GENERATION_MODEL),
                        help="model used for ontology, error design and rendering")
    parser.add_argument("--qualification-model", default=os.getenv("FULL_INFORMATION_MODEL", FULL_INFORMATION_MODEL))
    args = parser.parse_args()
    ONTOLOGY_MODEL = ERROR_SPEC_MODEL = RENDER_MODEL = args.generation_model
    FULL_INFORMATION_MODEL = args.qualification_model
    if not 0 <= args.positive_ratio <= 1:
        parser.error("--positive-ratio must be between 0 and 1")
    if args.start_task_number < 1:
        parser.error("--start-task-number must be at least one")
    if args.workers < 1:
        parser.error("--workers must be at least one")
    output_root = _fresh_output_root(args.output_root) if args.fresh else args.output_root
    from language_contract import validate_english_output_root
    try:
        validate_english_output_root(output_root)
    except ValueError as error:
        parser.error(str(error))
    calls_before = trace_call_ids(output_root)
    accepted_before = {path.name for path in _accepted_task_dirs(output_root)}
    ontology_factory, renderer, full_answer, error_spec_factory = _real_dependencies(output_root)
    from tqdm import tqdm
    from tqdm.contrib import DummyTqdmFile

    stage_labels = {
        "ontology": "生成本体", "compile": "编译任务", "error_spec": "设计错误注入",
        "prepare_reliable_pair": "准备配对基线", "render": "渲染资料",
        "full_information": "全信息验证", "derive_error": "派生 Error",
        "derive_neglect": "派生 Neglect",
        "derive_incomplete": "派生 Incomplete", "derive_mixed": "派生 Mixed", "materialize": "写入五种任务", "accepted": "已接收",
    }
    status_labels = {
        "starting": "准备生成", "resuming": "恢复已有进度", "complete": "全部完成",
        "rejected": "候选淘汰", "interrupted": "已中断，可续跑",
        "recoverable_error": "执行失败，可续跑", "candidate_budget_exhausted": "候选预算耗尽",
    }
    try:
        with tqdm(total=args.count, desc="生成任务组", unit="组", dynamic_ncols=True,
                  disable=args.no_progress, file=sys.stderr) as bar:
            def update_progress(event: dict[str, Any]) -> None:
                bar.update(event["completed"] - bar.n)
                details = [f"并发 {event['running']}/{event['workers']}"]
                if event["task_id"]:
                    details.append(f"{event['task_id']} / 候选 {event['attempt']}")
                if event["stage"]:
                    details.append(stage_labels.get(event["stage"], event["stage"]))
                if event["status"] in status_labels:
                    details.append(status_labels[event["status"]])
                bar.set_postfix_str(" · ".join(details))

            with redirect_stdout(DummyTqdmFile(sys.stdout)):
                accepted = generate_tasks(
                    count=args.count, seed=args.seed, workers=args.workers,
                    positive_ratio=args.positive_ratio,
                    start_task_number=args.start_task_number,
                    candidate_budget=args.candidate_budget if args.candidate_budget is not None else args.count * MAX_CANDIDATES_PER_TASK,
                    output_root=output_root, ontology_factory=ontology_factory,
                    renderer=renderer, full_answer=full_answer,
                    error_spec_factory=error_spec_factory,
                    qualification_model=FULL_INFORMATION_MODEL,
                    progress_callback=update_progress,
                )
    finally:
        _print_generation_summary(output_root, calls_before=calls_before, accepted_before=accepted_before)


if __name__ == "__main__":
    main()
