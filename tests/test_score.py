from eval.score import Counts, score_doc

ODW_GT = {
    "OdwolanieKIO": {"data": None, "czynnosc_powod_id": 9},
    "Odwolujacy": [{"nazwa": "Belmoria Rozwiązania S.A.", "nip": "9999284065"}],
    "Zamawiajacy": [
        {"nazwa": "Aurelink Automatyka S.A.", "nip": "1"},
        {"nazwa": "Gmina Wrocław", "nip": "2"},
    ],
}


def test_identical_is_perfect():
    c = score_doc(ODW_GT, ODW_GT)
    assert c.fp == 0 and c.fn == 0 and c.tp == 7
    assert c.f1 == 1.0


def test_empty_prediction_is_all_false_negatives():
    c = score_doc(ODW_GT, {})
    assert (c.tp, c.fp, c.fn) == (0, 0, 7)


def test_wrong_value_counts_as_false_positive_only():
    pred = {"OdwolanieKIO": {"data": None, "czynnosc_powod_id": 3}}
    c = score_doc({"OdwolanieKIO": {"data": None, "czynnosc_powod_id": 9}}, pred)
    assert (c.tp, c.fp, c.fn) == (0, 1, 0)


def test_value_where_ground_truth_is_null_is_false_positive():
    c = score_doc({"OdwolanieKIO": {"data": None}}, {"OdwolanieKIO": {"data": "2026-01-01"}})
    assert (c.tp, c.fp, c.fn, c.tn) == (0, 1, 0, 0)


def test_null_in_both_is_true_negative():
    c = score_doc({"OdwolanieKIO": {"data": None}}, {"OdwolanieKIO": {"data": None}})
    assert (c.tp, c.fp, c.fn, c.tn) == (0, 0, 0, 1)


def test_negative_document_expects_empty_object():
    assert score_doc({}, {}).fp == 0
    c = score_doc({}, {"przelew_bankowy": {"kwota": 200.0, "tytul": None}})
    assert c.fp == 1


def test_lists_are_matched_by_content_not_order():
    pred = dict(ODW_GT, Zamawiajacy=list(reversed(ODW_GT["Zamawiajacy"])))
    assert score_doc(ODW_GT, pred).f1 == 1.0


def test_long_strings_accept_80_percent_similarity():
    gt = {"Odwolujacy": [{"nazwa": "Kancelaria Adwokacka Spółka z ograniczoną odpowiedzialnością"}]}
    near = {"Odwolujacy": [{"nazwa": "Kancelaria Adwokacka Spółka z ograniczona odpowiedzialnoscia"}]}
    assert score_doc(gt, near).tp == 1


def test_short_identifier_fields_require_exact_match():
    gt = {"Odwolujacy": [{"nip": "9999284065"}]}
    assert score_doc(gt, {"Odwolujacy": [{"nip": "9999284066"}]}).fp == 1


def test_numbers_compare_by_value():
    gt = {"przelew_bankowy": {"kwota": 200.0}}
    assert score_doc(gt, {"przelew_bankowy": {"kwota": 200}}).tp == 1


def test_counts_add_up():
    total = Counts(1, 0, 1, 0) + Counts(1, 1, 0, 2)
    assert (total.tp, total.fp, total.fn, total.tn) == (2, 1, 1, 2)
