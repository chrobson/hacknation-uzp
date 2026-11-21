"""Robustness regression: surface changes (page width, typography, label case) must not change any output."""

from dataclasses import replace

import pytest

from eval.perturb import PERTURBATIONS
from eval.run import collect
from eval.score import score_doc
from odw.config import load_classes
from odw.pipeline import process_pdf
from odw.textio import load_pdf

CLASSES = load_classes()
ITEMS = [i for i in collect("all") if i[0] in {"przyklad_02", "przyklad_23", "przyklad_41", "przyklad_50", "przyklad_52", "przyklad_59", "negatywne"}]
DOCS = {pdf: load_pdf(pdf) for _, pdf, _, _ in ITEMS}


@pytest.mark.parametrize("name", [n for n in PERTURBATIONS if n != "baseline"])
def test_perturbation_keeps_every_value(name):
    classification_only = name.endswith("_cls")  # e.g. lost diacritics: values legitimately differ from GT
    fn = PERTURBATIONS[name]
    for case, pdf, gt, expected in ITEMS:
        doc = DOCS[pdf]
        result = process_pdf(pdf, CLASSES, doc=replace(doc, pages=[fn(p) for p in doc.pages]))
        c = score_doc(gt, result.data)
        assert result.verdict.name == expected, f"{name}: {case}/{pdf.name} classified as {result.verdict.name}"
        if not classification_only:
            assert (c.fp, c.fn) == (0, 0), f"{name}: {case}/{pdf.name} FP={c.fp} FN={c.fn}"
