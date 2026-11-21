"""How many ground-truth values pass each configured validator (why `validate:` is warn-only).

    python -m eval.validate_gt [--root data/train]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from odw.config import load_classes  # noqa: E402
from odw.validate import validate  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT / "data" / "train")
    args = ap.parse_args(argv)
    by_key = {next(iter(c.output_template)): c for c in load_classes()}
    stats: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for f in sorted(args.root.rglob("*.json")):
        try:
            gt = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        cls = next((by_key[k] for k in gt if k in by_key), None) if isinstance(gt, dict) else None
        if cls is None:
            continue
        for r in validate(gt, cls.raw.get("validate")):
            key = (cls.name, r["check"])
            stats[key][0] += r["ok"]
            stats[key][1] += 1
    print(f"{'klasa':16} {'check':16} pass/total")
    for (cls_name, check), (ok, total) in sorted(stats.items()):
        print(f"{cls_name:16} {check:16} {ok}/{total} ({ok / total:.0%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
