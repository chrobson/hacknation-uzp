"""Extensibility: a new document class defined only in YAML (examples/klasy), loaded with --classes-dir."""

import json
from pathlib import Path

from odw.__main__ import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "klasy"


def test_new_class_from_yaml_only(tmp_path):
    out = tmp_path / "out"
    assert main(["--classes-dir", str(EXAMPLES), "--input", str(EXAMPLES / "przyklady"), "--output", str(out)]) == 0
    data = json.loads((out / "sprawa1" / "pismo_kio.json").read_text(encoding="utf-8"))
    assert data == {
        "WezwanieKIO": {
            "sygnatura": "KIO 1234/26",
            "data": "2026-10-12",
            "adresat": "Belmoria Rozwiązania S.A.",
            "termin_dni": 3,
            "kwota_wpisu": 5000.0,
            "braki": "brak dowodu uiszczenia brakującej części wpisu w kwocie 5 000,00 zł oraz brak odpisu pełnomocnictwa.",
        }
    }


def test_without_the_flag_the_document_is_not_an_appeal(tmp_path):
    out = tmp_path / "out"
    main(["--input", str(EXAMPLES / "przyklady"), "--output", str(out)])
    assert json.loads((out / "sprawa1" / "pismo_kio.json").read_text(encoding="utf-8")) == {}
