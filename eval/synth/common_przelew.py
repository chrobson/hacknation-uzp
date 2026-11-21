"""Shared helpers for the PRZELEW (bank transfer confirmation) synthetic generator.

Everything here is dev-only tooling (reportlab + DejaVu fonts). Values are
recombined from the training ground truth, so every generated GT is exact.

Public pieces used by the templates:
  * ``sample_case(rng)``  -> ``Case``: GT values + context (payer, payee, bank...)
  * formatters: ``fmt_account``, ``fmt_amount``, ``fmt_date``, ``amount_words``
  * fonts: ``register_fonts()`` and ``FONT_FAMILIES``
  * ``random_stem(rng)`` for content-agnostic file names
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import random
import string
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TRAIN_DIR = REPO_ROOT / "data" / "train"

# ---------------------------------------------------------------------------
# Data pools (from training GT)
# ---------------------------------------------------------------------------

_POOLS: dict | None = None


def load_pools() -> dict:
    global _POOLS
    if _POOLS is not None:
        return _POOLS
    pools: dict[str, list] = {k: [] for k in (
        "titles", "amounts", "accounts", "dates", "refs", "payers", "payees",
        "attorneys", "tenders", "tender_titles")}
    for case in sorted(TRAIN_DIR.glob("przyklad_*")):
        p = case / "przelew.json"
        if p.exists():
            pb = json.loads(p.read_text(encoding="utf-8")).get("przelew_bankowy") or {}
            if pb:
                pools["titles"].append(pb["tytul"])
                pools["amounts"].append(float(pb["kwota"]))
                pools["accounts"] += [pb["z_rachunku"], pb["na_rachunek"]]
                pools["dates"].append(pb["data_operacji"])
                if pb.get("numer_transakcji"):
                    pools["refs"].append(pb["numer_transakcji"])
        o = case / "odwolanie.json"
        if o.exists():
            od = json.loads(o.read_text(encoding="utf-8"))
            for x in od.get("Odwolujacy") or []:
                if x.get("nazwa"):
                    pools["payers"].append(x["nazwa"])
                pel = x.get("pelnomocnik") or {}
                if pel.get("imie_nazwisko"):
                    pools["attorneys"].append(pel["imie_nazwisko"])
            for x in od.get("Zamawiajacy") or []:
                if x.get("nazwa"):
                    pools["payees"].append(x["nazwa"])
            zp = od.get("ZamowieniePubliczne") or {}
            if zp.get("numer_postepowania"):
                pools["tenders"].append(zp["numer_postepowania"])
            if zp.get("tytul"):
                pools["tender_titles"].append(zp["tytul"])
    # attorneys mentioned in titles ("dla X i Y w postępowaniu")
    for t in pools["titles"]:
        if " dla " in t and " w postępowaniu" in t:
            seg = t.split(" dla ", 1)[1].split(" w postępowaniu", 1)[0]
            for n in seg.split(" i "):
                n = n.strip()
                if len(n.split()) == 2:
                    pools["attorneys"].append(n)
    for k in pools:
        pools[k] = sorted(set(pools[k]), key=str) if k not in ("amounts",) else pools[k]
    _POOLS = pools
    return pools


STREETS = ["ul. Marszałkowska", "ul. Piotrkowska", "ul. Długa", "al. Jerozolimskie",
           "ul. Kościuszki", "ul. Mickiewicza", "ul. Słowackiego", "ul. Lipowa",
           "ul. Polna", "al. Niepodległości", "ul. Kartuska", "ul. Grunwaldzka",
           "ul. Sienkiewicza", "ul. Wrocławska", "pl. Wolności", "ul. Żeromskiego"]
CITIES = [("00-950", "Warszawa"), ("90-803", "Łódź"), ("50-580", "Wrocław"),
          ("80-416", "Gdańsk"), ("31-071", "Kraków"), ("61-713", "Poznań"),
          ("20-950", "Lublin"), ("40-098", "Katowice"), ("15-062", "Białystok"),
          ("35-959", "Rzeszów"), ("70-410", "Szczecin"), ("87-100", "Toruń")]

# Fictional banks (no real brands).
BANKS = [
    ("Bank Wiślany S.A.", "WISLPLPW"), ("NordPol Bank S.A.", "NRDPPLPX"),
    ("Bank Karpacki S.A.", "KARPPLPK"), ("Credo Bank Polska S.A.", "CRDOPLPW"),
    ("Mazowiecki Bank Spółdzielczy", "MBSPPLP1"), ("Lechia Bank S.A.", "LECHPLPG"),
    ("Silesia Kredyt Bank S.A.", "SLKBPLPK"), ("Bank Warmiński S.A.", "WARMPLPO"),
    ("Odra Bank S.A.", "ODRAPLPW"), ("Bank Podlaski Spółdzielczy", "BPSPPLPB"),
    ("Vistula Digital Bank", "VDBKPLPW"), ("Bank Kujawski S.A.", "KUJAPLPT"),
    ("Ekobank Polska", "EKOBPLPW"), ("Bank Tatrzański S.A.", "TATRPLPZ"),
]

MONTHS_GEN = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
              "sierpnia", "września", "października", "listopada", "grudnia"]
MONTHS_NOM = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec",
              "sierpień", "wrzesień", "październik", "listopad", "grudzień"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December"]
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


@dataclass
class Party:
    name: str
    street: str
    city: str

    @property
    def address(self) -> str:
        return f"{self.street}, {self.city}"


@dataclass
class Case:
    gt: dict                     # exact przelew_bankowy dict (schema order)
    payer: Party
    payee: Party
    bank: str
    bic: str
    payee_bank: str
    date: dt.date
    gen_date: dt.date            # distractor: document generation date
    ref_in_title: bool
    extra: dict = field(default_factory=dict)

    @property
    def pb(self) -> dict:
        return self.gt["przelew_bankowy"]


def _party(rng: random.Random, name: str) -> Party:
    pc, city = rng.choice(CITIES)
    return Party(name, f"{rng.choice(STREETS)} {rng.randint(1, 240)}", f"{pc} {city}")


def _gen_ref(rng: random.Random, d: dt.date) -> str:
    # CEN + YYMM(of next month-ish) + 9 digits, like the training refs
    m = d + dt.timedelta(days=rng.randint(5, 25))
    return f"CEN{m:%y%m}{rng.randint(10**9, 10**10 - 1):010d}"[:16]


def _attorney_list(rng: random.Random, pools: dict) -> str:
    names = rng.sample(pools["attorneys"], rng.choice([1, 1, 2, 2, 2, 3]))
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " i " + names[-1]


def sample_case(rng: random.Random) -> Case:
    """Recombine training GT into a new, internally-consistent case."""
    pools = load_pools()
    z, na = rng.sample(pools["accounts"], 2)
    base = dt.date.fromisoformat(rng.choice(pools["dates"]))
    date = base + dt.timedelta(days=rng.randint(-40, 40))
    payer = _party(rng, rng.choice(pools["payers"]))
    payee = _party(rng, rng.choice(pools["payees"]))
    tender = rng.choice(pools["tenders"])
    kind = rng.random()
    ref: str | None
    if kind < 0.55:
        # training-like title, ref appended to the title
        ref = _gen_ref(rng, date)
        title = (f"opłata skarbowa od pełnomocnictwa dla {_attorney_list(rng, pools)} "
                 f"w postępowaniu przed KIO w przetargu {tender} {ref}")
        amount = float(rng.choice(pools["amounts"]))
        ref_in_title = True
    elif kind < 0.70:
        # original training title verbatim (incl. its own ref)
        title = rng.choice(pools["titles"])
        ref = title.split()[-1] if title.split()[-1].startswith("CEN") else None
        amount = float(rng.choice(pools["amounts"]))
        ref_in_title = ref is not None
    elif kind < 0.85:
        # entry fee ("wpis") title, no transaction number at all
        ref = None
        ref_in_title = False
        zam = payee.name.upper()
        title = rng.choice([
            f"WPIS OD ODWOŁANIA, ZAM: {zam}, {tender}",
            f"Wpis od odwołania - postępowanie {tender}, zamawiający: {payee.name}",
            f"WPIS OD ODW., ZAM: {zam}, {tender}",
        ])
        amount = float(rng.choice([7500, 7500, 10000, 15000, 20000]))
    else:
        # stamp duty with a different wording; separate bank ref (not in title)
        ref = _gen_ref(rng, date)
        ref_in_title = False
        title = rng.choice([
            f"Opłata skarbowa za pełnomocnictwo - {_attorney_list(rng, pools)}, sprawa {tender}",
            f"opłata skarbowa pełnomocnictwo KIO {tender} pełn. {_attorney_list(rng, pools)}",
        ])
        amount = float(rng.choice([17.0, 17.0, 34.0, 51.0]))
    bank, bic = rng.choice(BANKS)
    payee_bank = rng.choice([b for b, _ in BANKS if b != bank])
    gt = {"przelew_bankowy": {
        "data_operacji": date.isoformat(),
        "kwota": amount,
        "na_rachunek": na,
        "numer_transakcji": ref,
        "tytul": title,
        "z_rachunku": z,
    }}
    return Case(gt=gt, payer=payer, payee=payee, bank=bank, bic=bic,
                payee_bank=payee_bank, date=date,
                gen_date=date + dt.timedelta(days=rng.randint(0, 6)),
                ref_in_title=ref_in_title)


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

ACCOUNT_STYLES = ["plain", "pl", "spaced", "pl_spaced", "pl_space_after"]


def fmt_account(acc: str, style: str) -> str:
    groups = acc[:2] + " " + " ".join(acc[i:i + 4] for i in range(2, len(acc), 4))
    if style == "plain":
        return acc
    if style == "pl":
        return "PL" + acc
    if style == "spaced":
        return groups
    if style == "pl_spaced":
        return "PL" + groups
    if style == "pl_space_after":
        return "PL " + groups
    if style == "dashed":
        return acc[:2] + "-" + "-".join(acc[i:i + 4] for i in range(2, len(acc), 4))
    raise ValueError(style)


def _group(n: int, sep: str) -> str:
    s = str(n)
    out = []
    while len(s) > 3:
        out.insert(0, s[-3:])
        s = s[:-3]
    out.insert(0, s)
    return sep.join(out)


AMOUNT_STYLES = ["pl", "pl_pln", "pln_pl", "pl_zl", "zl_pl", "pl_nogr_zl",
                 "pl_dot_thousands", "en", "en_pln", "pl_minus_pln", "pl_zl_dot"]


def fmt_amount(x: float, style: str) -> str:
    whole = int(round(x * 100)) // 100
    gr = int(round(x * 100)) % 100
    pl = f"{_group(whole, ' ')},{gr:02d}"
    if style == "pl":
        return pl
    if style == "pl_pln":
        return pl + " PLN"
    if style == "pln_pl":
        return "PLN " + pl
    if style == "pl_zl":
        return pl + " zł"
    if style == "zl_pl":
        return "zł " + pl
    if style == "pl_nogr_zl":
        return (f"{_group(whole, ' ')} zł" if gr == 0 else pl + " zł")
    if style == "pl_dot_thousands":
        return f"{_group(whole, '.')},{gr:02d} PLN"
    if style == "en":
        return f"{_group(whole, ',')}.{gr:02d}"
    if style == "en_pln":
        return f"PLN {_group(whole, ',')}.{gr:02d}"
    if style == "pl_minus_pln":
        return f"-{pl} PLN"
    if style == "pl_zl_dot":
        return f"{pl} zł."
    raise ValueError(style)


DATE_STYLES = ["iso", "dmy_dot", "dmy_dot_r", "dmy_slash", "dmy_dash", "words_r",
               "words", "roman", "roman_r", "en_long", "en_short", "dmy_dot_time",
               "iso_time"]


def fmt_date(d: dt.date, style: str, rng: random.Random | None = None) -> str:
    rng = rng or random.Random(0)
    if style == "iso":
        return d.isoformat()
    if style == "dmy_dot":
        return f"{d:%d.%m.%Y}"
    if style == "dmy_dot_r":
        return f"{d:%d.%m.%Y} r."
    if style == "dmy_slash":
        return f"{d:%d/%m/%Y}"
    if style == "dmy_dash":
        return f"{d:%d-%m-%Y}"
    if style == "words_r":
        return f"{d.day} {MONTHS_GEN[d.month - 1]} {d.year} r."
    if style == "words":
        return f"{d.day} {MONTHS_GEN[d.month - 1]} {d.year}"
    if style == "roman":
        return f"{d.day} {ROMAN[d.month - 1]} {d.year}"
    if style == "roman_r":
        return f"{d.day}.{ROMAN[d.month - 1]}.{d.year} r."
    if style == "en_long":
        return f"{MONTHS_EN[d.month - 1]} {d.day}, {d.year}"
    if style == "en_short":
        return f"{d.day:02d} {MONTHS_EN[d.month - 1][:3]} {d.year}"
    if style == "dmy_dot_time":
        return f"{d:%d.%m.%Y} {rng.randint(7, 21):02d}:{rng.randint(0, 59):02d}:{rng.randint(0, 59):02d}"
    if style == "iso_time":
        return f"{d.isoformat()} {rng.randint(7, 21):02d}:{rng.randint(0, 59):02d}"
    raise ValueError(style)


_ONES = ["", "jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć",
         "dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście", "piętnaście",
         "szesnaście", "siedemnaście", "osiemnaście", "dziewiętnaście"]
_TENS = ["", "", "dwadzieścia", "trzydzieści", "czterdzieści", "pięćdziesiąt",
         "sześćdziesiąt", "siedemdziesiąt", "osiemdziesiąt", "dziewięćdziesiąt"]
_HUND = ["", "sto", "dwieście", "trzysta", "czterysta", "pięćset", "sześćset",
         "siedemset", "osiemset", "dziewięćset"]


def _words999(n: int) -> list[str]:
    out = []
    if n >= 100:
        out.append(_HUND[n // 100])
        n %= 100
    if n >= 20:
        out.append(_TENS[n // 10])
        n %= 10
    if n:
        out.append(_ONES[n])
    return out


def _plural(n: int, one: str, few: str, many: str) -> str:
    if n == 1:
        return one
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return few
    return many


def amount_words(x: float) -> str:
    """Polish amount in words: 'dwieście złotych 00/100'."""
    whole = int(round(x * 100)) // 100
    gr = int(round(x * 100)) % 100
    parts: list[str] = []
    th, rest = divmod(whole, 1000)
    if th:
        if th == 1:
            parts.append("jeden tysiąc")
        else:
            parts += _words999(th) + [_plural(th, "tysiąc", "tysiące", "tysięcy")]
    parts += _words999(rest)
    if not parts:
        parts = ["zero"]
    return " ".join(parts) + " " + _plural(whole, "złoty", "złote", "złotych") + f" {gr:02d}/100"


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

_FONT_FILES = {
    "Sans": "DejaVuSans.ttf", "Sans-B": "DejaVuSans-Bold.ttf", "Sans-I": "DejaVuSans-Oblique.ttf",
    "Serif": "DejaVuSerif.ttf", "Serif-B": "DejaVuSerif-Bold.ttf", "Serif-I": "DejaVuSerif-Italic.ttf",
    "Mono": "DejaVuSansMono.ttf", "Mono-B": "DejaVuSansMono-Bold.ttf",
    "Cond": "DejaVuSansCondensed.ttf", "Cond-B": "DejaVuSansCondensed-Bold.ttf",
}
# (regular, bold) pairs; Cond only if available
FONT_FAMILIES = [("Sans", "Sans-B"), ("Serif", "Serif-B"), ("Mono", "Mono-B")]
_REGISTERED = False


def _font_dirs() -> list[str]:
    dirs = []
    env = os.environ.get("SYNTH_FONT_DIR")
    if env:
        dirs.append(env)
    try:
        import matplotlib  # dev dep: bundles DejaVu fonts
        dirs.append(os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf"))
    except Exception:
        pass
    dirs += ["/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu",
             "/opt/homebrew/share/fonts", "/Library/Fonts", os.path.expanduser("~/Library/Fonts")]
    return dirs


def register_fonts() -> None:
    global _REGISTERED
    if _REGISTERED:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping
    found = {}
    for name, fn in _FONT_FILES.items():
        for d in _font_dirs():
            hits = glob.glob(os.path.join(d, "**", fn), recursive=True) if os.path.isdir(d) else []
            if hits:
                found[name] = hits[0]
                break
    missing = [n for n in ("Sans", "Sans-B", "Serif", "Serif-B", "Mono", "Mono-B") if n not in found]
    if missing:
        raise RuntimeError(f"DejaVu fonts not found ({missing}); pip install matplotlib "
                           "or set SYNTH_FONT_DIR")
    for name, path in found.items():
        pdfmetrics.registerFont(TTFont(name, path))
    for fam in ("Sans", "Serif", "Mono"):
        addMapping(fam, 0, 0, fam)
        addMapping(fam, 1, 0, fam + "-B")
        addMapping(fam, 0, 1, found.get(fam + "-I") and fam + "-I" or fam)
        addMapping(fam, 1, 1, fam + "-B")
    _REGISTERED = True


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

def random_stem(rng: random.Random) -> str:
    style = rng.random()
    alnum = string.ascii_lowercase + string.digits
    if style < 0.4:
        return "".join(rng.choice(alnum) for _ in range(rng.randint(8, 14)))
    if style < 0.7:
        return "doc_" + "".join(rng.choice(string.hexdigits.lower()) for _ in range(10))
    if style < 0.85:
        return f"scan{rng.randint(1000, 99999)}"
    return "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(6)) + \
        f"_{rng.randint(1, 999):03d}"


def doc_number(rng: random.Random, d: dt.date) -> str:
    return rng.choice([
        f"{d:%Y/%m}/{rng.randint(1, 999999):06d}",
        f"DOK-{rng.randint(10**7, 10**8 - 1)}",
        f"{rng.randint(100, 999)}/{d:%y}/{rng.randint(1000, 9999)}",
    ])


def write_gt(path: Path, case: Case) -> None:
    path.write_text(json.dumps(case.gt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Rendering toolkit shared by templates (generic, layout-agnostic)
# ---------------------------------------------------------------------------

def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


PL_DATE_STYLES = ["iso", "dmy_dot", "dmy_dot_r", "dmy_slash", "dmy_dash", "words_r",
                  "words", "roman", "roman_r", "dmy_dot_time", "iso_time"]
EN_DATE_STYLES = ["iso", "en_long", "en_short", "dmy_slash", "dmy_dot", "iso_time"]
PL_AMOUNT_STYLES = ["pl", "pl_pln", "pln_pl", "pl_zl", "zl_pl", "pl_nogr_zl",
                    "pl_dot_thousands", "pl_zl_dot"]
EN_AMOUNT_STYLES = ["en", "en_pln", "pl_pln", "pln_pl"]


@dataclass
class Values:
    z: str
    na: str
    amount: str
    date: str
    ref: str | None
    title: str
    styles: dict


def render_values(case: Case, rng: random.Random, *, english: bool = False,
                  acct_styles=None, amount_styles=None, date_styles=None) -> Values:
    acct_styles = acct_styles or ACCOUNT_STYLES
    a1 = rng.choice(acct_styles)
    a2 = a1 if rng.random() < 0.8 else rng.choice(acct_styles)
    am = rng.choice(amount_styles or (EN_AMOUNT_STYLES if english else PL_AMOUNT_STYLES))
    ds = rng.choice(date_styles or (EN_DATE_STYLES if english else PL_DATE_STYLES))
    pb = case.pb
    return Values(z=fmt_account(pb["z_rachunku"], a1), na=fmt_account(pb["na_rachunek"], a2),
                  amount=fmt_amount(pb["kwota"], am), date=fmt_date(case.date, ds, rng),
                  ref=pb["numer_transakcji"], title=pb["tytul"],
                  styles={"z": a1, "na": a2, "amount": am, "date": ds})


def para_styles(font: tuple[str, str], base: float = 9.5):
    from reportlab.lib.styles import ParagraphStyle
    reg, bold = font
    return {
        "n": ParagraphStyle("n", fontName=reg, fontSize=base, leading=base * 1.3),
        "s": ParagraphStyle("s", fontName=reg, fontSize=base - 2, leading=(base - 2) * 1.3),
        "b": ParagraphStyle("b", fontName=bold, fontSize=base, leading=base * 1.3),
        "h1": ParagraphStyle("h1", fontName=bold, fontSize=base + 6, leading=(base + 6) * 1.25,
                             spaceAfter=4),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=base + 2, leading=(base + 2) * 1.3,
                             spaceBefore=6, spaceAfter=2),
        "r": ParagraphStyle("r", fontName=reg, fontSize=base, leading=base * 1.3, alignment=2),
        "c": ParagraphStyle("c", fontName=reg, fontSize=base, leading=base * 1.3, alignment=1),
        "j": ParagraphStyle("j", fontName=reg, fontSize=base, leading=base * 1.45, alignment=4),
    }


def pick_font(rng: random.Random, allow_mono: bool = True) -> tuple[str, str]:
    fams = FONT_FAMILIES if allow_mono else FONT_FAMILIES[:2]
    return rng.choice(fams)


FOOTERS_PL = [
    "Potwierdzenie ma charakter informacyjny i zostało sporządzone automatycznie.",
    "Dokument wygenerowany elektronicznie, nie wymaga podpisu ani stempla.",
    "Bank nie ponosi odpowiedzialności za treść tytułu przelewu podaną przez klienta.",
    "Wydruk z systemu bankowości elektronicznej. Dokument nie stanowi faktury VAT.",
]
FOOTERS_EN = [
    "This confirmation was generated automatically and does not require a signature.",
    "This document is for information purposes only.",
]
