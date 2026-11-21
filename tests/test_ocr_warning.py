"""Missing OCR must be loud: a run that leaves scans unread says so on stderr."""

from pathlib import Path

from odw import pipeline, textio
from odw.classify import Verdict


def test_unread_scans_are_reported(monkeypatch, capsys):
    monkeypatch.setattr(textio, "ocr_available", lambda: False)
    scan = textio.Document(Path("s.pdf"), [""])
    pipeline._warn_unread_scans([pipeline.Result(Path("s.pdf"), Verdict(None, {}), {}, scan)])
    assert "OCR NIEDOSTĘPNY: 1 skan" in capsys.readouterr().err


def test_no_warning_when_text_present(monkeypatch, capsys):
    monkeypatch.setattr(textio, "ocr_available", lambda: False)
    doc = textio.Document(Path("t.pdf"), ["Odwołanie " * 20])
    pipeline._warn_unread_scans([pipeline.Result(Path("t.pdf"), Verdict(None, {}), {}, doc)])
    assert capsys.readouterr().err == ""
