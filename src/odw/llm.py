"""Optional LLM fallback over an OpenAI-compatible HTTP API (EU-hosted, open-weight model).

Off by default. On only when an API key is configured AND (config/llm.yaml `enabled: true` OR `--llm on`).
Never raises: any network/format problem returns None and the rule-based result stands.

Configuration (environment or ./.env):
    LLM_BASE_URL   e.g. https://api.eu.mistral.ai/v1
    LLM_MODEL      e.g. ministral-3b-2512
    LLM_API_KEY    secret, never committed
    LLM_ENABLED    0 → rules only, whatever config/llm.yaml says
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from functools import cache
from pathlib import Path
from typing import Any, Callable

import yaml

from .config import ROOT

log = logging.getLogger(__name__)

SETTINGS_FILE = ROOT / "config" / "llm.yaml"
_FORCED: bool | None = None  # set by the CLI flag --llm on|off


def force(enabled: bool | None) -> None:
    global _FORCED, _DOWN
    global _REASON
    global _WAITED, _REFUSED
    _FORCED, _DOWN, _REASON, _WAITED, _REFUSED = enabled, False, "", 0.0, 0
    settings.cache_clear()


def _dotenv(path: Path = ROOT / ".env") -> dict[str, str]:
    """KEY=VALUE lines. Tolerates files saved on Windows: UTF-8 with BOM, UTF-16 (Notepad), CRLF; never raises."""
    out: dict[str, str] = {}
    try:
        raw = path.read_bytes() if path.is_file() else b""
    except OSError:
        return out
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16", errors="replace")
    else:
        text = raw.decode("utf-8-sig", errors="replace")
    if text:
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                out[key.strip()] = value.strip().strip('"').strip("'")
    return out


@cache
def settings() -> dict[str, Any]:
    file_cfg = yaml.safe_load(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.exists() else {}
    env = {**_dotenv(), **os.environ}
    cfg = {
        "base_url": env.get("LLM_BASE_URL") or file_cfg.get("base_url", ""),
        "model": env.get("LLM_MODEL") or file_cfg.get("model", ""),
        "api_key": env.get("LLM_API_KEY", ""),
        "timeout_s": float(file_cfg.get("timeout_s", 15)),
        "max_chars": int(file_cfg.get("max_chars", 6000)),
        "classify_tiebreak": bool(file_cfg.get("classify_tiebreak", False)),
    }
    wanted = bool(file_cfg.get("enabled", False))
    if env.get("LLM_ENABLED", "").strip().lower() in ("0", "false", "off", "no"):
        wanted = False  # LLM_ENABLED=0: rules only (gate, tests, offline runs)
    if _FORCED is not None:
        wanted = _FORCED
    cfg["enabled"] = wanted and bool(cfg["api_key"] and cfg["base_url"] and cfg["model"])
    if wanted and not cfg["enabled"]:
        log.warning("LLM requested but LLM_BASE_URL / LLM_MODEL / LLM_API_KEY are not all set: rules only")
    return cfg


CALLS = {"ok": 0, "failed": 0}  # per run, for the CLI summary
_REASON = ""  # why _DOWN was set by disable() (shown in the summary)
_DOWN = False  # circuit breaker: after a call fails on every attempt (network down, 401/429), stop asking for this run


def enabled() -> bool:
    return settings()["enabled"] and not _DOWN


def _post(url: str, payload: dict[str, Any], key: str, timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


TRANSPORT: Callable[[str, dict[str, Any], str, float], dict[str, Any]] = _post  # swapped in tests


def _valid(value: Any, schema: dict[str, Any]) -> bool:
    if value is None:
        return True
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), None)
    ok = {"string": isinstance(value, str), "integer": isinstance(value, int) and not isinstance(value, bool),
          "number": isinstance(value, (int, float)) and not isinstance(value, bool)}.get(t, True)
    if ok and "enum" in schema:
        ok = value in schema["enum"]
    if ok and isinstance(value, str) and "pattern" in schema:
        ok = re.fullmatch(schema["pattern"], value) is not None
    return ok


_FENCE = re.compile(r"\A\s*```(?:json)?\s*|\s*```\s*\Z", re.IGNORECASE)
_REFUSED = 0  # consecutive questions the endpoint refused as malformed (HTTP 400/422) even with the relaxed schema
_REFUSED_LIMIT = 3


def _answer(content: Any) -> Any:
    """The `value` of the model's JSON answer; tolerates a markdown fence around it (```json … ```)."""
    if isinstance(content, str):
        content = json.loads(_FENCE.sub("", content))
    return content["value"]


def ask(question: str, text: str, schema: dict[str, Any]) -> Any:
    """Ask for one value. Returns None when off, on error, on invalid output, or when the model says null."""
    cfg = settings()
    if not enabled():  # off, or the circuit breaker is open
        return None
    value_schema = {**schema}
    if "null" not in (value_schema.get("type") if isinstance(value_schema.get("type"), list) else [value_schema.get("type")]):
        value_schema["type"] = [value_schema.get("type", "string"), "null"]
    payload = {
        "model": cfg["model"],
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "Wyodrębniasz dane z polskich dokumentów urzędowych. Odpowiadasz wyłącznie JSON-em "
                                          "zgodnym ze schematem. Jeśli informacji nie ma w tekście, zwróć null. Nie zgaduj."},
            {"role": "user", "content": f"{question}\n\nTekst dokumentu:\n<<<\n{text[: cfg['max_chars']]}\n>>>"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "answer", "strict": True, "schema": {
                "type": "object", "properties": {"value": value_schema}, "required": ["value"], "additionalProperties": False}},
        },
    }
    global _DOWN, _WAITED, _REFUSED
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    failures = 0  # every failed call (for the summary)
    hard = 0  # failed attempts that were not rate limits: both attempts failing trips the circuit breaker
    refused = 0  # HTTP 400/422: the endpoint refuses THIS request, it is not down
    attempt = 0
    while attempt < 2:  # one retry; rate limits (429/503) are waited out and do not count as attempts
        try:
            data = TRANSPORT(url, payload, cfg["api_key"], cfg["timeout_s"])
            CALLS["ok"] += 1
            _REFUSED = 0
            try:
                value = _answer(data["choices"][0]["message"]["content"])
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                # a malformed answer to one question says nothing about the service: never trips the breaker
                log.warning("LLM answer unreadable (attempt %d): %s", attempt + 1, exc)
                attempt += 1
                continue
            if _valid(value, schema):
                return value
            log.info("LLM returned a value outside the schema: %r", value)
            attempt += 1
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                log.warning("LLM rejected the API key (HTTP %s): rules only for the rest of this run", exc.code)
                CALLS["failed"] += 1
                _DOWN = True
                return None
            if exc.code in (400, 422):
                # e.g. an endpoint that does not accept `pattern` under strict mode, or an over-long prompt.
                # Resend once without strict mode and without `pattern`; _valid() still checks the answer locally.
                log.warning("LLM refused the request (HTTP %s, attempt %d): retrying with a relaxed schema", exc.code, attempt + 1)
                js = payload["response_format"]["json_schema"]
                js["strict"] = False
                js["schema"]["properties"]["value"] = {k: v for k, v in value_schema.items() if k != "pattern"}
                failures += 1
                refused += 1
                attempt += 1
                continue
            wait = _retry_after(exc, failures)
            if exc.code in (429, 503) and wait is not None and _WAITED + wait <= MAX_RATE_WAIT_S:
                log.info("LLM HTTP %s: waiting %.0fs (rate limit)", exc.code, wait)
                _WAITED += wait
                failures += 1
                time.sleep(wait)
                continue
            log.warning("LLM call failed (attempt %d): HTTP %s", attempt + 1, exc.code)
            failures += 1
            hard += 1
            attempt += 1
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, IndexError, TypeError, ValueError) as exc:
            log.warning("LLM call failed (attempt %d): %s", attempt + 1, exc)
            failures += 1
            hard += 1
            attempt += 1
            time.sleep(0.5 * attempt)
    CALLS["failed"] += failures
    if refused >= 2:
        _REFUSED += 1
    if hard >= 2 or _REFUSED >= _REFUSED_LIMIT:
        _DOWN = True
        log.warning("LLM unavailable: rules only for the rest of this run")
    return None


MAX_RATE_WAIT_S = 300.0  # total time a run may spend waiting out rate limits (UZP: waiting does not lower the score)
_WAITED = 0.0


def _retry_after(exc: urllib.error.HTTPError, n: int) -> float | None:
    """Seconds to wait: the Retry-After header (capped at 30 s), else 2/4/8 s; None after 4 rate-limit waits."""
    if n >= 4:
        return None
    try:
        header = float(exc.headers.get("Retry-After", "")) if exc.headers else None
    except (TypeError, ValueError):
        header = None
    return min(30.0, header) if header is not None and header >= 0 else float(2 ** (n + 1))


def disable(reason: str) -> None:
    """Stop asking the model for the rest of the run (e.g. the time budget is at risk)."""
    global _DOWN, _REASON
    if not _DOWN:
        _DOWN, _REASON = True, reason


def summary() -> str:
    """One line for the end of a run: whether the model was used, how often, and why not (never the key)."""
    cfg = settings()
    if not cfg["enabled"]:
        return "LLM: wyłączony (tylko reguły)"
    state = (f" — wyłączony ({_REASON}), dokończono na regułach" if _REASON else
             " — niedostępny, dokończono na regułach") if _DOWN else ""
    return f"LLM: {cfg['model']} @ {cfg['base_url']}: {CALLS['ok']} wywołań, {CALLS['failed']} nieudanych{state}"
