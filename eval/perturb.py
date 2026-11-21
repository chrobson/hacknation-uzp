"""Robustness probe: perturb the extracted text of every labelled document and re-score.

    python -m eval.perturb [--split all] [--only NAME] [--fields]

Each perturbation imitates a plausible difference in an unseen document (page width, typography, label case).
A field whose F1 drops under a perturbation depends on that surface detail: candidate for a sturdier rule.
"""

from __future__ import annotations

import argparse
import re
import sys
import textwrap
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from odw.config import load_classes  # noqa: E402
from odw.pipeline import process_pdf  # noqa: E402
from odw.textio import Document, load_pdf  # noqa: E402

from eval.run import collect  # noqa: E402
from eval.score import Counts, score_fields  # noqa: E402

LABEL = re.compile(r"^(\s*)([A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż]+(?: [a-ząćęłńóśźż]+){0,3})(\s*:)", re.MULTILINE)


def narrow(text: str) -> str:  # narrower page: long lines wrap at ~55 characters
    return "\n".join(w for line in text.split("\n") for w in (textwrap.wrap(line, 55) or [""]))


def wide(text: str) -> str:  # wider page: a line continues on the previous one when it starts lowercase
    return re.sub(r"(?<=[^\n:.;])\n(?=[a-ząćęłńóśźż(])", " ", text)


def quotes(text: str) -> str:  # straight quotes and plain hyphens instead of „” and –
    return text.replace("„", '"').replace("”", '"').replace("–", "-").replace("—", "-")


def upper_labels(text: str) -> str:  # "Odwołujący:" → "ODWOŁUJĄCY:"
    return LABEL.sub(lambda m: m.group(1) + m.group(2).upper() + m.group(3), text)


def nbsp(text: str) -> str:  # non-breaking spaces after short tokens (common in Word exports)
    return re.sub(r"(\b\w{1,3}) (?=\w)", "\\1\u00a0", text)


def spaced_colons(text: str) -> str:  # "NIP: 123" → "NIP : 123"
    return re.sub(r"(?<=\w):(?= )", " :", text)


def no_diacritics(text: str) -> str:  # fonts/extraction that lose Polish letters: "Pełnomocnictwo" → "Pelnomocnictwo"
    return text.translate(str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ"))


PERTURBATIONS: dict[str, Callable[[str], str]] = {
    "baseline": lambda t: t, "narrow": narrow, "wide": wide, "quotes": quotes,
    "upper_labels": upper_labels, "nbsp": nbsp, "spaced_colons": spaced_colons,
    "no_diacritics_cls": no_diacritics,
    "combined": lambda t: spaced_colons(nbsp(upper_labels(quotes(narrow(wide(t)))))),
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "holdout", "all"], default="all")
    ap.add_argument("--only", action="append", help="run only these perturbations")
    ap.add_argument("--fields", action="store_true", help="list fields that lost F1")
    args = ap.parse_args(argv)

    classes = load_classes()
    items = collect(args.split)
    docs = {pdf: load_pdf(pdf) for _, pdf, _, _ in items}
    names = args.only or list(PERTURBATIONS)
    base_fields: dict[str, Counts] = {}
    print(f"{'perturbation':15s} {'F1':>7s} {'cls err':>7s} {'neg FP':>6s}  per class")
    for name in names:
        fn = PERTURBATIONS[name]
        per_class: dict[str, Counts] = defaultdict(Counts)
        per_field: dict[str, Counts] = defaultdict(Counts)
        cls_err = neg_fp = 0
        for case, pdf, gt, expected in items:
            doc = docs[pdf]
            pert = replace(doc, pages=[fn(p) for p in doc.pages])
            result = process_pdf(pdf, classes, doc=pert)
            if result.verdict.name != expected:
                cls_err += 1
                neg_fp += expected is None
            for field, c in score_fields(gt, result.data).items():
                per_field[field] = per_field[field] + c
                per_class[expected or "negatyw"] = per_class[expected or "negatyw"] + c
        total = sum(per_class.values(), Counts())
        cls = " ".join(f"{k}={v.f1:.3f}" for k, v in sorted(per_class.items()) if k != "negatyw")
        print(f"{name:15s} {total.f1:7.4f} {cls_err:7d} {neg_fp:6d}  {cls}", flush=True)
        if name == "baseline":
            base_fields = per_field
        elif args.fields:
            for field, c in sorted(per_field.items(), key=lambda kv: kv[1].f1):
                b = base_fields.get(field)
                if b and c.f1 < b.f1 - 1e-9:
                    print(f"      {c.f1:.3f} (was {b.f1:.3f})  {field}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
