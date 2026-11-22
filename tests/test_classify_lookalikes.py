"""Foreign documents that look like ours are rejected; documents of our kinds are kept (also without case context)."""

from pathlib import Path

import pytest

from odw.classify import classify
from odw.config import load_classes
from odw.textio import Document

C = load_classes()

FOREIGN = {
    "general_poa": "PEŁNOMOCNICTWO OGÓLNE\nJa, Jan Kowalski, PESEL 80010112345, udzielam Annie Nowak pełnomocnictwa do reprezentowania "
                   "mnie przed urzędami skarbowymi i ZUS oraz do odbioru korespondencji.\nJan Kowalski\n",
}
OURS = {
    # a bank confirmation is a transfer whatever it pays for (real-dev: invoice and donation confirmations are GT przelew)
    "invoice_transfer": ("przelew", "Potwierdzenie wykonania przelewu\nData operacji: 2025-03-10\nZ rachunku: 12 1020 1026 0000 1502 0123 4567\n"
                        "Na rachunek: 45 1140 2004 0000 3202 7654 3210\nOdbiorca: Hurtownia Budowlana Gamma sp. z o.o.\n"
                        "Tytuł: zapłata za fakturę FV/123/2025\nKwota: 1 230,00 PLN\n"),
    "stamp_duty_transfer": ("przelew", "PAYMENT CONFIRMATION\nDebit account PL 07 1044 6255 1544 8206 2521 6547\nBeneficiary Ilystera sp. k.\n"
                            "Beneficiary account (IBAN) PL 62 8946 9818 4293 6305 7088 5696\nAmount 34,00 PLN\nValue date 2026-08-04\n"
                            "Payment details Opłata skarbowa za pełnomocnictwo - Cezary Marciniak, sprawa SWZ.429.2026\n"),
}


@pytest.mark.parametrize("name", FOREIGN)
def test_foreign_lookalike_rejected(name):
    assert classify(Document(Path(name), [FOREIGN[name]]), C).cls is None


@pytest.mark.parametrize("name", OURS)
def test_real_kind_kept(name):
    want, text = OURS[name]
    assert getattr(classify(Document(Path(name), [text]), C).cls, "name", None) == want
