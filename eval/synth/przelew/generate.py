"""Generate synthetic PRZELEW (bank transfer confirmation) documents with exact GT.

    python -m eval.synth.przelew.generate --split dev   --n 30 --seed 1
    python -m eval.synth.przelew.generate --split blind --n 30 --seed 2

dev   -> data/synth/dev/przelew_XXX/<random>.pdf + <random>.gt.json
blind -> $SYNTH_BLIND_ROOT/cases/przelew_XXX/...  (templates loaded from
         $SYNTH_BLIND_ROOT/templates/przelew/*.py, kept OUTSIDE the repo;
         default SYNTH_BLIND_ROOT=/Users/mat2/orca/projects/hacknation/synth-blind)

GT follows docs/spec/przelew.json: {"przelew_bankowy": {...}}. Accounts are 26
digits (no "PL", no spaces), kwota is a float, data_operacji ISO, numer_transakcji
null when the document shows no transaction number.

A manifest_przelew.jsonl (case -> template, file) is written at the output root,
never inside case dirs. `--class przelew` is accepted for compatibility with a
shared eval.synth.generate dispatcher, which can also call ``generate(...)``.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import os
import pkgutil
import random
import shutil
import sys
from pathlib import Path

from eval.synth.common_przelew import REPO_ROOT, random_stem, register_fonts, sample_case, write_gt

BLIND_ROOT = Path(os.environ.get("SYNTH_BLIND_ROOT", "/Users/mat2/orca/projects/hacknation/synth-blind"))
PREFIX = "przelew_"


def load_templates(split: str) -> list:
    mods = []
    if split == "dev":
        from eval.synth.przelew import templates as pkg
        for m in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda m: m.name):
            mods.append(importlib.import_module(f"{pkg.__name__}.{m.name}"))
    else:
        tdir = BLIND_ROOT / "templates" / "przelew"
        for f in sorted(tdir.glob("*.py")):
            spec = importlib.util.spec_from_file_location(f"_blind_przelew_{f.stem}", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mods.append(mod)
        if not mods:
            sys.exit(f"no blind templates found in {tdir}")
    return [m for m in mods if hasattr(m, "render") and hasattr(m, "NAME")]


def default_out(split: str) -> Path:
    return REPO_ROOT / "data" / "synth" / "dev" if split == "dev" else BLIND_ROOT / "cases"


def generate(split: str, n: int, seed: int, out: Path | None = None, clean: bool = False,
             start: int = 0) -> list[dict]:
    register_fonts()
    out = out or default_out(split)
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "manifest_przelew.jsonl"
    if clean:
        for d in out.glob(PREFIX + "*"):
            shutil.rmtree(d)
        manifest.unlink(missing_ok=True)
    templates = load_templates(split)
    master = random.Random(f"przelew-{split}-{seed}")
    order: list = []
    while len(order) < n:  # round-robin over shuffled templates -> balanced coverage
        block = templates[:]
        master.shuffle(block)
        order += block
    records = []
    for i in range(n):
        tpl = order[i]
        rng = random.Random(f"przelew-{split}-{seed}-{i}")
        case = sample_case(rng)
        cdir = out / f"{PREFIX}{start + i:03d}"
        if cdir.exists():
            shutil.rmtree(cdir)
        cdir.mkdir(parents=True)
        stem = random_stem(rng)
        pdf = cdir / f"{stem}.pdf"
        tpl.render(case, rng, pdf)
        write_gt(cdir / f"{stem}.gt.json", case)
        rec = {"case": cdir.name, "file": pdf.name, "template": tpl.NAME, "split": split, "seed": seed}
        records.append(rec)
    with manifest.open("a", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return records


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--class", dest="cls", default="przelew", choices=["przelew", "przelew_bankowy"])
    ap.add_argument("--split", choices=["dev", "blind"], default="dev")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--start", type=int, default=0, help="first case index")
    ap.add_argument("--clean", action="store_true", help="remove existing przelew_* dirs in the output first")
    a = ap.parse_args(argv)
    recs = generate(a.split, a.n, a.seed, a.out, a.clean, a.start)
    out = a.out or default_out(a.split)
    print(f"wrote {len(recs)} przelew cases to {out} "
          f"({len({r['template'] for r in recs})} templates)")


if __name__ == "__main__":
    main()
