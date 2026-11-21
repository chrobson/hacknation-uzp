"""PDF text extraction. One string per page; empty list when the PDF has no text layer."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

log = logging.getLogger(__name__)

# Below this many non-whitespace characters we treat the PDF as having no text layer.
MIN_TEXT_CHARS = 40


@dataclass(frozen=True)
class Document:
    path: Path
    pages: list[str]

    @property
    def text(self) -> str:
        return "\n".join(self.pages)

    @property
    def has_text(self) -> bool:
        return sum(len(p.split()) for p in self.pages) > 0 and len("".join(self.text.split())) >= MIN_TEXT_CHARS


def load_pdf(path: Path) -> Document:
    pages: list[str] = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text(x_tolerance=1.5) or "")
    except Exception as exc:  # corrupt or encrypted PDF: treat as unreadable, never crash the batch
        log.warning("cannot read %s: %s", path, exc)
    return Document(path=path, pages=pages)
