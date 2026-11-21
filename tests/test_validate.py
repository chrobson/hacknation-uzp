"""Field validators configured in YAML (`validate:`): warn-only, never change the extracted data."""

import copy

import pytest

from odw.config import CLASSES_DIR, load_class
from odw.validate import CHECKS, config_errors, validate


def test_checksums_accept_valid_and_reject_typos():
    assert CHECKS["nip"]("526-000-12-46", {}) is None          # NIP with dashes, valid checksum
    assert CHECKS["nip"]("5260001247", {}) is not None
    assert CHECKS["regon"]("012100784", {}) is None
    assert CHECKS["regon"]("012100785", {}) is not None
    assert CHECKS["pesel"]("44051401359", {}) is None
    assert CHECKS["iban_pl"]("PL60101010100081362231000000", {}) is None  # UZP fee account
    assert CHECKS["iban_pl"]("60101010100081362231000001", {}) is not None
    assert CHECKS["krs"]("0000012345", {}) is None and CHECKS["krs"]("12345", {}) is not None


def test_parametrised_checks():
    assert CHECKS["amount_range"](17.0, {"min": 1, "max": 100000}) is None
    assert CHECKS["amount_range"](0.0, {"min": 1}) is not None
    assert CHECKS["date_not_future"]("2999-01-01", {}) is not None
    assert CHECKS["date_not_future"]("2010-01-01", {"not_before": "2016-07-28"}) is not None
    assert CHECKS["enum"]("osoba_prawna", {"values": ["osoba_prawna"]}) is None
    assert CHECKS["regex"]("2026/BZP00999778", {"pattern": r"\d{4}/BZP\d{8}"}) is None


def test_validate_walks_lists_and_never_mutates():
    data = {"Odwolujacy": [{"nip": "5260001246"}, {"nip": "123"}, {"nip": None}]}
    before = copy.deepcopy(data)
    out = validate(data, {"Odwolujacy[*].nip": [{"check": "nip"}]})
    assert data == before
    assert [(r["path"], r["ok"]) for r in out] == [("Odwolujacy[0].nip", True), ("Odwolujacy[1].nip", False)]
    assert all(r["action"] == "warn" for r in out)


def test_unknown_check_is_a_config_error(tmp_path):
    assert config_errors({"x": [{"check": "nope"}]}) and config_errors({"x": [{"check": "regex"}]})
    src = (CLASSES_DIR / "przelew.yaml").read_text(encoding="utf-8")
    bad = tmp_path / "przelew.yaml"
    bad.write_text(src + "\n  przelew_bankowy.tytul: [{check: literowka}]\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="literowka"):
        load_class(bad)
