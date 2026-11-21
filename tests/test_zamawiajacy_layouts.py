"""Contracting-authority block in appeals: role label after the data, prose, label-only lines, 'KRS pod numerem'."""

from pathlib import Path

import pytest

from odw.config import load_classes
from odw.pipeline import extract
from odw.textio import Document

CLS = {c.name: c for c in load_classes(Path(__file__).parents[1] / "config/classes")}["odwolanie"]
HEAD = "Warszawa, 12 marca 2025 r.\nKrajowa Izba Odwoławcza\nul. Postępu 17a, 02-676 Warszawa\n\n"
ODW = "Odwołujący:\nAlfa Budownictwo sp. z o.o.\nul. Prosta 5, 00-850 Warszawa\nKRS 0000123456, NIP 5213456789, REGON 146789012\n\n"
TAIL = ("\nODWOŁANIE\nod czynności Zamawiającego polegającej na wyborze oferty najkorzystniejszej w postępowaniu pn. "
        "„Budowa drogi gminnej nr 1”, nr ref. ZP.271.1.2025.\nDziałając w imieniu Odwołującego wnoszę odwołanie.\n")
GMINA = {"nazwa": "Gmina Rudnik Wielki", "nip": "8161234567", "regon": "690581234", "krs": None}

CASES = {
    "role_after_dash": ODW + "Gmina Rudnik Wielki\nul. Rynek 1, 37-300 Rudnik\nNIP 8161234567, REGON 690581234\n– Zamawiający\n",
    "role_after_dalej": "Alfa Budownictwo sp. z o.o. z siedzibą w Warszawie, KRS 0000123456, NIP 5213456789 (dalej: „Odwołujący”)\n\n"
                        "przeciwko\n\nGminie Rudnik Wielki z siedzibą w Rudniku, ul. Rynek 1, NIP 8161234567, REGON 690581234 "
                        "(dalej: „Zamawiający”)\n",
    "label_only_upper": ODW + "ZAMAWIAJĄCY\nGmina Rudnik Wielki\nul. Rynek 1, 37-300 Rudnik\nNIP 8161234567 REGON 690581234\n",
    "dane_zamawiajacego": ODW + "Dane Zamawiającego:\nGmina Rudnik Wielki\nul. Rynek 1, 37-300 Rudnik\nNIP 8161234567, REGON 690581234\n",
    "inline_parentheses": ODW + "Zamawiający – Gmina Rudnik Wielki (NIP 8161234567, REGON 690581234), ul. Rynek 1, 37-300 Rudnik\n",
    "przeciwko_dative": "Odwołanie Alfa Budownictwo sp. z o.o. (NIP 5213456789) przeciwko Zamawiającemu – Gminie Rudnik Wielki, "
                        "ul. Rynek 1, 37-300 Rudnik, NIP 8161234567, REGON 690581234.\n",
}


@pytest.mark.parametrize("name", CASES)
def test_authority_block(name):
    out = extract(Document(Path(name + ".pdf"), [HEAD + CASES[name] + TAIL]), CLS)
    (zam,) = out["Zamawiajacy"]
    assert {k: zam[k] for k in GMINA} == GMINA


def test_krs_pod_numerem():
    text = HEAD + ODW + ("Zamawiający:\nPolskie Koleje Państwowe S.A.\nul. Szczęśliwicka 62, 00-973 Warszawa\n"
                         "wpisana do rejestru przedsiębiorców KRS pod numerem 0000019193\nNIP 5260302703, REGON 000019193\n") + TAIL
    (zam,) = extract(Document(Path("pkp.pdf"), [text]), CLS)["Zamawiajacy"]
    assert zam["krs"] == "0000019193" and zam["nip"] == "5260302703"


def test_wrapped_prose_label_does_not_cut_the_act_section():
    """A prose line that wraps to just 'Zamawiający' must not open the authority section (it would end 'czynnosc')."""
    text = HEAD + ODW + "Zamawiający: Gmina Rudnik Wielki, NIP 8161234567\n" + TAIL + (
        "Zarzucam naruszenie art. 226 ust. 1 pkt 5 ustawy, poprzez zaniechanie odrzucenia oferty, w dniu 3 marca 2025 r.\n"
        "Zamawiający\npoinformował o wyborze oferty najkorzystniejszej.\n")
    base = extract(Document(Path("a.pdf"), [text.replace("Zamawiający\npoinformował", "Zamawiający poinformował")]), CLS)
    wrapped = extract(Document(Path("b.pdf"), [text]), CLS)
    assert wrapped["OdwolanieKIO"] == base["OdwolanieKIO"]
