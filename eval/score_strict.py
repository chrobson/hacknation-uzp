"""Independent implementation of the official UZP field metric (WYMAGANIA §9-§10).

    python -m eval.score_strict --pred output/ --gt data/train [--strict] [--fields] [--docs]

Per leaf field of the JSON schema:
  TP  value present in both and equal (exact after type-aware normalisation; fuzzy
      rapidfuzz ratio >= 80 for the long-string fields in FUZZY_FIELDS)
  TN  absent/null in both
  FP  present only in the output, or present in both but wrong; keys outside the
      schema are FP (one per emitted leaf)
  FN  absent/null in the output but present in the ground truth
Lists are matched by content (optimal assignment maximising TP), order is irrelevant.
Negative documents expect {}: every non-null leaf emitted for them is FP.

Modes
  lenient (default)  string/number coercion: '123' == 123, '10 000,00' == 10000.0,
                     dates DD.MM.YYYY == YYYY-MM-DD, code fields compared without spaces
  --strict           the output must carry the ground-truth JSON type ('123' != 123),
                     strings compared after whitespace collapse only

Ground truth layout (data/train): <gt>/<case>/*.pdf with odwolanie.json, pelnomocnictwo.json
and przelew.json next to them; a PDF without a JSON (other names, <gt>/negatywne) expects {}.
A <gt>/<case>/<pdf stem>.json file, if present, takes precedence (official layout).
Predictions: <pred>/<case>/<pdf stem>.json. A missing prediction file is scored as {};
prediction files without a matching PDF are reported and their leaves counted as FP.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

FUZZY_THRESHOLD = 80.0

# Leaf types: date, int, float, digits (identifier made of digits), code (identifier, spaces irrelevant),
# email, text (exact), fuzzy (long string, ratio >= 80).
SCHEMA: dict[str, Any] = {
    "odwolanie": {
        "OdwolanieKIO": {
            "data": "date",
            "czynnosc_dzien": "date",
            "czynnosc_powod_id": "int",
            "czynnosc_opis": "text",
            "miejscowosc": "text",
        },
        "Odwolujacy": [{
            "krs": "digits",
            "nazwa": "fuzzy",
            "nip": "digits",
            "regon": "digits",
            "przez-pelnomocnika": "int",
            "pelnomocnik": {"imie_nazwisko": "text", "nazwa": "fuzzy", "mail": "email"},
        }],
        "Zamawiajacy": [{
            "krs": "digits",
            "nazwa": "fuzzy",
            "nip": "digits",
            "regon": "digits",
            "prowadzacy_postepowanie": "int",
        }],
        "ZamowieniePubliczne": {
            "numer_bzp": "code",
            "numer_postepowania": "code",
            "numer_ted": "code",
            "tytul": "fuzzy",
        },
    },
    "pelnomocnictwo": {
        "mocodawca": [{
            "data": {"imie_nazwisko": "text", "krs": "digits", "nazwa": "text", "nip": "digits", "typ": "text"},
            "podpisujacy": [{"imie_nazwisko": "text"}],
        }],
        "pelnomocnicy": [{"imie_nazwisko": "text", "pesel": "digits"}],
    },
    "przelew": {
        "przelew_bankowy": {
            "data_operacji": "date",
            "kwota": "float",
            "na_rachunek": "digits",
            "numer_transakcji": "code",
            "tytul": "fuzzy",
            "z_rachunku": "digits",
        },
    },
}
# Top-level key -> class. Union of all classes is the global schema.
ROOT_SCHEMA: dict[str, Any] = {k: v for cls in SCHEMA.values() for k, v in cls.items()}
CLASS_OF_KEY = {k: cls for cls, sch in SCHEMA.items() for k in sch}


def _leaf_paths(schema: Any, prefix: str = "") -> list[tuple[str, str]]:
    if isinstance(schema, dict):
        out = []
        for k, v in schema.items():
            out += _leaf_paths(v, f"{prefix}.{k}" if prefix else k)
        return out
    if isinstance(schema, list):
        return _leaf_paths(schema[0], prefix + "[]")
    return [(prefix, schema)]


FUZZY_FIELDS = sorted(p for p, t in _leaf_paths(ROOT_SCHEMA) if t == "fuzzy")


@dataclass
class Counts:
    tp: int = 0
    tn: int = 0
    fp: int = 0
    fn: int = 0

    def __add__(self, o: "Counts") -> "Counts":
        return Counts(self.tp + o.tp, self.tn + o.tn, self.fp + o.fp, self.fn + o.fn)

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 1.0

    @property
    def f1(self) -> float:
        d = 2 * self.tp + self.fp + self.fn
        return 2 * self.tp / d if d else 1.0

    @property
    def accuracy(self) -> float:
        n = self.tp + self.tn + self.fp + self.fn
        return (self.tp + self.tn) / n if n else 1.0


# ---------------------------------------------------------------- normalisation

_WS = re.compile(r"\s+")
_DATE_DMY = re.compile(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$")
_DATE_YMD = re.compile(r"^(\d{4})[./-](\d{1,2})[./-](\d{1,2})$")


def _text(s: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFC", s)).strip()


def is_absent(v: Any, strict: bool = False) -> bool:
    """null / missing; in lenient mode also empty or whitespace-only strings and empty containers."""
    if v is None:
        return True
    if not strict and isinstance(v, str) and not v.strip():
        return True
    if isinstance(v, (dict, list)) and not v:
        return True
    return False


def _is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _to_float(v: Any) -> float | None:
    if _is_num(v):
        return float(v)
    if isinstance(v, str):
        s = re.sub(r"[\s ]|zł|PLN", "", v, flags=re.I)
        if "," in s and "." in s:  # 1.234,56 or 1,234.56
            s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
        else:
            s = s.replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _to_int(v: Any) -> int | None:
    f = _to_float(v)
    return int(f) if f is not None and math.isfinite(f) and f == int(f) else None


def _to_date(v: Any) -> str | None:
    if not isinstance(v, str):
        return None
    s = v.strip()
    if m := _DATE_YMD.match(s):
        y, mo, d = m.groups()
    elif m := _DATE_DMY.match(s):
        d, mo, y = m.groups()
    else:
        return _text(s)
    return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"


def _same_json_type(gt: Any, pred: Any) -> bool:
    if _is_num(gt):
        return _is_num(pred) and (isinstance(gt, float) or isinstance(pred, int))
    return type(gt) is type(pred)


def values_equal(kind: str, gt: Any, pred: Any, strict: bool = False) -> bool:
    """Both values are present (non-null)."""
    if isinstance(gt, (dict, list)) or isinstance(pred, (dict, list)):
        return False
    if strict:
        if not _same_json_type(gt, pred):
            return False
        if isinstance(gt, str):
            a, b = _text(gt), _text(pred)
            if kind == "fuzzy":
                return fuzz.ratio(a, b) >= FUZZY_THRESHOLD
            if kind == "email":
                return a.lower() == b.lower()
            return a == b
        if isinstance(gt, float) or isinstance(pred, float):
            return abs(float(gt) - float(pred)) < 0.005
        return gt == pred

    if kind == "int":
        a, b = _to_int(gt), _to_int(pred)
        return a is not None and a == b
    if kind == "float":
        a, b = _to_float(gt), _to_float(pred)
        return a is not None and b is not None and abs(a - b) < 0.005
    if kind == "date":
        return _to_date(gt) == _to_date(pred)
    a, b = _text(str(gt)), _text(str(pred))
    if kind == "digits":
        a, b = re.sub(r"[\s\-.]", "", a), re.sub(r"[\s\-.]", "", b)
        if _is_num(gt) or _is_num(pred):  # a number cannot carry leading zeros
            a, b = a.lstrip("0"), b.lstrip("0")
        return a == b
    if kind == "code":
        return _WS.sub("", a).upper() == _WS.sub("", b).upper()
    if kind == "email":
        return a.lower() == b.lower()
    if kind == "fuzzy":
        return fuzz.ratio(a, b) >= FUZZY_THRESHOLD
    return a == b


# ---------------------------------------------------------------- scoring

FieldCounts = dict[str, Counts]


def _add(acc: FieldCounts, path: str, **kw: int) -> None:
    acc[path] = acc.get(path, Counts()) + Counts(**kw)


def _merge(acc: FieldCounts, other: FieldCounts) -> None:
    for k, c in other.items():
        acc[k] = acc.get(k, Counts()) + c


def _emitted_leaves(v: Any, path: str, strict: bool) -> list[str]:
    """Non-null leaves of a value, with their paths ([] for list items)."""
    if isinstance(v, dict):
        return [p for k, x in v.items() for p in _emitted_leaves(x, f"{path}.{k}" if path else k, strict)]
    if isinstance(v, list):
        return [p for x in v for p in _emitted_leaves(x, path + "[]", strict)]
    return [] if is_absent(v, strict) else [path]


def _extra_leaves(v: Any, path: str) -> list[str]:
    """Every leaf of a key outside the schema, null or not (an extra key is FP by itself)."""
    if isinstance(v, dict) and v:
        return [p for k, x in v.items() for p in _extra_leaves(x, f"{path}.{k}")]
    if isinstance(v, list) and v:
        return [p for x in v for p in _extra_leaves(x, path + "[]")]
    return [path]


def _score(schema: Any, gt: Any, pred: Any, path: str, strict: bool) -> FieldCounts:
    acc: FieldCounts = {}
    if isinstance(schema, dict):
        gt_d = gt if isinstance(gt, dict) else {}
        pr_d = pred if isinstance(pred, dict) else {}
        if not is_absent(pred, strict) and not isinstance(pred, dict):  # wrong structure: scalar/list for an object
            for p in _emitted_leaves(pred, path, strict):
                _add(acc, p + "<!type>", fp=1)
        for k, sub in schema.items():
            _merge(acc, _score(sub, gt_d.get(k), pr_d.get(k), f"{path}.{k}" if path else k, strict))
        for k, v in pr_d.items():
            if k not in schema:
                for p in _extra_leaves(v, f"{path}.{k}" if path else k):
                    _add(acc, "<extra>" + p, fp=1)
        return acc
    if isinstance(schema, list):
        gt_l = gt if isinstance(gt, list) else ([] if is_absent(gt, strict) else [gt])
        pr_l = pred if isinstance(pred, list) else ([] if is_absent(pred, strict) else [pred])
        item_path = path + "[]"
        return _score_list(schema[0], gt_l, pr_l, item_path, strict)
    # leaf
    g_abs, p_abs = is_absent(gt, strict), is_absent(pred, strict)
    if g_abs and p_abs:
        _add(acc, path, tn=1)
    elif g_abs:
        _add(acc, path, fp=1)
    elif p_abs:
        _add(acc, path, fn=1)
    elif values_equal(schema, gt, pred, strict):
        _add(acc, path, tp=1)
    else:
        _add(acc, path, fp=1)
    return acc


def _errors(c: FieldCounts) -> tuple[int, int]:
    tot = sum(c.values(), Counts())
    return tot.tp, tot.fp + tot.fn


def _pair_weight(pair: FieldCounts, alone_g: FieldCounts, alone_p: FieldCounts) -> tuple[int, int, int] | None:
    """(TP, errors saved vs. leaving both unmatched, 1) or None when pairing is not allowed.

    Pairing maximises TP first, then minimises FP+FN (a wrong value in a paired item is one FP,
    while leaving both items unmatched costs FN + FP), then prefers more pairs.
    """
    tp, err = _errors(pair)
    gain = _errors(alone_g)[1] + _errors(alone_p)[1] - err
    return (tp, gain, 1) if tp > 0 or gain >= 0 else None


def _score_list(item_schema: Any, gt_l: list, pr_l: list, path: str, strict: bool) -> FieldCounts:
    n, m = len(gt_l), len(pr_l)
    pair = [[_score(item_schema, g, p, path, strict) for p in pr_l] for g in gt_l]
    alone_gt = [_score(item_schema, g, None, path, strict) for g in gt_l]
    alone_pr = [_score(item_schema, None, p, path, strict) for p in pr_l]
    assignment = _best_assignment([[_pair_weight(pair[i][j], alone_gt[i], alone_pr[j]) for j in range(m)]
                                   for i in range(n)], n, m)
    acc: FieldCounts = {}
    used_g, used_p = set(), set()
    for i, j in assignment:
        _merge(acc, pair[i][j])
        used_g.add(i)
        used_p.add(j)
    for i in range(n):
        if i not in used_g:
            _merge(acc, alone_gt[i])
    for j in range(m):
        if j not in used_p:
            _merge(acc, alone_pr[j])
    return acc


def _best_assignment(w: list[list[tuple[int, int, int] | None]], n: int, m: int) -> list[tuple[int, int]]:
    """Maximum-weight matching (lexicographic tuple weights summed); None = pair not allowed.

    Exact bitmask DP for small lists, greedy beyond that.
    """
    if not n or not m:
        return []
    if n > m:  # DP over the smaller side
        return [(i, j) for j, i in _best_assignment([[w[i][j] for i in range(n)] for j in range(m)], m, n)]
    if m <= 14:
        from functools import lru_cache

        @lru_cache(maxsize=None)
        def best(i: int, mask: int) -> tuple[tuple[int, ...], tuple[tuple[int, int], ...]]:
            if i == n:
                return (0, 0, 0), ()
            cand = best(i + 1, mask)  # leave gt item i unmatched
            for j in range(m):
                if not mask & (1 << j) and w[i][j] is not None:
                    sub, rest = best(i + 1, mask | (1 << j))
                    v = tuple(x + y for x, y in zip(sub, w[i][j]))
                    if v > cand[0]:
                        cand = (v, ((i, j),) + rest)
            return cand

        return list(best(0, 0)[1])
    pairs = sorted(((w[i][j], i, j) for i in range(n) for j in range(m) if w[i][j] is not None), reverse=True)
    out, ug, up = [], set(), set()
    for _, i, j in pairs:
        if i not in ug and j not in up:
            out.append((i, j))
            ug.add(i)
            up.add(j)
    return out


def doc_class(gt: Any) -> str:
    if isinstance(gt, dict):
        for k in gt:
            if k in CLASS_OF_KEY:
                return CLASS_OF_KEY[k]
    return "negatyw"


def score_document(gt: Any, pred: Any, strict: bool = False) -> FieldCounts:
    """Field -> counts for one document. Schema = the GT class plus every top-level key the output emits."""
    gt = gt if isinstance(gt, dict) else {}
    if not isinstance(pred, dict):
        acc: FieldCounts = {}
        for p in _emitted_leaves(pred, "<root>", strict):
            _add(acc, p, fp=1)
        return acc
    cls = doc_class(gt)
    schema = dict(SCHEMA.get(cls, {}))
    for k in pred:
        if k in ROOT_SCHEMA:
            schema.setdefault(k, ROOT_SCHEMA[k])
    return _score(schema, gt, pred, "", strict)


# ---------------------------------------------------------------- dataset

GT_BY_PDF = {"odwolanie.pdf": "odwolanie.json", "pelnomocnictwo.pdf": "pelnomocnictwo.json",
             "potwierdzenie_przelewu.pdf": "przelew.json"}


def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(text) if text.strip() else {}


def collect(gt_root: Path, pred_root: Path) -> tuple[list[tuple[str, Any, Any, str]], list[str]]:
    """[(doc id, gt, pred, problem)] for every PDF under gt_root, plus orphan prediction files."""
    docs, seen = [], set()
    for pdf in sorted(gt_root.rglob("*.pdf")):
        rel = pdf.relative_to(gt_root)
        own = pdf.with_suffix(".json")
        if own.exists() and own.name not in GT_BY_PDF.values():
            gt = _load(own)
        elif pdf.name in GT_BY_PDF and (pdf.parent / GT_BY_PDF[pdf.name]).exists():
            gt = _load(pdf.parent / GT_BY_PDF[pdf.name])
        else:
            gt = {}
        pf = pred_root / rel.with_suffix(".json")
        seen.add(pf.resolve())
        problem = ""
        if not pf.exists():
            pred, problem = {}, "missing"
        else:
            try:
                pred = _load(pf)
            except json.JSONDecodeError:
                pred, problem = {}, "invalid-json"
        docs.append((str(rel), gt, pred, problem))
    orphans = sorted(str(p.relative_to(pred_root)) for p in pred_root.rglob("*")
                     if p.is_file() and p.resolve() not in seen)
    return docs, orphans


def evaluate(gt_root: Path, pred_root: Path, strict: bool = False) -> dict[str, Any]:
    docs, orphans = collect(gt_root, pred_root)
    per_class: dict[str, Counts] = defaultdict(Counts)
    per_field: dict[str, Counts] = defaultdict(Counts)
    per_class_field: dict[tuple[str, str], Counts] = defaultdict(Counts)
    per_doc = []
    for doc_id, gt, pred, problem in docs:
        cls = doc_class(gt)
        fc = score_document(gt, pred, strict)
        tot = sum(fc.values(), Counts())
        per_doc.append((doc_id, cls, tot, problem, fc))
        per_class[cls] += tot
        for f, c in fc.items():
            per_field[f] += c
            per_class_field[(cls, f)] += c
    for o in orphans:  # extra files in output lower the score: every emitted leaf is FP
        try:
            leaves = _emitted_leaves(_load(pred_root / o), "", strict)
        except (json.JSONDecodeError, UnicodeDecodeError):
            leaves = ["<file>"]
        c = Counts(fp=max(len(leaves), 1))
        per_class["<orphan>"] += c
        per_field["<orphan file>"] += c
    total = sum(per_class.values(), Counts())
    return {"total": total, "per_class": dict(per_class), "per_field": dict(per_field),
            "per_class_field": dict(per_class_field), "per_doc": per_doc, "orphans": orphans,
            "n_docs": len(docs)}


def _fmt(c: Counts) -> str:
    return (f"F1={c.f1:.4f} P={c.precision:.4f} R={c.recall:.4f}  "
            f"TP={c.tp:5d} TN={c.tn:5d} FP={c.fp:5d} FN={c.fn:5d}")


def report(res: dict[str, Any], fields: bool = True, docs: bool = False) -> str:
    out = [f"docs={res['n_docs']}  orphan output files={len(res['orphans'])}",
           f"OVERALL (micro)  {_fmt(res['total'])}", "", "per class:"]
    for cls, c in sorted(res["per_class"].items()):
        out.append(f"  {cls:15s} {_fmt(c)}")
    if fields:
        out += ["", "per class / field:"]
        for (cls, f), c in sorted(res["per_class_field"].items()):
            out.append(f"  {cls:15s} {f:48s} {_fmt(c)}")
    if docs:
        out += ["", "documents with errors:"]
        for doc_id, cls, tot, problem, fc in res["per_doc"]:
            if tot.fp or tot.fn or problem:
                bad = ", ".join(f"{f}(FP{c.fp}/FN{c.fn})" for f, c in sorted(fc.items()) if c.fp or c.fn)
                out.append(f"  {doc_id} [{cls}] {problem} {bad}")
    for o in res["orphans"]:
        out.append(f"  ORPHAN {o}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="eval.score_strict", description=__doc__.split("\n")[0])
    ap.add_argument("--pred", type=Path, required=True, help="output folder: <case>/<pdf stem>.json")
    ap.add_argument("--gt", type=Path, required=True, help="ground truth folder (data/train layout)")
    ap.add_argument("--strict", action="store_true", help="exact JSON types ('123' != 123)")
    ap.add_argument("--no-fields", action="store_true", help="skip the per-field table")
    ap.add_argument("--docs", action="store_true", help="list documents with errors")
    ap.add_argument("--json", action="store_true", help="print a JSON summary instead")
    args = ap.parse_args(argv)
    if not args.gt.is_dir() or not args.pred.is_dir():
        print("--gt and --pred must be folders", file=sys.stderr)
        return 2
    res = evaluate(args.gt, args.pred, args.strict)
    if args.json:
        print(json.dumps({"mode": "strict" if args.strict else "lenient", "f1": res["total"].f1,
                          "total": vars(res["total"]),
                          "per_class": {k: vars(v) | {"f1": v.f1} for k, v in res["per_class"].items()},
                          "per_field": {k: vars(v) | {"f1": v.f1} for k, v in res["per_field"].items()}},
                         ensure_ascii=False, indent=1))
    else:
        print(f"mode={'strict' if args.strict else 'lenient'}")
        print(report(res, fields=not args.no_fields, docs=args.docs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
