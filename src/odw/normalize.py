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
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}
_ROMAN_ALT = "|".join(sorted(ROMAN, key=len, reverse=True))

DATE_RE = re.compile(
    r"(?P<iso>\b(?P<y1>\d{4})[-./](?P<m1>\d{1,2})[-./](?P<d1>\d{1,2})\b)"
    r"|(?P<dmy>\b(?P<d2>\d{1,2})[-./](?P<m2>\d{1,2})[-./](?P<y2>\d{4})\b)"
    rf"|(?P<word>\b(?P<d3>\d{{1,2}})\s+(?P<m3>{_MONTH_ALT})\s+(?P<y3>\d{{4}}))"
    rf"|(?P<roman>\b(?P<d4>\d{{1,2}})[ .]+(?P<m4>(?-i:{_ROMAN_ALT}))[ .]+(?P<y4>\d{{4}}))",
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
        elif m.group("roman"):
            y, mo, d = int(m.group("y4")), ROMAN[m.group("m4")], int(m.group("d4"))
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


# Whole amounts only count next to a currency: "17 PLN", "PLN 17", "17,- zł", "1 200 zł".
INT_AMOUNT_RE = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:[ \u00a0.]\d{3})+|\d+)(?:,-)?\s*(?:PLN|zł)(?!\w)"
    r"|(?:PLN|zł)\s*(\d{1,3}(?:[ \u00a0.]\d{3})+|\d+)(?![\d,.])",
    re.IGNORECASE,
)
_GROUP_SEP = re.compile(r"[ \u00a0.]")


def find_amount(text: str) -> float | None:
    """Earliest amount in the text: decimals anywhere, whole numbers only next to a currency."""
    candidates: list[tuple[int, float]] = []
    m = AMOUNT_RE.search(text)
    if m:
        candidates.append((m.start(), float(f"{_GROUP_SEP.sub('', m.group(1))}.{m.group(2)}")))
    m = INT_AMOUNT_RE.search(text)
    if m:
        candidates.append((m.start(), float(_GROUP_SEP.sub("", m.group(1) or m.group(2)))))
    return min(candidates)[1] if candidates else None


# Polish company name: capitalised words (small connectors allowed) ending with a legal form. Case-sensitive.
_WORD = r"(?!Mocodaw|Działając|Pełnomoc|Dane\b|Zamawiaj|Wykonawc|Odwołując|Konsorcj|Ja\b|Nazwa\b|Firma\b)" \
        r"(?:[A-ZŁŚŻŹĆŃÓ][a-ząćęłńóśźż][\w\-.&]*|[A-ZŁŚŻŹĆŃÓ0-9][\w]*-[\w\-]+|[A-ZŁŚŻŹĆŃÓ]{2,}|„[^”]+”)"
LEGAL_FORM = r"(?:S\.A\.|sp\.\s*z\s*o\.\s*o\.(?:\s*sp\.\s*k\.)?|Sp\.\s*z\s*o\.\s*o\.|sp\.\s*k\.|sp\.\s*j\.|sp\.\s*p\.|s\.c\.|" \
             r"spółka\s+(?:akcyjna|jawna|komandytowa|partnerska|z\s+ograniczoną\s+odpowiedzialnością))"
COMPANY_RE = re.compile(rf"(?<![\w])({_WORD}(?:[ \t\n]+(?:{_WORD}|i|w|z|oraz|im\.))*?[ \t\n]+{LEGAL_FORM})")
# Public bodies have no legal form: "Gmina X", "Miasto X", "Szpital ...", "Uniwersytet ...", "Zarząd Dróg ..."
PUBLIC_BODY_RE = re.compile(
    r"(?<![\w])((?:Gmina|Miasto|Powiat|Województwo|Skarb\s+Państwa|Szpital|Samodzielny|Uniwersytet|Politechnika|Akademia|"
    r"Zarząd|Urząd|Ministerstwo|Instytut|Państwowe|Regionaln\w+|Wojewódzk\w+|Miejsk\w+|Powiatow\w+|Centrum|Agencja|"
    r"Generalna|Komenda|Narodow\w+|Zakład|Przedsiębiorstwo)[^\n,;:()]{2,120}?)(?=\s*(?:,|\n|\(|;|$|\s+(?:ul\.|al\.|KRS|NIP|REGON)))"
)

ID_PATTERNS = {
    "nip": re.compile(r"NIP\W{0,3}(?:PL[ \u00a0-]?)?(\d(?:[ \u00a0-]?\d){9})(?!\d)", re.IGNORECASE),
    "krs": re.compile(r"KRS\W{0,3}(\d(?:[ \u00a0]?\d){9})(?!\d)", re.IGNORECASE),
    "regon": re.compile(r"REGON\W{0,3}(\d(?:[ \u00a0]?\d){13}|\d(?:[ \u00a0]?\d){8})(?!\d)", re.IGNORECASE),
    "pesel": re.compile(r"PESEL\W{0,3}(\d{11})(?!\d)", re.IGNORECASE),
    "email": re.compile(r"([\w.+-]+@[\w-]+(?:\.[\w-]+)+)"),
}


def find_company(text: str) -> str | None:
    m = COMPANY_RE.search(text) or PUBLIC_BODY_RE.search(text)
    return clean_text(m.group(1)) if m else None


def find_id(kind: str, text: str) -> str | None:
    m = ID_PATTERNS[kind].search(text)
    if not m:
        return None
    return m.group(1) if kind == "email" else digits(m.group(1))


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
