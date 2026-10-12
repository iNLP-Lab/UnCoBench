"""Shared direct-access budgets; copied into each standalone runtime."""
SETTINGS = ("reliable", "misaligned", "incomplete", "missed", "mixed")
TURN_BUDGETS = {"reliable": (2, 5), "misaligned": (4, 7), "incomplete": (3, 6), "missed": (3, 6), "mixed": (4, 7)}

def apply_budget(task):
    ideal, maximum = TURN_BUDGETS[task.get("setting", "reliable")]
    task["routing"]["finalize_ideal_round"] = ideal
    task["runtime"] = {"max_turns": maximum}
    return task
