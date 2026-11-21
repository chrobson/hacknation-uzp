"""Render synthetic ODWOLANIE PDFs with exact ground truth.

    python -m eval.synth.odwolanie.generate --split dev --n 30 --seed 1
    python -m eval.synth.odwolanie.generate --split blind --n 30 --seed 2

dev   templates: eval/synth/odwolanie/templates_dev/*.py -> data/synth/dev/odwolanie_XXX/
blind templates: $SYNTH_BLIND_ROOT/templates/odwolanie/*.py -> $SYNTH_BLIND_ROOT/cases/odwolanie_XXX/
(SYNTH_BLIND_ROOT defaults to /Users/mat2/orca/projects/hacknation/synth-blind)

Each case dir holds <random>.pdf and <random>.json (official odwolanie schema).
A manifest (template per case) is written next to the case dirs as manifest_odwolanie.jsonl.
The shared dispatcher can call generate(split, n, seed, out_root).
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import random
import shutil
import string
import sys
from pathlib import Path

from .core import BLIND_ROOT, REPO, Ctx, Template, load_template_module, sample_case

CLASS = "odwolanie"
DEV_TPL_DIR = Path(__file__).parent / "templates_dev"
BLIND_TPL_DIR = BLIND_ROOT / "templates" / CLASS


def load_templates(split: str) -> list[Template]:
    out: list[Template] = []
    if split == "dev":
        for f in sorted(DEV_TPL_DIR.glob("t*.py")):
            mod = importlib.import_module(f"{__package__}.templates_dev.{f.stem}")
            out.append(load_template_module(mod))
    elif split == "blind":
        if not BLIND_TPL_DIR.is_dir():
            raise SystemExit(f"blind templates not found in {BLIND_TPL_DIR}")
        for f in sorted(BLIND_TPL_DIR.glob("b*.py")):
            spec = importlib.util.spec_from_file_location(f"_odw_blind_{f.stem}", f)
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader
            spec.loader.exec_module(mod)
            t = load_template_module(mod)
            t.split = "blind"
            out.append(t)
    else:
        raise SystemExit(f"unknown split {split}")
    if not out:
        raise SystemExit(f"no templates for split {split}")
    return out


def random_stem(rng: random.Random) -> str:
    kind = rng.randrange(6)
    h = "".join(rng.choices(string.ascii_lowercase + string.digits, k=rng.randint(6, 10)))
    return [
        h,
        f"scan_{rng.randint(1000, 99999)}",
        f"dokument_{h[:5]}",
        f"{rng.randint(2025, 2026)}{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}_{h[:4]}",
        f"zal_{rng.randint(1, 9)}_{h[:6]}",
        f"plik ({rng.randint(1, 9)})_{h[:3]}",
    ][kind]


def default_out(split: str) -> Path:
    return REPO / "data" / "synth" / "dev" if split == "dev" else BLIND_ROOT / "cases"


def generate(split: str, n: int, seed: int, out_root: Path | None = None, clean: bool = True,
             start: int = 0) -> list[dict]:
    out_root = Path(out_root or default_out(split))
    out_root.mkdir(parents=True, exist_ok=True)
    if clean:
        for d in out_root.glob(f"{CLASS}_[0-9][0-9][0-9]"):  # keep *_mx_* (eval.synth.multi)
            if d.is_dir():
                shutil.rmtree(d)
    templates = load_templates(split)
    rng = random.Random(seed)
    order = []
    while len(order) < n:  # round-robin over shuffled templates -> balanced coverage
        batch = templates[:]
        rng.shuffle(batch)
        order += batch
    manifest = []
    for i in range(n):
        tpl = order[i]
        doc_rng = random.Random(rng.random())
        case = sample_case(doc_rng, tpl.overrides)
        ctx = Ctx(doc_rng)
        cdir = out_root / f"{CLASS}_{start + i:03d}"
        cdir.mkdir(parents=True, exist_ok=True)
        stem = random_stem(doc_rng)
        pdf = cdir / f"{stem}.pdf"
        tpl.render(case, ctx, pdf)
        gt = case.gt()
        (cdir / f"{stem}.json").write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest.append({"case": cdir.name, "file": pdf.name, "template": tpl.name, "split": split,
                         "font": ctx.font, "consortium": case.consortium, "n_zam": len(case.zams),
                         "n_att": len(case.attorneys)})
    with open(out_root / f"manifest_{CLASS}.jsonl", "w", encoding="utf-8") as fh:
        for m in manifest:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--class", dest="cls", default=CLASS)
    ap.add_argument("--split", choices=["dev", "blind"], default="dev")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-clean", action="store_true")
    a = ap.parse_args(argv)
    if a.cls != CLASS:
        print(f"this generator only handles --class {CLASS}", file=sys.stderr)
        return 2
    man = generate(a.split, a.n, a.seed, a.out, clean=not a.no_clean)
    from collections import Counter

    print(f"wrote {len(man)} {CLASS} docs ({a.split}) to {a.out or default_out(a.split)}")
    for t, c in sorted(Counter(m["template"] for m in man).items()):
        print(f"  {t}: {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
