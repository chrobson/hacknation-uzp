"""P0-1: the batch never crashes; every PDF gets exactly one JSON; failures degrade, not abort."""

import json
import shutil
import time
from pathlib import Path

import pytest

from odw import fields, pipeline
from odw.__main__ import main
from odw.config import load_classes

DATA = Path(__file__).resolve().parents[1] / "data" / "train"
CLASSES = load_classes()
GOOD = DATA / "przyklad_07" / "potwierdzenie_przelewu.pdf"


def _case(tmp_path: Path, files: dict[str, bytes | Path]) -> Path:
    case = tmp_path / "input" / "case1"
    case.mkdir(parents=True)
    for name, content in files.items():
        if isinstance(content, Path):
            shutil.copy(content, case / name)
        else:
            (case / name).write_bytes(content)
    return tmp_path / "input"


def test_corrupt_empty_and_truncated_pdfs_yield_empty_json(tmp_path):
    truncated = GOOD.read_bytes()[:400]
    inp = _case(tmp_path, {"random.pdf": b"\x00garbage" * 50, "empty.pdf": b"", "truncated.pdf": truncated, "ok.pdf": GOOD})
    out = tmp_path / "output"
    assert main(["--input", str(inp), "--output", str(out)]) == 0
    written = sorted(p.name for p in (out / "case1").iterdir())
    assert written == ["empty.json", "ok.json", "random.json", "truncated.json"]
    for name in ("random.json", "empty.json", "truncated.json"):
        assert json.loads((out / "case1" / name).read_text()) == {}
    assert json.loads((out / "case1" / "ok.json").read_text())["przelew_bankowy"]["kwota"] == 50.0


def test_failing_field_keeps_other_fields(monkeypatch):
    def boom(spec, ctx):
        raise RuntimeError("simulated extractor bug")

    monkeypatch.setitem(fields.TYPES, "account", boom)
    result = pipeline.process_pdf(GOOD, CLASSES)
    data = result.data["przelew_bankowy"]
    assert data["z_rachunku"] is None and data["na_rachunek"] is None  # failed fields → null
    assert data["kwota"] == 50.0 and data["numer_transakcji"] == "CEN2607152350299"  # others survive


def test_timeout_during_extraction_keeps_partial_result(monkeypatch):
    def slow(spec, ctx):
        time.sleep(5)

    monkeypatch.setitem(fields.TYPES, "text_after_label", slow)  # tytul is extracted after kwota/date/ref
    t0 = time.time()
    result = pipeline.process_pdf(GOOD, CLASSES, timeout=0.5)
    assert time.time() - t0 < 3
    data = result.data["przelew_bankowy"]
    assert result.verdict.name == "przelew"
    assert data["kwota"] == 50.0 and data["tytul"] is None


def test_timeout_before_classification_yields_empty(monkeypatch):
    monkeypatch.setattr(pipeline, "load_pdf", lambda p: time.sleep(5))
    result = pipeline.process_pdf(GOOD, CLASSES, timeout=0.3)
    assert result.data == {} and result.verdict.cls is None


def test_output_contains_only_one_json_per_pdf(tmp_path):
    inp = _case(tmp_path, {"a.pdf": GOOD, "b b.pdf": DATA / "negatywne" / "KIO_KIO 2617-21.pdf"})
    out = tmp_path / "output"
    main(["--input", str(inp), "--output", str(out)])
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == ["case1/a.json", "case1/b b.json"]
