"""Content-based classification with rejection. File names are never used."""

from __future__ import annotations

from dataclasses import dataclass

from functools import cache

from .config import DocClass, Signal, load_reject
from .textio import Document


@dataclass(frozen=True)
class Verdict:
    cls: DocClass | None
    scores: dict[str, float]

    @property
    def name(self) -> str | None:
        return self.cls.name if self.cls else None


def score(doc_class: DocClass, text: str) -> float:
    if doc_class.required and not any(sig.matches(text) for sig in doc_class.required):
        return float("-inf")
    return sum(sig.weight for sig in doc_class.signals if sig.matches(text))


@cache
def _reject_rules() -> tuple[Signal, ...]:
    return tuple(load_reject())


def rejected_by(text: str, rules: tuple[Signal, ...] | None = None) -> bool:
    return any(sig.matches(text) for sig in (_reject_rules() if rules is None else rules))


def classify(doc: Document, classes: list[DocClass]) -> Verdict:
    if not doc.has_text:
        return Verdict(None, {})
    text = doc.text
    if rejected_by(text):
        return Verdict(None, {})
    scores = {c.name: score(c, text) for c in classes}
    best = max(classes, key=lambda c: scores[c.name])
    if scores[best.name] < best.threshold:
        return Verdict(None, scores)
    return Verdict(best, scores)
