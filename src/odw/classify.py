"""Content-based classification with rejection. File names are never used."""

from __future__ import annotations

import re

from dataclasses import dataclass

from functools import cache

from .config import DocClass, Signal, load_reject, load_reject_protects
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


@cache
def _reject_protects() -> frozenset[str] | None:
    return load_reject_protects()


def rejected_by(text: str, rules: tuple[Signal, ...] | None = None) -> bool:
    return any(sig.matches(text) for sig in (_reject_rules() if rules is None else rules))


def classify(doc: Document, classes: list[DocClass]) -> Verdict:
    if not doc.has_text:
        return Verdict(None, {})
    text = doc.text
    if rejected_by(text):
        # The reject list guards the classes it names (`protects`). A class added for exactly such a document
        # (an invoice, a KIO ruling …) is still scored; with only the guarded classes loaded the result is {}.
        protects = _reject_protects()
        classes = [] if protects is None else [c for c in classes if c.name not in protects]
        if not classes:
            return Verdict(None, {})
    scores = {c.name: score(c, text) for c in classes}
    best = max(classes, key=lambda c: scores[c.name])
    if best.threshold - GREY_BELOW <= scores[best.name] < best.threshold + GREY_ABOVE:
        decided = _llm_tiebreak(text, classes, scores)
        if decided is not _UNDECIDED:
            return Verdict(decided, scores)
    if scores[best.name] < best.threshold:
        if doc.ocr:  # OCR errors break exact anchors ("0DWOŁANlE"): fuzzy keyword vote as a safety net,
            # but never for a class the rules actively voted against (one of its negative signals fired)
            open_ = [c for c in classes if scores[c.name] == float("-inf")
                     or not any(sig.weight < 0 and sig.matches(text) for sig in c.signals)]
            voted = _fuzzy_vote(text, classes)
            return Verdict(voted if voted in open_ else None, scores)
        return Verdict(None, scores)
    return Verdict(best, scores)


def _fuzzy_vote(text: str, classes: list[DocClass]) -> DocClass | None:
    """Count each class's `classify.fuzzy.words` that occur in the text up to OCR errors (similarity ≥ 0.8).
    The class wins only with ≥ min_hits distinct words and a margin of ≥ 2 over the runner-up."""
    from difflib import SequenceMatcher

    tokens = {t for t in re.findall(r"\w{5,}", text.lower()[:20000])}
    head_tokens = {t for t in re.findall(r"\w{5,}", text.lower()[:600])}
    close = lambda w, toks: w in toks or any(abs(len(t) - len(w)) <= 2 and SequenceMatcher(None, w, t).ratio() >= 0.8 for t in toks)
    hits: dict[str, int] = {}
    for c in classes:
        fz = (c.raw.get("classify") or {}).get("fuzzy") or {}
        if fz.get("head") and not any(close(h.lower(), head_tokens) for h in fz["head"]):
            hits[c.name] = 0  # the document's heading must name the class (e.g. "ODWOŁANIE" at the top)
            continue
        n = 0
        for word in fz.get("words", []):
            w = word.lower()
            if w in tokens or any(abs(len(t) - len(w)) <= 2 and SequenceMatcher(None, w, t).ratio() >= 0.8 for t in tokens):
                n += 1
        hits[c.name] = n if n >= int(fz.get("min_hits", 99)) else 0
    ranked = sorted(hits.items(), key=lambda kv: -kv[1])
    if not ranked or ranked[0][1] == 0 or (len(ranked) > 1 and ranked[0][1] - ranked[1][1] < 2):
        return None
    return next(c for c in classes if c.name == ranked[0][0])


GREY_BELOW, GREY_ABOVE = 2.0, 1.0  # grey zone [threshold-2, threshold+1): rules are unsure
_UNDECIDED = object()


def _llm_tiebreak(text: str, classes: list[DocClass], scores: dict[str, float]):
    """Ask the LLM (if enabled) which class the document is, among classes whose required anchors matched."""
    from . import llm

    if not llm.enabled() or not llm.settings().get("classify_tiebreak"):
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
    # reject-only: the model may veto a grey-zone document ("inny"), never accept one or switch its class
    return None if answer == "inny" else _UNDECIDED
