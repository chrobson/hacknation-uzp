"""Self-check for generated negatives.

    python -m eval.synth.negatywy.selfcheck [DIR ...]   (default: data/synth/negatives-dev)

For every <stem>.pdf: the sibling <stem>.json must be exactly {}, the PDF must have a text layer
(pdfplumber), Polish diacritics must survive extraction (font check), and the text should contain several
"confuser" terms shared with the positive classes. Optionally reports how the production classifier
(src/odw) labels each document (any non-None label = false positive to look at).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pdfplumber

from eval.synth.common_negatywy import ROOT

CONFUSERS = [r"Zamawiając", r"Odwołując", r"\bNIP\b", r"\bKRS\b", r"Sygn\.?\s*akt", r"Krajow\w+ Izb\w+ Odwoławcz",
             r"pełnomoc", r"rachun", r"(zł|PLN)\b", r"odwołani", r"zarzut", r"REGON", r"BZP"]


def main(argv=None):
    dirs = [Path(a) for a in (argv if argv is not None else sys.argv[1:])] or [ROOT / "data" / "synth" / "negatives-dev"]
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from odw.classify import classify
        from odw.config import load_classes
        from odw.textio import load_pdf

        classes = load_classes()
    except Exception as e:  # production code optional
        print("production classifier unavailable:", e)
        classify = None
    problems, warnings, labels, n = [], [], Counter(), 0
    for d in dirs:
        for pdf in sorted(d.rglob("*.pdf")):
            n += 1
            gt = pdf.with_name(pdf.stem + ".json")
            if gt.exists() and json.loads(gt.read_text(encoding="utf-8")) != {}:
                problems.append(f"{pdf}: negative must have no JSON (or exactly {{}})")
            with pdfplumber.open(pdf) as p:
                text = "\n".join((pg.extract_text() or "") for pg in p.pages)
                npages = len(p.pages)
            if len(text.split()) < 50:
                problems.append(f"{pdf}: too little text ({len(text.split())} words)")
            if not re.search(r"[ąęłóśżźćń]", text) or "�" in text or "■" in text:
                problems.append(f"{pdf}: Polish glyphs missing/broken")
            hits = [c for c in CONFUSERS if re.search(c, text, re.I)]
            if len(hits) < 3:
                warnings.append(f"{pdf}: only {len(hits)} confuser terms (weak hard-negative)")
            lab = None
            if classify:
                v = classify(load_pdf(pdf), classes)
                lab = v.name
                labels[lab] += 1
            print(f"{pdf.relative_to(d)}  pages={npages} words={len(text.split())} confusers={len(hits)} prod={lab}")
    print(f"\n{n} PDFs checked; production labels: {dict(labels)}")
    if warnings:
        print("warnings:", *warnings, sep="\n  ")
    print("problems:" if problems else "no problems", *problems, sep="\n  ")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
