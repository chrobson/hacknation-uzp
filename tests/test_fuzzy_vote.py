"""OCR-only safety net: a scan whose exact anchors are broken by OCR errors is still classified by a fuzzy vote."""

from pathlib import Path

from odw.classify import classify
from odw.config import load_classes
from odw.textio import Document

C = load_classes()
BROKEN = ("0DWOŁANlE\nOdwołujqcy: Alfa sp. z o.o.\nZamawiajacy: Gmina Beta\nWnosze odwołanle od czynnosci, zarzucam naruszenle "
          "art. 226 ustawy, postepowania prowadzonego przez Zamawlającego; uzasadnlenie ponizej, zaniechanla odrzucenia " * 2)


def test_broken_ocr_appeal_recovered_only_for_scans():
    assert classify(Document(Path("x.pdf"), [BROKEN]), C).cls is None  # text PDF: rules only
    assert classify(Document(Path("x.pdf"), [BROKEN], ocr=True), C).cls.name == "odwolanie"


def test_vote_needs_the_heading():
    body = "NOTATKA SŁUŻBOWA\n" + "Spotkanie zespołu w sprawie budżetu i harmonogramu prac. " * 12 + BROKEN.replace("0DWOŁANlE\n", "")
    assert classify(Document(Path("x.pdf"), [body], ocr=True), C).cls is None
