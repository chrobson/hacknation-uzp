"""Run the pipeline on a labelled set and report F1 the way UZP scores it.

    python -m eval.run [--split train|holdout|all] [--root DIR] [--fields] [--keep-names] [--strict]

* Every PDF is copied under a random name, so classification cannot lean on file names.
* Ground truth for X.pdf: the train mapping (odwolanie/pelnomocnictwo/potwierdzenie_przelewu), else X.json
  next to the PDF, else {} (the document must be rejected).
* data/train: a fixed 15-case holdout is excluded from "train". --root evaluates any other folder of cases.
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
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from odw.config import load_classes  # noqa: E402
from odw.pipeline import run  # noqa: E402

from eval import score as scoring  # noqa: E402
from eval.score import Counts, score_fields  # noqa: E402

DATA = ROOT / "data" / "train"
GT_BY_PDF = {"odwolanie.pdf": "odwolanie.json", "pelnomocnictwo.pdf": "pelnomocnictwo.json", "potwierdzenie_przelewu.pdf": "przelew.json", "przelew.pdf": "przelew.json"}
CLASS_BY_KEY = {"OdwolanieKIO": "odwolanie", "mocodawca": "pelnomocnictwo", "przelew_bankowy": "przelew"}
HOLDOUT_SEED, HOLDOUT_SIZE = 2026, 15

Item = tuple[str, Path, dict, "str | None"]


def cases(root: Path = DATA) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("przyklad_"))


def holdout() -> set[str]:
    names = [c.name for c in cases()]
    return set(random.Random(HOLDOUT_SEED).sample(names, HOLDOUT_SIZE))


def _gt_for(pdf: Path) -> dict:
    mapped = GT_BY_PDF.get(pdf.name)
    gt_path = pdf.parent / mapped if mapped else pdf.with_suffix(".json")
    return json.loads(gt_path.read_text(encoding="utf-8")) if gt_path.exists() else {}


def _class_of(gt: dict) -> str | None:
    return next((cls for key, cls in CLASS_BY_KEY.items() if key in gt), None)


def collect(split: str = "train", root: Path | None = None) -> list[Item]:
    """(case, pdf, ground truth, expected class) for every PDF."""
    items: list[Item] = []
    if root is not None:  # any folder: <root>/<case>/*.pdf (+ optional same-stem .json)
        for pdf in sorted(root.rglob("*.pdf")):
            gt = _gt_for(pdf)
            items.append((pdf.parent.relative_to(root).as_posix() or ".", pdf, gt, _class_of(gt)))
        return items
    hold = holdout()
    for case in cases():
        if (split == "train" and case.name in hold) or (split == "holdout" and case.name not in hold):
            continue
        for pdf in sorted(case.glob("*.pdf")):
            gt = _gt_for(pdf)
            items.append((case.name, pdf, gt, _class_of(gt)))
    if split in ("train", "all"):
        for pdf in sorted((DATA / "negatywne").glob("*.pdf")):
            items.append(("negatywne", pdf, {}, None))
    return items


def evaluate(items: list[Item], keep_names: bool = False, strict: bool = False, seed: int = 7) -> dict[str, Any]:
    rng = random.Random(seed)
    scoring.STRICT = strict
    try:
        with tempfile.TemporaryDirectory() as tmp:
            inp, out = Path(tmp, "input"), Path(tmp, "output")
            mapping = {}
            for i, (case, pdf, gt, cls) in enumerate(items):
                name = pdf.name if keep_names else f"dok_{rng.randrange(10**6):06d}_{i}.pdf"
                dst = inp / f"c{i:04d}_{Path(case).name}" / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(pdf, dst)
                mapping[dst.relative_to(inp)] = (case, pdf, gt, cls)
            t0 = time.time()
            results = run(inp, out, load_classes())
            elapsed = time.time() - t0
            predicted = {r.source.relative_to(inp): r for r in results}
            per_class: dict[str, Counts] = defaultdict(Counts)
            per_field: dict[str, Counts] = defaultdict(Counts)
            misclassified, neg_fp, outputs = [], 0, {}
            for rel, (case, pdf, gt, cls) in mapping.items():
                r = predicted[rel]
                got = r.verdict.name
                if got != cls:
                    misclassified.append(f"{case}/{pdf.name}: expected {cls}, got {got} {r.verdict.scores}")
                    if cls is None:
                        neg_fp += 1
                pred = json.loads((out / rel.with_suffix(".json")).read_text(encoding="utf-8"))
                outputs[f"{case}/{pdf.name}"] = pred
                for field, c in score_fields(gt, pred).items():
                    per_field[field] = per_field[field] + c
                    per_class[cls or "negatyw"] = per_class[cls or "negatyw"] + c
            produced = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
            expected_files = sorted(rel.with_suffix(".json").as_posix() for rel in mapping)
    finally:
        scoring.STRICT = False
    total = sum(per_class.values(), Counts())
    return {
        "docs": len(items), "elapsed": elapsed, "f1": total.f1, "total": total, "per_class": dict(per_class),
        "per_field": dict(per_field), "misclassified": misclassified, "negatives_accepted": neg_fp,
        "outputs": outputs, "files_ok": produced == expected_files,
    }


def report(res: dict[str, Any], label: str, fields: bool = False) -> None:
    t = res["total"]
    print(f"{label}: docs={res['docs']} time={res['elapsed']:.1f}s ({res['elapsed'] / max(res['docs'], 1):.2f}s/doc)")
    print(f"classification errors: {len(res['misclassified'])}, negatives accepted as a class: {res['negatives_accepted']}")
    print(f"F1 overall: {t.f1:.4f}  (TP={t.tp} FP={t.fp} FN={t.fn} TN={t.tn})")
    for name, c in sorted(res["per_class"].items()):
        print(f"  {name:15s} F1={c.f1:.4f}  TP={c.tp} FP={c.fp} FN={c.fn}")
    for line in res["misclassified"]:
        print("  MISCLASSIFIED", line)
    if fields:
        print("\nper field (worst first):")
        for field, c in sorted(res["per_field"].items(), key=lambda kv: kv[1].f1):
            if c.tp + c.fp + c.fn:
                print(f"  {c.f1:.3f}  {field:45s} TP={c.tp:3d} FP={c.fp:3d} FN={c.fn:3d}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["train", "holdout", "all"], default="train")
    ap.add_argument("--root", type=Path, help="evaluate another folder of cases instead of data/train")
    ap.add_argument("--fields", action="store_true", help="print per-field table")
    ap.add_argument("--keep-names", action="store_true", help="do not randomise file names")
    ap.add_argument("--strict", action="store_true", help="exact strings and exact JSON types")
    ap.add_argument("--save", type=Path, help="append a JSON summary line (e.g. notes/eval-history.jsonl)")
    args = ap.parse_args(argv)

    res = evaluate(collect(args.split, args.root), keep_names=args.keep_names, strict=args.strict)
    report(res, f"split={args.root or args.split}{' strict' if args.strict else ''}", args.fields)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        line = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "split": str(args.root or args.split), "f1": round(res["f1"], 4),
                "classes": {k: round(v.f1, 4) for k, v in res["per_class"].items()}, "misclassified": len(res["misclassified"])}
        with args.save.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
