"""Render multi-entity / party-detail dev cases with exact ground truth.

    python -m eval.synth.multi.generate [--seed 11] [--out data/synth/dev]

Writes data/synth/dev/odwolanie_mx_XXX/ and pelnomocnictwo_mx_XXX/ (one <random>.pdf +
<same stem>.json each) and manifest_multi.jsonl. Only *_mx_* dirs are replaced; the
other generators only clean their own *_NNN dirs.

Scenarios cover: 2-3 contracting authorities (numbered, 'Zamawiający 1/2', 'wspólnie',
'w imieniu i na rzecz', tables, one paragraph), a leading authority (prowadzacy 1, others 0;
all 0 when none is designated; null for a single authority), consortium appellants (GT =
leader only, also when listed second), attorneys with and without a law firm, titles
(adw., r.pr., radca prawny, mec.) and inflected names, POAs with two principals and
several signatories, identifiers in footers and key:value tables.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path

from ..odwolanie.core import Ctx as OdwCtx
from ..odwolanie.generate import random_stem
from ..pelnomocnictwo import lib as L
from . import odw, poa

REPO = Path(__file__).resolve().parents[3]

# (template, make_case kwargs, variant)
ODW_SCENARIOS = [
    ("m01_numbered", dict(n_zam=2, lead=0), {}),
    ("m01_numbered", dict(n_zam=3, lead=1, att="nofirm", title="adw"), {}),
    ("m02_labelled", dict(n_zam=2, lead=1), {}),
    ("m02_labelled", dict(n_zam=3, lead=0, n_odw=2), {"inline": True}),
    ("m03_prose_wspolnie", dict(n_zam=2, lead=None), {}),
    ("m03_prose_wspolnie", dict(n_zam=3, lead=2, title="rp"), {}),
    ("m04_w_imieniu", dict(n_zam=2, lead=0), {}),
    ("m04_w_imieniu", dict(n_zam=3, lead=0, att="nofirm"), {}),
    ("m05_tables", dict(n_zam=2, lead=1), {}),
    ("m05_tables", dict(n_zam=3, lead=0, n_odw=2), {"leader_last": True}),
    ("m06_kv_footer", dict(n_zam=1), {}),
    ("m06_kv_footer", dict(n_zam=2, lead=1, att="nofirm", n_odw=2), {}),
    ("m07_consortium_prose", dict(n_zam=1, n_odw=2, title="adw"), {}),
    ("m07_consortium_prose", dict(n_zam=1, n_odw=3, att="nofirm", title="rp"), {}),
    ("m08_leader_second", dict(n_zam=1, n_odw=2, n_att=2), {}),
    ("m08_leader_second", dict(n_zam=2, lead=0, n_odw=2, n_att=3), {}),
    ("m09_two_columns", dict(n_zam=2, lead=0, n_odw=2), {}),
    ("m09_two_columns", dict(n_zam=3, lead=None, att="none"), {}),
    ("m10_firm_letterhead", dict(n_zam=1, title=""), {}),
    ("m10_firm_letterhead", dict(n_zam=2, lead=1, att="nofirm", title="rp"), {}),
]

POA_SCENARIOS = [
    ("p01_columns", dict(n_principals=2, n_sig=(2, 1), n_att=1)),
    ("p01_columns", dict(n_principals=2, n_sig=(1, 2), n_att=2)),
    ("p02_prose_inflected", dict(n_principals=2, n_sig=(2, 2), n_att=1)),
    ("p02_prose_inflected", dict(n_principals=2, n_sig=(1, 1), n_att=2, fizyczna=(False, True))),
    ("p03_footer_ids", dict(n_principals=1, n_sig=(3,), n_att=2)),
    ("p03_footer_ids", dict(n_principals=1, n_sig=(2,), n_att=1)),
    ("p04_kv_forms", dict(n_principals=2, n_sig=(2, 1), n_att=2)),
    ("p04_kv_forms", dict(n_principals=2, n_sig=(1, 1), n_att=3, fizyczna=(True, False))),
    ("p05_joint_letter", dict(n_principals=2, n_sig=(2, 2), n_att=1)),
    ("p05_joint_letter", dict(n_principals=2, n_sig=(3, 1), n_att=2)),
]


def generate(seed: int = 11, out_root: Path | None = None) -> list[dict]:
    out_root = Path(out_root or REPO / "data" / "synth" / "dev")
    out_root.mkdir(parents=True, exist_ok=True)
    for d in list(out_root.glob("odwolanie_mx_*")) + list(out_root.glob("pelnomocnictwo_mx_*")):
        if d.is_dir():
            shutil.rmtree(d)
    rng = random.Random(f"multi:{seed}")
    manifest = []
    for i, (tpl, kw, variant) in enumerate(ODW_SCENARIOS):
        crng = random.Random(rng.randrange(1 << 30))
        case = odw.make_case(crng, **kw)
        ctx = OdwCtx(crng)
        cdir = out_root / f"odwolanie_mx_{i:03d}"
        cdir.mkdir()
        stem = random_stem(crng)
        odw.TEMPLATES[tpl](case, ctx, cdir / f"{stem}.pdf", variant)
        (cdir / f"{stem}.json").write_text(json.dumps(case.gt(), ensure_ascii=False, indent=2), encoding="utf-8")
        manifest.append({"case": cdir.name, "file": f"{stem}.pdf", "template": tpl, "font": ctx.font, **kw, **variant})
    for i, (tpl, kw) in enumerate(POA_SCENARIOS):
        crng = random.Random(rng.randrange(1 << 30))
        case = poa.make_case(crng, **kw)
        cdir = out_root / f"pelnomocnictwo_mx_{i:03d}"
        cdir.mkdir()
        stem = L.random_filename(crng)
        fn = poa.TEMPLATES[tpl]
        info = L.render_pdf(lambda c, fn=fn: fn(c, {}), case, crng, cdir / f"{stem}.pdf")
        (cdir / f"{stem}.json").write_text(json.dumps(case.ground_truth(), ensure_ascii=False, indent=2), encoding="utf-8")
        manifest.append({"case": cdir.name, "file": f"{stem}.pdf", "template": tpl, "font": info["font"],
                         **{k: list(v) if isinstance(v, tuple) else v for k, v in kw.items()}})
    with open(out_root / "manifest_multi.jsonl", "w", encoding="utf-8") as fh:
        for m in manifest:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    man = generate(a.seed, a.out)
    print(f"wrote {len(man)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
