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
