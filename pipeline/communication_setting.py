"""Paired neglect intervention; private business facts remain unchanged."""
import copy
import random
from task_types import validate_task_graph
from runtime_settings import apply_budget


def derive_neglect_task(reliable):
    if reliable.get("setting") != "reliable":
        raise ValueError("Neglect must be derived from Reliable")
    required = set(reliable["routing"]["required_record_ids"])
    roles = {r["role_id"]: r for r in reliable["roles"]}
    eligible = sorted({r["owner_role_id"] for r in reliable["records"]
                       if r["record_id"] in required and roles[r["owner_role_id"]]["kind"] != "distractor"})
    if not eligible:
        raise ValueError("Neglect requires necessary business roles")
    if reliable.get('intervention_plan'):
        eligible = [r for r in eligible if r == reliable['intervention_plan']['neglect_role_id']]
        if not eligible:
            raise ValueError('planned Neglect role is not eligible')
    rng = random.Random(f"{reliable['task_id']}:{reliable['seed']}:slow")
    task = copy.deepcopy(reliable)
    task["setting"] = "missed"
    task["neglect_profile"] = {"role_ids": [rng.choice(eligible)]}
    return validate_task_graph(apply_budget(task))
