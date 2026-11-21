"""Generate NEGATIVE documents (classified as none, expected output {}).

    python -m eval.synth.negatywy.generate --split dev   --n 20 --seed 1
    python -m eval.synth.negatywy.generate --split sprawa --n 20 --seed 1   (case-folder documents, templates_sprawa)
    python -m eval.synth.negatywy.generate --split blind --n 20 --seed 2

dev   -> data/synth/negatives-dev/case_XXX/<random>.pdf + <random>.json ({})
blind -> $SYNTH_BLIND_ROOT/negatives/case_XXX/...   (templates loaded from $SYNTH_BLIND_ROOT/templates/negatywy/*.py,
         which are kept OUTSIDE the repo; default SYNTH_BLIND_ROOT=/Users/mat2/orca/projects/hacknation/synth-blind)

A manifest.jsonl (file -> template) is written at the output root, never inside the case dirs.
`--class none|negatywy` is accepted for CLI compatibility with eval.synth.generate.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import shutil
import sys
from pathlib import Path

from eval.synth.common_negatywy import BLIND_ROOT, ROOT, make_ctx, write_case


def load_templates(split: str) -> dict:
    if split == "sprawa":  # documents from a KIO case folder next to the appeal (harder, class-specific vocabulary)
        from eval.synth.negatywy.templates_sprawa import TEMPLATES

        return dict(TEMPLATES)
    if split == "dev":
        from eval.synth.negatywy.templates_dev import TEMPLATES

        return dict(TEMPLATES)
    tdir = BLIND_ROOT / "templates" / "negatywy"
    out = {}
    for f in sorted(tdir.glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"_blind_neg_{f.stem}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out.update(getattr(mod, "TEMPLATES", {}))
    if not out:
        sys.exit(f"no blind templates found in {tdir}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--class", dest="cls", default="none", choices=["none", "negatywy", "negative"])
    ap.add_argument("--split", choices=["dev", "sprawa", "blind"], default="dev")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--clean", action="store_true", help="remove existing case_* dirs in the output first")
    a = ap.parse_args(argv)

    out = a.out or {"dev": ROOT / "data" / "synth" / "negatives-dev",
                    "sprawa": ROOT / "data" / "synth" / "negatives-sprawa"}.get(a.split, BLIND_ROOT / "negatives")
    out.mkdir(parents=True, exist_ok=True)
    if a.clean:
        for d in out.glob("case_*"):
            shutil.rmtree(d)
        (out / "manifest.jsonl").unlink(missing_ok=True)
    templates = load_templates(a.split)
    rng = random.Random(f"negatywy-{a.split}-{a.seed}")
    names = list(templates)
    order = []
    while len(order) < a.n:  # every template appears before any repeats
        rng.shuffle(names)
        order += names
    start = 1 + len(list(out.glob("case_*")))
    with open(out / "manifest.jsonl", "a", encoding="utf-8") as man:
        for i, tname in enumerate(order[: a.n]):
            case = f"case_{start + i:03d}"
            drng = random.Random(f"{a.seed}-{a.split}-{i}-{tname}")
            ctx = make_ctx(drng)
            pdf, gt = write_case(out, case, drng, lambda p: templates[tname](ctx, p))
            man.write(json.dumps({"pdf": str(pdf.relative_to(out)), "template": tname, "split": a.split,
                                  "seed": a.seed, "expected": {}}, ensure_ascii=False) + "\n")
            print(f"{case}  {tname:28s} {pdf.name}")


if __name__ == "__main__":
    main()
