"""Mutation proof, step 3: map mutated output back to original keys and diff against the normal output.

    python scripts/mutation/unmutate.py REVERSE_MAP MUTATED_OUT NORMAL_OUT [--evidence-mut DIR --evidence-ref DIR]

Prints differing files/leaves; last line: 'IDENTICAL: 0 differences in K files' or 'DIFFERENT: ...'. Exit 0 iff identical.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


LEAKED: set[str] = set()  # keys in the mutated output that are not tokens = names the code wrote by itself


def unmap(obj, km):
    if isinstance(obj, dict):
        LEAKED.update(k for k in obj if k not in km)
        return {km.get(k, "LEAK:" + k): unmap(v, km) for k, v in obj.items()}
    if isinstance(obj, list):
        return [unmap(v, km) for v in obj]
    return obj


def leaves(obj, prefix=""):
    if isinstance(obj, dict):
        if not obj:
            yield prefix or "$", "{}"
        for k, v in obj.items():
            yield from leaves(v, f"{prefix}.{k}" if prefix else k)
    elif isinstance(obj, list):
        if not obj:
            yield prefix, "[]"
        for i, v in enumerate(obj):
            yield from leaves(v, f"{prefix}[{i}]")
    else:
        yield prefix, json.dumps(obj, ensure_ascii=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("reverse_map", type=Path)
    ap.add_argument("mutated", type=Path)
    ap.add_argument("normal", type=Path)
    a = ap.parse_args()
    km = json.loads(a.reverse_map.read_text(encoding="utf-8"))["keys"]
    mut = {p.relative_to(a.mutated): p for p in a.mutated.rglob("*.json")}
    ref = {p.relative_to(a.normal): p for p in a.normal.rglob("*.json")}
    files = sorted(set(mut) | set(ref))
    bad_files, bad_leaves, n_leaves = 0, 0, 0
    for rel in files:
        if rel not in mut or rel not in ref:
            print(f"MISSING {'mutated' if rel not in mut else 'normal'}: {rel}")
            bad_files += 1
            continue
        m = dict(leaves(unmap(json.loads(mut[rel].read_text(encoding="utf-8")), km)))
        r = dict(leaves(json.loads(ref[rel].read_text(encoding="utf-8"))))
        n_leaves += len(r)
        diff = [k for k in sorted(set(m) | set(r)) if m.get(k) != r.get(k)]
        if diff:
            bad_files += 1
            bad_leaves += len(diff)
            for k in diff:
                print(f"DIFF {rel} {k}: normal={r.get(k)} mutated={m.get(k)}")
    if LEAKED:
        print(f"LEAKED keys (hardcoded in code, not from YAML): {sorted(LEAKED)}")
    if bad_files == 0:
        print(f"IDENTICAL: 0 differences in {len(files)} files ({n_leaves} leaves)")
        return 0
    print(f"DIFFERENT: {bad_leaves} leaves in {bad_files} of {len(files)} files")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
