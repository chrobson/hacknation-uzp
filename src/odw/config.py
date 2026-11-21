"""Document-class configuration. Every class is one YAML file in config/classes/."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CLASSES_DIR = ROOT / "config" / "classes"

_FLAGS = re.IGNORECASE | re.MULTILINE


@dataclass(frozen=True)
class Signal:
    pattern: re.Pattern[str]
    weight: float
    head_chars: int | None  # search only the first N characters of the document; None = whole text


@dataclass(frozen=True)
class DocClass:
    name: str
    signals: list[Signal]
    threshold: float
    output_template: dict[str, Any]
    raw: dict[str, Any] = field(repr=False)


def _signals(items: list[dict[str, Any]] | None) -> list[Signal]:
    out = []
    for item in items or []:
        out.append(
            Signal(
                pattern=re.compile(item["pattern"], _FLAGS),
                weight=float(item.get("weight", 1)),
                head_chars=item.get("head_chars"),
            )
        )
    return out


def load_class(path: Path) -> DocClass:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    cls = raw["classify"]
    return DocClass(
        name=raw["name"],
        signals=_signals(cls.get("signals")),
        threshold=float(cls["threshold"]),
        output_template=raw["output_template"],
        raw=raw,
    )


REJECT_FILE = ROOT / "config" / "reject.yaml"


def load_reject(path: Path = REJECT_FILE) -> list[Signal]:
    if not path.exists():
        return []
    return _signals(yaml.safe_load(path.read_text(encoding="utf-8")).get("reject"))


def load_classes(directory: Path = CLASSES_DIR) -> list[DocClass]:
    classes = [load_class(p) for p in sorted(directory.glob("*.yaml"))]
    if not classes:
        raise SystemExit(f"no document classes found in {directory}")
    return classes
