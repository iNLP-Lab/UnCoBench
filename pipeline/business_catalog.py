from __future__ import annotations

import copy
import random
from typing import Any

from key_routing import assign_record_keys


def role_display_name(role: dict[str, Any]) -> str:
    suffix = (f"（{role['role_abbreviation']}）" if any("\u4e00" <= c <= "\u9fff" for c in role["name"])
              else f" ({role['role_abbreviation']})")
    name = role["name"].strip()
    return name if name.endswith(suffix) else name + suffix


def add_secondary_businesses(task: dict[str, Any]) -> None:
    """Compile independently keyed business facts without changing formal predicates."""
    topics = task.setdefault("supplemental_topics", [])
    catalog = task["routing"].setdefault("catalog_only_record_ids", [])
    for role in task["roles"]:
        secondary = role["secondary_business"]
        topic = copy.deepcopy(secondary["topic"])
        topic["topic_id"] = f"supplemental_{role['role_id']}"
        topics.append(topic)
        values = list(topic["domain"])
        random.Random(f"{task['task_id']}:{task['seed']}:{role['role_id']}:secondary").shuffle(values)
        for index, candidate in enumerate(task["candidates"]):
            candidate_id = candidate["candidate_id"]
            observation_id = f"obs_supplemental_{role['role_id']}_{candidate_id}"
            task["observations"].append({
                "observation_id": observation_id, "observation_type": "supplemental",
                "predicate_id": None, "reporter_role_id": role["role_id"],
                "candidate_id": candidate_id, "topic_id": topic["topic_id"],
                "claimed_value": values[index % len(values)], "handoff_topics": [],
            })
            record_id = f"rec_{role['role_id']}_{candidate_id}_supplemental"
            task["records"].append({
                "record_id": record_id, "record_type": "supplemental",
                "owner_role_id": role["role_id"], "candidate_id": candidate_id,
                "business_abbreviation": secondary["business_abbreviation"],
                "business_title": secondary["title"],
                "observation_ids": [observation_id],
            })
            catalog.append(record_id)
    task["routing"]["record_keys"] = assign_record_keys(
        task_id=task["task_id"], records=task["records"], roles=task["roles"],
    )
