"""Export mapping configured in YAML: config/mappings/<name>.yaml -> exports/<name>.csv, one row per case.

    columns:
      - {column: Odwołujący, path: odwolanie.Odwolujacy[*].nazwa, join: "; "}

Paths are the same as in case_rules.yaml (`<class>.<json path>`); `_sprawa` is the case folder name and
`_kontrola.<field>` reads the formal-check report (passed/evaluated/summary). Never writes to output/.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml

from .case_check import Case, group_cases, summary_line, values
from .config import ROOT

MAPPINGS_DIR = ROOT / "config" / "mappings"


def load_mapping(name: str, directory: Path = MAPPINGS_DIR) -> dict[str, Any]:
    path = directory / f"{name}.yaml"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in directory.glob("*.yaml"))) or "brak"
        raise SystemExit(f"brak mapowania {name!r} w {directory} (dostępne: {available})")
    spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for col in spec.get("columns") or []:
        if not {"column", "path"} <= col.keys():
            raise SystemExit(f"{path.name}: każda kolumna wymaga pól column i path: {col}")
    return spec


def _cell(name: str, case: Case, report: dict[str, Any] | None, col: dict[str, Any]) -> str:
    path = col["path"]
    if path == "_sprawa":
        vals: list[Any] = [name]
    elif path.startswith("_kontrola."):
        key = path.split(".", 1)[1]
        vals = [] if report is None else [summary_line(name, report).split(": ", 1)[1] if key == "summary" else report.get(key)]
    else:
        vals = values(case, path)
    vals = [v for v in vals if v not in (None, "")]
    if not vals:
        return str(col.get("default", ""))
    if "join" not in col:
        vals = vals[:1]
    return str(col.get("join", "")).join(dict.fromkeys(str(v) for v in vals))  # de-duplicated, order kept


def rows(spec: dict[str, Any], cases: dict[str, Case], reports: dict[str, dict[str, Any]]) -> list[list[str]]:
    cols = spec["columns"]
    return [[c["column"] for c in cols]] + [[_cell(n, cases[n], reports.get(n), c) for c in cols] for n in sorted(cases)]


def export(name: str, results: list[Any], input_dir: Path, exports_dir: Path,
           reports: dict[str, dict[str, Any]] | None = None) -> Path:
    spec = load_mapping(name)
    cases = group_cases(results, input_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)
    target = exports_dir / f"{name}.csv"
    # utf-8 with BOM and ";" so that Excel with Polish locale opens it directly with diacritics
    with target.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=spec.get("delimiter", ";")).writerows(rows(spec, cases, reports or {}))
    return target
