"""CLI: python -m odw [--input input] [--output output]"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import CLASSES_DIR, ROOT, load_classes
from .pipeline import run


def _setup_logging(verbose: bool) -> None:
    """Console: warnings (or info with -v). File: everything, in ./logs/ (never in output/)."""
    import time

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO if verbose else logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    root.addHandler(console)
    try:
        logs = ROOT / "logs"
        logs.mkdir(exist_ok=True)
        fh = logging.FileHandler(logs / f"run-{time.strftime('%Y%m%d-%H%M%S')}.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(fh)
    except OSError:
        pass  # read-only checkout: console logging only


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="odw", description="Odwołania2JSON: PDF -> JSON")
    ap.add_argument("--input", type=Path, default=ROOT / "input", help="folder z podfolderami spraw (domyślnie ./input)")
    ap.add_argument("--output", type=Path, default=ROOT / "output", help="folder wynikowy (domyślnie ./output)")
    ap.add_argument("--classes", type=Path, default=CLASSES_DIR, help="folder z definicjami klas dokumentów (YAML)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    _setup_logging(args.verbose)
    if not args.input.is_dir():
        print(f"brak folderu wejściowego: {args.input}", file=sys.stderr)
        return 2
    results = run(args.input, args.output, load_classes(args.classes))
    rejected = sum(1 for r in results if r.verdict.cls is None)
    print(f"przetworzono {len(results)} PDF, odrzucono {rejected}, wynik: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
