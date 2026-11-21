"""F1 scoring that mirrors the UZP rules (Discord, 21.11.2026).

Per leaf field:
  TP  value in prediction and equal to ground truth
  FP  value in prediction but ground truth is null/absent, or the value is wrong
  FN  ground truth has a value, prediction is null/absent
  TN  null/absent in both
Long-string fields accept >= 80% similarity. Lists are matched by content, not order.
A document that should be rejected has ground truth {}.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from typing import Any

from rapidfuzz import fuzz

FUZZY_FIELDS = {
    "Odwolujacy.nazwa",
    "Zamawiajacy.nazwa",
    "Odwolujacy.pelnomocnik.nazwa",
    "przelew_bankowy.tytul",
    "ZamowieniePubliczne.tytul",
}
FUZZY_THRESHOLD = 80.0


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def __add__(self, o: "Counts") -> "Counts":
        return Counts(self.tp + o.tp, self.fp + o.fp, self.fn + o.fn, self.tn + o.tn)

    @property
    def f1(self) -> float:
        denom = 2 * self.tp + self.fp + self.fn
        return 1.0 if denom == 0 else 2 * self.tp / denom


STRICT = False  # strict mode: no fuzzy matching, JSON types must match exactly (int vs float vs str)


def _equal(path: str, gt: Any, pred: Any) -> bool:
    if STRICT:
        return type(gt) is type(pred) and gt == pred
    if isinstance(gt, (int, float)) and isinstance(pred, (int, float)) and not isinstance(gt, bool):
        return float(gt) == float(pred)
    if isinstance(gt, str) and isinstance(pred, str):
        g, p = " ".join(gt.split()), " ".join(pred.split())
        if path in FUZZY_FIELDS:
            return fuzz.ratio(g, p) >= FUZZY_THRESHOLD
        return g == p
    return gt == pred


def _leaf(path: str, gt: Any, pred: Any, out: dict[str, Counts]) -> None:
    c = out.setdefault(path, Counts())
    if gt is None and pred is None:
        c.tn += 1
    elif pred is None:
        c.fn += 1
    elif gt is None or not _equal(path, gt, pred):
        c.fp += 1
    else:
        c.tp += 1


def _walk(path: str, gt: Any, pred: Any, out: dict[str, Counts]) -> None:
    if isinstance(gt, dict) or isinstance(pred, dict):
        g = gt if isinstance(gt, dict) else {}
        p = pred if isinstance(pred, dict) else {}
        for key in g.keys() | p.keys():
            _walk(f"{path}.{key}" if path else key, g.get(key), p.get(key), out)
    elif isinstance(gt, list) or isinstance(pred, list):
        _walk_list(path, gt if isinstance(gt, list) else [], pred if isinstance(pred, list) else [], out)
    else:
        _leaf(path, gt, pred, out)


def _walk_list(path: str, gt: list, pred: list, out: dict[str, Counts]) -> None:
    """Pair list items to maximise TP; unmatched items are scored against an empty item."""
    n = max(len(gt), len(pred))
    g = gt + [None] * (n - len(gt))
    p = pred + [None] * (n - len(pred))

    def pair_score(gi: Any, pi: Any) -> tuple[int, int]:
        tmp: dict[str, Counts] = {}
        _walk(path, gi, pi, tmp)
        total = sum(tmp.values(), Counts())
        return total.tp, -total.fp

    if n <= 6:
        best = max(permutations(range(n)), key=lambda perm: tuple(map(sum, zip(*(pair_score(g[i], p[j]) for i, j in enumerate(perm))))) if n else ())
    else:  # greedy fallback for unusually long lists
        best, free = [], list(range(n))
        for i in range(n):
            j = max(free, key=lambda j: pair_score(g[i], p[j]))
            best.append(j)
            free.remove(j)
    for i, j in enumerate(best):
        _walk(path, g[i], p[j], out)


def score_fields(gt: Any, pred: Any) -> dict[str, Counts]:
    out: dict[str, Counts] = {}
    _walk("", gt, pred, out)
    return out


def score_doc(gt: Any, pred: Any) -> Counts:
    return sum(score_fields(gt, pred).values(), Counts())
