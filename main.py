"""Entry point that works without installing the package: python main.py [--input ...] [--output ...]"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from odw.__main__ import main  # noqa: E402

raise SystemExit(main())
