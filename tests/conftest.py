"""Tests measure the rules: never call a real LLM, even with a key in ./.env (tests that need one fake the transport)."""

import pytest

from odw import llm


@pytest.fixture(autouse=True)
def _rules_only(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "0")
    llm.force(None)
    yield
    llm.force(None)
