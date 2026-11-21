"""Value parsers and normalisers shared by all document classes."""

from __future__ import annotations

import re
from datetime import date

MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6,
    "lipca": 7, "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12,
    "styczeń": 1, "luty": 2, "marzec": 3, "kwiecień": 4, "maj": 5, "czerwiec": 6,
    "lipiec": 7, "sierpień": 8, "wrzesień": 9, "październik": 10, "listopad": 11, "grudzień": 12,
}
_MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))

DATE_RE = re.compile(
    r"(?P<iso>\b(?P<y1>\d{4})[-./](?P<m1>\d{1,2})[-./](?P<d1>\d{1,2})\b)"
    r"|(?P<dmy>\b(?P<d2>\d{1,2})[-./](?P<m2>\d{1,2})[-./](?P<y2>\d{4})\b)"
    rf"|(?P<word>\b(?P<d3>\d{{1,2}})\s+(?P<m3>{_MONTH_ALT})\s+(?P<y3>\d{{4}}))",
    re.IGNORECASE,
)

# 1 234,56 | 1.234,56 | 17.00 | 50,00 — always with exactly two decimals
AMOUNT_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[  .]\d{3})+|\d+)[,.](\d{2})(?![\d])")

# 26-digit Polish account number, optional PL, any whitespace (incl. line breaks) between groups
ACCOUNT_RE = re.compile(r"(?<![\dA-Z])(?:PL)?\s?(\d{2}(?:\s?\d{4}){6})(?!\d)")


def parse_date(m: re.Match[str]) -> str | None:
    try:
        if m.group("iso"):
            y, mo, d = int(m.group("y1")), int(m.group("m1")), int(m.group("d1"))
        elif m.group("dmy"):
            y, mo, d = int(m.group("y2")), int(m.group("m2")), int(m.group("d2"))
        else:
            y, mo, d = int(m.group("y3")), MONTHS[m.group("m3").lower()], int(m.group("d3"))
        return date(y, mo, d).isoformat()
    except (ValueError, KeyError):
        return None


def find_date(text: str) -> str | None:
    for m in DATE_RE.finditer(text):
        if (iso := parse_date(m)) is not None:
            return iso
    return None


def find_amount(text: str) -> float | None:
    m = AMOUNT_RE.search(text)
    if not m:
        return None
    whole = re.sub(r"[  .]", "", m.group(1))
    return float(f"{whole}.{m.group(2)}")


def digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def iban_valid(account26: str) -> bool:
    """Polish IBAN checksum. Synthetic data often fails it, so use only as a tiebreaker."""
    if len(account26) != 26:
        return False
    return int(account26[2:] + "2521" + account26[:2]) % 97 == 1


def clean_text(s: str) -> str:
    s = " ".join(s.split())
    return s.strip(" \t„”\"'«»:;,").strip()
