"""Mutation proof, step 1: rename every class name and every output key in config/classes/*.yaml.

    python scripts/mutation/mutate.py SRC_DIR OUT_DIR [--seed N] [--strict]

Writes OUT_DIR/classes/<token>.yaml and OUT_DIR/reverse_map.json ({"classes": {...}, "keys": {...}}).
Regexes, labels, dictionaries, thresholds stay byte-identical; only identifiers that end up in the JSON output
(class `name`, output_template keys, and every place a YAML refers to an output path) are replaced by random tokens.
--strict: do not add the explicit `field:` to `type: names` specs (exposes the Python default name).
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

import yaml


def collect_keys(obj, keys: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            collect_keys(v, keys)
    elif isinstance(obj, list):
        for v in obj:
            collect_keys(v, keys)


def rename_tree(obj, km: dict[str, str]):
    if isinstance(obj, dict):
        return {km[k]: rename_tree(v, km) for k, v in obj.items()}
    if isinstance(obj, list):
        return [rename_tree(v, km) for v in obj]
    return obj


def rename_path(path: str, km: dict[str, str]) -> str:
    """a.b[0].c -> km[a].km[b][0].km[c]"""
    return re.sub(r"[^.\[\]]+", lambda m: km[m.group(0)], path)


def fix_specs(specs, km: dict[str, str], strict: bool):
    """Field specs (one dict or a list): rename every value that is an output path or output key."""
    items = specs if isinstance(specs, list) else [specs]
    for s in items:
        if not isinstance(s, dict):
            continue
        for ref in ("exclude_from", "before_field"):
            if ref in s:
                s[ref] = rename_path(s[ref], km)
        if s.get("type") == "names":
            if "field" in s:
                s["field"] = km[s["field"]]
            elif not strict:
                s["field"] = km["imie_nazwisko"]  # Python default (fields.py), made explicit
            if "company_field" in s:
                s["company_field"] = km[s["company_field"]]
            for sub in ("extra", "attrs"):
                if sub in s:
                    s[sub] = {km[k]: v for k, v in s[sub].items()}
    return specs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--reverse-order", action="store_true", help="tokens sort in the opposite order to the original files")
    a = ap.parse_args()

    # JSON round-trip breaks YAML anchor/alias sharing so each spec is rewritten exactly once.
    raws = {p: json.loads(json.dumps(yaml.safe_load(p.read_text(encoding="utf-8")))) for p in sorted(a.src.glob("*.yaml"))}
    keys: set[str] = set()
    for r in raws.values():
        collect_keys(r["output_template"], keys)
    rng = random.Random(a.seed)
    tokens = rng.sample(range(100, 999), len(keys) + len(raws))
    km = {k: f"f{tokens[i]}" for i, k in enumerate(sorted(keys))}
    # class tokens keep the original sort order of files, so any order-dependent tie-break is unchanged
    n = len(raws)
    cm = {r["name"]: f"klasa_{chr(97 + (n - 1 - i if a.reverse_order else i))}" for i, r in enumerate(raws.values())}

    (a.out / "classes").mkdir(parents=True, exist_ok=True)
    for p, r in raws.items():
        r["name"] = cm[r["name"]]
        r["output_template"] = rename_tree(r["output_template"], km)
        r["fields"] = {rename_path(k, km): fix_specs(v, km, a.strict) for k, v in (r.get("fields") or {}).items()}
        if r.get("lists"):
            new = {}
            for k, spec in r["lists"].items():
                spec["fields"] = {rename_path(fk, km): fix_specs(fv, km, a.strict) for fk, fv in spec["fields"].items()}
                new[rename_path(k, km)] = spec
            r["lists"] = new
        if r.get("derive"):
            r["derive"] = {rename_path(k, km): {**v, "from": rename_path(v["from"], km)} for k, v in r["derive"].items()}
        (a.out / "classes" / f"{r['name']}.yaml").write_text(
            yaml.safe_dump(r, allow_unicode=True, sort_keys=False, width=10**6), encoding="utf-8")
    rev = {"classes": {v: k for k, v in cm.items()}, "keys": {v: k for k, v in km.items()}}
    (a.out / "reverse_map.json").write_text(json.dumps(rev, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"mutated {len(raws)} classes, {len(km)} output keys -> {a.out}/classes", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
