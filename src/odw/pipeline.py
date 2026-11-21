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
from .fields import Context, extract_field, extract_list, set_path
from .textio import Document, load_pdf

log = logging.getLogger(__name__)


@dataclass
class Result:
    source: Path
    verdict: Verdict
    data: dict[str, Any]


def extract(doc: Document, doc_class: DocClass) -> dict[str, Any]:
    out = copy.deepcopy(doc_class.output_template)
    ctx = Context(doc.text, doc_class.raw)
    excluded: dict[str, list[str]] = {}
    ctx.cfg = {**doc_class.raw, "_excluded_names": excluded}
    for path, specs in (doc_class.raw.get("fields") or {}).items():
        value = extract_field(specs, ctx)
        if isinstance(value, list):  # names-type field: remember names so other fields can exclude them
            excluded[path] = [next(iter(v.values())) for v in value if isinstance(v, dict)]
        if value is not None or not isinstance(out.get(path), list):
            set_path(out, path, value)
    for path, spec in (doc_class.raw.get("lists") or {}).items():
        template = doc_class.output_template[path][0]
        out[path] = extract_list(spec, ctx, template)
    for path, spec in (doc_class.raw.get("derive") or {}).items():
        set_path(out, path, _derive(out, spec))
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
