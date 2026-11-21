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
    also: tuple[re.Pattern[str], ...] = ()  # extra patterns that must ALL match too (same head_chars)
    min_count: int = 1  # the main pattern must occur at least this many times (e.g. two account numbers)

    def matches(self, text: str) -> bool:
        hay = text[: self.head_chars] if self.head_chars else text
        if self.min_count > 1:
            found = len({m.group(0) for m in self.pattern.finditer(hay)}) >= self.min_count
        else:
            found = bool(self.pattern.search(hay))
        return found and all(p.search(hay) for p in self.also)


@dataclass(frozen=True)
class DocClass:
    name: str
    signals: list[Signal]
    threshold: float
    required: list[Signal]  # at least one must match, otherwise the class is not considered
    output_template: dict[str, Any]
    raw: dict[str, Any] = field(repr=False)


def _signals(items: list[dict[str, Any]] | None) -> list[Signal]:
    out = []
    for item in items or []:
        if isinstance(item, str):
            item = {"pattern": item}
        patterns = item["all"] if "all" in item else [item["pattern"]]
        out.append(
            Signal(
                pattern=re.compile(patterns[0], _FLAGS),
                weight=float(item.get("weight", 1)),
                head_chars=item.get("head_chars"),
                also=tuple(re.compile(p, _FLAGS) for p in patterns[1:]),
                min_count=int(item.get("min_count", 1)),
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
        required=_signals(cls.get("required")),
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
