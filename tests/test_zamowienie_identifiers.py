"""Procurement title and identifiers in real-looking appeals: unquoted titles, ',,' quotes, quoted statutes,
unlabeled reference after the title, 'Dz.U./S' TED notation, spaced and pre-2021 BZP numbers."""

from pathlib import Path

import pytest

from odw.config import load_classes
from odw.pipeline import extract
from odw.textio import Document

CLS = {c.name: c for c in load_classes(Path(__file__).parents[1] / "config/classes")}["odwolanie"]
HEAD = ("Warszawa, 12 marca 2025 r.\nKrajowa Izba Odwoławcza\nul. Postępu 17a, 02-676 Warszawa\n\n"
        "Odwołujący:\nAlfa Budownictwo sp. z o.o.\nul. Prosta 5, 00-850 Warszawa\nNIP 5213456789\n\n"
        "Zamawiający:\nGmina Rudnik Wielki\nul. Rynek 1, 37-300 Rudnik\nNIP 8161234567\n\n")
BODY = ("\nODWOŁANIE\nDziałając w imieniu Odwołującego wnoszę odwołanie od czynności wyboru oferty najkorzystniejszej.\n"
        "Zgodnie z art. 513 ustawy „Odwołanie przysługuje wyłącznie od niezgodnej z przepisami ustawy czynności”.\n")
TITLE = "Budowa drogi gminnej w miejscowości Rudnik"


def zp(text):
    return extract(Document(Path("t.pdf"), [text]), CLS)["ZamowieniePubliczne"]


def test_quoted_statute_is_not_title():
    out = zp(HEAD + "Dotyczy: postępowania pn. " + TITLE + ", nr sprawy ZP.271.1.2025\n" + BODY)
    assert out["tytul"] == TITLE
    assert out["numer_postepowania"] == "ZP.271.1.2025"


def test_old_style_quote_and_unlabeled_reference():
    out = zp(HEAD + "Dotyczy: postępowania pn. ,," + TITLE + "” ZP/13/022/D/21\n" + BODY)
    assert out["tytul"] == TITLE
    assert out["numer_postepowania"] == "ZP/13/022/D/21"


@pytest.mark.parametrize("line,ted", [
    ("Ogłoszenie: Dz.U./S 43 03/03/2021 106827-2021-PL", "106827-2021"),
    ("Numer ogłoszenia: 108118-2025", "108118-2025"),
])
def test_ted_notations(line, ted):
    out = zp(HEAD + "Dotyczy: postępowania pn. „" + TITLE + "”\n" + line + "\n" + BODY)
    assert out["numer_ted"] == ted


@pytest.mark.parametrize("line,bzp", [
    ("Ogłoszenie nr 2023/BZP 021 13995", "2023/BZP02113995"),
    ("Ogłoszenie nr 522995-N-2020 z dnia 1.02.2020", "522995-N-2020"),
])
def test_bzp_notations(line, bzp):
    out = zp(HEAD + "Dotyczy: postępowania pn. „" + TITLE + "”\n" + line + "\n" + BODY)
    assert out["numer_bzp"] == bzp


def test_numer_sprawy_with_spaced_prefix():
    out = zp(HEAD + "Dotyczy: postępowania pn. „" + TITLE + "”, Numer sprawy: SP ZOZ ZSM/ZP/11/2020\n" + BODY)
    assert out["numer_postepowania"] == "SP ZOZ ZSM/ZP/11/2020"
