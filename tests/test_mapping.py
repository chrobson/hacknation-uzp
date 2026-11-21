"""Export mapping (config/mappings/*.yaml): one CSV row per case, never inside output/."""

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from odw.__main__ import main
from odw.mapping import export, load_mapping, rows


def _result(path, cls, data):
    return SimpleNamespace(source=Path(path), verdict=SimpleNamespace(name=cls), data=data)


CASES = {"sprawa_1": {"odwolanie": [{"Odwolujacy": [{"nazwa": "A sp. z o.o."}, {"nazwa": "B S.A."}]}],
                      "przelew": [{"przelew_bankowy": {"kwota": 17.0}}, {"przelew_bankowy": {"kwota": 15000.0}}]}}


def test_columns_join_and_default():
    spec = {"columns": [{"column": "Sprawa", "path": "_sprawa"},
                        {"column": "Odw", "path": "odwolanie.Odwolujacy[*].nazwa", "join": " | "},
                        {"column": "Pierwszy", "path": "odwolanie.Odwolujacy[*].nazwa"},
                        {"column": "Kwoty", "path": "przelew.przelew_bankowy.kwota", "join": " + "},
                        {"column": "Brak", "path": "pelnomocnictwo.pelnomocnicy[*].imie_nazwisko", "default": "-"}]}
    assert rows(spec, CASES, {}) == [["Sprawa", "Odw", "Pierwszy", "Kwoty", "Brak"],
                                     ["sprawa_1", "A sp. z o.o. | B S.A.", "A sp. z o.o.", "17.0 + 15000.0", "-"]]


def test_export_one_row_per_case_excel_friendly(tmp_path):
    results = [_result("in/s1/a.pdf", "odwolanie", {"Odwolujacy": [{"nazwa": "Żółw sp. z o.o."}]}),
               _result("in/s2/b.pdf", "odwolanie", {"Odwolujacy": [{"nazwa": "B"}]}),
               _result("in/neg/c.pdf", None, {})]
    target = export("rejestr_kio", results, Path("in"), tmp_path)
    raw = target.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")  # BOM: Excel shows Polish diacritics
    table = list(csv.reader(raw.decode("utf-8-sig").splitlines(), delimiter=";"))
    assert len(table) == 3 and table[1][0] == "s1" and "Żółw sp. z o.o." in table[1]


def test_unknown_mapping_and_exports_inside_output_refused(tmp_path):
    with pytest.raises(SystemExit, match="rejestr_kio"):
        load_mapping("nie_ma_takiego")
    (tmp_path / "in").mkdir()
    out = tmp_path / "out"
    assert main(["--input", str(tmp_path / "in"), "--output", str(out), "--map", "rejestr_kio",
                 "--exports", str(out / "exports"), "--no-evidence"]) == 2
