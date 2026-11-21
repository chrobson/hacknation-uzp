"""Time budget: text PDFs first, every scan gets {} at once, OCR only while the budget lasts."""
import json
import shutil
from pathlib import Path

from odw.pipeline import run

ROOT = Path(__file__).resolve().parents[1]


def test_scans_keep_placeholder_when_budget_is_gone(tmp_path, monkeypatch):
    inp, out = tmp_path / "in", tmp_path / "out"
    inp.mkdir()
    shutil.copy(ROOT / "data/scans/potwierdzenia/0001/0001.pdf", inp / "skan.pdf")
    shutil.copy(ROOT / "data/train/przyklad_01/potwierdzenie_przelewu.pdf", inp / "tekst.pdf")
    monkeypatch.setenv("ODW_BUDGET_S", "0")
    results = run(inp, out)
    assert len(results) == 2
    assert json.loads((out / "skan.json").read_text()) == {}  # no OCR: budget exhausted
    assert json.loads((out / "tekst.json").read_text())["przelew_bankowy"]["kwota"] == 200.0
