"""P1 normalisation: formats absent from train but plausible in the hidden test set."""

from pathlib import Path

import pytest

from odw.config import load_classes
from odw.normalize import find_amount, find_date
from odw.pipeline import extract
from odw.textio import Document

CLS = {c.name: c for c in load_classes()}


@pytest.mark.parametrize("text,expected", [("21 IX 2026", "2026-09-21"), ("3.XII.2025 r.", "2025-12-03"), ("21.07.2026 r.", "2026-07-21")])
def test_roman_months_and_r_suffix(text, expected):
    assert find_date(text) == expected


@pytest.mark.parametrize("text,expected", [("17 PLN", 17.0), ("PLN 200", 200.0), ("50,- zł", 50.0), ("1 200 zł", 1200.0), ("nr 17", None)])
def test_whole_amounts_next_to_currency(text, expected):
    assert find_amount(text) == expected


def _odw(dotyczy: bool, ted: str) -> dict:
    body = "dotyczy:\npostępowania pn. „Dostawa sprzętu biurowego dla urzędu”, " if dotyczy else "W postępowaniu pn. „Dostawa sprzętu biurowego dla urzędu”, "
    text = f"""Warszawa, dnia 28 września 2026 r.
Prezes Krajowej Izby Odwoławczej
Odwołujący:
Alfa Budownictwo sp. z o.o.
KRS: 0000 123 456, NIP: PL 123-456-78-90, REGON: 123 456 789
Zamawiający:
Gmina Beta
NIP: 987 654 32 10, REGON: 987654321
{body}ogłoszenie w BZP nr 2026/BZP 00123456/01, numer ogłoszenia TED: {ted}
ODWOŁANIE
Działając w imieniu Odwołującego wnoszę odwołanie. Zamawiający w dniu 21 IX 2026 r. odrzucił ofertę Odwołującego.
Zarzut nr 1 – bezpodstawnego odrzucenia oferty Odwołującego, tj. naruszenie art. 226 Pzp."""
    return extract(Document(Path("x.pdf"), [text]), CLS["odwolanie"])


@pytest.mark.parametrize("dotyczy", [True, False])
def test_identifiers_with_spaces_prefix_and_ted_zeros(dotyczy):
    out = _odw(dotyczy, "00364525-2025")
    odw, zam, zp = out["Odwolujacy"][0], out["Zamawiajacy"][0], out["ZamowieniePubliczne"]
    assert (odw["krs"], odw["nip"], odw["regon"]) == ("0000123456", "1234567890", "123456789")
    assert zam["nip"] == "9876543210"
    assert zp["numer_bzp"] == "2026/BZP00123456/01"
    assert zp["numer_ted"] == "364525-2025"
    assert out["OdwolanieKIO"]["czynnosc_dzien"] == "2026-09-21"
    assert out["OdwolanieKIO"]["czynnosc_powod_id"] == 1


def test_ted_official_journal_form():
    assert _odw(True, "2026/S 113-00999562")["ZamowieniePubliczne"]["numer_ted"] == "999562-2026"


def test_representative_without_professional_title():
    text = """PEŁNOMOCNICTWO
Alfa sp. z o.o., ul. Długa 1, 00-001 Warszawa, KRS 0000123456, NIP 1234567890,
niniejszym udziela pełnomocnictwa: Jan Nowak, PESEL 80010112345, do reprezentowania Mocodawcy.
............................................
Anna Kowalska
Prezes Zarządu"""
    out = extract(Document(Path("p.pdf"), [text]), CLS["pelnomocnictwo"])
    assert out["pelnomocnicy"] == [{"imie_nazwisko": "Jan Nowak", "pesel": "80010112345"}]
    assert out["mocodawca"][0]["podpisujacy"] == [{"imie_nazwisko": "Anna Kowalska"}]
    assert out["mocodawca"][0]["data"]["nazwa"] == "Alfa sp. z o.o."
