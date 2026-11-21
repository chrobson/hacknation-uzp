"""PDF -> class -> JSON. A rejected document yields {} (required by the task)."""

from __future__ import annotations

import contextlib
import copy
import json
import logging
import signal
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .classify import Verdict, classify
from .config import DocClass, load_classes
from .fields import Context, extract_field, extract_list, set_path
from .textio import Document, canonical, load_pdf

log = logging.getLogger(__name__)

DOC_TIMEOUT_S = 180  # per document (OCR of a multi-page scan takes a while); a pathological PDF or regex must not stall the batch


class DocTimeout(Exception):
    pass


@contextlib.contextmanager
def deadline(seconds: float):
    """Raise DocTimeout after `seconds` (POSIX main thread only; elsewhere a no-op)."""
    usable = hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread() and seconds > 0
    if not usable:
        yield
        return

    def _raise(signum, frame):
        raise DocTimeout(f"document exceeded {seconds}s")

    old = signal.signal(signal.SIGALRM, _raise)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


@dataclass
class Result:
    source: Path
    verdict: Verdict
    data: dict[str, Any]
    doc: Document | None = None


def extract(doc: Document, doc_class: DocClass, out: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fill `out` (default: a fresh schema skeleton) in place, so a caller keeps partial work on timeout."""
    if out is None:
        out = copy.deepcopy(doc_class.output_template)
    ctx = Context(doc.text, doc_class.raw)
    excluded: dict[str, list[str]] = {}
    ctx.cfg = {**doc_class.raw, "_excluded_names": excluded}
    # Every field is isolated: a failure (or the document deadline) keeps everything extracted so far.
    for path, specs in (doc_class.raw.get("fields") or {}).items():
        try:
            value = extract_field(specs, ctx)
            ctx.values[path] = value
            if isinstance(value, list):  # names-type field: remember names so other fields can exclude them
                excluded[path] = [next(iter(v.values())) for v in value if isinstance(v, dict)]
            if value is not None or not isinstance(out.get(path), list):
                set_path(out, path, value)
        except DocTimeout:
            raise
        except Exception:
            log.exception("%s: field %s failed", doc.path, path)
    for path, spec in (doc_class.raw.get("lists") or {}).items():
        try:
            template = doc_class.output_template[path][0]
            out[path] = extract_list(spec, ctx, template)
        except DocTimeout:
            raise
        except Exception:
            log.exception("%s: list %s failed", doc.path, path)
    for path, spec in (doc_class.raw.get("derive") or {}).items():
        try:
            set_path(out, path, _derive(out, spec))
        except DocTimeout:
            raise
        except Exception:
            log.exception("%s: derived field %s failed", doc.path, path)
    return out


def _derive(out: dict[str, Any], spec: dict[str, Any]) -> Any:
    """A field computed from another one, e.g. canonical description looked up from an id dictionary."""
    from .config import ROOT
    import yaml

    source: Any = out
    for part in spec["from"].split("."):
        source = source.get(part) if isinstance(source, dict) else None
    if source is None:
        return None
    table = yaml.safe_load((ROOT / "config" / "dictionaries" / f"{spec['dictionary']}.yaml").read_text(encoding="utf-8"))
    return table.get(source)


def process_pdf(path: Path, classes: list[DocClass], timeout: float = DOC_TIMEOUT_S, doc: Document | None = None) -> Result:
    """Never raises. Unreadable/unclassifiable → {}; extraction failure → partial result.
    `doc` lets callers (e.g. perturbation tests) pass already-loaded text instead of reading the PDF."""
    verdict = Verdict(None, {})
    try:
        with deadline(timeout):
            doc = canonical(doc if doc is not None else load_pdf(path))
            verdict = classify(doc, classes)
            if verdict.cls is None:
                return Result(path, verdict, {}, doc)
            partial = _partial_or_template(verdict.cls)
            try:
                extract(doc, verdict.cls, partial)
            except DocTimeout:
                log.error("%s: extraction timed out after %ss; keeping fields extracted so far", path, timeout)
            return Result(path, verdict, partial, doc)
    except DocTimeout:
        log.error("%s: timed out before classification finished → {}", path)
    except Exception:
        log.exception("%s: failed before extraction → {}", path)
    return Result(path, verdict if verdict.cls else Verdict(None, {}), _partial_or_template(verdict.cls) if verdict.cls else {})


def _write_evidence(target: Path, result: Result) -> None:
    from .evidence import build

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = build(result.doc, result.verdict.name, result.data)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # evidence is a convenience; it must never break the run
        log.exception("evidence for %s failed", result.source)


def _partial_or_template(doc_class: DocClass) -> dict[str, Any]:
    return copy.deepcopy(doc_class.output_template)


def run(input_dir: Path, output_dir: Path, classes: list[DocClass] | None = None,
        evidence_dir: Path | None = None) -> list[Result]:
    classes = classes or load_classes()
    results = []
    for pdf in sorted(p for p in input_dir.rglob("*") if p.suffix.lower() == ".pdf"):
        rel = pdf.relative_to(input_dir).with_suffix(".json")
        result = process_pdf(pdf, classes)
        target = output_dir / rel
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result.data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            log.exception("cannot write %s", target)
        if evidence_dir is not None and result.doc is not None:
            _write_evidence(evidence_dir / rel.with_suffix(".evidence.json"), result)
        log.info("%s -> %s", rel.with_suffix(".pdf"), result.verdict.name or "{} (rejected)")
        results.append(result)
    return results
