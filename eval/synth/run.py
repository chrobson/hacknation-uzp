"""Run the production pipeline on synthetic cases and score them with eval/score.py.

    python -m eval.synth.run                                  # data/synth/dev + data/synth/negatives-dev
    python -m eval.synth.run --fields                         # + per-field table per class
    python -m eval.synth.run --root "$SYNTH_BLIND_ROOT/cases" --root "$SYNTH_BLIND_ROOT/negatives"

A case is any directory holding exactly one ``<stem>.pdf`` with its ``<stem>.gt.json``.
The expected class comes from the directory prefix (odwolanie_/pelnomocnictwo_/przelew_);
anything else (e.g. negatives' case_XXX) expects ``{}``. meta.json and manifests are never
shown to the pipeline: only the PDF is copied, under a random name.
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from odw.config import load_classes  # noqa: E402
from odw.pipeline import run  # noqa: E402

from eval.score import Counts, score_fields  # noqa: E402

CLASSES = ("odwolanie", "pelnomocnictwo", "przelew")
DEFAULT_ROOTS = [ROOT / "data" / "synth" / "dev", ROOT / "data" / "synth" / "negatives-dev"]


def expected_class(case_dir: Path) -> str | None:
    for c in CLASSES:
        if case_dir.name.startswith(c + "_"):
            return c
    return None


def collect(roots: list[Path]) -> list[tuple[str, Path, dict, str | None]]:
    items = []
    for root in roots:
        for case in sorted(p for p in root.iterdir() if p.is_dir()):
            for gt_file in sorted(case.glob("*.gt.json")):
                pdf = gt_file.with_name(gt_file.name[: -len(".gt.json")] + ".pdf")
                if not pdf.exists():
                    raise SystemExit(f"missing PDF for {gt_file}")
                gt = json.loads(gt_file.read_text(encoding="utf-8"))
                items.append((f"{root.name}/{case.name}", pdf, gt, expected_class(case)))
    return items


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, action="append", help="case root (repeatable); default dev + negatives-dev")
    ap.add_argument("--fields", action="store_true", help="print per-field table per class")
    ap.add_argument("--worst", type=int, default=0, help="list the N worst documents")
    args = ap.parse_args(argv)

    items = collect(args.root or DEFAULT_ROOTS)
    rng = random.Random(7)
    with tempfile.TemporaryDirectory() as tmp:
        inp, out = Path(tmp, "input"), Path(tmp, "output")
        mapping = {}
        for i, (case, pdf, gt, cls) in enumerate(items):
            dst = inp / f"c{i:04d}" / f"dok_{rng.randrange(10**6):06d}.pdf"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(pdf, dst)
            mapping[dst.relative_to(inp)] = (case, pdf, gt, cls)
        t0 = time.time()
        results = run(inp, out, load_classes())
        elapsed = time.time() - t0
        predicted = {r.source.relative_to(inp): r for r in results}

        per_class: dict[str, Counts] = defaultdict(Counts)
        per_field: dict[str, dict[str, Counts]] = defaultdict(lambda: defaultdict(Counts))
        confusion: dict[tuple, int] = defaultdict(int)
        misclassified, doc_scores = [], []
        for rel, (case, pdf, gt, cls) in mapping.items():
            got = predicted[rel].verdict.name
            confusion[(cls, got)] += 1
            if got != cls:
                misclassified.append(f"{case}/{pdf.name}: expected {cls}, got {got} {predicted[rel].verdict.scores}")
            pred = json.loads((out / rel.with_suffix(".json")).read_text(encoding="utf-8"))
            doc = Counts()
            for field, c in score_fields(gt, pred).items():
                per_field[cls or "negatyw"][field] += c
                per_class[cls or "negatyw"] += c
                doc += c
            doc_scores.append((doc.f1, doc.fp + doc.fn, case))

    total = sum(per_class.values(), Counts())
    n_docs = len(items)
    correct = sum(v for (e, g), v in confusion.items() if e == g)
    neg_docs = sum(v for (e, _), v in confusion.items() if e is None)
    neg_fp = sum(v for (e, g), v in confusion.items() if e is None and g is not None)
    print(f"roots={[str(r) for r in (args.root or DEFAULT_ROOTS)]}")
    print(f"docs={n_docs} time={elapsed:.1f}s ({elapsed / max(n_docs, 1):.2f}s/doc)")
    print(f"classification: {correct}/{n_docs} correct, negatives accepted as a class: {neg_fp}/{neg_docs}")
    print(f"F1 overall: {total.f1:.4f}  (TP={total.tp} FP={total.fp} FN={total.fn} TN={total.tn})")
    for name, c in sorted(per_class.items()):
        print(f"  {name:15s} F1={c.f1:.4f}  TP={c.tp} FP={c.fp} FN={c.fn}")
    for line in misclassified:
        print("  MISCLASSIFIED", line)
    if args.fields:
        for name in sorted(per_field):
            rows = [(f, c) for f, c in per_field[name].items() if c.tp + c.fp + c.fn]
            if not rows:
                continue
            print(f"\n[{name}] per field (worst first):")
            for field, c in sorted(rows, key=lambda kv: (kv[1].f1, kv[0])):
                print(f"  {c.f1:.3f}  {field:45s} TP={c.tp:3d} FP={c.fp:3d} FN={c.fn:3d}")
    if args.worst:
        print(f"\nworst {args.worst} documents:")
        for f1, errs, case in sorted(doc_scores)[: args.worst]:
            print(f"  {f1:.3f}  errors={errs:3d}  {case}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
