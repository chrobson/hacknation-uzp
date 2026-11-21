"""rc4: fixes found on realistic UZP scans (OCR deskew, OCR typos, transfer layouts, appeal anchors)."""
from odw.fields import _assign_accounts
from odw.normalize import find_date
from odw.textio import _EMAIL_DOUBLE, _EMAIL_PAREN, _OCR_ZOO, _skew_deg


def _tsv(slope: float) -> str:
    rows = ["level\tpage\tblock\tpar\tline\tword\tleft\ttop\twidth\theight\tconf\ttext"]
    for line in range(5):
        for w in range(6):
            x = 100 + w * 150
            rows.append(f"5\t1\t1\t1\t{line}\t{w}\t{x}\t{200 + line * 80 + round(x * slope)}\t100\t30\t90\tsłowo")
    return "\n".join(rows)


def test_skew_estimate():
    assert abs(_skew_deg(_tsv(0.0))) < 0.01
    assert 1.0 < _skew_deg(_tsv(0.025)) < 1.6  # atan(0.025) ≈ 1.43°


def test_ocr_email_and_legal_form_typos():
    fix = lambda t: _EMAIL_PAREN.sub(r"\1@", _EMAIL_DOUBLE.sub(r"\1@", t))  # noqa: E731
    assert fix("e-mail: z.olszewska(Osikora-kancelaria.example") == "e-mail: z.olszewska@sikora-kancelaria.example"
    assert fix("biuroQ@olszewski-kancelaria.example") == "biuro@olszewski-kancelaria.example"
    assert fix("(np. art. 5)") == "(np. art. 5)"
    assert _OCR_ZOO.sub(r"\1o.o.", "Alfa Sp. z 0.0.") == "Alfa Sp. z o.o."
    assert _OCR_ZOO.sub(r"\1o.o.", "Alfa sp. z o.o.") == "Alfa sp. z o.o."


def test_date_glued_to_r():
    assert find_date("dnia 05.06.2026r.") == "2026-06-05"
    assert find_date("2026-06-05r.") == "2026-06-05"


def test_receiver_is_public_office():
    cfg = {"sender_keywords": [r"\bz\s+rachunku"], "receiver_keywords": [r"\bna\s+rachunek(?!\s+(?:obcy|własny|w\s))"],
           "receiver_hints": [r"(?-i:Urząd|URZĄD)\s+(?i:Zamówień|Miasta)"]}
    text = ("Przelew na rachunek obcy\n11 1111 1111 1111 1111 1111 1111\nUrząd Zamówień Publicznych\n"
            "Nadawca\n22 2222 2222 2222 2222 2222 2222\nFirma Alfa\n")
    assert _assign_accounts(text, cfg) == {"receiver": "1" * 26, "sender": "2" * 26}


def test_signers_skip_company_words_and_ocr_debris():
    from odw.fields import Context, _names

    ctx = Context("……………\nDorota Grabowska\nTervana Systemy Informatyczne sp. k.\nPawia Il", {})
    ctx.item = {"data": {"nazwa": "Tervana Systemy Informatyczne sp. k."}}
    spec = {"type": "names", "not_in": "data.nazwa", "min_word_len": 3}
    assert _names(spec, ctx) == [{"imie_nazwisko": "Dorota Grabowska"}]
