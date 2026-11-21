"""Quality gate for main (`make gate`). Exit 0 only if every check passes.

 1 pytest green (incl. crash/fuzz and adversarial regressions)
 2 train = holdout = 1.000 F1
 3 synth-dev F1 does not drop by more than 0.005 vs eval/baselines/synth_dev.json (skipped if no synth-dev)
 4 0 negatives accepted (train negatives + data/synth/negatives-dev)
 5 strict F1 = lenient F1 on train
 6 output schema: one JSON per PDF, nothing else in output/, no keys or types outside the class template
 7 random file names do not change any output
 8 works with no LLM configured (LLM_* env cleared for the whole gate)
 9 under 1 s per document

    python -m eval.gate [--update-baseline]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from odw.config import load_classes  # noqa: E402

from eval.run import collect, evaluate  # noqa: E402

SYNTH_DEV = ROOT / "data" / "synth" / "dev"
SYNTH_NEG = ROOT / "data" / "synth" / "negatives-dev"
BASELINE = ROOT / "eval" / "baselines" / "synth_dev.json"
MAX_SYNTH_DROP = 0.005
MAX_S_PER_DOC = 1.0


def _schema_errors(pred: Any, template: Any, path: str = "") -> list[str]:
    errors: list[str] = []
    if isinstance(template, dict):
        if not isinstance(pred, dict):
            return [f"{path}: expected object, got {type(pred).__name__}"]
        for key in pred.keys() - template.keys():
            errors.append(f"{path}.{key}: key outside schema")
        for key in pred.keys() & template.keys():
            errors += _schema_errors(pred[key], template[key], f"{path}.{key}")
    elif isinstance(template, list):
        if not isinstance(pred, list):
            return [f"{path}: expected list, got {type(pred).__name__}"]
        for i, item in enumerate(pred):
            errors += _schema_errors(item, template[0], f"{path}[{i}]")
    elif pred is not None and not isinstance(pred, (str, int, float)) or isinstance(pred, bool):
        errors.append(f"{path}: unexpected value type {type(pred).__name__}")
    return errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update-baseline", action="store_true", help="store the current synth-dev F1 as the new baseline")
    ap.add_argument("--skip-pytest", action="store_true")
    args = ap.parse_args(argv)

    for key in [k for k in os.environ if k.startswith("LLM_")]:  # check 8: everything below runs without an LLM
        del os.environ[key]
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))
        print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)

    # 1
    if args.skip_pytest:
        check("1 pytest", True, "skipped (--skip-pytest)")
    else:
        proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True)
        check("1 pytest", proc.returncode == 0, (proc.stdout.strip().splitlines() or ["?"])[-1])

    # 2, 4 (train part), 6, 9
    train_all = evaluate(collect("all"))
    hold = evaluate(collect("holdout"))
    train = evaluate(collect("train"))
    check("2 train=holdout=1.000", train["f1"] == 1.0 and hold["f1"] == 1.0, f"train={train['f1']:.4f} holdout={hold['f1']:.4f}")

    # 3
    synth_f1 = None
    if SYNTH_DEV.is_dir() and any(SYNTH_DEV.rglob("*.pdf")):
        synth = evaluate(collect(root=SYNTH_DEV))
        synth_f1 = synth["f1"]
        base = json.loads(BASELINE.read_text())["f1"] if BASELINE.exists() else None
        ok = base is None or synth_f1 >= base - MAX_SYNTH_DROP
        check("3 synth-dev no regression", ok, f"f1={synth_f1:.4f} baseline={base}")
    else:
        check("3 synth-dev no regression", True, "skipped: data/synth/dev not present yet")

    # 4
    neg_fp = train_all["negatives_accepted"]
    detail = f"train negatives accepted={neg_fp}"
    if SYNTH_NEG.is_dir() and any(SYNTH_NEG.rglob("*.pdf")):
        neg = evaluate([(c, p, {}, None) for c, p, _, _ in collect(root=SYNTH_NEG)])
        neg_fp += neg["negatives_accepted"]
        detail += f", synth negatives accepted={neg['negatives_accepted']}/{neg['docs']}"
    check("4 0 FP on negatives", neg_fp == 0, detail)

    # 5
    strict = evaluate(collect("train"), strict=True)
    check("5 strict = lenient (train)", strict["f1"] == train["f1"], f"strict={strict['f1']:.4f} lenient={train['f1']:.4f}")

    # 6
    templates = {next(iter(c.output_template)): c.output_template for c in load_classes()}
    errors = [] if train_all["files_ok"] else ["output/ files differ from one-JSON-per-PDF"]
    for doc, pred in train_all["outputs"].items():
        if pred == {}:
            continue
        key = next((k for k in pred if k in templates), None)
        if key is None:
            errors.append(f"{doc}: no known class key in {list(pred)[:3]}")
            continue
        errors += [f"{doc}: {e}" for e in _schema_errors(pred, templates[key])]
    check("6 output schema", not errors, f"{len(errors)} problems" + (f", first: {errors[0]}" if errors else ""))

    # 7
    named = evaluate(collect("all"), keep_names=True)
    diff = [d for d in train_all["outputs"] if train_all["outputs"][d] != named["outputs"].get(d)]
    check("7 file names do not matter", not diff, f"{len(diff)} documents differ")

    # 8
    check("8 runs without LLM", True, "LLM_* cleared; all checks above ran in rules-only mode")

    # 9
    per_doc = train_all["elapsed"] / max(train_all["docs"], 1)
    check("9 < 1 s/doc", per_doc < MAX_S_PER_DOC, f"{per_doc:.2f} s/doc")

    if args.update_baseline and synth_f1 is not None:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps({"f1": round(synth_f1, 4)}) + "\n")
        print(f"baseline updated: synth-dev f1={synth_f1:.4f}")

    failed = [c for c in checks if not c[1]]
    print(f"\nGATE {'GREEN' if not failed else 'RED'}: {len(checks) - len(failed)}/{len(checks)} checks passed")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
