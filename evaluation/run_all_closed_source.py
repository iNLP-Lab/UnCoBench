#!/usr/bin/env python3
"""Evaluate paired tasks with remote or locally hosted OpenAI-compatible main models."""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import csv
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import io
import json
import multiprocessing
import os
from pathlib import Path
import re
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ("reliable", "misaligned", "incomplete", "missed", "mixed")
sys.dont_write_bytecode = True


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def save_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def load_environment():
    for directory in (ROOT, *ROOT.parents):
        path = directory / ".env"
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
            break


def fingerprint(directory):
    files = [directory / "tasks/run_one.py", *sorted((directory / "role_agents").glob("*.json"))]
    if not files[0].is_file() or len(files) < 2:
        raise ValueError(f"Missing runtime or role files: {directory}")
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(directory)).encode() + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def discover_tasks(data_root, settings, start, end):
    paired_ids = None
    tasks = []
    for setting in settings:
        directory = data_root / setting
        ids = sorted(p.name for p in directory.glob("task_*")
                     if p.is_dir() and re.fullmatch(r"task_\d+", p.name)
                     and start <= int(p.name[5:]) <= end)
        if not ids:
            raise ValueError(f"No tasks selected in {directory}")
        if paired_ids is not None and ids != paired_ids:
            raise ValueError(f"Task IDs are not paired across settings: {setting}")
        paired_ids = ids
        for task_id in ids:
            path = directory / task_id
            tasks.append({"setting": setting, "task_id": task_id, "fingerprint": fingerprint(path)})
    return tasks


def make_jobs(config):
    return [{**task, "model": model, "job_id": f"model_{i:02d}/{task['setting']}/{task['task_id']}"}
            for i, model in enumerate(config["models"], 1) for task in config["tasks"]]


def load_task(path):
    spec = importlib.util.spec_from_file_location("benchmark_task", path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


def extract_metrics(result):
    evaluation = result["evaluation"]
    communication = evaluation["communication_evaluation"]
    correct = evaluation["joint_correctness"]
    turns = communication["turns_to_finalize"]
    if correct not in (0, 1) or type(turns) is not int or turns < 1:
        raise ValueError("Runtime returned invalid correctness or turn count")
    return {"correctness": int(correct), "turns": turns,
            "misaligned_recovered": communication.get("error_fact_returned"),
            "incomplete_recovered": communication.get("incomplete_threshold_returned"),
            "missed_delivered": communication.get("neglect_delivered_count")}


def redact(text, keys):
    for key in keys.values():
        if key:
            text = text.replace(key, "[REDACTED]")
    return text


def configure_local_main(client, config):
    """Adapt only the main client's requests for a locally hosted model."""
    create = client.chat.completions.create

    def local_create(**kwargs):
        # Use the task's JSON instructions without forcing a decoding backend.
        kwargs.pop("response_format", None)
        extra_body = dict(kwargs.pop("extra_body", None) or {})
        extra_body.pop("reasoning", None)
        extra_body.update(config["main_extra_body"])
        kwargs["extra_body"] = extra_body
        kwargs.setdefault("max_tokens", config["main_max_tokens"])
        return create(**kwargs)

    client.chat.completions.create = local_create


def run_job(job, config, output, keys):
    """Run one episode; retain failed attempts and never retry a wrong answer."""
    from openai import OpenAI

    base = Path(output) / "runs" / job["job_id"]
    base.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix="attempt_", dir=base))
    record = {"job_id": job["job_id"], "status": "failed",
              "attempt": str(attempt.relative_to(output)),
              "started_at": datetime.now(timezone.utc).isoformat()}
    started = time.monotonic()
    with (attempt / "runtime.log").open("w", encoding="utf-8") as log:
        with redirect_stdout(log), redirect_stderr(log):
            try:
                directory = Path(config["data_root"]) / job["setting"] / job["task_id"]
                if fingerprint(directory) != job["fingerprint"]:
                    raise ValueError(f"Task changed after discovery: {directory}")
                module = load_task(directory / "tasks/run_one.py")
                if module.SETTING != job["setting"]:
                    raise ValueError("Runtime setting does not match its directory")
                module.ROLE_REASONING_EFFORT = config["role_reasoning_effort"]
                module.LLM_REASONING_EFFORT = config["reasoning_effort"]
                module.MAIN_AGENT_ROLE_ORDER_SEED = None
                defaults = module.runtime_defaults()
                ideal = defaults["finalize_ideal_round"]
                if job["setting"] in {"missed", "mixed"}:
                    ideal += config["required_followups"] - 1
                maximum = ideal + 3
                with ExitStack() as stack:
                    main_client = stack.enter_context(OpenAI(api_key=keys["main"],
                        base_url=config["main_base_url"], timeout=120, max_retries=2))
                    role_client = stack.enter_context(OpenAI(api_key=keys["role"],
                        base_url=config["role_base_url"], timeout=120, max_retries=2))
                    if config.get("local_main"):
                        configure_local_main(main_client, config)
                    roles = module.build_role_agents(role_client,
                        agent_dir=str(directory / "role_agents"), model=config["role_model"])
                    agent = module.MainAgent(main_client, roles, model=job["model"], max_turns=maximum)
                    agent.runtime_config.update(finalize_ideal_round=ideal, max_turns=maximum,
                        neglect_required_followups=config["required_followups"])
                    result = agent.run(module.build_task())
                metrics = extract_metrics(result)
                result_path = attempt / "result.json"
                save_json(result_path, result)
                record.update(status="success", metrics=metrics,
                              result_path=str(result_path.relative_to(output)))
            except Exception as error:
                record.update(error=redact(str(error), keys), error_type=type(error).__name__)
    record["elapsed_seconds"] = time.monotonic() - started
    save_json(attempt / "record.json", record)
    save_json(base / "record.json", record)
    return record


def load_records(output, jobs):
    records = {}
    for job in jobs:
        path = output / "runs" / job["job_id"] / "record.json"
        if path.is_file():
            record = read_json(path)
            if record["job_id"] != job["job_id"]:
                raise ValueError(f"Mismatched saved job: {path}")
            if record["status"] == "success":
                if extract_metrics(read_json(output / record["result_path"])) != record["metrics"]:
                    raise ValueError(f"Saved metrics do not match result: {path}")
            records[job["job_id"]] = record
    return records


def save_summary(output, config, jobs, records):
    rows = []
    for model in config["models"]:
        for setting in config["settings"]:
            selected = [j for j in jobs if j["model"] == model and j["setting"] == setting]
            current = [records[j["job_id"]] for j in selected if j["job_id"] in records]
            valid = [r["metrics"] for r in current if r["status"] == "success"]
            rows.append({"model": model, "setting": setting, "total": len(selected),
                "completed": len(valid), "failed": len(current) - len(valid),
                "pending": len(selected) - len(current),
                "accuracy": sum(m["correctness"] for m in valid) / len(valid) if valid else None,
                "mean_turns": sum(m["turns"] for m in valid) / len(valid) if valid else None})
    save_json(output / "summary.json", rows)
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    atomic_write(output / "summary.csv", stream.getvalue())


def run_experiment(output, config, jobs, keys, workers):
    from tqdm import tqdm

    records = load_records(output, jobs)
    pending = iter(j for j in jobs if records.get(j["job_id"], {}).get("status") != "success")
    futures = {}
    last_summary = time.monotonic()
    worker_config = {key: value for key, value in config.items() if key != "tasks"}
    # Separate processes isolate task imports, environment loading and stdout.
    with ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("spawn")) as pool:
        with tqdm(total=len(jobs), initial=sum(r["status"] == "success" for r in records.values()),
                  unit="task") as progress:
            try:
                while True:
                    while len(futures) < workers:
                        job = next(pending, None)
                        if job is None:
                            break
                        futures[pool.submit(run_job, job, worker_config, str(output), keys)] = job
                    if not futures:
                        break
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        job = futures.pop(future)
                        records[job["job_id"]] = future.result()
                        progress.update()
                    if time.monotonic() - last_summary >= 15:
                        save_summary(output, config, jobs, records)
                        last_summary = time.monotonic()
            except KeyboardInterrupt:
                for future in futures:
                    future.cancel()
                print("Interrupted. Waiting for active tasks to save; resume with --resume.", file=sys.stderr)
                raise
    save_summary(output, config, jobs, records)
    return records


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Must be a positive integer")
    return number


def json_object(value):
    try:
        parsed = json.loads(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error)) from error
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("Must be a JSON object")
    return parsed


def main(argv=None):
    load_environment()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", help="Main model IDs exposed by the API")
    parser.add_argument("--role-model", help="Model ID shared by all role agents")
    parser.add_argument("--settings", nargs="+", choices=SETTINGS)
    parser.add_argument("--start", type=positive_int, help="First task number (inclusive)")
    parser.add_argument("--end", type=positive_int, help="Last task number (inclusive)")
    parser.add_argument("--workers", type=positive_int, default=20)
    parser.add_argument("--main-base-url")
    parser.add_argument("--role-base-url")
    parser.add_argument("--local-main", action="store_true", default=None,
                        help="Use a locally hosted main model; keep role agents on their API")
    parser.add_argument("--main-max-tokens", type=positive_int,
                        help="Maximum output tokens for a local main model (default: 8192)")
    parser.add_argument("--main-extra-body", type=json_object,
                        help="JSON request options for a local main model, such as chat_template_kwargs")
    parser.add_argument("--reasoning-effort")
    parser.add_argument("--role-reasoning-effort")
    parser.add_argument("--required-followups", type=positive_int)
    parser.add_argument("--resume", type=Path, help="Existing experiment directory")
    parser.add_argument("--dry-run", action="store_true", help="Check task inventory without API calls or output files")
    args = parser.parse_args(argv)
    keys = {}
    try:
        saved = read_json(args.resume / "config.json") if args.resume else {}
        local_main = args.local_main or saved.get("local_main", False)
        keys = {"main": os.getenv("MAIN_AGENT_API_KEY") or
                       ("local" if local_main else os.getenv("OPENROUTER_API_KEY", "")),
                "role": os.getenv("ROLE_AGENT_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")}
        defaults = {"models": [os.environ["MAIN_AGENT_MODEL_NAME"]] if os.getenv("MAIN_AGENT_MODEL_NAME") else [],
                    "role_model": os.getenv("ROLE_AGENT_MODEL_NAME",
                                            "deepseek/deepseek-v4-flash-0731" if local_main else ""),
                    "settings": list(SETTINGS), "start": 1, "end": 1000,
                    "main_base_url": os.getenv("MAIN_AGENT_BASE_URL",
                                              "http://127.0.0.1:8000/v1" if local_main else "https://openrouter.ai/api/v1"),
                    "role_base_url": os.getenv("ROLE_AGENT_BASE_URL", "https://openrouter.ai/api/v1"),
                    "reasoning_effort": "medium", "role_reasoning_effort": "low", "required_followups": 1}
        if local_main:
            defaults.update(local_main=True, main_max_tokens=8192, main_extra_body={})
        config = {key: getattr(args, key) if getattr(args, key) is not None else saved.get(key, default)
                  for key, default in defaults.items()}
        if config["start"] > config["end"]:
            raise ValueError("--start must not exceed --end")
        for key in ("models", "settings"):
            config[key] = list(dict.fromkeys(config[key]))
        config.update(schema_version=1, data_root=str(ROOT / "data"))
        config["tasks"] = discover_tasks(ROOT / "data", config["settings"], config["start"], config["end"])
        if saved and saved != config:
            raise ValueError("Resume configuration or task contents changed; start a new experiment")
        print(f"Selected {len(config['tasks'])} task instances across {len(config['settings'])} settings.", flush=True)
        if args.dry_run:
            print(f"Evaluations: {len(config['tasks']) * len(config['models']) if config['models'] else 'specify --models'}")
            return 0
        if not config["models"] or not config["role_model"]:
            raise ValueError("Specify --models and --role-model, or their model environment variables")
        if not all(keys.values()):
            raise ValueError("Set ROLE_AGENT_API_KEY or OPENROUTER_API_KEY for role agents; "
                             "remote main models also need MAIN_AGENT_API_KEY or OPENROUTER_API_KEY")
        output_root = ROOT / "outputs/evaluation"
        output_root.mkdir(parents=True, exist_ok=True)
        output = args.resume.resolve() if args.resume else Path(tempfile.mkdtemp(
            prefix=("open_source_" if local_main else "closed_source_") +
                   datetime.now().strftime("%Y%m%d_%H%M%S_"), dir=output_root))
        jobs = make_jobs(config)
        with (output / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            save_json(output / "config.json", config)
            print(f"Output: {output}\nEvaluations: {len(jobs)}; workers: {args.workers}", flush=True)
            try:
                records = run_experiment(output, config, jobs, keys, args.workers)
            finally:
                save_summary(output, config, jobs, load_records(output, jobs))
        failed = sum(r["status"] != "success" for r in records.values())
        print(f"Completed: {len(records) - failed}; failed: {failed}. Summary: {output / 'summary.csv'}")
        return int(failed > 0)
    except KeyboardInterrupt:
        return 130
    except Exception as error:
        print(redact(f"Evaluation failed: {error}", keys), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
