from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


UNSUPPORTED_STRICT_SCHEMA_KEYWORDS = {"oneOf"}
NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404, 405, 409, 422}
_TRACE_LOCK = threading.Lock()
_TRACE_COUNTER = 0


class SchemaCompatibilityError(ValueError):
    """Raised before an API call when a strict-output schema is unsupported."""


class NonRetryableApiError(RuntimeError):
    """Raised when repeating the same request cannot repair the failure."""


def openrouter_extra_body(*, require_parameters: bool = False) -> dict[str, Any]:
    body: dict[str, Any] = {
        "reasoning": {
            "effort": os.getenv("AUTOMATION_REASONING_EFFORT", "medium"),
            "exclude": os.getenv("AUTOMATION_REASONING_EXCLUDE", "1") != "0",
        }
    }
    if require_parameters:
        body["provider"] = {"require_parameters": True}
    return body


def preflight_json_schema(schema: dict[str, Any], *, label: str) -> None:
    """Validate the strict Structured Outputs subset used by this pipeline."""

    def visit(node: Any, path: str) -> None:
        if isinstance(node, list):
            for index, item in enumerate(node):
                visit(item, f"{path}[{index}]")
            return
        if not isinstance(node, dict):
            return
        unsupported = UNSUPPORTED_STRICT_SCHEMA_KEYWORDS & set(node)
        if unsupported:
            raise SchemaCompatibilityError(
                f"{label} uses unsupported schema keyword(s) {sorted(unsupported)} at {path}"
            )
        if node.get("type") == "object":
            properties = node.get("properties")
            required = node.get("required")
            if not isinstance(properties, dict):
                raise SchemaCompatibilityError(f"{label} object has no properties at {path}")
            if node.get("additionalProperties") is not False:
                raise SchemaCompatibilityError(
                    f"{label} object must set additionalProperties=false at {path}"
                )
            if set(required or []) != set(properties):
                raise SchemaCompatibilityError(
                    f"{label} strict object must require every property at {path}"
                )
        for key, value in node.items():
            visit(value, f"{path}.{key}")

    visit(schema, "$")


def is_non_retryable_error(error: BaseException) -> bool:
    if isinstance(error, (SchemaCompatibilityError, NonRetryableApiError)):
        return True
    status_code = getattr(error, "status_code", None)
    if status_code in NON_RETRYABLE_STATUS_CODES:
        return True
    message = str(error).lower()
    markers = (
        "authentication", "invalid api key", "unauthorized", "forbidden",
        "response_format", "json schema", "structured output", "oneof",
        "no endpoints found", "no endpoint found", "missing dependency",
    )
    return any(marker in message for marker in markers)


def _next_trace_id(stage: str) -> str:
    global _TRACE_COUNTER
    with _TRACE_LOCK:
        _TRACE_COUNTER += 1
        counter = _TRACE_COUNTER
    safe_stage = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stage)
    return f"{safe_stage}_{os.getpid()}_{time.time_ns()}_{counter:04d}"


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


def traced_chat_completion(
    client: Any,
    *,
    stage: str,
    trace_dir: str | Path | None = None,
    **request: Any,
) -> Any:
    """Call Chat Completions and persist a thread-safe request/response pair."""
    configured_root = trace_dir or os.getenv("AUTOMATION_TRACE_DIR")
    trace_root = Path(configured_root) if configured_root else None
    trace_id = _next_trace_id(stage)
    call_dir = trace_root / stage / trace_id if trace_root else None
    started_at = datetime.now(timezone.utc)
    if call_dir:
        call_dir.mkdir(parents=True, exist_ok=False)
        (call_dir / "request.json").write_text(
            json.dumps(
                {
                    "trace_id": trace_id,
                    "stage": stage,
                    "started_at": started_at.isoformat(),
                    "request": _jsonable(request),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    started = time.perf_counter()
    try:
        response = client.chat.completions.create(**request)
    except Exception as error:
        if call_dir:
            (call_dir / "error.json").write_text(
                json.dumps(
                    {
                        "trace_id": trace_id,
                        "stage": stage,
                        "elapsed_seconds": time.perf_counter() - started,
                        "error_type": type(error).__name__,
                        "status_code": getattr(error, "status_code", None),
                        "message": str(error),
                        "retryable": not is_non_retryable_error(error),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        raise
    if call_dir:
        (call_dir / "response.json").write_text(
            json.dumps(
                {
                    "trace_id": trace_id,
                    "stage": stage,
                    "elapsed_seconds": time.perf_counter() - started,
                    "response": _jsonable(response),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return response
