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
    ap.add_argument(
        "--classes-dir", type=Path, action="append", default=[], metavar="DIR",
        help="dodatkowy folder z klasami (YAML), dołączany do klas podstawowych; można podać wiele razy",
    )
    ap.add_argument("--evidence", type=Path, default=ROOT / "evidence",
                    help="folder na pliki evidence (strona + fragment źródła dla każdego pola); domyślnie ./evidence")
    ap.add_argument("--no-evidence", action="store_true", help="nie zapisuj evidence")
    ap.add_argument("--llm", choices=["on", "off"], help="wymuś włączenie/wyłączenie LLM (domyślnie: config/llm.yaml)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    _setup_logging(args.verbose)
    if args.llm:
        from . import llm

        llm.force(args.llm == "on")
    if not args.input.is_dir():
        print(f"brak folderu wejściowego: {args.input}", file=sys.stderr)
        return 2
    classes = load_classes(args.classes)
    for extra in args.classes_dir:
        classes += load_classes(extra)
    if args.evidence.resolve() == args.output.resolve() or args.output.resolve() in args.evidence.resolve().parents:
        print("evidence nie może trafiać do folderu output (dodatkowe pliki obniżają ocenę)", file=sys.stderr)
        return 2
    results = run(args.input, args.output, classes, None if args.no_evidence else args.evidence)
    rejected = sum(1 for r in results if r.verdict.cls is None)
    from . import llm
    print(f"przetworzono {len(results)} PDF, odrzucono {rejected}, wynik: {args.output}")
    print(llm.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
