"""Regression: every training PDF lands in its class; every negative is rejected. File names are randomised by the runner."""
import pytest

from eval.run import collect
from odw.classify import classify
from odw.config import load_classes
from odw.textio import load_pdf

ITEMS = collect("all")
CLASSES = load_classes()


@pytest.mark.parametrize("case,pdf,gt,expected", ITEMS, ids=[f"{i[0]}/{i[1].name}" for i in ITEMS])
def test_classification(case, pdf, gt, expected):
    assert classify(load_pdf(pdf), CLASSES).name == expected
