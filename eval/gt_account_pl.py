"""Rewrite local ground truth for account numbers to the convention confirmed by UZP.

UZP answer (HackNation Discord, 21.11.2026 21:17): the account number is "the number contained in the document";
reference JSONs without the "PL" prefix are an error that will not occur in the evaluation set.
Rule applied here: if the PDF prints "PL" before the number (also "PL 12 3456 ...", "IBAN: PL..."), the GT value
becomes "PL" + 26 digits without spaces; otherwise it stays 26 digits.

    python -m eval.gt_account_pl [--write] [DIR ...]     (default: data/train data/scans data/synth/dev)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from odw import normalize as N  # noqa: E402
from odw.textio import canonical, load_pdf  # noqa: E402

FIELDS = ("z_rachunku", "na_rachunek")
DEFAULT_DIRS = ("data/train", "data/scans", "data/synth/dev")


def pdf_for(gt: Path) -> Path | None:
    same = gt.with_suffix(".pdf")
    if same.exists():
        return same
    pdfs = [p for p in gt.parent.glob("*.pdf") if "przelew" in p.name.lower()]
    return pdfs[0] if len(pdfs) == 1 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*", default=list(DEFAULT_DIRS))
    ap.add_argument("--write", action="store_true", help="save the rewritten JSON files (default: dry run)")
    args = ap.parse_args()
    total = prefixed = changed = 0
    for d in args.dirs:
        for gt in sorted(Path(d).rglob("*.json")):
            if gt.name.startswith("manifest"):
                continue
            data = json.loads(gt.read_text(encoding="utf-8"))
            pb = data.get("przelew_bankowy") if isinstance(data, dict) else None
            if not isinstance(pb, dict):
                continue
            pdf = pdf_for(gt)
            if pdf is None:
                print(f"!! brak PDF dla {gt}", file=sys.stderr)
                continue
            text = canonical(load_pdf(pdf)).text
            with_pl = {N.digits(m.group("num")) for m in N.ACCOUNT_RE.finditer(text) if m.group("pl")}
            dirty = False
            for f in FIELDS:
                v = pb.get(f)
                if not isinstance(v, str) or not v:
                    continue
                num = N.digits(v)
                total += 1
                new = ("PL" + num) if num in with_pl else num
                prefixed += new.startswith("PL")
                if new != v:
                    print(f"{gt}: {f} {v} -> {new}")
                    pb[f] = new
                    changed += 1
                    dirty = True
            if dirty and args.write:
                gt.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"pól rachunku: {total}, z PL w dokumencie: {prefixed}, zmienionych: {changed}"
          + ("" if args.write else " (dry run)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
