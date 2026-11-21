"""OCR fallback for scans without a text layer (UZP added synthetic scans on 21.11)."""

from pathlib import Path

import pytest

from odw.config import load_classes
from odw.pipeline import process_pdf
from odw.textio import ocr_available

SCAN = Path(__file__).resolve().parents[1] / "data" / "scans" / "odwolania" / "0001" / "0001.pdf"
pytestmark = pytest.mark.skipif(not ocr_available(), reason="tesseract with the 'pol' model is not installed")


def test_scan_is_read_with_ocr_and_classified():
    result = process_pdf(SCAN, load_classes())
    assert result.doc.ocr and len(result.doc.pages) >= 1
    assert result.verdict.name == "odwolanie"
    odw = result.data["Odwolujacy"][0]
    assert odw["nip"] == "9992956550" and odw["krs"] == "9991022552"
    assert odw["pelnomocnik"]["mail"] == "a.rybak@rybak-kancelaria.example"  # '@' repaired after OCR


def test_ocr_words_have_boxes_in_pdf_points():
    result = process_pdf(SCAN, load_classes())
    width, height = result.doc.sizes[0]
    words = result.doc.words[0]
    assert words and all(0 <= w["x0"] < w["x1"] <= width + 1 and 0 <= w["top"] < w["bottom"] <= height + 1 for w in words)
