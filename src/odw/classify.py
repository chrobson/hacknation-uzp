"""Content-based classification with rejection. File names are never used."""

from __future__ import annotations

from dataclasses import dataclass

from .config import DocClass
from .textio import Document


@dataclass(frozen=True)
class Verdict:
    cls: DocClass | None
    scores: dict[str, float]

    @property
    def name(self) -> str | None:
        return self.cls.name if self.cls else None


def score(doc_class: DocClass, text: str) -> float:
    total = 0.0
    for sig in doc_class.signals:
        hay = text[: sig.head_chars] if sig.head_chars else text
        if sig.pattern.search(hay):
            total += sig.weight
    return total


def classify(doc: Document, classes: list[DocClass]) -> Verdict:
    if not doc.has_text:
        return Verdict(None, {})
    text = doc.text
    scores = {c.name: score(c, text) for c in classes}
    best = max(classes, key=lambda c: scores[c.name])
    if scores[best.name] < best.threshold:
        return Verdict(None, scores)
    return Verdict(best, scores)
