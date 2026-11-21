"""PDF text extraction. One string per page.

Text-layer PDFs are read with pdfplumber. PDFs without a text layer (scans) are rendered with pypdfium2 and read
with Tesseract OCR (`tesseract -l pol`, called as a subprocess). Without Tesseract or its Polish model the scan
yields no text and the document is rejected ({}), with a warning in the log.
"""

from __future__ import annotations

import logging
import math
import os
from concurrent.futures import ThreadPoolExecutor
import re
import shutil
import subprocess
import tempfile
import threading
from functools import cache
from dataclasses import dataclass, field, replace
from pathlib import Path
from statistics import median

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


def usable_cpus() -> int:
    """CPUs this process may really use: affinity mask and a cgroup v2 quota (docker --cpus), not the host's count."""
    try:
        n = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        n = os.cpu_count() or 2
    try:
        quota, period = Path("/sys/fs/cgroup/cpu.max").read_text().split()[:2]
        if quota != "max":
            n = min(n, max(1, int(int(quota) / int(period))))
    except (OSError, ValueError):
        pass
    return max(1, n)


OCR_WORKERS = max(1, min(8, usable_cpus()))
OCR_LANG = os.environ.get("ODW_OCR_LANG", "pol")
_OCR_ZOO = re.compile(r"(?i)(\bsp\.?\s*z\s*)(?:0\.\s?[0o]|o\.\s?0)\.")  # at least one zero: real "o.o." untouched
# "@" read as "(O", "(Q", "(d", "(a", "(" (then the domain) or with a stray letter before it ("biuroQ@")
_EMAIL_PAREN = re.compile(r"\b([\w.+-]{2,})\([OQGadwo0]?(?=[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b)")
_EMAIL_DOUBLE = re.compile(r"\b([\w.+-]{2,}?)[QG]@(?=[\w-])")
_EMAIL_AT = re.compile(r"\b([\w.+-]{2,})[Q©®](?=[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b)")


@cache
def _tessdata_dir() -> Path | None:
    """Directory with the Polish model for the tesserocr fallback (TESSDATA_PREFIX, else where start.sh puts it)."""
    for d in (os.environ.get("TESSDATA_PREFIX"), str(Path.home() / ".local/share/tessdata")):
        if d and Path(d, f"{OCR_LANG}.traineddata").is_file():
            return Path(d)
    return None


@cache
def _lib_ocr() -> bool:
    """Fallback without the tesseract program (e.g. no sudo): the tesserocr wheel bundles libtesseract."""
    if _tessdata_dir() is None:
        return False
    try:
        import tesserocr  # noqa: F401
    except Exception:  # missing wheel or a broken native library: no fallback
        return False
    return True


def ocr_available() -> bool:
    exe = shutil.which("tesseract")
    if not exe:
        if _lib_ocr():
            return True
        log.warning("tesseract not found: scanned PDFs cannot be read (install tesseract-ocr tesseract-ocr-pol)")
        return False
    try:
        langs = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=20).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return False
    if OCR_LANG not in langs:
        if _lib_ocr():
            return True
        log.warning("tesseract has no '%s' model: scanned PDFs cannot be read (install tesseract-ocr-pol)", OCR_LANG)
        return False
    return True


@cache
def _use_lib() -> bool:
    """tesserocr only when the tesseract program (with the Polish model) is not usable (ODW_OCR_ENGINE=lib forces it)."""
    if os.environ.get("ODW_OCR_ENGINE") == "lib":
        return _lib_ocr()
    exe = shutil.which("tesseract")
    if exe:
        try:
            if OCR_LANG in subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=20).stdout.split():
                return False
        except (OSError, subprocess.SubprocessError):
            pass
    return _lib_ocr()


OCR_PSM = os.environ.get("ODW_OCR_PSM", "3")  # 3 = automatic page segmentation (better than 4 on real scans)


_TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
_LIB = threading.local()  # one tesserocr API per OCR worker thread (an API object is not thread-safe)


def _lib_tsv(image_path: Path) -> str:
    from tesserocr import PyTessBaseAPI

    api = getattr(_LIB, "api", None)
    if api is None:
        api = _LIB.api = PyTessBaseAPI(path=str(_tessdata_dir()), lang=OCR_LANG, psm=int(OCR_PSM))
    api.SetImageFile(str(image_path))
    return _TSV_HEADER + "\n" + api.GetTSVText(0)


def _tesseract_tsv(image_path: Path) -> str:
    if _use_lib():
        try:
            return _lib_tsv(image_path)
        except Exception as exc:
            log.warning("%s: tesserocr failed: %s", image_path.name, exc)
            return ""
    try:
        return subprocess.run(
            ["tesseract", str(image_path), "stdout", "-l", OCR_LANG, "--psm", OCR_PSM, "-c", "tessedit_create_tsv=1"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=OCR_PAGE_TIMEOUT_S,
            env={**os.environ, "OMP_THREAD_LIMIT": "1"},  # pages run in parallel; one thread each avoids oversubscription
        ).stdout
    except subprocess.TimeoutExpired:  # one stuck page must not lose the rest of the document
        log.warning("%s: OCR page timed out after %ss", image_path.name, OCR_PAGE_TIMEOUT_S)
        return ""


def _skew_deg(tsv: str) -> float:
    """Median baseline slope of the longer text lines (least squares over word centres), in degrees."""
    by_line: dict[tuple[str, str, str], list[tuple[float, float]]] = {}
    for row in tsv.splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12 or c[0] != "5" or len(c[11].strip()) < 3:
            continue
        left, top, width, height = (int(x) for x in c[6:10])
        by_line.setdefault((c[2], c[3], c[4]), []).append((left + width / 2, top + height / 2))
    slopes = []
    for pts in by_line.values():
        if len(pts) < 4 or pts[-1][0] - pts[0][0] < 400:
            continue
        n = len(pts)
        mx, my = sum(x for x, _ in pts) / n, sum(y for _, y in pts) / n
        den = sum((x - mx) ** 2 for x, _ in pts)
        if den:
            slopes.append(sum((x - mx) * (y - my) for x, y in pts) / den)
    return math.degrees(math.atan(median(slopes))) if len(slopes) >= 3 else 0.0


def _ocr_page(image_path: Path, scale: float, deskew: bool = True) -> tuple[str, list[dict]]:
    """Tesseract TSV → page text (one line per OCR line) and word boxes in PDF points (origin top-left).
    A skewed scan (0.15°–10°, estimated from the first pass) is straightened and read again."""
    out = _tesseract_tsv(image_path)
    angle = _skew_deg(out) if deskew else 0.0
    if 0.15 < abs(angle) < 10:
        from PIL import Image

        with Image.open(image_path) as im:
            im.convert("L").rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=255).save(image_path)
        out = _tesseract_tsv(image_path)
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
    page_text = _OCR_ZOO.sub(r"\1o.o.", page_text)  # OCR reads "sp. z o.o." as "sp. z 0.0."
    page_text = _EMAIL_PAREN.sub(r"\1@", _EMAIL_DOUBLE.sub(r"\1@", page_text))
    return _EMAIL_AT.sub(r"\1@", page_text), words


def ocr_pdf(path: Path, fast: bool = False) -> Document:
    """`fast` (time budget at risk): only the first 3 pages and the last one, single OCR pass (no deskew)."""
    import pypdfium2 as pdfium

    pages: list[str] = []
    words: list[list[dict]] = []
    sizes: list[tuple[float, float]] = []
    scale = OCR_DPI / 72
    pdf = pdfium.PdfDocument(str(path))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            images: list[Path | None] = []
            n = min(len(pdf), OCR_MAX_PAGES)
            for i in range(n):  # rendering stays sequential (pdfium is not thread-safe)
                page = pdf[i]
                width, height = page.get_size()
                sizes.append((round(width, 1), round(height, 1)))
                if fast and 3 <= i < n - 1:
                    images.append(None)  # skipped page keeps its index (evidence page numbers stay right)
                    continue
                image = Path(tmp, f"p{i}.png")
                page.render(scale=scale).to_pil().save(image, compress_level=1)
                images.append(image)

            def read(im: Path | None) -> tuple[str, list[dict]]:
                return ("", []) if im is None else _ocr_page(im, scale, deskew=not fast)

            # tesseract processes in parallel, one per page (a 7-page scan: ~17 s → ~4 s on 8 cores)
            with ThreadPoolExecutor(max_workers=OCR_WORKERS) as pool:
                for text, page_words in pool.map(read, images):
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


def load_pdf(path: Path, ocr: bool | str = True) -> Document:
    """Text layer; a PDF without one goes to OCR unless `ocr` is False ("fast" = reduced OCR, see ocr_pdf)."""
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
    if ocr and not doc.has_text and pages and ocr_available():
        try:
            return ocr_pdf(path, fast=ocr == "fast")
        except Exception as exc:  # OCR failure must not break the batch
            log.warning("OCR failed for %s: %s", path, exc)
    return doc
