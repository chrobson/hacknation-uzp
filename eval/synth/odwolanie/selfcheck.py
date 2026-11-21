"""Check that every non-null GT value is present (in some surface form) in the PDF text.

    python -m eval.synth.odwolanie.selfcheck data/synth/dev [--sample 10] [-v]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import re
import sys
from pathlib import Path

import pdfplumber
from rapidfuzz import fuzz

from .core import MONTHS_GEN, MONTHS_EN, ROMAN, inflect


def text_of(pdf: Path) -> str:
    """Plain text plus a column-wise re-read (left/right halves) so side-by-side
    blocks that pdfplumber interleaves line by line are also searchable."""
    parts, cols = [], []
    with pdfplumber.open(pdf) as p:
        for pg in p.pages:
            parts.append(pg.extract_text() or "")
            w = pg.width
            cuts = [0.0, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 1.0]
            for i, a in enumerate(cuts):
                for b in cuts[i + 1:]:
                    if b - a >= 0.15:
                        cols.append(pg.crop((w * a, 0, w * b, pg.height)).extract_text() or "")
            for tb in pg.extract_tables():
                for row in tb:
                    cols += [c for c in row if c]
    return "\n".join(parts) + "\n" + "\n".join(cols)


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def _digits_view(t: str) -> str:
    # drop separators used inside IDs: spaces, dashes, 'PL' prefix
    t = re.sub(r"PL\s?(?=\d)", "", t)
    return re.sub(r"(?<=\d)[\s\-.](?=\d)", "", t)


def date_forms(d: dt.date) -> list[str]:
    dd, m, y = d.day, d.month, d.year
    return [f"{dd:02d}.{m:02d}.{y}", f"{dd}.{m:02d}.{y}", f"{dd} {MONTHS_GEN[m-1]} {y}", f"{dd} {ROMAN[m-1]} {y}",
            f"{dd}.{ROMAN[m-1]}.{y}", d.isoformat(), f"{dd:02d}/{m:02d}/{y}", f"{dd:02d}-{m:02d}-{y}",
            f"{dd} {MONTHS_EN[m-1]} {y}"]


def check_value(path: str, val, text: str, flat: str, digits: str) -> bool:
    if val is None or path.endswith("powod_id") or path.endswith("przez-pelnomocnika") \
            or path.endswith("prowadzacy_postepowanie") or path.endswith("czynnosc_opis"):
        return True
    s = str(val)
    if path.endswith(("data", "czynnosc_dzien")):
        return any(f in flat for f in date_forms(dt.date.fromisoformat(s)))
    if path.endswith(("nip", "regon", "krs")):
        return s in digits
    if path.endswith("numer_bzp"):
        return s in flat.replace(" ", "")
    if path.endswith("numer_ted"):
        num, year = s.split("-")
        return s in flat or re.search(rf"{year}/S\s?\d{{1,3}}-{num}", flat) is not None
    if path.endswith("imie_nazwisko"):
        forms = [s] + [f for f in (inflect(s, c) for c in ("acc", "gen", "inst")) if f]
        return any(f in flat for f in forms)
    if path.endswith(("nazwa", "tytul")):
        if s in flat:
            return True
        return fuzz.partial_ratio(s, flat) >= 90
    return s in flat


def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v, path)
    else:
        yield path, obj


def check_pdf(pdf: Path, gt: dict) -> list[str]:
    text = text_of(pdf)
    flat = _squash(text.replace("-\n", "-"))
    digits = _digits_view(flat)
    bad = []
    for p, v in walk(gt):
        if not check_value(p, v, text, flat, digits):
            bad.append(f"{p}={v!r}")
    # sanity: class markers
    if "ODWOŁANI" not in flat.upper():
        bad.append("marker:ODWOŁANIE missing")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path)
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args(argv)
    pairs = sorted((p, p.with_name(p.stem + ".gt.json")) for p in a.root.glob("odwolanie_*/*.pdf"))
    if a.sample:
        pairs = random.Random(a.seed).sample(pairs, min(a.sample, len(pairs)))
    n_bad = 0
    for pdf, gtp in pairs:
        gt = json.loads(gtp.read_text(encoding="utf-8"))
        bad = check_pdf(pdf, gt)
        if bad:
            n_bad += 1
            print(f"FAIL {pdf.parent.name}/{pdf.name}: {bad}")
        elif a.v:
            print(f"ok   {pdf.parent.name}/{pdf.name}")
    print(f"checked {len(pairs)} docs, {n_bad} with missing values")
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
