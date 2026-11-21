"""Formal check of a whole case (one input subfolder) with rules from config/case_rules.yaml.

Runs after all PDFs of the run are processed, reads only the extracted JSONs, and writes
evidence/<sprawa>/_sprawa.report.json (never output/). Paths are `<class>.<json path>`, e.g.
`przelew.przelew_bankowy.kwota` = that field in every document of class `przelew` in the case.
Operators: exists, in, eq, fuzzy_eq (stdlib difflib), one_of_amounts, days_between_le. A new operator = one function in OPS.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from pathlib import Path
from typing import Any, Callable

import yaml

from .config import ROOT, fold
from .validate import resolve

log = logging.getLogger(__name__)
RULES_FILE = ROOT / "config" / "case_rules.yaml"

Case = dict[str, list[dict[str, Any]]]  # class name -> extracted JSONs of that class in the case


def values(case: Case, ref: str) -> list[Any]:
    cls, _, path = ref.partition(".")
    out = []
    for doc in case.get(cls, []):
        out += [v for _, v in resolve(doc, path) if v not in (None, "")] if path else [doc]
    return out


def _from_file(spec: dict[str, Any]) -> list[Any]:
    """`values_from: {file: config/classes/przelew.yaml, key: accounts.known_receivers}` — reuse existing config."""
    node: Any = yaml.safe_load((ROOT / spec["file"]).read_text(encoding="utf-8"))
    for part in spec["key"].split("."):
        node = node.get(part, []) if isinstance(node, dict) else []
    return list(node or [])


def _norm(v: Any) -> str:
    s = fold(str(v)).lower()
    return "".join(s.split()).removeprefix("pl") if s.replace(" ", "").removeprefix("pl").isdigit() else " ".join(s.split())


def _rhs(rule: dict[str, Any], case: Case) -> list[Any]:
    if "right" in rule:
        return values(case, rule["right"])
    if "values_from" in rule:
        return _from_file(rule["values_from"])
    return list(rule.get("values", []))


def op_exists(left: list[Any], rule: dict[str, Any], case: Case) -> tuple[bool, str]:
    return bool(left), f"znaleziono {len(left)}"


def op_in(left: list[Any], rule: dict[str, Any], case: Case) -> tuple[bool, str]:
    allowed = {_norm(v) for v in _rhs(rule, case)}
    hit = [v for v in left if _norm(v) in allowed]
    return bool(hit), f"{hit[0]} na liście" if hit else f"{', '.join(map(str, left))} spoza listy ({len(allowed)} pozycji)"


def op_eq(left: list[Any], rule: dict[str, Any], case: Case) -> tuple[bool, str]:
    right = {_norm(v) for v in _rhs(rule, case)}
    hit = [v for v in left if _norm(v) in right]
    return bool(hit), f"zgodne: {hit[0]}" if hit else f"{left} ≠ {_rhs(rule, case)}"


def similarity(a: Any, b: Any) -> float:
    """0-100, case/diacritics/word-order insensitive; stdlib only (rapidfuzz is a dev dependency)."""
    from difflib import SequenceMatcher

    ta, tb = (sorted(re.findall(r"\w+", _norm(x))) for x in (a, b))
    if not ta or not tb:
        return 0.0
    if len(ta) > 1 and len(tb) > 1 and (set(ta) <= set(tb) or set(tb) <= set(ta)):
        return 100.0  # "Silvatica Automatyka" ~ "Silvatica Automatyka sp. k."
    return 100.0 * SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()


def op_fuzzy_eq(left: list[Any], rule: dict[str, Any], case: Case) -> tuple[bool, str]:
    right = _rhs(rule, case)
    best = max(((similarity(a, b), a, b) for a in left for b in right), default=(0, None, None))
    ok = best[0] >= float(rule.get("min_score", 85))
    return ok, f"podobieństwo {best[0]:.0f}%: „{best[1]}” ~ „{best[2]}”"


def op_one_of_amounts(left: list[Any], rule: dict[str, Any], case: Case) -> tuple[bool, str]:
    amounts = [float(a) for a in _rhs(rule, case)]
    hit = [v for v in left if isinstance(v, (int, float)) and any(abs(v - a) < 0.005 for a in amounts)]
    return bool(hit), f"kwota {hit[0]} zł" if hit else f"kwoty {left} spoza {amounts}"


def op_days_between_le(left: list[Any], rule: dict[str, Any], case: Case) -> tuple[bool, str]:
    right = _rhs(rule, case)
    later, earlier = dt.date.fromisoformat(str(left[0])), dt.date.fromisoformat(str(right[0]))
    days = (later - earlier).days
    return 0 <= days <= int(rule["max"]), f"{days} dni (limit {rule['max']})"


OPS: dict[str, Callable[[list[Any], dict[str, Any], Case], tuple[bool, str]]] = {
    "exists": op_exists, "in": op_in, "eq": op_eq, "fuzzy_eq": op_fuzzy_eq,
    "one_of_amounts": op_one_of_amounts, "days_between_le": op_days_between_le,
}
NEEDS_RIGHT = {"eq", "fuzzy_eq", "days_between_le"}  # comparisons: not evaluable when either side is missing


def load_rules(path: Path = RULES_FILE) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rules = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("rules") or []
    for r in rules:
        if r.get("op") not in OPS:
            raise SystemExit(f"{path.name}: reguła {r.get('id')}: nieznany operator {r.get('op')!r} (dostępne: {', '.join(OPS)})")
    return rules


def check_case(case: Case, rules: list[dict[str, Any]]) -> dict[str, Any]:
    results = []
    for rule in rules:
        entry = {"id": rule["id"], "label": rule.get("label", rule["id"]), "severity": rule.get("severity", "error")}
        missing_when = [w for w in rule.get("when", []) if not values(case, w)]
        left = values(case, rule["left"])
        if missing_when:
            entry.update(status="n/a", message=f"nie dotyczy: brak {', '.join(missing_when)}")
        elif not left and (rule["op"] in NEEDS_RIGHT or rule.get("missing") == "n/a"):
            entry.update(status="n/a", message=f"brak danych: {rule['left']}")
        elif rule["op"] in NEEDS_RIGHT and not _rhs(rule, case):
            entry.update(status="n/a", message=f"brak danych: {rule.get('right')}")
        else:
            try:
                ok, msg = OPS[rule["op"]](left, rule, case) if left or rule["op"] == "exists" else (False, "brak wartości")
            except Exception as e:  # a broken rule or odd value must not break the run
                ok, msg = False, f"błąd reguły: {e}"
            entry.update(status="ok" if ok else "fail", message=msg)
            if not ok and rule.get("on_fail"):
                entry["hint"] = rule["on_fail"]
        results.append(entry)
    evaluated = [r for r in results if r["status"] != "n/a"]
    passed = [r for r in evaluated if r["status"] == "ok"]
    return {"documents": {k: len(v) for k, v in case.items()}, "passed": len(passed), "evaluated": len(evaluated),
            "total": len(results), "rules": results}


def summary_line(name: str, report: dict[str, Any]) -> str:
    fails = [("info: " if r["severity"] == "info" else "") + (r.get("hint") or r["label"])
             for r in report["rules"] if r["status"] == "fail"]
    fails.sort(key=lambda f: f.startswith("info: "))  # errors first
    na = report["total"] - report["evaluated"]
    tail = ("; " + "; ".join(fails)) if fails else ""
    return f"{name}: {report['passed']}/{report['evaluated']} OK" + (f" ({na} n/d)" if na else "") + tail


def group_cases(results: list[Any], input_dir: Path) -> dict[str, Case]:
    """Pipeline results grouped by input subfolder ("." for PDFs directly in input/); folders with only rejected documents are skipped."""
    cases: dict[str, Case] = {}
    for r in results:
        rel = r.source.relative_to(input_dir).parent
        if r.verdict.name:
            cases.setdefault(rel.as_posix() if rel.parts else ".", {}).setdefault(r.verdict.name, []).append(r.data)
    return cases


def run_cases(results: list[Any], input_dir: Path, evidence_dir: Path | None, rules: list[dict[str, Any]] | None = None,
              echo: Callable[[str], None] | None = None) -> dict[str, dict[str, Any]]:
    """Group pipeline results by input subfolder, check each case, write _sprawa.report.json next to the evidence."""
    rules = load_rules() if rules is None else rules
    if not rules:
        return {}
    reports = {}
    for name, case in sorted(group_cases(results, input_dir).items()):
        report = check_case(case, rules)
        reports[name] = report
        if evidence_dir is not None:
            try:
                target = evidence_dir / name / "_sprawa.report.json"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({"sprawa": name, **report}, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                log.exception("cannot write case report for %s", name)
        if echo:
            echo(summary_line(name, report))
    return reports
