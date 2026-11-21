"""PDF text extraction. One string per page; empty list when the PDF has no text layer."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace
from pathlib import Path

import pdfplumber

log = logging.getLogger(__name__)

# Below this many non-whitespace characters we treat the PDF as having no text layer.
MIN_TEXT_CHARS = 40


@dataclass(frozen=True)
class Document:
    path: Path
    pages: list[str]
    # per page: words with positions (x0, top, x1, bottom in PDF points, origin top-left) for evidence boxes
    words: list[list[dict]] = field(default_factory=list)
    sizes: list[tuple[float, float]] = field(default_factory=list)  # (width, height) per page

    @property
    def text(self) -> str:
        return "\n".join(self.pages)

    @property
    def has_text(self) -> bool:
        return sum(len(p.split()) for p in self.pages) > 0 and len("".join(self.text.split())) >= MIN_TEXT_CHARS


_NBSP = str.maketrans({"\u00a0": " ", "\u2007": " ", "\u202f": " ", "\u2009": " "})
_SPACE_BEFORE_COLON = re.compile(r"[ \t]+:")


def canonical(doc: Document) -> Document:
    """Typography that should never change a value: exotic spaces → space, "NIP :" → "NIP:"."""
    pages = [_SPACE_BEFORE_COLON.sub(":", p.translate(_NBSP)) for p in doc.pages]
    return replace(doc, pages=pages)


def load_pdf(path: Path) -> Document:
    pages: list[str] = []
    words: list[list[dict]] = []
    sizes: list[tuple[float, float]] = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text(x_tolerance=1.5) or "")
                words.append([
                    {"text": w["text"], "x0": round(w["x0"], 1), "top": round(w["top"], 1), "x1": round(w["x1"], 1), "bottom": round(w["bottom"], 1)}
                    for w in page.extract_words(x_tolerance=1.5)
                ])
                sizes.append((round(float(page.width), 1), round(float(page.height), 1)))
    except Exception as exc:  # corrupt or encrypted PDF: treat as unreadable, never crash the batch
        log.warning("cannot read %s: %s", path, exc)
    return Document(path=path, pages=pages, words=words, sizes=sizes)
