"""Field validation configured in YAML (`validate:` section of a class file). Warn-only by design.

    validate:
      Odwolujacy[*].nip: [{check: nip}]
      przelew_bankowy.kwota: [{check: amount_range, min: 1, max: 100000}]

Results go to the evidence JSON under `validation` ({path, check, ok, message}); the output JSON is never
changed. Warn-only is deliberate: many values in the organiser's data are synthetic (checksums fail), so a
"drop invalid value" policy would remove correct answers. A new check is one function in CHECKS.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Callable, Iterator

from . import normalize as N

Check = Callable[[Any, dict[str, Any]], "str | None"]  # returns None when OK, else a human-readable message


def _digits(v: Any) -> str:
    return re.sub(r"\D", "", str(v))


def _weighted(d: str, weights: list[int]) -> int:
    return sum(int(a) * w for a, w in zip(d, weights))


def check_nip(v: Any, _: dict[str, Any]) -> str | None:
    d = _digits(v)
    if len(d) != 10:
        return f"NIP ma {len(d)} cyfr (powinno być 10)"
    c = _weighted(d, [6, 5, 7, 2, 3, 4, 5, 6, 7]) % 11
    return None if c != 10 and c == int(d[9]) else "błędna suma kontrolna NIP"


def check_regon(v: Any, _: dict[str, Any]) -> str | None:
    d = _digits(v)
    if len(d) == 9:
        w = [8, 9, 2, 3, 4, 5, 6, 7]
    elif len(d) == 14:
        w = [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8]
    else:
        return f"REGON ma {len(d)} cyfr (powinno być 9 lub 14)"
    return None if _weighted(d, w) % 11 % 10 == int(d[-1]) else "błędna suma kontrolna REGON"


def check_krs(v: Any, _: dict[str, Any]) -> str | None:
    return None if re.fullmatch(r"\d{10}", str(v)) else "KRS powinien mieć 10 cyfr"


def check_pesel(v: Any, _: dict[str, Any]) -> str | None:
    d = _digits(v)
    if len(d) != 11:
        return f"PESEL ma {len(d)} cyfr (powinno być 11)"
    c = (10 - _weighted(d, [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]) % 10) % 10
    return None if c == int(d[10]) else "błędna suma kontrolna PESEL"


def check_iban_pl(v: Any, _: dict[str, Any]) -> str | None:
    d = str(v).replace(" ", "").upper().removeprefix("PL")
    if not re.fullmatch(r"\d{26}", d):
        return "rachunek powinien mieć 26 cyfr (opcjonalnie z prefiksem PL)"
    return None if N.iban_valid(d) else "błędna suma kontrolna IBAN"


def check_date_not_future(v: Any, spec: dict[str, Any]) -> str | None:
    try:
        day = dt.date.fromisoformat(str(v))
    except ValueError:
        return "data nie jest w formacie RRRR-MM-DD"
    if day > dt.date.today():
        return "data z przyszłości"
    if spec.get("not_before") and day < dt.date.fromisoformat(str(spec["not_before"])):
        return f"data wcześniejsza niż {spec['not_before']}"
    return None


def check_amount_range(v: Any, spec: dict[str, Any]) -> str | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return "kwota nie jest liczbą"
    lo, hi = spec.get("min"), spec.get("max")
    if lo is not None and v < lo or hi is not None and v > hi:
        return f"kwota {v} poza zakresem [{lo}, {hi}]"
    return None


def check_regex(v: Any, spec: dict[str, Any]) -> str | None:
    return None if re.fullmatch(spec["pattern"], str(v)) else spec.get("message", f"nie pasuje do wzorca {spec['pattern']}")


def check_enum(v: Any, spec: dict[str, Any]) -> str | None:
    return None if v in spec["values"] else f"wartość spoza listy: {v!r}"


CHECKS: dict[str, Check] = {
    "nip": check_nip, "regon": check_regon, "krs": check_krs, "pesel": check_pesel, "iban_pl": check_iban_pl,
    "date_not_future": check_date_not_future, "amount_range": check_amount_range, "regex": check_regex,
    "enum": check_enum,
}


def resolve(obj: Any, path: str) -> Iterator[tuple[str, Any]]:
    """Yield (concrete path, value) for a path such as `Odwolujacy[*].pelnomocnik.mail` (`[*]` = every item)."""
    parts = re.findall(r"[^.\[\]]+|\[\*\]", path)

    def walk(o: Any, i: int, here: str) -> Iterator[tuple[str, Any]]:
        if i == len(parts):
            yield here, o
            return
        p = parts[i]
        if p == "[*]":
            for k, item in enumerate(o if isinstance(o, list) else []):
                yield from walk(item, i + 1, f"{here}[{k}]")
        elif isinstance(o, dict) and p in o:
            yield from walk(o[p], i + 1, f"{here}.{p}" if here else p)

    yield from walk(obj, 0, "")


def config_errors(rules: dict[str, Any] | None) -> list[str]:
    """Problems in a `validate:` section (unknown check, missing parameter), reported when the class loads."""
    errors = []
    for path, checks in (rules or {}).items():
        for spec in checks or []:
            name = spec.get("check") if isinstance(spec, dict) else None
            if name not in CHECKS:
                errors.append(f"{path}: nieznany check {name!r} (dostępne: {', '.join(CHECKS)})")
            elif name == "regex" and "pattern" not in spec or name == "enum" and "values" not in spec:
                errors.append(f"{path}: check {name} wymaga parametru {'pattern' if name == 'regex' else 'values'}")
    return errors


def validate(data: dict[str, Any], rules: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Run every configured check on every non-empty value; never modifies `data`."""
    out = []
    for path, checks in (rules or {}).items():
        for concrete, value in resolve(data, path):
            if value in (None, ""):
                continue
            for spec in checks or []:
                fn = CHECKS.get(spec.get("check"))
                if fn is None:
                    continue
                try:
                    msg = fn(value, spec)
                except Exception as e:  # a broken rule must not break the run
                    msg = f"błąd reguły: {e}"
                out.append({"path": concrete, "check": spec["check"], "ok": msg is None, "message": msg or "OK",
                            "action": "warn"})
    return out
