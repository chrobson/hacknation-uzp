"""Evidence: where in the PDF each extracted value comes from (page + text snippet).

Values are located after extraction, independently of how they were extracted, so every field type gets
evidence for free. Written to ./evidence/, never to output/ (extra files there lower the UZP score).
"""

from __future__ import annotations

import re
from typing import Any, Iterator

from . import normalize as N
from .textio import Document

SNIPPET = 70


def _leaves(obj: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _leaves(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _leaves(v, f"{path}[{i}]")
    else:
        yield path, obj


def _digits_pattern(digits: str) -> re.Pattern[str]:
    return re.compile(r"(?<!\d)" + r"[\s\- ]?".join(map(re.escape, digits)) + r"(?!\d)")


def _locate(value: Any, text: str) -> tuple[int, int] | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, float):
        for rx in (N.AMOUNT_RE, N.INT_AMOUNT_RE):
            for m in rx.finditer(text):
                if N.find_amount(m.group(0)) == value:
                    return m.span()
        return None
    if isinstance(value, int):
        return None  # small codes (e.g. reason id, 0/1 flags) are derived, not quoted
    s = str(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        for m in N.DATE_RE.finditer(text):
            if N.parse_date(m) == s:
                return m.span()
        return None
    if re.fullmatch(r"(?:PL)?\d{5,}", s):  # identifiers; accounts may keep the printed "PL" prefix
        m = _digits_pattern(s.removeprefix("PL")).search(text)
        return m.span() if m else None
    words = s.split()
    if not words:
        return None
    m = re.compile(r"[\s„”\"]*".join(map(re.escape, words)), re.IGNORECASE).search(text)
    if m:
        return m.span()
    # normalised identifiers such as "2026/BZP00999778" or "999137-2026": match on their digit runs
    runs = [r.lstrip("0") or "0" for r in re.findall(r"\d{4,}", s)]
    for order in (runs, runs[::-1]):  # "999475-2026" is printed as "2026/S 239-999475" (reversed runs)
        if order:
            m = re.compile(r"0*" + r".{0,12}?0*".join(map(re.escape, order)), re.DOTALL).search(text)
            if m:
                return m.span()
    return None


def _boxes(doc: Document, page: int, matched: str) -> list[dict[str, float]]:
    """Bounding boxes (one per text line) of the words that spell `matched` on a 1-based page."""
    if page - 1 >= len(doc.words):
        return []
    words = doc.words[page - 1]
    flat, owner = [], []  # whitespace-free page text and, per character, the index of its word
    for i, w in enumerate(words):
        flat.append(w["text"])
        owner.extend([i] * len(w["text"]))
    needle = "".join(matched.split())
    pos = "".join(flat).find(needle)
    if not needle or pos < 0:
        return []
    hit = sorted(set(owner[pos : pos + len(needle)]))
    lines: dict[float, dict[str, float]] = {}
    for i in hit:
        w = words[i]
        key = next((k for k in lines if abs(k - w["top"]) < 3), w["top"])
        box = lines.setdefault(key, {"x0": w["x0"], "top": w["top"], "x1": w["x1"], "bottom": w["bottom"]})
        box.update(x0=min(box["x0"], w["x0"]), top=min(box["top"], w["top"]), x1=max(box["x1"], w["x1"]), bottom=max(box["bottom"], w["bottom"]))
    return list(lines.values())


def build(doc: Document, class_name: str | None, data: dict[str, Any]) -> dict[str, Any]:
    starts, pos = [], 0
    for page in doc.pages:
        starts.append(pos)
        pos += len(page) + 1  # pages are joined with "\n" in Document.text
    text = doc.text
    fields: dict[str, Any] = {}
    for path, value in _leaves(data):
        if value is None:
            continue
        span = _locate(value, text)
        entry: dict[str, Any] = {"value": value}
        if span:
            page = max(i for i, s in enumerate(starts) if s <= span[0]) + 1
            a, b = max(0, span[0] - SNIPPET), min(len(text), span[1] + SNIPPET)
            matched = " ".join(text[span[0]:span[1]].split())
            entry.update(page=page, start=span[0], end=span[1], snippet=" ".join(text[a:b].split()), match=matched,
                         boxes=_boxes(doc, page, matched))
        else:
            entry["source"] = "derived"  # e.g. id mapped from a dictionary or a 0/1 flag
        fields[path] = entry
    return {"source": doc.path.name, "class": class_name, "pages": len(doc.pages),
            "page_sizes": [list(s) for s in doc.sizes], "coordinates": "PDF points, origin top-left (pdfplumber)",
            "fields": fields}
