"""Formal case check (config/case_rules.yaml): rules over all JSONs of one case folder."""

from odw.case_check import check_case, load_rules, summary_line

ODW = {"OdwolanieKIO": {"data": "2026-03-02", "czynnosc_dzien": "2026-02-16"},
       "Odwolujacy": [{"nazwa": "Silvatica Automatyka sp. k.", "pelnomocnik": {"imie_nazwisko": "Norbert Szulc"}}]}
POA = {"mocodawca": [{"data": {"nazwa": "SILVATICA Automatyka Sp. k."}}], "pelnomocnicy": [{"imie_nazwisko": "Norbert Szulc"}]}
FEE = {"przelew_bankowy": {"kwota": 15000.0, "na_rachunek": "PL60101010100081362231000000"}}
STAMP = {"przelew_bankowy": {"kwota": 17.0, "na_rachunek": "PL09460896147587484470692985"}}


def _status(report):
    return {r["id"]: r["status"] for r in report["rules"]}


def test_complete_case_passes_all_rules():
    report = check_case({"odwolanie": [ODW], "pelnomocnictwo": [POA], "przelew": [FEE, STAMP]}, load_rules())
    assert report["total"] == 5 and report["passed"] == 5, report
    assert summary_line("przyklad_x", report) == "przyklad_x: 5/5 OK"


def test_missing_power_of_attorney_makes_poa_rules_not_applicable():
    report = check_case({"odwolanie": [ODW], "przelew": [FEE]}, load_rules())
    st = _status(report)
    assert st["oplata_skarbowa_pelnomocnictwo"] == st["mocodawca_to_odwolujacy"] == st["pelnomocnik_zgodny"] == "n/a"
    assert st["wpis_na_rachunek_uzp"] == st["termin_odwolania"] == "ok"


def test_mismatches_are_reported():
    other = {**POA, "pelnomocnicy": [{"imie_nazwisko": "Jan Kowalski"}]}
    late = {**ODW, "OdwolanieKIO": {"data": "2026-04-30", "czynnosc_dzien": "2026-02-16"}}
    report = check_case({"odwolanie": [late], "pelnomocnictwo": [other], "przelew": [STAMP]}, load_rules())
    st = _status(report)
    assert st["pelnomocnik_zgodny"] == st["termin_odwolania"] == st["wpis_na_rachunek_uzp"] == "fail"
    assert "pełnomocnik nieumocowany" in summary_line("s", report)


def test_rules_are_data(tmp_path):
    f = tmp_path / "rules.yaml"
    f.write_text("rules:\n  - {id: r1, op: one_of_amounts, left: przelew.przelew_bankowy.kwota, values: [17]}\n", encoding="utf-8")
    assert check_case({"przelew": [STAMP]}, load_rules(f))["passed"] == 1
    f.write_text("rules:\n  - {id: r1, op: nieznany, left: x}\n", encoding="utf-8")
    import pytest
    with pytest.raises(SystemExit, match="nieznany"):
        load_rules(f)
