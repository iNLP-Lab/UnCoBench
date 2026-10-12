from __future__ import annotations

import json
import os
import time
import threading
import random
import sys
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable

from llm_runtime import openrouter_extra_body, traced_chat_completion, is_non_retryable_error


HERE = Path(__file__).resolve().parent

ROLE_RENDER_REASONING_EFFORT = "low"


class LlmCallError(RuntimeError):
    """An exhausted model call that should be recoverable on a later run."""


class RateLimitCooldown:
    """Share the next permissible request time across workers for one model."""

    def __init__(self):
        self.lock = threading.Lock()
        self.until = 0.0

    def defer(self, seconds: float) -> None:
        with self.lock:
            self.until = max(self.until, time.monotonic() + seconds)

    def wait(self, cancel_event=None) -> None:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise LlmCallError("generation interrupted while waiting for rate limit recovery")
            with self.lock:
                remaining = self.until - time.monotonic()
            if remaining <= 0:
                return
            if cancel_event is None:
                time.sleep(min(remaining, 1.0))
            else:
                cancel_event.wait(min(remaining, 1.0))


_COOLDOWNS = {}
_COOLDOWNS_LOCK = threading.Lock()


def _is_rate_limit(error: Exception) -> bool:
    status = getattr(error, "status_code", None)
    if status == 429:
        return True
    if status is not None and status not in {500, 502, 503, 504}:
        return False
    body = getattr(error, "body", None)
    def contains_429(value):
        if isinstance(value, dict):
            return str(value.get("code")) == "429" or any(contains_429(v) for v in value.values())
        if isinstance(value, list):
            return any(contains_429(v) for v in value)
        return False
    message = str(error).lower()
    return contains_429(body) or any(marker in message for marker in (
        "rate limited", "rate-limited", "rate limit exceeded", "too many requests",
    ))


def _rate_limit_delay(error: Exception, retry: int) -> float:
    headers = getattr(getattr(error, "response", None), "headers", {}) or {}
    retry_after = headers.get("retry-after") or headers.get("Retry-After")
    if retry_after is not None:
        try:
            return max(1.0, float(retry_after))
        except (ValueError, TypeError):
            try:
                return max(1.0, parsedate_to_datetime(retry_after).timestamp() - time.time())
            except (ValueError, TypeError, OverflowError):
                pass
    return min(30 * 2 ** min(retry, 4), 300) + random.uniform(0, 3)


def _ensure_json_instruction(system_prompt: str) -> str:
    if "json" in system_prompt.lower():
        return system_prompt
    return "Return exactly one valid JSON object.\n\n" + system_prompt


def load_project_env(start: Path = HERE) -> Path | None:
    for directory in (start.resolve(), *start.resolve().parents):
        path = directory / ".env"
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))
        return path
    return None


def build_json_caller(
    *, model: str, stage: str, system_prompt: str,
    base_url: str | None = None, api_key: str | None = None,
    trace_dir: Path | None = None,
    max_attempts: int = 1,
    cancel_event: threading.Event | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    try:
        from openai import OpenAI
    except ImportError as error:
        raise RuntimeError("openai>=1.0 is required") from error
    resolved_key = api_key or os.getenv("AUTOMATION_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")
    if not resolved_key:
        raise ValueError("AUTOMATION_API_KEY or OPENROUTER_API_KEY must be set")
    cooldown_key = (base_url or os.getenv("AUTOMATION_BASE_URL", "https://openrouter.ai/api/v1"), resolved_key, model)
    with _COOLDOWNS_LOCK:
        cooldown = _COOLDOWNS.setdefault(cooldown_key, RateLimitCooldown())
    local = threading.local()
    effective_system_prompt = _ensure_json_instruction(system_prompt)

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")

    def call(payload: dict[str, Any]) -> dict[str, Any]:
        last_error: Exception | None = None
        if not hasattr(local, "client"):
            local.client = OpenAI(
                base_url=base_url or os.getenv("AUTOMATION_BASE_URL", "https://openrouter.ai/api/v1"),
                api_key=resolved_key, max_retries=0, timeout=120.0,
            )
        attempt = 0
        rate_retries = 0
        while attempt < max_attempts:
            cooldown.wait(cancel_event)
            try:
                extra_body = openrouter_extra_body(require_parameters=True)
                if stage == "render" and payload.get("kind") == "role":
                    extra_body["reasoning"]["effort"] = ROLE_RENDER_REASONING_EFFORT
                response = traced_chat_completion(
                    local.client, stage=stage, trace_dir=trace_dir, model=model,
                    messages=[
                        {"role": "system", "content": effective_system_prompt},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
                    ],
                    response_format={"type": "json_object"},
                    extra_body=extra_body,
                )
                content = response.choices[0].message.content
                if not isinstance(content, str) or not content.strip():
                    raise ValueError(f"{stage} returned empty content")
                value = json.loads(content)
                if not isinstance(value, dict):
                    raise ValueError(f"{stage} must return a JSON object")
                return value
            except Exception as error:
                last_error = error
                if _is_rate_limit(error):
                    delay = _rate_limit_delay(error, rate_retries)
                    rate_retries += 1
                    cooldown.defer(delay)
                    print(f"[{stage}] {model} 上游限流，等待至少 {delay:.0f} 秒后自动重试（第 {rate_retries} 次）；同模型并发请求共享冷却。", file=sys.stderr, flush=True)
                    continue
                if is_non_retryable_error(error):
                    raise LlmCallError(f"{stage} cannot be retried: {error}") from error
                attempt += 1
                if attempt < max_attempts:
                    time.sleep(min(2 ** (attempt - 1), 16))
        assert last_error is not None
        raise LlmCallError(f"{stage} failed after {max_attempts} attempt(s): {last_error}") from last_error

    return call
