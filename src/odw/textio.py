"""PDF text extraction. One string per page.

Text-layer PDFs are read with pdfplumber. PDFs without a text layer (scans) are rendered with pypdfium2 and read
with Tesseract OCR (`tesseract -l pol`, called as a subprocess). Without Tesseract or its Polish model the scan
yields no text and the document is rejected ({}), with a warning in the log.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
import re
import shutil
import subprocess
import tempfile
from functools import cache
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
    ocr: bool = False  # text comes from OCR (scan without a text layer)

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


OCR_DPI = 300
OCR_MAX_PAGES = 12
OCR_PAGE_TIMEOUT_S = 60
OCR_WORKERS = max(1, min(8, (os.cpu_count() or 2)))
OCR_LANG = os.environ.get("ODW_OCR_LANG", "pol")
_EMAIL_AT = re.compile(r"\b([\w.+-]{2,})[Q©®](?=[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b)")


@cache
def ocr_available() -> bool:
    exe = shutil.which("tesseract")
    if not exe:
        log.warning("tesseract not found: scanned PDFs cannot be read (install tesseract-ocr tesseract-ocr-pol)")
        return False
    try:
        langs = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=20).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return False
    if OCR_LANG not in langs:
        log.warning("tesseract has no '%s' model: scanned PDFs cannot be read (install tesseract-ocr-pol)", OCR_LANG)
        return False
    return True


def _ocr_page(image_path: Path, scale: float) -> tuple[str, list[dict]]:
    """Tesseract TSV → page text (one line per OCR line) and word boxes in PDF points (origin top-left)."""
    out = subprocess.run(
        ["tesseract", str(image_path), "stdout", "-l", OCR_LANG, "--psm", "4", "-c", "tessedit_create_tsv=1"],
        capture_output=True, text=True, timeout=OCR_PAGE_TIMEOUT_S,
        env={**os.environ, "OMP_THREAD_LIMIT": "1"},  # pages run in parallel; one thread each avoids oversubscription
    ).stdout
    lines: dict[tuple[int, int, int], list[str]] = {}
    words: list[dict] = []
    for row in out.splitlines()[1:]:
        cols = row.split("\t")
        if len(cols) < 12 or cols[0] != "5" or not cols[11].strip():
            continue
        block, par, line = int(cols[2]), int(cols[3]), int(cols[4])
        left, top, width, height = (int(c) for c in cols[6:10])
        text = cols[11].strip()
        lines.setdefault((block, par, line), []).append(text)
        words.append({"text": text, "x0": round(left / scale, 1), "top": round(top / scale, 1),
                      "x1": round((left + width) / scale, 1), "bottom": round((top + height) / scale, 1)})
    page_text = "\n".join(" ".join(ws) for _, ws in sorted(lines.items()))
    return _EMAIL_AT.sub(r"\1@", page_text), words


def ocr_pdf(path: Path) -> Document:
    import pypdfium2 as pdfium

    pages: list[str] = []
    words: list[list[dict]] = []
    sizes: list[tuple[float, float]] = []
    scale = OCR_DPI / 72
    pdf = pdfium.PdfDocument(str(path))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            images = []
            for i in range(min(len(pdf), OCR_MAX_PAGES)):  # rendering stays sequential (pdfium is not thread-safe)
                page = pdf[i]
                width, height = page.get_size()
                image = Path(tmp, f"p{i}.png")
                page.render(scale=scale).to_pil().save(image)
                images.append(image)
                sizes.append((round(width, 1), round(height, 1)))
            # tesseract processes in parallel, one per page (a 7-page scan: ~17 s → ~4 s on 8 cores)
            with ThreadPoolExecutor(max_workers=OCR_WORKERS) as pool:
                for text, page_words in pool.map(lambda im: _ocr_page(im, scale), images):
                    pages.append(text)
                    words.append(page_words)
    finally:
        pdf.close()
    log.info("%s: OCR of %d page(s)", path.name, len(pages))
    return Document(path=path, pages=pages, words=words, sizes=sizes, ocr=True)


_ROLE_HEAD = re.compile(r"^(?:ODWOŁUJĄC\w*|Odwołując\w*|ZAMAWIAJĄC\w*|Zamawiając\w*):?$")


def _page_text(page) -> str:
    """Page text; a two-column party header ("ODWOŁUJĄCY   ZAMAWIAJĄCY" side by side) is read column by column,
    otherwise every line would mix both parties (left half + right half)."""
    text = page.extract_text(x_tolerance=1.5) or ""
    if not re.search(r"(?im)^\s*odwołując\w*:?[ \t]+zamawiając\w*:?\s*$", text):
        return text
    try:
        words = page.extract_words(x_tolerance=1.5)
        lines: dict[int, list[dict]] = {}
        for w in words:
            lines.setdefault(round(w["top"] / 3), []).append(w)
        rows = [sorted(ws, key=lambda w: w["x0"]) for _, ws in sorted(lines.items())]
        head = next(r for r in rows if len(r) == 2 and all(_ROLE_HEAD.match(w["text"]) for w in r)
                    and r[1]["x0"] - r[0]["x1"] > page.width * 0.15)
        split, top = head[1]["x0"] - 4, min(w["top"] for w in head) - 1
        # the block ends at the first later line that crosses the column gap (e.g. a centred "ODWOŁANIE")
        later = [r for r in rows if min(w["top"] for w in r) > top + 2]
        cross = next((r for r in later if any(w["x0"] < split < w["x1"] for w in r) or
                      (r[0]["x0"] < split and r[-1]["x1"] < split and len(r) == 1 and r[0]["text"].isupper()
                       and len(r[0]["text"]) > 6)), None)
        bottom = min(w["top"] for w in cross) - 1 if cross else float(page.height)
        part = lambda box: page.crop(box).extract_text(x_tolerance=1.5) or ""
        return "\n".join(t for t in (part((0, 0, page.width, top)),
                                      part((0, top, split, bottom)),
                                      part((split, top, page.width, bottom)),
                                      part((0, bottom, page.width, page.height)) if cross else "") if t)
    except (StopIteration, ValueError):
        return text


def load_pdf(path: Path) -> Document:
    pages: list[str] = []
    words: list[list[dict]] = []
    sizes: list[tuple[float, float]] = []
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                pages.append(_page_text(page))
                words.append([
                    {"text": w["text"], "x0": round(w["x0"], 1), "top": round(w["top"], 1), "x1": round(w["x1"], 1), "bottom": round(w["bottom"], 1)}
                    for w in page.extract_words(x_tolerance=1.5)
                ])
                sizes.append((round(float(page.width), 1), round(float(page.height), 1)))
    except Exception as exc:  # corrupt or encrypted PDF: treat as unreadable, never crash the batch
        log.warning("cannot read %s: %s", path, exc)
        return Document(path=path, pages=pages, words=words, sizes=sizes)
    doc = Document(path=path, pages=pages, words=words, sizes=sizes)
    if not doc.has_text and pages and ocr_available():
        try:
            return ocr_pdf(path)
        except Exception as exc:  # OCR failure must not break the batch
            log.warning("OCR failed for %s: %s", path, exc)
    return doc
