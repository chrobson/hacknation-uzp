"""Check that every GT value of generated cases appears in the PDF text (in some form).

    python -m eval.synth.pelnomocnictwo.selfcheck data/synth/dev [--all]

Numbers are compared on digit-only text (so 'PL 999-123-45-67' matches); names are
matched by stems of each token (inflected forms like 'Piotrowi Zalewskiemu' match
'Piotr Zalewski'); company names after whitespace normalisation, case-insensitive.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pdfplumber


def norm(s: str) -> str:
    return " ".join(s.split()).lower()


def name_ok(name: str, text: str) -> bool:
    t = norm(text)
    for tok in name.split():
        tok = tok.lower()
        # short names change their stem when inflected (Ewa -> Ewie, Olga -> Oldze): keep 2 letters
        stem = tok[: max(3, min(len(tok) - 2, 6))] if len(tok) > 4 else tok[:2]
        if stem not in t:
            return False
    return True


def check_case(pdf: Path) -> list[str]:
    gt = \
        json.loads((pdf.parent / (pdf.stem + ".gt.json")).read_text())
    with pdfplumber.open(pdf) as d:
        text = "\n".join(p.extract_text() or "" for p in d.pages)
    digits = re.sub(r"\D", "", text)
    flat = norm(text)
    errs = []
    for m in gt["mocodawca"]:
        x = m["data"]
        if norm(x["nazwa"]) not in flat:
            errs.append(f"nazwa {x['nazwa']!r}")
        for f in ("krs", "nip"):
            if x[f] and x[f] not in digits:
                errs.append(f"{f} {x[f]}")
        if x["imie_nazwisko"] and not name_ok(x["imie_nazwisko"], text):
            errs.append(f"imie_nazwisko {x['imie_nazwisko']}")
        for s in m["podpisujacy"]:
            if not name_ok(s["imie_nazwisko"], text):
                errs.append(f"podpisujacy {s['imie_nazwisko']}")
    for a in gt["pelnomocnicy"]:
        if not name_ok(a["imie_nazwisko"], text):
            errs.append(f"pelnomocnik {a['imie_nazwisko']}")
        if a["pesel"] and a["pesel"] not in digits:
            errs.append(f"pesel {a['pesel']}")
    return errs


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    root = Path(argv[0])
    pdfs = sorted(root.glob("pelnomocnictwo_*/*.pdf"))
    bad = 0
    for p in pdfs:
        e = check_case(p)
        if e:
            bad += 1
            print(f"FAIL {p}: {e}")
    print(f"checked {len(pdfs)} cases, {bad} with missing values")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
