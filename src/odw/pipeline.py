"""PDF -> class -> JSON. A rejected document yields {} (required by the task)."""

from __future__ import annotations

import copy
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .classify import Verdict, classify
from .config import DocClass, load_classes
from .textio import Document, load_pdf

log = logging.getLogger(__name__)


@dataclass
class Result:
    source: Path
    verdict: Verdict
    data: dict[str, Any]


def extract(doc: Document, doc_class: DocClass) -> dict[str, Any]:
    # Extraction is filled in per class; until then the schema skeleton (all null) is returned.
    return copy.deepcopy(doc_class.output_template)


def process_pdf(path: Path, classes: list[DocClass]) -> Result:
    doc = load_pdf(path)
    verdict = classify(doc, classes)
    data = extract(doc, verdict.cls) if verdict.cls else {}
    return Result(path, verdict, data)


def run(input_dir: Path, output_dir: Path, classes: list[DocClass] | None = None) -> list[Result]:
    classes = classes or load_classes()
    results = []
    for pdf in sorted(p for p in input_dir.rglob("*") if p.suffix.lower() == ".pdf"):
        rel = pdf.relative_to(input_dir).with_suffix(".json")
        result = process_pdf(pdf, classes)
        target = output_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result.data, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("%s -> %s", rel.with_suffix(".pdf"), result.verdict.name or "{} (rejected)")
        results.append(result)
    return results
