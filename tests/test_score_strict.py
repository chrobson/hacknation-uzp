import json

import pytest

from eval.score_strict import FUZZY_FIELDS, Counts, evaluate, score_document, values_equal


def total(fc):
    return sum(fc.values(), Counts())


PRZELEW = {"przelew_bankowy": {"data_operacji": "2025-10-09", "kwota": 10000.0,
                               "na_rachunek": "60101010100081362231000000", "numer_transakcji": None,
                               "tytul": "WPIS OD ODWOŁANIA ZSCKR/822/2025 BUDOWA DROGI POŻAROWEJ",
                               "z_rachunku": "50802054600000588874424400"}}


def test_fuzzy_fields_are_the_official_five():
    assert FUZZY_FIELDS == sorted(["Odwolujacy[].nazwa", "Zamawiajacy[].nazwa", "Odwolujacy[].pelnomocnik.nazwa",
                                   "przelew_bankowy.tytul", "ZamowieniePubliczne.tytul"])


def test_perfect_przelew_tp_and_tn():
    fc = score_document(PRZELEW, json.loads(json.dumps(PRZELEW)))
    assert total(fc) == Counts(tp=5, tn=1)
    assert fc["przelew_bankowy.numer_transakcji"] == Counts(tn=1)


def test_fp_fn_definitions():
    pred = json.loads(json.dumps(PRZELEW))["przelew_bankowy"]
    pred["numer_transakcji"] = "X1"  # present only in output -> FP
    pred["kwota"] = 10.0  # wrong -> FP (not FN)
    pred["na_rachunek"] = None  # missing -> FN
    fc = score_document(PRZELEW, {"przelew_bankowy": pred})
    assert fc["przelew_bankowy.numer_transakcji"] == Counts(fp=1)
    assert fc["przelew_bankowy.kwota"] == Counts(fp=1)
    assert fc["przelew_bankowy.na_rachunek"] == Counts(fn=1)
    assert total(fc) == Counts(tp=3, fp=2, fn=1)


def test_missing_key_equals_null():
    pred = {"przelew_bankowy": {k: v for k, v in PRZELEW["przelew_bankowy"].items() if k != "numer_transakcji"}}
    assert total(score_document(PRZELEW, pred)) == Counts(tp=5, tn=1)


def test_fuzzy_threshold_only_on_long_fields():
    assert values_equal("fuzzy", "Filharmonia Pomorska im. I. J. Paderewskiego", "Filharmonia Pomorska im. I.J. Paderewskiego")
    assert not values_equal("fuzzy", "Filharmonia Pomorska", "Szpital Miejski w Gdańsku")
    assert not values_equal("text", "Jan Kowalski", "Jan Kowalsky")
    gt = {"przelew_bankowy": {"tytul": "Wpis od odwolania nr 1234"}}
    assert total(score_document(gt, {"przelew_bankowy": {"tytul": "Wpis od odwołania nr 1234"}})).tp == 1


def test_extra_keys_are_fp():
    pred = json.loads(json.dumps(PRZELEW))
    pred["przelew_bankowy"]["evidence"] = "page 1"
    pred["confidence"] = {"a": 0.9, "b": None}
    fc = score_document(PRZELEW, pred)
    assert total(fc) == Counts(tp=5, tn=1, fp=3)


def test_negative_document():
    assert total(score_document({}, {})) == Counts()
    fc = score_document({}, PRZELEW)
    assert total(fc) == Counts(fp=5, tn=1)


def test_wrong_class_counts_both_sides():
    odw = {"OdwolanieKIO": {"data": "2025-01-02", "czynnosc_powod_id": 4}}
    fc = score_document(odw, PRZELEW)
    t = total(fc)
    assert t.fp == 5 and t.fn == 2 and t.tp == 0


ODW = {
    "OdwolanieKIO": {"data": None, "czynnosc_dzien": "2025-10-01", "czynnosc_powod_id": 4,
                     "czynnosc_opis": "Publikacja specyfikacji warunków zamówienia (SWZ)", "miejscowosc": None},
    "Odwolujacy": [{"krs": "0000054588", "nazwa": "STRABAG Sp. z o.o.", "nip": "1234567890", "regon": "123456789",
                    "przez-pelnomocnika": 1,
                    "pelnomocnik": {"imie_nazwisko": "Jan Nowak", "nazwa": "Kancelaria Nowak", "mail": "a@b.pl"}}],
    "Zamawiajacy": [
        {"krs": None, "nazwa": "Gmina Alfa", "nip": "1111111111", "regon": "111111111", "prowadzacy_postepowanie": 1},
        {"krs": None, "nazwa": "Gmina Beta", "nip": "2222222222", "regon": "222222222", "prowadzacy_postepowanie": 0},
    ],
    "ZamowieniePubliczne": {"numer_bzp": "2025/BZP00143067", "numer_postepowania": "ZP.039.2025",
                            "numer_ted": None, "tytul": "Budowa drogi"},
}


def test_lists_matched_by_content_not_order():
    pred = json.loads(json.dumps(ODW))
    pred["Zamawiajacy"].reverse()
    a, b = total(score_document(ODW, ODW)), total(score_document(ODW, pred))
    assert a == b and a.fp == a.fn == 0


def test_list_missing_and_extra_items():
    pred = json.loads(json.dumps(ODW))
    pred["Zamawiajacy"] = [pred["Zamawiajacy"][1], {"nazwa": "Powiat Gamma", "nip": "3333333333"}]
    fc = score_document(ODW, pred)
    # Beta matched fully; Alfa and Gamma share no value but pairing them saves errors
    # (wrong-in-both = FP, instead of FN + FP), so they are paired
    assert fc["Zamawiajacy[].nazwa"] == Counts(tp=1, fp=1)
    assert fc["Zamawiajacy[].nip"] == Counts(tp=1, fp=1)
    assert fc["Zamawiajacy[].regon"] == Counts(tp=1, fn=1)
    assert fc["Zamawiajacy[].prowadzacy_postepowanie"] == Counts(tp=1, fn=1)


def test_unrelated_extra_item_not_paired_when_it_costs_more():
    gt = {"pelnomocnicy": [{"imie_nazwisko": "Jan Nowak", "pesel": None}]}
    pred = {"pelnomocnicy": [{"imie_nazwisko": "Jan Nowak", "pesel": None},
                             {"imie_nazwisko": "Anna Kowalska", "pesel": "85010112345"}]}
    fc = score_document(gt, pred)
    assert fc["pelnomocnicy[].imie_nazwisko"] == Counts(tp=1, fp=1)
    assert fc["pelnomocnicy[].pesel"] == Counts(tn=1, fp=1)


def test_single_wrong_list_value_is_one_fp():
    gt = {"pelnomocnicy": [{"imie_nazwisko": "Jan Nowak", "pesel": None}]}
    fc = score_document(gt, {"pelnomocnicy": [{"imie_nazwisko": "Jan Nowakowski", "pesel": None}]})
    assert fc["pelnomocnicy[].imie_nazwisko"] == Counts(fp=1)


def test_lenient_vs_strict_types():
    pred = json.loads(json.dumps(ODW))
    pred["OdwolanieKIO"]["czynnosc_powod_id"] = "4"
    pred["Odwolujacy"][0]["nip"] = 1234567890
    pred["Odwolujacy"][0]["krs"] = 54588
    lenient = score_document(ODW, pred)
    strict = score_document(ODW, pred, strict=True)
    for f in ("OdwolanieKIO.czynnosc_powod_id", "Odwolujacy[].nip", "Odwolujacy[].krs"):
        assert lenient[f] == Counts(tp=1), f
        assert strict[f] == Counts(fp=1), f


def test_lenient_normalisation():
    assert values_equal("date", "2025-10-09", "09.10.2025")
    assert values_equal("float", 10000.0, "10 000,00 zł")
    assert values_equal("float", 34.0, 34)
    assert values_equal("code", "2025/BZP00143067", "2025/BZP 00143067")
    assert values_equal("digits", "123-456-78-90", "1234567890")
    assert values_equal("email", "Info@Prawnik.pl", "info@prawnik.pl")
    assert not values_equal("date", "2025-10-09", "2025-10-08")
    # strict: whitespace collapse only, json number int == float
    assert values_equal("float", 34.0, 34, strict=True)
    assert not values_equal("float", 34.0, "34", strict=True)
    assert not values_equal("code", "2025/BZP00143067", "2025/BZP 00143067", strict=True)
    assert values_equal("text", "Jan  Nowak ", "Jan Nowak", strict=True)


def test_empty_string_is_absent_only_in_lenient():
    gt = {"przelew_bankowy": {"numer_transakcji": None}}
    pred = {"przelew_bankowy": {"numer_transakcji": ""}}
    assert score_document(gt, pred)["przelew_bankowy.numer_transakcji"] == Counts(tn=1)
    assert score_document(gt, pred, strict=True)["przelew_bankowy.numer_transakcji"] == Counts(fp=1)


def test_nested_lists_pelnomocnictwo():
    gt = {"mocodawca": [{"data": {"imie_nazwisko": None, "krs": "1", "nazwa": "A", "nip": "2", "typ": "osoba_prawna"},
                         "podpisujacy": [{"imie_nazwisko": "X Y"}, {"imie_nazwisko": "Z W"}]}],
          "pelnomocnicy": [{"imie_nazwisko": "P Q", "pesel": None}]}
    pred = json.loads(json.dumps(gt))
    pred["mocodawca"][0]["podpisujacy"].reverse()
    assert total(score_document(gt, pred)) == Counts(tp=7, tn=2)


def test_evaluate_dataset(tmp_path):
    gt, out = tmp_path / "gt", tmp_path / "out"
    (gt / "c1").mkdir(parents=True)
    (gt / "neg").mkdir()
    for n in ("potwierdzenie_przelewu.pdf", "obcy.pdf"):
        (gt / "c1" / n).write_bytes(b"%PDF")
    (gt / "neg" / "x.pdf").write_bytes(b"%PDF")
    (gt / "c1" / "przelew.json").write_text(json.dumps(PRZELEW), encoding="utf-8")
    (out / "c1").mkdir(parents=True)
    (out / "neg").mkdir()
    (out / "c1" / "potwierdzenie_przelewu.json").write_text(json.dumps(PRZELEW), encoding="utf-8")
    (out / "c1" / "obcy.json").write_text("{}", encoding="utf-8")
    # neg/x.json missing -> scored as {} -> nothing counted
    (out / "c1" / "notes.json").write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")
    res = evaluate(gt, out)
    assert res["per_class"]["przelew"] == Counts(tp=5, tn=1)
    assert res["per_class"]["negatyw"] == Counts()
    assert res["orphans"] == ["c1/notes.json"]
    assert res["total"] == Counts(tp=5, tn=1, fp=2)
    assert res["n_docs"] == 3


@pytest.mark.parametrize("strict", [False, True])
def test_train_gt_scores_perfectly_against_itself(tmp_path, strict):
    from pathlib import Path
    import shutil
    data = Path(__file__).resolve().parents[1] / "data" / "train"
    if not data.is_dir():
        pytest.skip("no training data")
    out = tmp_path / "out"
    names = {"odwolanie.json": "odwolanie.json", "pelnomocnictwo.json": "pelnomocnictwo.json",
             "przelew.json": "potwierdzenie_przelewu.json"}
    for case in data.iterdir():
        if not case.is_dir():
            continue
        (out / case.name).mkdir(parents=True)
        for pdf in case.glob("*.pdf"):
            (out / case.name / (pdf.stem + ".json")).write_text("{}", encoding="utf-8")
        for src, dst in names.items():
            if (case / src).exists():
                shutil.copy(case / src, out / case.name / dst)
    res = evaluate(data, out, strict)
    assert res["total"].fp == res["total"].fn == 0
    assert res["total"].tp > 0 and not res["orphans"]
