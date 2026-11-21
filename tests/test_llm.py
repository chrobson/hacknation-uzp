"""LLM fallback: off by default, validated output, never raises, used only when rules give nothing."""

import json
from pathlib import Path

import pytest

from odw import llm
from odw.config import load_classes
from odw.pipeline import extract
from odw.textio import Document

CLS = {c.name: c for c in load_classes()}


@pytest.fixture
def fake(monkeypatch):
    calls = []
    answers = []

    def transport(url, payload, key, timeout):
        calls.append(payload)
        a = answers.pop(0) if answers else {"value": None}
        if isinstance(a, Exception):
            raise a
        return {"choices": [{"message": {"content": json.dumps(a)}}]}

    monkeypatch.setattr(llm, "TRANSPORT", transport)
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    for k, v in {"LLM_BASE_URL": "https://example.invalid/v1", "LLM_MODEL": "m", "LLM_API_KEY": "k"}.items():
        monkeypatch.setenv(k, v)
    llm.force(True)
    yield calls, answers
    llm.force(None)


def test_off_by_default_without_key(monkeypatch):
    for k in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(llm, "_dotenv", lambda path=None: {})
    llm.force(None)
    assert not llm.enabled()
    assert llm.ask("q", "t", {"type": "string"}) is None


def test_valid_answer_and_schema_rejection(fake):
    calls, answers = fake
    answers += [{"value": 7}]
    assert llm.ask("q", "t", {"type": "integer", "enum": [1, 7]}) == 7
    answers += [{"value": 99}, {"value": 98}]  # outside the enum twice → None after one retry
    assert llm.ask("q", "t", {"type": "integer", "enum": [1, 7]}) is None
    assert calls[0]["temperature"] == 0 and calls[0]["response_format"]["type"] == "json_schema"


def test_network_error_never_raises(fake):
    _, answers = fake
    answers += [OSError("down"), OSError("still down")]
    assert llm.ask("q", "t", {"type": "string"}) is None


APPEAL_WITHOUT_KNOWN_ACTION = """Warszawa, dnia 1 marca 2026 r.
Prezes Krajowej Izby Odwoławczej
Odwołujący:
Alfa sp. z o.o.
Zamawiający:
Gmina Beta
dotyczy: postępowania pn. „Dostawa sprzętu biurowego dla urzędu”, nr referencyjny: ZP.1.2026
ODWOŁANIE
Działając w imieniu Odwołującego wnoszę odwołanie wobec czynności, o której mowa poniżej.
Zarzut nr 1 – naruszenia art. 16 Pzp."""


def test_llm_fills_only_fields_rules_could_not(fake):
    calls, answers = fake
    answers += [{"value": "2026-02-27"}, {"value": "projektowane postanowienia umowy"}]  # czynnosc_dzien, then czynnosc_powod_id
    out = extract(Document(Path("x.pdf"), [APPEAL_WITHOUT_KNOWN_ACTION]), CLS["odwolanie"])
    assert out["OdwolanieKIO"]["czynnosc_dzien"] == "2026-02-27"
    assert out["OdwolanieKIO"]["czynnosc_powod_id"] == 12
    assert out["OdwolanieKIO"]["czynnosc_opis"] == "Projektowane postanowienia umowy"
    assert out["ZamowieniePubliczne"]["tytul"] == "Dostawa sprzętu biurowego dla urzędu"  # rule hit → no LLM call
    assert len(calls) == 2
    sent = calls[0]["messages"][1]["content"]
    assert "Zarzut nr 1" in sent and "Odwołujący:" not in sent  # only the relevant fragment is sent


def test_rules_only_mode_makes_no_calls(monkeypatch):
    llm.force(False)
    monkeypatch.setattr(llm, "TRANSPORT", lambda *a: (_ for _ in ()).throw(AssertionError("called")))
    out = extract(Document(Path("x.pdf"), [APPEAL_WITHOUT_KNOWN_ACTION]), CLS["odwolanie"])
    assert out["OdwolanieKIO"]["czynnosc_powod_id"] is None
    llm.force(None)


def test_reason_asks_with_word_labels_on_first_charge_only(fake):
    """Small models pick word labels, not numbers; the model sees at most 1500 characters of the first charge."""
    calls, answers = fake
    answers += [{"value": None}, {"value": "zaniechanie wykluczenia wykonawcy"}]
    out = extract(Document(Path("x.pdf"), [APPEAL_WITHOUT_KNOWN_ACTION]), CLS["odwolanie"])
    assert out["OdwolanieKIO"]["czynnosc_powod_id"] == 8
    q = calls[1]
    enum = q["response_format"]["json_schema"]["schema"]["properties"]["value"]["enum"]
    assert "zaniechanie wykluczenia wykonawcy" in enum and all(isinstance(e, str) for e in enum)
    assert len(q["messages"][1]["content"].split("<<<\n", 1)[1]) <= 1500 + 4
