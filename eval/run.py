"""Run the pipeline on data/train and report F1 the way UZP scores it.

    python -m eval.run [--split train|holdout|all] [--fields] [--keep-names]

* Every PDF is copied under a random name, so classification cannot lean on file names.
* PDFs without a ground-truth JSON (mixed into cases, or in data/train/negatywne) expect {}.
* A fixed 15-case holdout is excluded from the default "train" split; check it rarely to spot overfitting.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from odw.config import load_classes  # noqa: E402
from odw.pipeline import run  # noqa: E402

from eval.score import Counts, score_fields  # noqa: E402

DATA = ROOT / "data" / "train"
GT_BY_PDF = {"odwolanie.pdf": "odwolanie.json", "pelnomocnictwo.pdf": "pelnomocnictwo.json", "potwierdzenie_przelewu.pdf": "przelew.json"}
CLASS_BY_GT = {"odwolanie.json": "odwolanie", "pelnomocnictwo.json": "pelnomocnictwo", "przelew.json": "przelew"}
HOLDOUT_SEED, HOLDOUT_SIZE = 2026, 15


def cases() -> list[Path]:
    return sorted(p for p in DATA.iterdir() if p.is_dir() and p.name.startswith("przyklad_"))


def holdout() -> set[str]:
    names = [c.name for c in cases()]
    return set(random.Random(HOLDOUT_SEED).sample(names, HOLDOUT_SIZE))


def collect(split: str) -> list[tuple[str, Path, dict, str | None]]:
    """(case, pdf, ground truth, expected class) for every PDF in the split."""
    hold = holdout()
    items = []
    for case in cases():
        if (split == "train" and case.name in hold) or (split == "holdout" and case.name not in hold):
            continue
        for pdf in sorted(case.glob("*.pdf")):
            gt_name = GT_BY_PDF.get(pdf.name)
            gt = json.loads((case / gt_name).read_text(encoding="utf-8")) if gt_name else {}
            items.append((case.name, pdf, gt, CLASS_BY_GT.get(gt_name) if gt_name else None))
    if split in ("train", "all"):
        for pdf in sorted((DATA / "negatywne").glob("*.pdf")):
            items.append(("negatywne", pdf, {}, None))
    return items


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "holdout", "all"], default="train")
    ap.add_argument("--fields", action="store_true", help="print per-field table")
    ap.add_argument("--keep-names", action="store_true", help="do not randomise file names")
    ap.add_argument("--save", type=Path, help="append a JSON summary line to this file (e.g. notes/eval-history.jsonl)")
    args = ap.parse_args(argv)

    items = collect(args.split)
    rng = random.Random(7)
    with tempfile.TemporaryDirectory() as tmp:
        inp, out = Path(tmp, "input"), Path(tmp, "output")
        mapping = {}
        for i, (case, pdf, gt, cls) in enumerate(items):
            name = pdf.name if args.keep_names else f"dok_{rng.randrange(10**6):06d}_{i}.pdf"
            dst = inp / case / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(pdf, dst)
            mapping[dst.relative_to(inp)] = (case, pdf, gt, cls)
        t0 = time.time()
        results = run(inp, out, load_classes())
        elapsed = time.time() - t0
        predicted = {r.source.relative_to(inp): r for r in results}

        per_class: dict[str, Counts] = defaultdict(Counts)
        per_field: dict[str, Counts] = defaultdict(Counts)
        confusion = defaultdict(int)
        misclassified = []
        for rel, (case, pdf, gt, cls) in mapping.items():
            r = predicted[rel]
            got = r.verdict.name
            confusion[(cls, got)] += 1
            if got != cls:
                misclassified.append(f"{case}/{pdf.name}: expected {cls}, got {got} {r.verdict.scores}")
            pred = json.loads((out / rel.with_suffix(".json")).read_text(encoding="utf-8"))
            for field, c in score_fields(gt, pred).items():
                per_field[field] = per_field[field] + c
                per_class[cls or "negatyw"] = per_class[cls or "negatyw"] + c

    total = sum(per_class.values(), Counts())
    n_docs = len(items)
    correct = sum(v for (e, g), v in confusion.items() if e == g)
    neg_fp = sum(v for (e, g), v in confusion.items() if e is None and g is not None)
    print(f"split={args.split} docs={n_docs} time={elapsed:.1f}s ({elapsed / max(n_docs, 1):.2f}s/doc)")
    print(f"classification: {correct}/{n_docs} correct, negatives accepted as a class: {neg_fp}")
    print(f"F1 overall: {total.f1:.4f}  (TP={total.tp} FP={total.fp} FN={total.fn} TN={total.tn})")
    for name, c in sorted(per_class.items()):
        print(f"  {name:15s} F1={c.f1:.4f}  TP={c.tp} FP={c.fp} FN={c.fn}")
    for line in misclassified:
        print("  MISCLASSIFIED", line)
    if args.fields:
        print("\nper field (worst first):")
        for field, c in sorted(per_field.items(), key=lambda kv: kv[1].f1):
            if c.tp + c.fp + c.fn:
                print(f"  {c.f1:.3f}  {field:45s} TP={c.tp:3d} FP={c.fp:3d} FN={c.fn:3d}")
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        line = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "split": args.split, "f1": round(total.f1, 4),
                "classes": {k: round(v.f1, 4) for k, v in per_class.items()}, "misclassified": len(misclassified)}
        with args.save.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
