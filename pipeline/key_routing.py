from __future__ import annotations

import hashlib
import re
from typing import Any


KEY_PATTERN = re.compile(r"^[A-Z]+-[A-Z]+-[A-Z0-9]{3}$")
ABBREVIATION_PATTERN = re.compile(r"^[A-Z]{2,10}$")
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def random_code(seed: str, salt: int = 0) -> str:
    digest = hashlib.sha256(f"{seed}:{salt}".encode("utf-8")).digest()
    number = int.from_bytes(digest[:8], "big")
    chars: list[str] = []
    for _ in range(3):
        chars.append(ALPHABET[number % len(ALPHABET)])
        number //= len(ALPHABET)
    return "".join(chars)


def reserve_unique_code(seed: str, used_codes: set[str]) -> str:
    salt = 0
    while True:
        code = random_code(seed, salt)
        if code not in used_codes:
            used_codes.add(code)
            return code
        salt += 1


def assign_record_keys(
    *, task_id: str, records: list[dict[str, Any]], roles: list[dict[str, Any]],
) -> dict[str, str]:
    role_by_id = {role["role_id"]: role for role in roles}
    result: dict[str, str] = {}
    used_codes: set[str] = set()
    for record in records:
        role = role_by_id[record["owner_role_id"]]
        role_abbreviation = role["role_abbreviation"]
        business_abbreviation = record["business_abbreviation"]
        code = reserve_unique_code(
            f"{task_id}:{role_abbreviation}:{business_abbreviation}:{record['record_id']}",
            used_codes,
        )
        key = f"{role_abbreviation}-{business_abbreviation}-{code}"
        if not KEY_PATTERN.fullmatch(key):
            raise ValueError(f"generated invalid key: {key}")
        result[record["record_id"]] = key
    return result


def role_id_for_key(task: dict[str, Any], key: str) -> str | None:
    if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key):
        return None
    record_id = next(
        (
            record_id for record_id, record_key in task["routing"]["record_keys"].items()
            if record_key == key
        ),
        None,
    )
    if record_id is None:
        return None
    record = next(item for item in task["records"] if item["record_id"] == record_id)
    return record["owner_role_id"]
