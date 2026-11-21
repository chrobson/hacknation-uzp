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
    if best.threshold - GREY_BELOW <= scores[best.name] < best.threshold + GREY_ABOVE:
        decided = _llm_tiebreak(text, classes, scores)
        if decided is not _UNDECIDED:
            return Verdict(decided, scores)
    if scores[best.name] < best.threshold:
        return Verdict(None, scores)
    return Verdict(best, scores)


GREY_BELOW, GREY_ABOVE = 2.0, 1.0  # grey zone [threshold-2, threshold+1): rules are unsure
_UNDECIDED = object()


def _llm_tiebreak(text: str, classes: list[DocClass], scores: dict[str, float]):
    """Ask the LLM (if enabled) which class the document is, among classes whose required anchors matched."""
    from . import llm

    if not llm.enabled():
        return _UNDECIDED
    candidates = [c for c in classes if scores[c.name] != float("-inf")]
    if not candidates:
        return _UNDECIDED
    described = "; ".join(f"{c.name}: {c.raw.get('description', c.name)}" for c in candidates)
    answer = llm.ask(
        f"Jakiego rodzaju jest ten dokument? Możliwe rodzaje: {described}. "
        "Jeśli to inny dokument (np. ogłoszenie, wyrok, przystąpienie, odpowiedź na odwołanie), odpowiedz \"inny\".",
        text, {"type": "string", "enum": [c.name for c in candidates] + ["inny"]},
    )
    if answer is None:
        return _UNDECIDED
    return next((c for c in candidates if c.name == answer), None)
