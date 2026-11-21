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
    assert not llm.enabled()  # circuit breaker: no more calls (and no more timeouts) in this run
    llm.force(True)
    assert llm.enabled()


APPEAL_WITHOUT_KNOWN_ACTION = """Warszawa, dnia 1 marca 2026 r.
Prezes Krajowej Izby Odwoławczej
Odwołujący:
Alfa sp. z o.o.
Zamawiający:
Gmina Beta
dotyczy: postępowania pn. „Dostawa sprzętu biurowego dla urzędu”, nr referencyjny: ZP.1.2026
ODWOŁANIE
Działając w imieniu Odwołującego wnoszę odwołanie wobec czynności, o której mowa poniżej.
Zarzut nr 1 – naruszenia art. 16 Pzp w zakresie postanowień umowy, termin 27.02.2026."""


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
    answers += [{"value": None}, {"value": "projektowane postanowienia umowy"}]
    out = extract(Document(Path("x.pdf"), [APPEAL_WITHOUT_KNOWN_ACTION]), CLS["odwolanie"])
    assert out["OdwolanieKIO"]["czynnosc_powod_id"] == 12
    q = calls[1]
    enum = q["response_format"]["json_schema"]["schema"]["properties"]["value"]["enum"]
    assert "zaniechanie wykluczenia wykonawcy" in enum and all(isinstance(e, str) for e in enum)
    assert len(q["messages"][1]["content"].split("<<<\n", 1)[1]) <= 1500 + 4


def test_classification_tiebreak_off_by_default(fake):
    """Rules classify perfectly; the grey-zone model is opt-in (classify_tiebreak) and may only veto."""
    from odw import classify as C
    calls, answers = fake
    answers += [{"value": "odwolanie"}]
    assert C._llm_tiebreak("x", list(CLS.values()), {n: 0.0 for n in CLS}) is C._UNDECIDED
    assert calls == []


def test_title_must_be_quoted_verbatim(fake):
    from odw.fields import Context, extract_field
    calls, answers = fake
    spec = {"type": "llm", "question": "q", "verbatim": True}
    answers += [{"value": "Budowa drogi"}, {"value": "Remont szkoły"}]
    ctx = Context("Zamówienie pn. „Budowa  drogi” w gminie.", {})
    assert extract_field([spec], ctx) == "Budowa drogi"
    assert extract_field([spec], ctx) is None


def test_reason_without_evidence_and_date_not_in_text_are_rejected(fake):
    from odw.fields import Context, extract_field
    calls, answers = fake
    reason = {"type": "llm", "question": "q", "choices": {"wykluczenie wykonawcy": 3, "odrzucenie oferty": 1},
              "evidence": {3: ["wyklucz"], 1: ["odrzuc"]}}
    ctx = Context("Zarzucam zaniechanie odrzucenia oferty z dnia 3 marca 2025 r.", {})
    answers += [{"value": "wykluczenie wykonawcy"}, {"value": "odrzucenie oferty"}]
    assert extract_field([reason], ctx) is None  # nothing about exclusion in the passage
    assert extract_field([reason], ctx) == 1
    date = {"type": "llm", "question": "q", "value": "date", "date_in_text": True}
    answers += [{"value": "2025-03-04"}, {"value": "2025-03-03"}]
    assert extract_field([date], ctx) is None
    assert extract_field([date], ctx) == "2025-03-03"


def test_gate_and_tests_ignore_dotenv_key(monkeypatch):
    monkeypatch.setattr(llm, "_dotenv", lambda path=None: {"LLM_BASE_URL": "u", "LLM_MODEL": "m", "LLM_API_KEY": "k"})
    llm.force(None)
    assert not llm.enabled()  # conftest sets LLM_ENABLED=0


def test_act_date_must_precede_the_letter(fake):
    from odw.fields import Context, extract_field
    calls, answers = fake
    ctx = Context("Pismo z dnia 12.03.2025. Czynność z dnia 03.03.2025.", {})
    ctx.values["OdwolanieKIO.data"] = "2025-03-12"
    spec = {"type": "llm", "question": "q", "value": "date", "before_field": "OdwolanieKIO.data"}
    answers += [{"value": "2025-03-12"}, {"value": "2025-03-03"}]
    assert extract_field([spec], ctx) is None  # the letter's own date
    assert extract_field([spec], ctx) == "2025-03-03"


def _http(code, retry_after=None):
    import email.message
    import urllib.error

    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = str(retry_after)
    return urllib.error.HTTPError("https://example.invalid", code, "x", headers, None)


def test_rate_limit_is_waited_out(fake, monkeypatch):
    slept = []
    monkeypatch.setattr(llm.time, "sleep", slept.append)
    _, answers = fake
    answers += [_http(429, 3), _http(503), {"value": "ok"}]
    assert llm.ask("q", "t", {"type": "string"}) == "ok"
    assert slept == [3.0, 4.0] and llm.enabled()


def test_bad_key_trips_breaker_at_once(fake):
    calls, answers = fake
    answers += [_http(401)]
    assert llm.ask("q", "t", {"type": "string"}) is None
    assert len(calls) == 1 and not llm.enabled()


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
def test_dotenv_saved_on_windows(tmp_path, encoding):
    env = tmp_path / ".env"
    env.write_bytes("LLM_API_KEY=abc\r\nLLM_MODEL=m\r\n".encode(encoding))
    assert llm._dotenv(env) == {"LLM_API_KEY": "abc", "LLM_MODEL": "m"}


def test_fenced_json_answer_is_read(fake, monkeypatch):
    calls, _ = fake
    monkeypatch.setattr(llm, "TRANSPORT", lambda *a: {"choices": [{"message": {"content": '```json\n{"value": "abc"}\n```'}}]})
    assert llm.ask("q", "t", {"type": "string"}) == "abc"


def test_unreadable_answer_does_not_open_the_breaker(fake, monkeypatch):
    monkeypatch.setattr(llm, "TRANSPORT", lambda *a: {"choices": [{"message": {"content": '{"value": "trunc'}}]})
    assert llm.ask("q", "t", {"type": "string"}) is None
    assert llm.enabled()  # one document's malformed answer must not switch the model off for the whole run


def test_schema_refused_with_400_is_resent_relaxed(fake):
    calls, answers = fake
    answers += [_http(400), {"value": "2026-03-12"}]
    assert llm.ask("q", "t", {"type": "string", "pattern": r"\d{4}-\d{2}-\d{2}"}) == "2026-03-12"
    js = calls[1]["response_format"]["json_schema"]
    assert js["strict"] is False and "pattern" not in js["schema"]["properties"]["value"]
    answers += [_http(400), {"value": "12 marca"}, {"value": "12 marca"}]  # the pattern is still enforced locally
    assert llm.ask("q", "t", {"type": "string", "pattern": r"\d{4}-\d{2}-\d{2}"}) is None
    assert llm.enabled()


def test_breaker_opens_after_repeated_refusals_and_on_auth_errors(fake):
    _, answers = fake
    for _ in range(2):
        answers += [_http(400), _http(400)]
        assert llm.ask("q", "t", {"type": "string"}) is None
        assert llm.enabled()
    answers += [_http(400), _http(400)]
    assert llm.ask("q", "t", {"type": "string"}) is None
    assert not llm.enabled()  # three questions in a row refused: the endpoint cannot be used
    llm.force(True)
    answers += [_http(401), _http(401)]
    assert llm.ask("q", "t", {"type": "string"}) is None
    assert not llm.enabled()


def test_ask_respects_the_open_breaker(fake):
    calls, answers = fake
    answers += [OSError("down"), OSError("down")]
    assert llm.ask("q", "t", {"type": "string"}) is None
    n = len(calls)
    assert llm.ask("q", "t", {"type": "string"}) is None and len(calls) == n  # no request once the breaker is open
