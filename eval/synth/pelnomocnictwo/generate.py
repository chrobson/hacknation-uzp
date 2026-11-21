"""Generate synthetic PEŁNOMOCNICTWO PDFs with exact ground truth.

    python -m eval.synth.pelnomocnictwo.generate --split dev --n 30 --seed 1
    python -m eval.synth.pelnomocnictwo.generate --split blind --n 30 --seed 2

(--class pelnomocnictwo is accepted for compatibility with the shared
``eval.synth.generate`` dispatcher, which can call ``generate()`` directly.)

Output per case: <out>/pelnomocnictwo_XXX/<random_name>.pdf + <random_name>.json
(+ meta.json with template id / seed). Dev goes to data/synth/dev/, blind to
<BLIND_ROOT>/cases/. Existing pelnomocnictwo_* case dirs in the target are replaced.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

from eval.synth.pelnomocnictwo import lib

PREFIX = "pelnomocnictwo_"


def default_out(split: str) -> Path:
    return lib.REPO_ROOT / "data" / "synth" / "dev" if split == "dev" else lib.BLIND_ROOT / "cases"


def generate(split: str = "dev", n: int = 30, seed: int = 0, out_dir: Path | None = None, clean: bool = True) -> list[Path]:
    if split not in ("dev", "blind"):
        raise ValueError("split must be dev or blind")
    out = Path(out_dir) if out_dir else default_out(split)
    out.mkdir(parents=True, exist_ok=True)
    if clean:
        for d in out.glob(PREFIX + "[0-9][0-9][0-9]"):  # keep *_mx_* (eval.synth.multi)
            if d.is_dir():
                shutil.rmtree(d)
    templates = lib.load_templates(split)
    rng = random.Random(f"{split}:{seed}")
    order = []
    while len(order) < n:  # round-robin over shuffled templates so every template is used
        batch = templates[:]
        rng.shuffle(batch)
        order.extend(batch)
    written = []
    for i, tpl in enumerate(order[:n]):
        case_seed = rng.randrange(1 << 30)
        crng = random.Random(case_seed)
        case = lib.sample_case(crng, getattr(tpl, "PREFS", None))
        cdir = out / f"{PREFIX}{i:03d}"
        cdir.mkdir(parents=True, exist_ok=True)
        stem = lib.random_filename(crng)
        pdf = cdir / f"{stem}.pdf"
        info = lib.render_pdf(tpl.build, case, crng, pdf)
        gt = case.ground_truth()
        (cdir / f"{stem}.json").write_text(json.dumps(gt, ensure_ascii=False, indent=2), encoding="utf-8")
        (cdir / "meta.json").write_text(json.dumps({"class": lib.CLASS_NAME, "split": split, "template": tpl.ID,
                                                    "case_seed": case_seed, "font": info["font"], "pdf": pdf.name},
                                                   ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(pdf)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--class", dest="cls", default=lib.CLASS_NAME)
    ap.add_argument("--split", choices=["dev", "blind"], default="dev")
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-clean", action="store_true")
    a = ap.parse_args(argv)
    if a.cls != lib.CLASS_NAME:
        print(f"this generator only handles --class {lib.CLASS_NAME}", file=sys.stderr)
        return 2
    paths = generate(a.split, a.n, a.seed, a.out, clean=not a.no_clean)
    print(f"wrote {len(paths)} {lib.CLASS_NAME} cases ({a.split}) to {paths[0].parent.parent if paths else '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
