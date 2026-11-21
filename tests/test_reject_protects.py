"""The reject list guards the task's classes; a user-added class for a rejected document type still works."""

from pathlib import Path

import yaml

from odw.classify import classify
from odw.config import load_class, load_classes
from odw.textio import Document

INVOICE = """Faktura VAT nr FV/12/2026
Sprzedawca: Alfa sp. z o.o., NIP 5250000000
Nabywca: Gmina Beta
Razem do zapłaty: 1 230,00 PLN
"""
STAMP_DUTY = """Potwierdzenie realizacji przelewu
Z rachunku: 11 1111 1111 1111 1111 1111 1111
Na rachunek: 22 2222 2222 2222 2222 2222 2222
Odbiorca: Urząd Miasta Stołecznego Warszawy
Kwota: 17,00 PLN
Tytuł: Opł. skarb. za pełn. Jan Kowalski
"""


def _doc(text):
    return Document(path=Path("x.pdf"), pages=[text], words=[[]], sizes=[(595.0, 842.0)])


def test_rejected_type_stays_rejected_for_task_classes():
    assert classify(_doc(INVOICE), load_classes()).cls is None


def test_user_class_for_a_rejected_type_is_scored(tmp_path):
    (tmp_path / "faktura.yaml").write_text(yaml.safe_dump({
        "name": "faktura_vat",
        "classify": {"threshold": 2, "required": [r"^\s*Faktura"], "signals": [{"pattern": r"^\s*Faktura", "weight": 2}]},
        "output_template": {"Faktura": {"numer": None}},
        "fields": {"Faktura.numer": {"type": "pattern", "pattern": r"nr\s+(\S+)"}},
    }, allow_unicode=True), encoding="utf-8")
    classes = load_classes() + [load_class(tmp_path / "faktura.yaml")]
    assert classify(_doc(INVOICE), classes).name == "faktura_vat"


def test_abbreviated_stamp_duty_title_is_not_rejected():
    assert classify(_doc(STAMP_DUTY), load_classes()).name == "przelew"
