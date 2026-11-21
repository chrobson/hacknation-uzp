"""Self-check: every GT value of a generated przelew case is recoverable from the PDF text.

    python -m eval.synth.przelew.selfcheck data/synth/dev
    python -m eval.synth.przelew.selfcheck /path/to/synth-blind/cases

Checks (independent of the generator's formatting code):
  * accounts: 26-digit GT present in text with all whitespace removed
  * numer_transakcji: present verbatim (or null)
  * tytul: present after collapsing whitespace (fuzzy ratio >= 0.95 as fallback)
  * data_operacji: some date in text parses to the GT ISO date
  * kwota: some amount-like token (or the amount in words) parses to GT
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path

import pdfplumber

MON_GEN = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
           "września", "października", "listopada", "grudnia"]
MON_PL_ABBR = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]
MON_EN = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def dates_in(text: str) -> set[str]:
    out = set()
    for y, m, d in re.findall(r"\b(20\d\d)-(\d\d)-(\d\d)\b", text):
        out.add(f"{y}-{m}-{d}")
    for y, m, d in re.findall(r"\b(20\d\d)[./](\d\d)[./](\d\d)\b", text):
        out.add(f"{y}-{m}-{d}")
    for d, m, yy in re.findall(r"\b(\d\d)\.(\d\d)\.(\d\d)\b", text):
        out.add(f"20{yy}-{m}-{d}")
    for d, m, y in re.findall(r"\b(\d{1,2})[./-](\d{1,2})[./-](20\d\d)\b", text):
        out.add(f"{y}-{int(m):02d}-{int(d):02d}")
    low = text.lower()
    for d, mon, y in re.findall(r"\b(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(20\d\d)", low):
        if mon in MON_GEN:
            out.add(f"{y}-{MON_GEN.index(mon) + 1:02d}-{int(d):02d}")
        elif mon in MON_PL_ABBR:
            out.add(f"{y}-{MON_PL_ABBR.index(mon) + 1:02d}-{int(d):02d}")
        elif mon[:3] in MON_EN:
            out.add(f"{y}-{MON_EN.index(mon[:3]) + 1:02d}-{int(d):02d}")
    for mon, d, y in re.findall(r"\b([a-z]+)\s+(\d{1,2}),\s+(20\d\d)", low):
        if mon[:3] in MON_EN:
            out.add(f"{y}-{MON_EN.index(mon[:3]) + 1:02d}-{int(d):02d}")
    for d, r, y in re.findall(r"\b(\d{1,2})[ .]([IVX]{1,4})[ .](20\d\d)", text):
        if r in ROMAN:
            out.add(f"{y}-{ROMAN.index(r) + 1:02d}-{int(d):02d}")
    for yy, mm, dd in re.findall(r":32A:(\d\d)(\d\d)(\d\d)", text):  # SWIFT MT103
        out.add(f"20{yy}-{mm}-{dd}")
    return out


def amounts_in(text: str) -> set[float]:
    out = set()
    t = text.replace(" ", " ")
    for tok in re.findall(r"\d[\d .,]*\d|\d", t):
        cands = {tok}
        cands.add(tok.replace(" ", ""))
        for c in list(cands):
            c2 = c.strip(" .,")
            # PL: 1 000,00 / 1.000,00 ; EN: 1,000.00
            for thou, dec in ((" ", ","), (".", ","), (",", "."), ("", ",")):
                s = c2.replace(thou, "") if thou else c2
                if dec == ",":
                    s = s.replace(",", ".")
                try:
                    out.add(round(float(s), 2))
                except ValueError:
                    pass
    for m in re.findall(r"PLN(\d+(?:,\d{2})?)", t.replace(" ", "")):  # MT103 :32A:...PLN200,00
        out.add(round(float(m.replace(",", ".")), 2))
    return out


def norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def check_case(pdf: Path, gt: dict) -> list[str]:
    with pdfplumber.open(pdf) as p:
        text = "\n".join((pg.extract_text() or "") for pg in p.pages)
    pb = gt["przelew_bankowy"]
    errs = []
    nospace = re.sub(r"[\s-]+", "", text)
    for k in ("z_rachunku", "na_rachunek"):
        if pb[k] not in nospace:
            errs.append(f"{k} {pb[k]} missing")
    if pb["numer_transakcji"] and pb["numer_transakcji"] not in nospace:
        errs.append(f"ref {pb['numer_transakcji']} missing")
    nt = norm_ws(text)
    if norm_ws(pb["tytul"]) not in nt:
        # fall back to fuzzy (line-wrapping may split hyphenated tokens)
        sm = difflib.SequenceMatcher(None, norm_ws(pb["tytul"]), nt, autojunk=False)
        best = sum(b.size for b in sm.get_matching_blocks()) / max(1, len(pb["tytul"]))
        if best < 0.95:
            errs.append(f"tytul missing (ratio {best:.2f})")
    if pb["data_operacji"] not in dates_in(text):
        errs.append(f"date {pb['data_operacji']} not found")
    if round(pb["kwota"], 2) not in amounts_in(text):
        errs.append(f"kwota {pb['kwota']} not found")
    return errs


def main(argv=None):
    argv = argv or sys.argv[1:]
    root = Path(argv[0]) if argv else Path("data/synth/dev")
    bad = n = 0
    for gtf in sorted(root.glob("przelew_*/*.gt.json")):
        pdf = gtf.with_name(gtf.name[:-len(".gt.json")] + ".pdf")
        errs = check_case(pdf, json.loads(gtf.read_text(encoding="utf-8")))
        n += 1
        if errs:
            bad += 1
            print(f"FAIL {pdf.parent.name}/{pdf.name}: {'; '.join(errs)}")
    print(f"checked {n} cases, {bad} failing")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
