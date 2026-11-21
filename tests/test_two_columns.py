"""Two-column party header ("ODWOŁUJĄCY   ZAMAWIAJĄCY" side by side) is read column by column."""

import glob
from pathlib import Path

import pytest

from odw.textio import load_pdf

PDFS = glob.glob(str(Path(__file__).parents[1] / "data/synth/dev/odwolanie_026/*.pdf"))


@pytest.mark.skipif(not PDFS, reason="synth-dev not present")
def test_columns_are_not_interleaved():
    text = load_pdf(Path(PDFS[0])).text
    odw, zam = text.index("ODWOŁUJĄCY"), text.index("ZAMAWIAJĄCY")
    assert odw < text.index("Zarendel Automatyka sp. j.") < zam < text.index("Lubelskie Przedsiębiorstwo") < text.index("ODWOŁANIE")
    assert "Białystok Wodociągów" not in text  # no left+right line mixing
