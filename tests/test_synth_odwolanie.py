"""Odwołanie: general rules (enumerated contested acts, party blocks without colon labels, near fallbacks)."""

from pathlib import Path

from odw.classify import classify
from odw.config import load_classes
from odw.pipeline import extract
from odw.textio import Document

CLS = {c.name: c for c in load_classes()}

HEAD = "Gdańsk, 12.03.2026 r.\nDo Prezesa Krajowej Izby Odwoławczej\nODWOŁANIE\n"
ACTS = (
    "Działając w imieniu Odwołującego wnoszę odwołanie wobec czynności i zaniechań Zamawiającego, polegających na:\n"
    "1) zaniechaniu odrzucenia oferty wykonawcy konkurencyjnego (02.03.2026 r.);\n"
    "2) czynności unieważnienia postępowania z dnia 01.03.2026 r.;\n"
    "Zarzut nr 1 – naruszenia art. 226 Pzp.\n"
)


def run(text: str) -> dict:
    doc = Document(Path("x.pdf"), [text])
    verdict = classify(doc, list(CLS.values()))
    assert verdict.name == "odwolanie"
    return extract(doc, CLS["odwolanie"])


def test_reason_and_date_come_from_first_enumerated_act():
    out = run(HEAD + "Odwołujący:\nAlfa Budownictwo sp. z o.o.\nZamawiający:\nGmina Rudnik Wielki\n" + ACTS)
    assert out["OdwolanieKIO"]["czynnosc_powod_id"] == 7
    assert out["OdwolanieKIO"]["czynnosc_dzien"] == "2026-03-02"


def test_party_synonyms_and_numbered_blocks():
    text = HEAD + (
        "1. Wykonawca wnoszący odwołanie\nAlfa Budownictwo sp. z o.o.\nul. Polna 1, 00-001 Warszawa\nNIP: 1234567890\n"
        "2. Instytucja zamawiająca\nGmina Rudnik Wielki\nul. Długa 2, 00-002 Rudnik\nNIP: 9990264287\n"
    ) + ACTS
    out = run(text)
    assert out["Odwolujacy"][0]["nazwa"] == "Alfa Budownictwo sp. z o.o."
    assert out["Odwolujacy"][0]["nip"] == "1234567890"
    assert out["Zamawiajacy"][0]["nazwa"] == "Gmina Rudnik Wielki"
    assert out["Zamawiajacy"][0]["nip"] == "9990264287"


def test_prose_parties_and_representative_without_blocks():
    text = HEAD + (
        "Odwołującym jest Alfa Budownictwo sp. z o.o. z siedzibą w Warszawie, NIP 1234567890, "
        "reprezentowana przez adw. Jan Nowak, Kancelaria Adwokacka Nowak, e-mail: jan@nowak.example.\n"
        "Odwołanie wnoszone jest przeciwko Zamawiającemu, którym jest Gmina Rudnik Wielki z siedzibą w Rudniku, "
        "NIP 9990264287.\n"
    ) + ACTS
    out = run(text)
    odw = out["Odwolujacy"][0]
    assert odw["nazwa"] == "Alfa Budownictwo sp. z o.o."
    assert odw["nip"] == "1234567890"
    assert odw["przez-pelnomocnika"] == 1
    assert odw["pelnomocnik"]["imie_nazwisko"] == "Jan Nowak"
    assert odw["pelnomocnik"]["mail"] == "jan@nowak.example"
    assert out["Zamawiajacy"][0]["nazwa"] == "Gmina Rudnik Wielki"
    assert out["Zamawiajacy"][0]["nip"] == "9990264287"


def test_appeal_addressed_to_kio_without_wnosze_phrase_is_classified():
    text = (
        "ODWOŁANIE DO PREZESA KRAJOWEJ IZBY ODWOŁAWCZEJ\nMiejscowość Poznań\nData sporządzenia 05/02/2026\n"
        "Odwołujący: Alfa Budownictwo sp. z o.o.\nZamawiający: Gmina Rudnik Wielki\nZarzuty: naruszenie art. 226 Pzp.\n"
    )
    out = run(text)
    assert out["OdwolanieKIO"]["miejscowosc"] == "Poznań"
    assert out["OdwolanieKIO"]["data"] == "2026-02-05"
