"""Bank transfer confirmations in layouts beyond the training set (invented texts, not copies of data files)."""

from pathlib import Path

import pytest

from odw.classify import score
from odw.config import load_class, load_classes
from odw.fields import Context, extract_field

CLS = load_class(Path(__file__).resolve().parents[1] / "config" / "classes" / "przelew.yaml")
FIELDS = CLS.raw["fields"]


def get(text: str, field: str):
    return extract_field(FIELDS[f"przelew_bankowy.{field}"], Context(text, CLS.raw))


TITLE_FIRST = """BANK PRZYKŁADOWY
Tytuł operacji
opłata skarbowa od pełnomocnictwa w sprawie
ZP.1.2026 ABC1234567890
PLN 17,00
zrealizowano 03-02-2026
numer transakcji ABC1234567890
Rachunek obciążony: PL61109010140000071219812874 (Alfa sp. z o.o.)
Rachunek uznany: PL27114020040000300201355387 (Beta S.A.)
Wydruk: 2026-02-05 10:00"""

GRID = """Szczegóły przelewu
Rachunek nadawcy PL 61 1090 1014 0000 0712 1981 2874
Data księgowania 2026-03-04
Wpis od odwołania w postępowaniu
Tytuł przelewu ZP/7/2026, zamawiający: Gmina
Przykładowo
Kwota przelewu 7 500,00 PLN
Numer operacji XYZ0000012345"""

ENGLISH = """PAYMENT CONFIRMATION
Ordering party Alfa sp. z o.o.
Debit account PL 61 1090 1014 0000 0712 1981 2874
Beneficiary Beta S.A.
Beneficiary account (IBAN) PL 27 1140 2004 0000 3002 0135 5387
Amount 34,00 PLN
Value date 2026-05-06
Payment details Opłata skarbowa za pełnomocnictwo
Transaction ID ABC2605000000001
Status Executed
Fee 0.00 PLN"""

STATEMENT = """WYCIĄG Z RACHUNKU BANKOWEGO nr 1/2026
Numer rachunku: PL61109010140000071219812874
Data Data Opis operacji Kwota Saldo
księg. waluty
Saldo początkowe 123 456,78
07/01/2026 07/01/2026 PRZELEW WYCHODZĄCY -100,00 123 356,78
Odbiorca: Beta S.A.
Rachunek odbiorcy: PL27114020040000300201355387
Tytuł: opłata skarbowa od pełnomocnictwa
Nr transakcji: ABC2601000000002
Saldo końcowe 123 356,78"""


@pytest.mark.parametrize("text", [TITLE_FIRST, GRID, ENGLISH, STATEMENT])
def test_layout_is_classified_as_transfer(text):
    scores = {c.name: score(c, text) for c in load_classes()}
    assert scores["przelew"] >= CLS.threshold
    assert scores["przelew"] == max(scores.values())


def test_invoice_without_heading_is_not_a_transfer():
    text = """Dokument sprzedaży 12/2026
Sprzedawca: Alfa sp. z o.o.   Nabywca: Beta S.A.
Termin płatności: 14 dni, przelewem na rachunek PL61109010140000071219812874
Tytułem: 12/2026
Do zapłaty: 1 230,00 PLN"""
    assert score(CLS, text) < CLS.threshold


def test_title_first_layout():
    assert get(TITLE_FIRST, "kwota") == 17.0
    assert get(TITLE_FIRST, "data_operacji") == "2026-02-03"
    assert get(TITLE_FIRST, "tytul") == "opłata skarbowa od pełnomocnictwa w sprawie ZP.1.2026 ABC1234567890"
    assert get(TITLE_FIRST, "z_rachunku") == "61109010140000071219812874"


def test_grid_label_in_the_middle_of_wrapped_value():
    assert " ".join(get(GRID, "tytul").split()) == "Wpis od odwołania w postępowaniu ZP/7/2026, zamawiający: Gmina Przykładowo"
    assert get(GRID, "kwota") == 7500.0


def test_english_layout():
    assert get(ENGLISH, "kwota") == 34.0
    assert get(ENGLISH, "data_operacji") == "2026-05-06"
    assert get(ENGLISH, "tytul") == "Opłata skarbowa za pełnomocnictwo"
    assert get(ENGLISH, "z_rachunku") == "61109010140000071219812874"
    assert get(ENGLISH, "na_rachunek") == "27114020040000300201355387"


def test_statement_takes_the_operation_not_the_balance():
    assert get(STATEMENT, "kwota") == 100.0
    assert get(STATEMENT, "data_operacji") == "2026-01-07"
    assert get(STATEMENT, "tytul") == "opłata skarbowa od pełnomocnictwa"


def test_layout_independent_fallbacks():
    text = "Przelew zrealizowany dnia 9 marca 2026 na kwotę 250 zł, nr ref ABC2603000000003. Wydrukowano 10.03.2026."
    assert get(text, "kwota") == 250.0
    assert get(text, "data_operacji") == "2026-03-09"
    assert get(text, "numer_transakcji") == "ABC2603000000003"
