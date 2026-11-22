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
MONTHS.update({m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"])})
for _abbr, _n in {"sty": 1, "lut": 2, "mar": 3, "kwi": 4, "maj": 5, "cze": 6, "lip": 7, "sie": 8, "wrz": 9, "paź": 10,
                  "paz": 10, "lis": 11, "gru": 12, "jan": 1, "feb": 2, "apr": 4, "may": 5, "jun": 6, "jul": 7, "aug": 8,
                  "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}.items():
    MONTHS.setdefault(_abbr, _n)
_MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}
_ROMAN_ALT = "|".join(sorted(ROMAN, key=len, reverse=True))

DATE_RE = re.compile(
    r"(?P<iso>\b(?P<y1>\d{4})[-./](?P<m1>\d{1,2})[-./](?P<d1>\d{1,2})(?!\d))"  # (?!\d), not \b: "05.06.2026r."
    r"|(?P<dmy>\b(?P<d2>\d{1,2})[-./](?P<m2>\d{1,2})[-./](?P<y2>\d{4})(?!\d))"
    rf"|(?P<word>\b(?P<d3>\d{{1,2}})[\s-]+(?P<m3>{_MONTH_ALT})\.?[\s-]+(?P<y3>\d{{4}}))"
    rf"|(?P<roman>\b(?P<d4>\d{{1,2}})[\s.]+(?P<m4>(?-i:{_ROMAN_ALT}))[\s.]+(?P<y4>\d{{4}}))"
    rf"|(?P<en>\b(?P<m5>{_MONTH_ALT})\.?\s+(?P<d5>\d{{1,2}}),?\s+(?P<y5>\d{{4}}))"
    r"|(?P<dmy2>\b(?P<d6>\d{1,2})[.\-/](?P<m6>\d{1,2})[.\-/](?P<y6>\d{2})\b(?![.\-/]\d))",
    re.IGNORECASE,
)

# 1 234,56 | 1.234,56 | 17.00 | 50,00 — always with exactly two decimals
AMOUNT_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:[  .]\d{3})+|\d+)[,.](\d{2})(?![\d])")

# 26-digit Polish account number, optional PL, any whitespace (incl. line breaks) between groups.
# group "num" = the digits, group "pl" = the country prefix when the document prints one (on the same line:
# "WARSZAWA PL" ending an address line above the number is not a prefix).
ACCOUNT_RE = re.compile(r"(?<![\dA-Z])(?:(?P<pl>PL)[ \t -]?)?(?P<num>(?:\d[\s-]?){25}\d)(?!\d)")


def account_value(m: re.Match[str]) -> str:
    """Account as printed in the document: "PL" + 26 digits when the document has the prefix, else 26 digits.
    UZP (Discord, 21.11 21:17): the number as contained in the document; reference JSONs without PL are an error."""
    return ("PL" if m.group("pl") else "") + digits(m.group("num"))


def parse_date(m: re.Match[str]) -> str | None:
    try:
        if m.group("iso"):
            y, mo, d = int(m.group("y1")), int(m.group("m1")), int(m.group("d1"))
        elif m.group("dmy"):
            y, mo, d = int(m.group("y2")), int(m.group("m2")), int(m.group("d2"))
        elif m.group("dmy2"):
            y, mo, d = 2000 + int(m.group("y6")), int(m.group("m6")), int(m.group("d6"))
        elif m.group("en"):
            y, mo, d = int(m.group("y5")), MONTHS[m.group("m5").lower()], int(m.group("d5"))
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


EN_AMOUNT_RE = re.compile(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+)\.(\d{2})(?![\d])")  # 7,500.00


def find_amount(text: str) -> float | None:
    """Earliest amount in the text: decimals anywhere, whole numbers only next to a currency."""
    candidates: list[tuple[int, float]] = []
    m = EN_AMOUNT_RE.search(text)
    if m:
        candidates.append((m.start() - 0.5, float(f"{m.group(1).replace(',', '')}.{m.group(2)}")))
    m = AMOUNT_RE.search(text)
    if m:
        candidates.append((m.start(), float(f"{_GROUP_SEP.sub('', m.group(1))}.{m.group(2)}")))
    m = INT_AMOUNT_RE.search(text)
    if m:
        candidates.append((m.start(), float(_GROUP_SEP.sub("", m.group(1) or m.group(2)))))
    return min(candidates)[1] if candidates else None


# Polish company name: capitalised words (small connectors allowed) ending with a legal form. Case-sensitive.
_WORD = r"(?!Mocodaw|Działając|Pełnomoc|Dane\b|Zamawiaj|Wykonawc|Odwołując|Konsorcj|Ja\b|Nazwa\b|Firma\b)" \
        r"(?:[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż][\w\-.&]*|[A-ZĄĆĘŁŃÓŚŹŻ0-9][\w]*-[\w\-]+|[A-ZĄĆĘŁŃÓŚŹŻ]{2,}|„[^”]+”)"
LEGAL_FORM = r"(?:S\.A\.|sp\.\s*z\s*o\.\s*o\.(?:\s*sp\.\s*k\.)?|Sp\.\s*z\s*o\.\s*o\.|sp\.\s*k\.|sp\.\s*j\.|sp\.\s*p\.|s\.c\.|" \
             r"spółka\s+(?:akcyjna|jawna|komandytowa|partnerska|z\s+ograniczoną\s+odpowiedzialnością))"
COMPANY_RE = re.compile(rf"(?<![\w])({_WORD}(?:[ \t\n]+(?:{_WORD}|i|w|z|oraz|im\.))*?[ \t\n]+{LEGAL_FORM})")
# Public bodies have no legal form: "Gmina X", "Miasto X", "Szpital ...", "Uniwersytet ...", "Zarząd Dróg ..."
PUBLIC_BODY_RE = re.compile(
    r"(?<![\w])((?:Gmina|Miasto|Powiat|Województwo|Skarb\s+Państwa|Szpital|Samodzielny|Uniwersytet|Politechnika|Akademia|"
    r"Zarząd|Urząd|Ministerstwo|Instytut|Państwow[aey]|Zespół|Muzeum|Filharmonia|Ośrodek|Teatr|Biblioteka|Nadleśnictwo|Regionaln\w+|Wojewódzk\w+|Miejsk\w+|Powiatow\w+|Centrum|Agencja|"
    r"Generalna|Komenda|Narodow\w+|Zakład|Przedsiębiorstwo|"
    r"Gminie|Miastu|Powiatowi|Województwu|Skarbowi\s+Państwa|Szpitalowi|Uniwersytetowi|Politechnice|Akademii|Zarządowi|"
    r"Urzędowi|Ministerstwu|Instytutowi|Agencji|Komendzie|Zakładowi|Przedsiębiorstwu)"
    r"[^\n,;:()]{2,120}?)(?=\s*(?:,|\n|\(|;|$|\s+(?:ul\.|al\.|KRS|NIP|REGON|z\s+siedzibą)))"
)
# "przeciwko Gminie X" → the head word back to the nominative ("Gmina X"); fuzzy scoring tolerates the rest
_DATIVE_HEAD = {"Gminie": "Gmina", "Miastu": "Miasto", "Powiatowi": "Powiat", "Województwu": "Województwo",
                "Skarbowi": "Skarb", "Szpitalowi": "Szpital", "Uniwersytetowi": "Uniwersytet", "Politechnice": "Politechnika",
                "Akademii": "Akademia", "Zarządowi": "Zarząd", "Urzędowi": "Urząd", "Ministerstwu": "Ministerstwo",
                "Instytutowi": "Instytut", "Agencji": "Agencja", "Komendzie": "Komenda", "Zakładowi": "Zakład",
                "Przedsiębiorstwu": "Przedsiębiorstwo"}

ID_PATTERNS = {
    "nip": re.compile(r"NIP(?:\s+(?:pod\s+)?(?:nr|numer\w*)\.?)?\W{0,3}(?:PL[\s-]?)?(\d(?:[ \u00a0-]?\d){9})(?!\d)", re.IGNORECASE),
    "krs": re.compile(r"KRS(?:\s+(?:pod\s+)?(?:nr|numer\w*)\.?)?\W{0,3}(\d(?:[ \u00a0]?\d){9})(?!\d)", re.IGNORECASE),
    "regon": re.compile(r"REGON(?:\s+(?:pod\s+)?(?:nr|numer\w*)\.?)?\W{0,3}(\d(?:[ \u00a0]?\d){13}|\d(?:[ \u00a0]?\d){8})(?!\d)", re.IGNORECASE),
    "pesel": re.compile(r"PESEL\W{0,3}(\d{11})(?!\d)", re.IGNORECASE),
    "email": re.compile(r"([\w.+-]+@[\w-]+(?:\.[\w-]+)+)"),
}


# role labels / descriptions glued after a name: "Gmina X – Zamawiający", "Gmina X (dalej …", "Gmina X reprezentowana przez …"
_NAME_TAIL = re.compile(r"\s*(?:[–—-]\s*(?:Zamawiając|Odwołując|Wykonawc|Lider|prowadząc)\w*|\(\s*(?:dalej|zwan)\w*|"
                        r"\b(?:zwan\w*|reprezentowan\w*|działając\w*|w\s+imieniu|z\s+siedzibą|adres\w*|tel\.)\b).*$",
                        re.IGNORECASE | re.DOTALL)


def find_company(text: str) -> str | None:
    m = COMPANY_RE.search(text)
    if m:
        return clean_text(m.group(1))
    m = PUBLIC_BODY_RE.search(text)
    if not m:
        return None
    head, _, rest = _NAME_TAIL.sub("", m.group(1)).partition(" ")
    return clean_text(" ".join(filter(None, [_DATIVE_HEAD.get(head, head), rest]))) or None


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
    """Collapse whitespace; strip separators, and quotes only when unbalanced (keeps „Alfa” sp. z o.o. intact)."""
    s = " ".join(s.split()).strip(" \t:;,'")
    if s.startswith("„") and "”" not in s:
        s = s[1:]
    if s.endswith("”") and "„" not in s:
        s = s[:-1]
    if s.startswith("„") and s.endswith("”") and s.count("„") == 1 and s.count("”") == 1:
        s = s[1:-1]
    if s.count('"') % 2 == 1:
        s = s.strip('"')
    elif s.startswith('"') and s.endswith('"') and s.count('"') == 2:
        s = s[1:-1]
    return s.strip(" \t:;,'«»")
