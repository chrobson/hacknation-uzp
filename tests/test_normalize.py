import pytest

from odw.fields import Context, _assign_accounts
from odw.normalize import find_amount, find_date, iban_valid


@pytest.mark.parametrize("text,expected", [
    ("2026-03-21", "2026-03-21"), ("17.02.2026", "2026-02-17"), ("04-07-2026", "2026-07-04"),
    ("23 sierpnia 2026", "2026-08-23"), ("1 października 2025 r.", "2025-10-01"), ("31.02.2026", None),
])
def test_find_date(text, expected):
    assert find_date(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("200,00 PLN", 200.0), ("17.00 PLN", 17.0), ("1 234,56 zł", 1234.56), ("1.234,56", 1234.56), ("brak", None),
])
def test_find_amount(text, expected):
    assert find_amount(text) == expected


def test_iban_checksum():
    assert iban_valid("61109010140000071219812874")
    assert not iban_valid("61109010140000071219812875")


CFG = {"sender_keywords": ["nadawc\\w*", "\\bz\\s+rachunku"], "receiver_keywords": ["beneficjent\\w*", "\\bna\\s+rachunek"]}
A, B = "1" * 26, "2" * 26


def test_accounts_by_nearest_keyword_in_prose():
    roles = _assign_accounts(f"w dniu z rachunku nr {A}, wykonano przelew na rachunek nr {B}.", CFG)
    assert roles == {"sender": A, "receiver": B}


def test_accounts_in_two_column_layout_follow_header_order():
    text = f"Beneficjent Nadawca\nFirma X Firma Y\nul. Długa 1 ul. Krótka 2 ul. Krótka 2 ul. Krótka 2\n{A} {B}\n"
    assert _assign_accounts(text, CFG) == {"receiver": A, "sender": B}
