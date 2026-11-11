"""Select final role-count benchmarks and maintain independent fault states."""

import importlib.util
import json
from pathlib import Path
import re


COUNT_SETTINGS = ("misaligned", "incomplete", "missed")


def resolve_task(data_root, setting, task_id, k=1):
    data_root = Path(data_root).resolve()
    if k not in (1, 2, 3):
        raise ValueError("k must be 1, 2 or 3")
    if k == 1 or setting not in COUNT_SETTINGS:
        return data_root / setting / task_id, None
    manifest = data_root / "number_expansion" / setting / task_id / "manifest.json"
    document = json.loads(manifest.read_text(encoding="utf-8"))
    if document["setting"] != setting or document["task_id"] != task_id:
        raise ValueError(f"Role-count manifest identity mismatch: {manifest}")
    variant = document["variants"][str(k)]
    roles, names = variant["role_ids"], variant["role_names"]
    if len(roles) != k or len(set(roles)) != k or len(names) != k or len(set(names)) != k:
        raise ValueError(f"Expected {k} distinct unreliable roles: {manifest}")
    if document["variants"]["3"]["role_ids"][:2] != document["variants"]["2"]["role_ids"]:
        raise ValueError(f"k=3 must retain the k=2 roles: {manifest}")
    directory = (data_root / variant["directory"]).resolve()
    if not directory.is_relative_to(data_root):
        raise ValueError(f"Task directory must be inside the benchmark: {directory}")
    return directory, variant


def configure_task(module, variant, k):
    if getattr(module, "ACTIVE_ROLE_COUNT", None) is not None:
        raise ValueError("Role-count runtime is already configured")
    if module.SETTING not in COUNT_SETTINGS:
        raise ValueError("Role counts apply to misaligned, incomplete and missed")
    names = variant["role_names"]
    if not set(names) <= {r["role_name"] for r in module.PUBLIC_ROLES}:
        raise ValueError("Unreliable roles do not match the task roster")
    extra = {}
    if module.SETTING == "incomplete":
        profiles = variant["profiles"]
        if [p["role_name"] for p in profiles] != names:
            raise ValueError("Incomplete profiles do not match the selected roles")
        for field in ("key", "role_name", "threshold_value"):
            if profiles[0][field] != module.INCOMPLETE_INJECTION[field]:
                raise ValueError("The original Incomplete profile must be retained")
        extra = {p["role_name"]: p for p in profiles[1:]}
    elif module.SETTING == "misaligned":
        if [p["role_name"] for p in variant["error_profiles"]] != names:
            raise ValueError("Misaligned profiles do not match the selected roles")
    else:
        module.COMMUNICATION_ROLE_NAMES = list(names)

    original_class = module.MainAgent

    class CountedMainAgent(original_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.extra_policies = {name: module.IncompletePolicy(profile)
                                   for name, profile in extra.items()}

        def run(self, task):
            for policy in self.extra_policies.values():
                policy.reset()
            return super().run(task)

        def _answer_question(self, role_name, question):
            name = module.resolve_role_name(role_name, self.role_agents)
            policy = self.extra_policies.get(name)
            if policy is None:
                return super()._answer_question(role_name, question)
            original_profile = module.INCOMPLETE_INJECTION
            original_policy = self.incomplete_policy
            module.INCOMPLETE_INJECTION, self.incomplete_policy = extra[name], policy
            try:
                return super()._answer_question(role_name, question)
            finally:
                module.INCOMPLETE_INJECTION = original_profile
                self.incomplete_policy = original_policy

        def _result(self, final, transcript, final_turn):
            result = super()._result(final, transcript, final_turn)
            if module.SETTING == "missed":
                per_role = {}
                for name in names:
                    events = {e["kind"]: e["turn"] for e in self.neglect_policy.events
                              if e["role_agent"] == name}
                    per_role[name] = {
                        "triggered": "neglect_ignored" in events,
                        "recovered": "neglect_delivered" in events,
                        "omitted_turn": events.get("neglect_ignored"),
                        "recovery_turn": events.get("neglect_delivered"),
                    }
            elif module.SETTING == "misaligned":
                per_role = {}
                for profile in variant["error_profiles"]:
                    metrics = module.error_recovery_metrics(profile, transcript)
                    per_role[profile["role_name"]] = {
                        "triggered": metrics["mismatch_key_queried"],
                        "recovered": metrics["error_fact_returned"],
                        "status": metrics["error_recovery_status"],
                        "omitted_turn": metrics["mismatch_key_turn"],
                        "recovery_turn": metrics["recovery_turn"],
                    }
            else:
                context = {"correct": bool(result["evaluation"]["joint_correctness"]),
                           "finalized": final_turn is not None}
                communication = result["evaluation"]["communication_evaluation"]
                per_role = {}
                for index, profile in enumerate(variant["profiles"]):
                    state = (communication if index == 0 else
                             self.extra_policies[profile["role_name"]].metrics(**context))
                    metrics = module.incomplete_numeric_metrics(
                        profile, transcript, state, **context)
                    per_role[profile["role_name"]] = {
                        "triggered": metrics["incomplete_omission_triggered"],
                        "recovered": metrics["incomplete_threshold_returned"],
                        "status": metrics["incomplete_recovery_status"],
                        "omitted_turn": metrics["incomplete_omission_turn"],
                        "recovery_turn": metrics["incomplete_recovery_turn"],
                    }
            result["role_count"] = {"k": k, "role_ids": variant["role_ids"],
                                    "role_names": names, "per_role": per_role}
            return result

    module.MainAgent = CountedMainAgent
    module.ACTIVE_ROLE_COUNT = k


def run_single(runtime_path, k):
    runtime_path = Path(runtime_path).resolve()
    root = Path(__file__).resolve().parents[1]
    task_id = next(p.name for p in runtime_path.parents if re.fullmatch(r"task_\d+", p.name))
    spec = importlib.util.spec_from_file_location("counted_benchmark_task", runtime_path)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    directory, variant = resolve_task(root / "data", original.SETTING, task_id, k)
    spec = importlib.util.spec_from_file_location("counted_benchmark_task",
                                                directory / "tasks/run_one.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if variant is not None:
        configure_task(module, variant, k)
    save_result = module.save_single_run_result

    def save_counted_result(result, output_root=None):
        return save_result(result, output_root=output_root or
                           root / "outputs/single" / original.SETTING / f"k{k}" / task_id)

    module.save_single_run_result = save_counted_result
    module._run_single()
