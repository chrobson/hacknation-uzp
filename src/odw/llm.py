"""Optional LLM fallback over an OpenAI-compatible HTTP API (EU-hosted, open-weight model).

Off by default. On only when an API key is configured AND (config/llm.yaml `enabled: true` OR `--llm on`).
Never raises: any network/format problem returns None and the rule-based result stands.

Configuration (environment or ./.env):
    LLM_BASE_URL   e.g. https://api.eu.mistral.ai/v1
    LLM_MODEL      e.g. ministral-3b-2512
    LLM_API_KEY    secret, never committed
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
    global _FORCED
    _FORCED = enabled
    settings.cache_clear()


def _dotenv(path: Path = ROOT / ".env") -> dict[str, str]:
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
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
    }
    wanted = bool(file_cfg.get("enabled", False)) if _FORCED is None else _FORCED
    cfg["enabled"] = wanted and bool(cfg["api_key"] and cfg["base_url"] and cfg["model"])
    if wanted and not cfg["enabled"]:
        log.warning("LLM requested but LLM_BASE_URL / LLM_MODEL / LLM_API_KEY are not all set: rules only")
    return cfg


def enabled() -> bool:
    return settings()["enabled"]


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


def ask(question: str, text: str, schema: dict[str, Any]) -> Any:
    """Ask for one value. Returns None when off, on error, on invalid output, or when the model says null."""
    cfg = settings()
    if not cfg["enabled"]:
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
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    for attempt in range(2):  # one retry
        try:
            data = TRANSPORT(url, payload, cfg["api_key"], cfg["timeout_s"])
            content = data["choices"][0]["message"]["content"]
            value = json.loads(content)["value"] if isinstance(content, str) else content["value"]
            if _valid(value, schema):
                return value
            log.info("LLM returned a value outside the schema: %r", value)
        except (urllib.error.URLError, TimeoutError, OSError, KeyError, IndexError, TypeError, ValueError) as exc:
            log.warning("LLM call failed (attempt %d): %s", attempt + 1, exc)
            time.sleep(0.5 * (attempt + 1))
    return None
