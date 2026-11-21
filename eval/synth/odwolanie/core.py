"""Core of the ODWOLANIE (appeal to KIO) synthetic generator.

Responsibilities:
  * font registration (DejaVu from matplotlib, system fonts as extra families),
  * value pools recombined from train ground truth (data/train/*/odwolanie.json),
  * case sampling -> exact ground truth in the official schema,
  * surface-form variation helpers (dates, NIP/REGON/KRS, BZP/TED numbers),
  * a tiny Polish name inflector (GT always keeps the nominative),
  * shared text snippets (zarzuty per czynnosc_powod_id, filler, requests),
  * a PDF renderer on top of reportlab platypus.

Templates (dev ones in templates_dev/, blind ones outside the repo) only
arrange content: they get a Case and a Ctx and return a story or build the
PDF themselves.
"""

from __future__ import annotations

import copy
import datetime as dt
import glob
import json
import os
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

REPO = Path(__file__).resolve().parents[3]
TRAIN_DIR = REPO / "data" / "train"
BLIND_ROOT = Path(os.environ.get("SYNTH_BLIND_ROOT", "/Users/mat2/orca/projects/hacknation/synth-blind"))

# --------------------------------------------------------------------------- fonts

_FONT_FAMILIES: list[str] = []


def _font_candidates() -> list[tuple[str, str, str]]:
    """(family, regular, bold) triples that exist on this machine."""
    out: list[tuple[str, str, str]] = []
    try:
        import matplotlib

        base = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        for fam, r, b in [
            ("DejaVuSans", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
            ("DejaVuSerif", "DejaVuSerif.ttf", "DejaVuSerif-Bold.ttf"),
        ]:
            if (base / r).exists():
                out.append((fam, str(base / r), str(base / b)))
    except Exception:
        pass
    extra = [
        ("Carlito", "/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf",
         "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf"),
        ("DejaVuSansSys", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("Arial", "/System/Library/Fonts/Supplemental/Arial.ttf",
         "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ("TimesNR", "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
         "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"),
        ("Georgia", "/System/Library/Fonts/Supplemental/Georgia.ttf",
         "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"),
        ("Verdana", "/System/Library/Fonts/Supplemental/Verdana.ttf",
         "/System/Library/Fonts/Supplemental/Verdana Bold.ttf"),
    ]
    env = os.environ.get("SYNTH_FONT_DIR")
    if env:
        for p in sorted(Path(env).glob("*.ttf")):
            if "bold" not in p.name.lower():
                b = next(iter(sorted(Path(env).glob(p.stem.split("-")[0] + "*Bold*.ttf"))), p)
                extra.insert(0, (p.stem.replace("-", ""), str(p), str(b)))
    for fam, r, b in extra:
        if os.path.exists(r) and os.path.exists(b):
            out.append((fam, r, b))
    return out


def fonts() -> list[str]:
    if not _FONT_FAMILIES:
        for fam, r, b in _font_candidates():
            try:
                pdfmetrics.registerFont(TTFont(fam, r))
                pdfmetrics.registerFont(TTFont(fam + "-Bold", b))
                from reportlab.lib.fonts import addMapping

                addMapping(fam, 0, 0, fam)
                addMapping(fam, 1, 0, fam + "-Bold")
                addMapping(fam, 0, 1, fam)
                addMapping(fam, 1, 1, fam + "-Bold")
                _FONT_FAMILIES.append(fam)
            except Exception:
                continue
        if not _FONT_FAMILIES:
            raise RuntimeError(
                "No TTF font with Polish glyphs found. pip install matplotlib (ships DejaVu) "
                "or set SYNTH_FONT_DIR to a folder with Carlito/DejaVu TTF files."
            )
    return _FONT_FAMILIES


# --------------------------------------------------------------------------- pools

MONTHS_GEN = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
              "sierpnia", "września", "października", "listopada", "grudnia"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]

CANON = {
    1: "Decyzja o odrzuceniu oferty",
    2: "Ogłoszenie wyboru oferty",
    3: "Decyzja o wykluczeniu wykonawcy",
    4: "Publikacja specyfikacji warunków zamówienia (SWZ)",
    5: "Modyfikacja treści SWZ",
    6: "Odpowiedzi i wyjaśnienia do SWZ",  # train GT wording (dict says "Odpowiedzi/wyjaśnienia")
    7: "Zaniechanie odrzucenia oferty",
    8: "Zaniechanie wykluczenia wykonawcy",
    9: "Decyzja o unieważnieniu postępowania",
    10: "Zaniechanie unieważnienia postępowania",
    11: "Opis przedmiotu zamówienia (OPZ)",
    12: "Projektowane postanowienia umowy",
}

STREETS = ["Marszałkowska", "Piłsudskiego", "Mickiewicza", "Słowackiego", "Kościuszki", "Długa",
           "Ogrodowa", "Polna", "Lipowa", "Kwiatowa", "Złota", "Żelazna", "Grunwaldzka",
           "Wojska Polskiego", "Jagiellońska", "Świętokrzyska", "Narutowicza", "Łąkowa",
           "Przemysłowa", "Fabryczna", "Szeroka", "Wrocławska", "Hoża", "Batorego", "Sienkiewicza", "Reja", "Kopernika"]
CITIES = ["Warszawa", "Kraków", "Łódź", "Wrocław", "Poznań", "Gdańsk", "Szczecin", "Bydgoszcz",
          "Lublin", "Białystok", "Katowice", "Gdynia", "Częstochowa", "Radom", "Toruń", "Kielce",
          "Rzeszów", "Gliwice", "Olsztyn", "Opole", "Zielona Góra", "Tarnów", "Koszalin", "Płock",
          "Elbląg", "Legnica", "Siedlce", "Pruszków", "Nowy Sącz"]
FIRST_NAMES_SIGN = ["Jan Kowalski", "Anna Nowicka", "Tomasz Wrona", "Ewa Lis", "Paweł Mazur",
                    "Monika Kurek", "Adam Pietrzak", "Beata Kozieł"]
SIGNER_ROLES = ["Prezes Zarządu", "Członek Zarządu", "Prokurent", "Wiceprezes Zarządu"]
TITLES = {
    "rp": ("r. pr.", "radca prawny", "radcy prawnego", "radcę prawnego"),
    "adw": ("adw.", "adwokat", "adwokata", "adwokata"),
    "apl": ("apl. radc.", "aplikant radcowski", "aplikanta radcowskiego", "aplikanta radcowskiego"),
    "": ("", "", "", ""),
}
PROC_MODES = ["przetargu nieograniczonego", "podstawowym bez negocjacji",
              "podstawowym z możliwością negocjacji", "przetargu ograniczonego",
              "negocjacji z ogłoszeniem", "dialogu konkurencyjnego"]


def _load_train() -> list[dict]:
    out = []
    for f in sorted(glob.glob(str(TRAIN_DIR / "przyklad_*" / "odwolanie.json"))):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        if d:
            out.append(d)
    if not out:
        raise RuntimeError(f"no train GT found under {TRAIN_DIR}")
    return out


@dataclass
class Pools:
    odw: list[dict]
    zam: list[dict]
    att: list[dict]  # imie_nazwisko + firm (nazwa, mail)
    titles: list[str]
    nr: list[str]
    bzp: list[str]
    ted: list[str]
    places: list[str]
    dates: list[dt.date]


_POOLS: Pools | None = None


def pools() -> Pools:
    global _POOLS
    if _POOLS is None:
        tr = _load_train()

        def uniq(items, key):
            seen, res = set(), []
            for it in items:
                k = key(it)
                if k not in seen:
                    seen.add(k)
                    res.append(it)
            return res

        ent = lambda e: {k: e[k] for k in ("nazwa", "krs", "nip", "regon")}
        odw = uniq([ent(d["Odwolujacy"][0]) for d in tr], lambda e: e["nazwa"])
        zam = uniq([ent(z) for d in tr for z in d["Zamawiajacy"]], lambda e: e["nazwa"])
        att = uniq([dict(d["Odwolujacy"][0]["pelnomocnik"]) for d in tr
                    if d["Odwolujacy"][0].get("pelnomocnik", {}).get("imie_nazwisko")],
                   lambda a: a["imie_nazwisko"])
        zp = [d["ZamowieniePubliczne"] for d in tr]
        dates = [dt.date.fromisoformat(d["OdwolanieKIO"]["data"]) for d in tr if d["OdwolanieKIO"]["data"]]
        _POOLS = Pools(
            odw=odw, zam=zam, att=att,
            titles=sorted({z["tytul"] for z in zp if z["tytul"]}),
            nr=sorted({z["numer_postepowania"] for z in zp if z["numer_postepowania"]}),
            bzp=sorted({z["numer_bzp"] for z in zp if z["numer_bzp"]}),
            ted=sorted({z["numer_ted"] for z in zp if z["numer_ted"]}),
            places=sorted({d["OdwolanieKIO"]["miejscowosc"] for d in tr if d["OdwolanieKIO"]["miejscowosc"]}),
            dates=dates,
        )
    return _POOLS


# --------------------------------------------------------------------------- inflection

_FEM_EXC_FIRST = {"Beatrycze": None}
_MASC_FIRST_STEM = {"Marek": "Mark", "Leszek": "Leszk", "Aleksander": "Aleksandr", "Jacek": "Jack",
                    "Wojciech": "Wojciech", "Paweł": "Pawł", "Przemek": "Przemk", "Józef": "Józef"}


def _female_first(first: str) -> bool:
    return first.endswith("a") and first not in {"Kuba", "Barnaba", "Bonawentura"}


def _inflect_first(first: str, case: str) -> str | None:
    if _female_first(first):
        stem = first[:-1]
        if case == "acc":
            return stem + "ę"
        if case == "inst":
            return stem + "ą"
        if case == "gen":
            if stem.endswith("i"):
                return stem + "i"
            return stem + ("i" if stem[-1] in "kgl" else "y")
        return None
    if first.endswith("y"):  # Cezary, Ignacy
        return {"acc": first[:-1] + "ego", "gen": first[:-1] + "ego", "inst": first[:-1] + "ym"}.get(case)
    stem = _MASC_FIRST_STEM.get(first, first)
    if not stem[-1].isalpha() or stem[-1] in "aeiouyąęó":
        return None
    if case in ("acc", "gen"):
        return stem + "a"
    if case == "inst":
        return stem + ("iem" if stem[-1] in "kg" else "em")
    return None


def _inflect_last(last: str, female: bool, case: str) -> str | None:
    if "-" in last:
        parts = [_inflect_last(p, female, case) for p in last.split("-")]
        return None if None in parts else "-".join(parts)  # type: ignore[arg-type]
    if female:
        if re.search(r"(ska|cka|dzka)$", last):
            return {"acc": last[:-1] + "ą", "inst": last[:-1] + "ą", "gen": last[:-1] + "iej"}.get(case)
        if last.endswith("a"):
            return None  # e.g. Sikora (female) - avoid
        if re.search(r"(ski|cki|dzki)$", last):
            return None  # gender mismatch in source data: keep nominative
        return last  # consonant-final female surnames do not inflect
    if re.search(r"(ski|cki|dzki)$", last):
        return {"acc": last + "ego", "gen": last + "ego", "inst": last + "m"}.get(case)
    if last.endswith("a"):
        return {"acc": last[:-1] + "ę", "gen": last[:-1] + "y", "inst": last[:-1] + "ą"}.get(case)
    if last.endswith("ień"):
        stem = last[:-3] + "ni"
    elif last.endswith("ek"):
        stem = last[:-2] + "k"
    elif last.endswith("ec"):
        stem = last[:-2] + "c"
    elif last[-1] in "aeiouyąęó":
        return None
    else:
        stem = last
    if case in ("acc", "gen"):
        return stem + "a"
    if case == "inst":
        return stem + ("iem" if stem[-1] in "kg" else "em")
    return None


def inflect(full: str, case: str) -> str | None:
    """Return 'Imię Nazwisko' in acc/gen/inst, or None when unsure."""
    parts = full.split()
    if len(parts) != 2:
        return None
    first, last = parts
    female = _female_first(first)
    f = _inflect_first(first, case)
    l = _inflect_last(last, female, case)
    if f is None or l is None:
        return None
    return f"{f} {l}"


# --------------------------------------------------------------------------- formatting


def roman(n: int) -> str:
    return ROMAN[n - 1]


def fmt_date(d: dt.date, style: str) -> str:
    dd, mm_, yy = d.day, d.month, d.year
    return {
        "dots": f"{dd:02d}.{mm_:02d}.{yy}",
        "dots_r": f"{dd:02d}.{mm_:02d}.{yy} r.",
        "dots_short": f"{dd}.{mm_:02d}.{yy} r.",
        "words": f"{dd} {MONTHS_GEN[mm_ - 1]} {yy} r.",
        "words_roku": f"{dd} {MONTHS_GEN[mm_ - 1]} {yy} roku",
        "words_bare": f"{dd} {MONTHS_GEN[mm_ - 1]} {yy}",
        "roman": f"{dd} {ROMAN[mm_ - 1]} {yy} r.",
        "roman_dots": f"{dd}.{ROMAN[mm_ - 1]}.{yy}",
        "iso": d.isoformat(),
        "slash": f"{dd:02d}/{mm_:02d}/{yy}",
        "dash": f"{dd:02d}-{mm_:02d}-{yy}",
        "en": f"{dd} {MONTHS_EN[mm_ - 1]} {yy}",
    }[style]


DATE_STYLES_HEADER = ["dots", "dots_r", "dots_short", "words", "words_roku", "roman", "roman_dots",
                      "iso", "slash", "dash"]
DATE_STYLES_BODY = ["dots_r", "dots", "words", "words_roku", "words", "roman", "dash"]


def fmt_nip(nip: str, style: str) -> str:
    n = nip
    return {
        "plain": n,
        "dash": f"{n[:3]}-{n[3:6]}-{n[6:8]}-{n[8:]}",
        "dash2": f"{n[:3]}-{n[3:5]}-{n[5:7]}-{n[7:]}",
        "pl": f"PL{n}",
        "pl_space": f"PL {n}",
        "space": f"{n[:3]} {n[3:6]} {n[6:8]} {n[8:]}",
    }[style]


NIP_STYLES = ["plain", "plain", "dash", "dash2", "pl", "pl_space", "space"]


def fmt_regon(r: str, style: str) -> str:
    if style == "space" and len(r) == 9:
        return f"{r[:3]} {r[3:6]} {r[6:]}"
    return r


def fmt_krs(k: str, style: str) -> str:
    if style == "space":
        return f"{k[:4]} {k[4:7]} {k[7:]}"
    return k


def fmt_bzp(b: str, style: str) -> str:
    m = re.match(r"(\d{4})/BZP\s*(\d{8})(/\d{2})?$", b)
    if not m:
        return b
    y, num, suf = m.group(1), m.group(2), m.group(3) or ""
    return {
        "compact": f"{y}/BZP{num}{suf}",
        "space": f"{y}/BZP {num}{suf}",
        "space2": f"{y}/BZP {num}{suf}".replace("/BZP ", "/BZP  "),
    }[style]


def fmt_ted(t: str, style: str, rng: random.Random) -> str:
    num, year = t.split("-")
    if style == "plain":
        return t
    s_no = rng.randint(100, 240)
    if style == "ojs":
        return f"{year}/S {s_no}-{num}"
    if style == "ojs_long":
        return f"Dz.U./S S{s_no} {year}/S {s_no}-{num}"
    return t


def esc(s: Any) -> str:
    return escape(str(s))


# --------------------------------------------------------------------------- case model


@dataclass
class Entity:
    nazwa: str
    krs: str | None
    nip: str | None
    regon: str | None
    address: str
    email: str | None = None
    prowadzacy: int | None = None
    role: str = ""  # e.g. "Lider", "Partner"

    def gt(self, kind: str) -> dict:
        d = {"krs": self.krs, "nazwa": self.nazwa, "nip": self.nip, "regon": self.regon}
        if kind == "zam":
            d["prowadzacy_postepowanie"] = self.prowadzacy
        return d


@dataclass
class Attorney:
    imie_nazwisko: str
    title_key: str  # rp / adw / apl / ""

    @property
    def title_short(self) -> str:
        return TITLES[self.title_key][0]

    @property
    def title_long(self) -> str:
        return TITLES[self.title_key][1]

    def with_title(self, style: str = "short", rng: random.Random | None = None) -> str:
        t = self.title_short if style == "short" else self.title_long
        return f"{t} {self.imie_nazwisko}".strip()

    def inflected(self, case: str, with_title: bool = True) -> str:
        """Accusative/genitive/instrumental form, nominative when the inflector is unsure."""
        name = inflect(self.imie_nazwisko, case) or self.imie_nazwisko
        if not with_title or not self.title_key:
            return name
        idx = {"acc": 3, "gen": 2, "inst": 2}[case]
        if case == "inst":
            t = {"rp": "radcą prawnym", "adw": "adwokatem", "apl": "aplikantem radcowskim"}[self.title_key]
            return f"{t} {name}"
        return f"{TITLES[self.title_key][idx]} {name}"


@dataclass
class Zarzut:
    powod_id: int
    date: dt.date | None


@dataclass
class Case:
    data: dt.date | None
    miejscowosc: str | None
    zarzuty: list[Zarzut]
    odw: list[Entity]  # [0] = Odwołujący or consortium leader
    consortium: bool
    attorneys: list[Attorney]
    firm_nazwa: str | None
    firm_mail: str | None
    firm_address: str
    firm_phone: str
    zams: list[Entity]
    bzp: str | None
    nr: str | None
    ted: str | None
    tytul: str
    tryb: str
    signer: str
    signer_role: str
    kio_sygn: str | None
    wpis: str
    extra_dates: list[dt.date] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    @property
    def first(self) -> Zarzut:
        return self.zarzuty[0]

    @property
    def przez(self) -> int:
        return 1 if self.attorneys else 0

    def gt(self) -> dict:
        lead = self.odw[0]
        o = lead.gt("odw")
        o["przez-pelnomocnika"] = self.przez
        if self.attorneys:
            o["pelnomocnik"] = {"imie_nazwisko": self.attorneys[0].imie_nazwisko,
                                "nazwa": self.firm_nazwa, "mail": self.firm_mail}
        else:
            o["pelnomocnik"] = {"imie_nazwisko": None, "nazwa": None, "mail": None}
        return {
            "OdwolanieKIO": {
                "data": self.data.isoformat() if self.data else None,
                "czynnosc_dzien": self.first.date.isoformat() if self.first.date else None,
                "czynnosc_powod_id": self.first.powod_id,
                "czynnosc_opis": CANON[self.first.powod_id],
                "miejscowosc": self.miejscowosc,
            },
            "Odwolujacy": [o],
            "Zamawiajacy": [z.gt("zam") for z in self.zams],
            "ZamowieniePubliczne": {
                "numer_bzp": self.bzp.replace(" ", "") if self.bzp else None,
                "numer_postepowania": self.nr,
                "numer_ted": self.ted,
                "tytul": self.tytul,
            },
        }


DEFAULT_PROBS = {
    "data_null": 0.15,
    "consortium": 0.18,
    "multi_zam": 0.18,
    "no_attorney": 0.10,
    "multi_attorney": 0.45,
    "no_title": 0.15,
    "czynnosc_date_null": 0.06,
    "krs_null": 0.12,
    "regon_null": 0.12,
    "nip_null": 0.04,
    "zam_krs_null": 0.35,
    "zam_regon_null": 0.10,
    "zam_nip_null": 0.05,
    "bzp_null": 0.25,
    "ted_null": 0.30,
    "nr_null": 0.06,
    "kio_sygn": 0.25,
}


def _addr(rng: random.Random, city: str | None = None) -> str:
    city = city or rng.choice(CITIES)
    no = rng.randint(1, 180)
    flat = f"/{rng.randint(1, 40)}" if rng.random() < 0.3 else ""
    return f"ul. {rng.choice(STREETS)} {no}{flat}, {rng.randint(0, 99):02d}-{rng.randint(1, 999):03d} {city}"


def _entity(rng: random.Random, src: dict, krs_null: float, regon_null: float, nip_null: float) -> Entity:
    def maybe(v, p):
        return None if (v is None or rng.random() < p) else v

    slug = re.sub(r"[^a-z]", "", src["nazwa"].lower().split()[0].translate(str.maketrans("ąćęłńóśźż", "acelnoszz")))
    return Entity(
        nazwa=src["nazwa"],
        krs=maybe(src["krs"], krs_null),
        nip=maybe(src["nip"], nip_null),
        regon=maybe(src["regon"], regon_null),
        address=_addr(rng),
        email=rng.choice(["sekretariat", "biuro", "zamowienia", "kontakt", "zp"]) + f"@{slug or 'firma'}.example",
    )


def sample_case(rng: random.Random, overrides: dict | None = None) -> Case:
    P = dict(DEFAULT_PROBS)
    P.update(overrides or {})
    pl = pools()
    hit = lambda k: rng.random() < P[k]

    # dates
    base = rng.choice(pl.dates)
    base = base + dt.timedelta(days=rng.randint(-40, 40))
    data = None if hit("data_null") else base
    miejsc = rng.choice(pl.places + CITIES[:8]) if data else None
    first_date = base - dt.timedelta(days=rng.randint(2, 10))
    n_z = rng.choice([1, 2, 2, 3, 3, 4])
    first_id = rng.choices(list(CANON), weights=[8, 8, 8, 8, 6, 6, 8, 8, 8, 6, 7, 4])[0]
    others = rng.sample([i for i in CANON if i != first_id], n_z - 1)
    zs = [Zarzut(first_id, None if hit("czynnosc_date_null") else first_date)]
    for oid in others:
        zs.append(Zarzut(oid, first_date - dt.timedelta(days=rng.randint(1, 30))))

    # appellant(s)
    n_odw = rng.choice([2, 2, 3]) if hit("consortium") else 1
    odw_src = rng.sample(pl.odw, n_odw)
    odw = [_entity(rng, s, P["krs_null"], P["regon_null"], P["nip_null"]) for s in odw_src]
    if n_odw > 1:
        odw[0].role = "Lider"
        for e in odw[1:]:
            e.role = "Partner"

    # contracting authorities
    n_zam = rng.choice([2, 2, 3]) if hit("multi_zam") else 1
    zam_src = rng.sample([z for z in pl.zam if z["nazwa"] not in {o["nazwa"] for o in odw_src}], n_zam)
    zams = [_entity(rng, s, P["zam_krs_null"], P["zam_regon_null"], P["zam_nip_null"]) for s in zam_src]
    if n_zam > 1:
        lead = rng.randrange(n_zam) if rng.random() < 0.3 else 0
        for i, z in enumerate(zams):
            z.prowadzacy = 1 if i == lead else 0

    # attorneys
    attorneys: list[Attorney] = []
    firm_nazwa = firm_mail = None
    if not hit("no_attorney"):
        src = rng.choice(pl.att)
        firm_nazwa, firm_mail = src["nazwa"], src["mail"]
        tk = "" if hit("no_title") else rng.choice(["rp", "adw", "rp", "adw"])
        attorneys.append(Attorney(src["imie_nazwisko"], tk))
        if hit("multi_attorney"):
            for other in rng.sample([a for a in pl.att if a["imie_nazwisko"] != src["imie_nazwisko"]],
                                    rng.choice([1, 1, 2])):
                attorneys.append(Attorney(other["imie_nazwisko"], rng.choice(["rp", "adw", "apl"]) if tk else ""))

    bzp = None if hit("bzp_null") else rng.choice(pl.bzp)
    ted = None if (hit("ted_null") and bzp) else rng.choice(pl.ted)
    nr = None if hit("nr_null") else rng.choice(pl.nr)
    signer = rng.choice(FIRST_NAMES_SIGN)
    kio = f"KIO {rng.randint(1000, 4999)}/{(data or base).year % 100}" if hit("kio_sygn") else None
    extra = [base - dt.timedelta(days=rng.randint(11, 90)) for _ in range(3)]
    return Case(
        data=data, miejscowosc=miejsc, zarzuty=zs, odw=odw, consortium=n_odw > 1,
        attorneys=attorneys, firm_nazwa=firm_nazwa, firm_mail=firm_mail,
        firm_address=_addr(rng), firm_phone=f"+48 {rng.randint(500, 799)} {rng.randint(100, 999)} {rng.randint(100, 999)}",
        zams=zams, bzp=bzp, nr=nr, ted=ted, tytul=rng.choice(pl.titles), tryb=rng.choice(PROC_MODES),
        signer=signer, signer_role=rng.choice(SIGNER_ROLES), kio_sygn=kio,
        wpis=rng.choice(["7 500,00 zł", "15 000,00 zł", "20 000 zł", "PLN 7.500,00", "zł 15 000"]),
        extra_dates=extra,
    )


# --------------------------------------------------------------------------- zarzuty texts

# {d} = date phrase; segments in [[...]] disappear when the date is unknown.
ZARZUT_TEXT: dict[int, dict[str, list[str]]] = {
    1: {
        "action": ["odrzuceniu oferty Odwołującego[[, o czym Zamawiający poinformował pismem z dnia {d}]]",
                   "czynności odrzucenia oferty złożonej przez Odwołującego[[ dokonanej w dniu {d}]]",
                   "odrzuceniu oferty Odwołującego na podstawie art. 226 ust. 1 pkt 5 Pzp[[ ({d})]]"],
        "fact": ["[[W dniu {d} ]]Zamawiający odrzucił ofertę Odwołującego, uznając ją za niezgodną z warunkami zamówienia.",
                 "Pismem[[ z dnia {d}]] Zamawiający zawiadomił o odrzuceniu oferty Odwołującego.",
                 "Zamawiający[[ w dniu {d}]] podjął decyzję o odrzuceniu oferty Odwołującego jako zawierającej rażąco niską cenę."],
        "head": ["naruszenia art. 226 ust. 1 pkt 5 Pzp poprzez bezpodstawne odrzucenie oferty Odwołującego",
                 "naruszenia art. 226 ust. 1 pkt 8 w zw. z art. 224 ust. 6 Pzp przez odrzucenie oferty Odwołującego"],
    },
    2: {
        "action": ["wyborze jako najkorzystniejszej oferty innego wykonawcy[[, ogłoszonym w dniu {d}]]",
                   "czynności wyboru oferty najkorzystniejszej[[ z dnia {d}]]",
                   "ogłoszeniu wyniku postępowania i wyborze oferty firmy konkurencyjnej[[ ({d})]]"],
        "fact": ["[[W dniu {d} ]]Zamawiający poinformował o wyborze oferty najkorzystniejszej, którą uznał ofertę innego wykonawcy.",
                 "Zamawiający[[ w dniu {d}]] opublikował zawiadomienie o wyborze najkorzystniejszej oferty.",
                 "Informacja o wyborze najkorzystniejszej oferty została przekazana wykonawcom[[ w dniu {d}]]."],
        "head": ["naruszenia art. 239 ust. 1 Pzp poprzez wybór oferty, która nie jest ofertą najkorzystniejszą",
                 "naruszenia art. 16 pkt 1 i art. 239 Pzp przez dokonanie wadliwego wyboru oferty najkorzystniejszej"],
    },
    3: {
        "action": ["wykluczeniu Odwołującego z postępowania[[, o którym poinformowano w dniu {d}]]",
                   "czynności wykluczenia Odwołującego z udziału w postępowaniu[[ z dnia {d}]]"],
        "fact": ["[[W dniu {d} ]]Zamawiający wykluczył Odwołującego z postępowania na podstawie art. 109 ust. 1 pkt 4 Pzp.",
                 "Pismem[[ z dnia {d}]] Zamawiający zawiadomił o wykluczeniu Odwołującego z postępowania."],
        "head": ["naruszenia art. 109 ust. 1 pkt 4 Pzp poprzez bezpodstawne wykluczenie Odwołującego",
                 "naruszenia art. 108 ust. 1 pkt 1 Pzp przez wykluczenie Odwołującego z postępowania"],
    },
    4: {
        "action": ["ustaleniu treści Specyfikacji Warunków Zamówienia[[ opublikowanej w dniu {d}]]",
                   "publikacji SWZ zawierającej postanowienia naruszające uczciwą konkurencję[[ ({d})]]",
                   "sformułowaniu postanowień SWZ udostępnionej na stronie prowadzonego postępowania[[ w dniu {d}]]"],
        "fact": ["[[W dniu {d} ]]Zamawiający opublikował ogłoszenie o zamówieniu i udostępnił Specyfikację Warunków Zamówienia.",
                 "Specyfikacja Warunków Zamówienia została opublikowana[[ w dniu {d}]] na platformie zakupowej Zamawiającego."],
        "head": ["naruszenia art. 99 ust. 1 i 4 Pzp poprzez ustalenie warunków SWZ ograniczających konkurencję",
                 "naruszenia art. 112 ust. 1 Pzp poprzez określenie nieproporcjonalnych warunków udziału w SWZ"],
    },
    5: {
        "action": ["modyfikacji treści SWZ dokonanej[[ w dniu {d}]]",
                   "zmianie treści Specyfikacji Warunków Zamówienia[[ z dnia {d}]] w zakresie wymagań technicznych"],
        "fact": ["[[W dniu {d} ]]Zamawiający dokonał modyfikacji treści SWZ, zmieniając wymagania dotyczące doświadczenia.",
                 "Zamawiający[[ w dniu {d}]] zmodyfikował treść SWZ w zakresie kryteriów oceny ofert."],
        "head": ["naruszenia art. 137 ust. 1 Pzp poprzez niezgodną z prawem modyfikację treści SWZ",
                 "naruszenia art. 137 ust. 1 i 4 w zw. z art. 16 Pzp przez zmianę SWZ"],
    },
    6: {
        "action": ["udzieleniu odpowiedzi na pytania wykonawców[[ w dniu {d}]], w sposób zmieniający treść SWZ",
                   "wyjaśnieniach treści SWZ opublikowanych[[ w dniu {d}]]"],
        "fact": ["[[W dniu {d} ]]Zamawiający udzielił odpowiedzi na pytania wykonawców dotyczące treści SWZ.",
                 "Zamawiający opublikował[[ w dniu {d}]] wyjaśnienia treści SWZ (odpowiedzi na pytania nr 4, 7 i 12)."],
        "head": ["naruszenia art. 135 ust. 2 i 6 Pzp poprzez udzielenie wyjaśnień treści SWZ prowadzących do jej zmiany",
                 "naruszenia art. 135 Pzp przez wadliwe odpowiedzi na pytania do SWZ"],
    },
    7: {
        "action": ["zaniechaniu odrzucenia oferty wykonawcy konkurencyjnego[[, które ujawniło się w dniu {d}]]",
                   "zaniechaniu odrzucenia oferty złożonej przez konkurenta mimo jej niezgodności z SWZ[[ ({d})]]"],
        "fact": ["[[W dniu {d} ]]Zamawiający zaniechał odrzucenia oferty wykonawcy konkurencyjnego, mimo że jest ona niezgodna z warunkami zamówienia.",
                 "Z informacji przekazanej[[ w dniu {d}]] wynika, że Zamawiający nie odrzucił oferty konkurenta zawierającej rażąco niską cenę."],
        "head": ["naruszenia art. 226 ust. 1 pkt 5 Pzp poprzez zaniechanie odrzucenia oferty konkurenta",
                 "naruszenia art. 226 ust. 1 pkt 8 Pzp przez zaniechanie odrzucenia oferty z rażąco niską ceną"],
    },
    8: {
        "action": ["zaniechaniu wykluczenia z postępowania wykonawcy konkurencyjnego[[ ({d})]]",
                   "zaniechaniu wykluczenia wykonawcy, który wprowadził Zamawiającego w błąd[[, ujawnionym w dniu {d}]]"],
        "fact": ["[[W dniu {d} ]]Zamawiający zaniechał wykluczenia z postępowania wykonawcy, który nie wykazał braku podstaw wykluczenia.",
                 "Zamawiający[[ w dniu {d}]] uznał, że brak jest podstaw do wykluczenia wykonawcy konkurencyjnego."],
        "head": ["naruszenia art. 109 ust. 1 pkt 8 Pzp poprzez zaniechanie wykluczenia wykonawcy",
                 "naruszenia art. 108 ust. 1 Pzp przez zaniechanie wykluczenia konkurenta"],
    },
    9: {
        "action": ["unieważnieniu postępowania o udzielenie zamówienia[[ w dniu {d}]]",
                   "czynności unieważnienia postępowania[[ z dnia {d}]]"],
        "fact": ["[[W dniu {d} ]]Zamawiający unieważnił postępowanie, powołując się na art. 255 pkt 3 Pzp.",
                 "Zamawiający[[ w dniu {d}]] unieważnił postępowanie."],
        "head": ["naruszenia art. 255 pkt 3 Pzp poprzez bezpodstawne unieważnienie postępowania",
                 "naruszenia art. 255 pkt 6 Pzp przez unieważnienie postępowania mimo braku wady"],
    },
    10: {
        "action": ["zaniechaniu unieważnienia postępowania obarczonego niemożliwą do usunięcia wadą[[ ({d})]]",
                   "zaniechaniu unieważnienia postępowania[[, mimo wiedzy o wadzie posiadanej od dnia {d}]]"],
        "fact": ["[[W dniu {d} ]]Zamawiający, mimo wady postępowania, zaniechał jego unieważnienia i kontynuował czynności.",
                 "Zamawiający[[ w dniu {d}]] poinformował, że nie widzi podstaw do unieważnienia postępowania."],
        "head": ["naruszenia art. 255 pkt 6 Pzp poprzez zaniechanie unieważnienia postępowania",
                 "naruszenia art. 255 pkt 6 w zw. z art. 457 Pzp przez zaniechanie unieważnienia"],
    },
    11: {
        "action": ["dokonaniu opisu przedmiotu zamówienia w sposób utrudniający uczciwą konkurencję[[ (OPZ udostępniony w dniu {d})]]",
                   "sporządzeniu Opisu Przedmiotu Zamówienia[[ opublikowanego w dniu {d}]] w sposób niejednoznaczny"],
        "fact": ["[[W dniu {d} ]]Zamawiający udostępnił Opis Przedmiotu Zamówienia stanowiący załącznik nr 1 do SWZ.",
                 "Opis przedmiotu zamówienia (OPZ)[[ udostępniony w dniu {d}]] wskazuje parametry właściwe dla jednego producenta."],
        "head": ["naruszenia art. 99 ust. 4 Pzp poprzez opisanie przedmiotu zamówienia w sposób utrudniający konkurencję",
                 "naruszenia art. 99 ust. 1 i 2 Pzp przez niejednoznaczny opis przedmiotu zamówienia"],
    },
    12: {
        "action": ["określeniu projektowanych postanowień umowy[[ udostępnionych w dniu {d}]] w sposób nadmiernie obciążający wykonawcę",
                   "ustaleniu treści projektowanych postanowień umowy (załącznik nr 4 do SWZ)[[ z dnia {d}]]"],
        "fact": ["[[W dniu {d} ]]Zamawiający udostępnił projektowane postanowienia umowy przewidujące kary umowne bez limitu.",
                 "Projektowane postanowienia umowy[[ opublikowane w dniu {d}]] nakładają na wykonawcę nieograniczoną odpowiedzialność."],
        "head": ["naruszenia art. 433 pkt 1-4 Pzp poprzez określenie projektowanych postanowień umowy z klauzulami abuzywnymi",
                 "naruszenia art. 436 Pzp przez ukształtowanie projektowanych postanowień umowy z naruszeniem równowagi stron"],
    },
}


def fill(template: str, d: dt.date | None, style: str) -> str:
    if d is None:
        return re.sub(r"\[\[.*?\]\]", "", template).replace("  ", " ")
    return re.sub(r"\[\[(.*?)\]\]", lambda m: m.group(1), template).replace("{d}", fmt_date(d, style))


REQUESTS = [
    "uwzględnienie odwołania w całości",
    "nakazanie Zamawiającemu unieważnienia zaskarżonej czynności",
    "nakazanie Zamawiającemu powtórzenia czynności badania i oceny ofert",
    "nakazanie Zamawiającemu dokonania zmiany treści SWZ",
    "dopuszczenie i przeprowadzenie dowodów wskazanych w treści uzasadnienia",
    "zasądzenie od Zamawiającego na rzecz Odwołującego kosztów postępowania odwoławczego",
]
FILLER = [
    "Odwołujący ma interes w uzyskaniu zamówienia oraz może ponieść szkodę w wyniku naruszenia przez Zamawiającego przepisów ustawy.",
    "Oferta Odwołującego, w razie uwzględnienia odwołania, mogłaby zostać uznana za najkorzystniejszą w świetle przyjętych kryteriów oceny.",
    "Zamawiający nie uzasadnił w sposób należyty swojego stanowiska, co uniemożliwia weryfikację prawidłowości podjętych czynności.",
    "Zgodnie z utrwalonym orzecznictwem Krajowej Izby Odwoławczej zasada przejrzystości wymaga, aby czynności zamawiającego były weryfikowalne.",
    "Termin na wniesienie odwołania został zachowany, a kopia odwołania została przekazana Zamawiającemu przed upływem terminu.",
    "Wpis od odwołania został uiszczony na rachunek Urzędu Zamówień Publicznych, co potwierdza załączony dowód przelewu.",
    "Wymagania Zamawiającego nie znajdują uzasadnienia w jego obiektywnych potrzebach i prowadzą do ograniczenia kręgu wykonawców.",
    "W ocenie Odwołującego Zamawiający dokonał błędnej wykładni postanowień dokumentacji postępowania.",
    "Dowód: dokumentacja postępowania, w tym protokół wraz z załącznikami.",
    "Odwołujący wskazuje, że analogiczne stanowisko zajęła Izba w wyroku z dnia 12 kwietnia 2024 r., sygn. akt KIO 1022/24.",
    "Wykonawca konkurencyjny nie wykazał spełniania warunków udziału w postępowaniu w zakresie doświadczenia zawodowego.",
    "Wyjaśnienia złożone przez wykonawcę były ogólnikowe i nie zawierały kalkulacji pozwalającej na weryfikację ceny.",
    "Mając na uwadze powyższe, odwołanie zasługuje na uwzględnienie w całości.",
]
ATTACHMENTS = ["pełnomocnictwo", "dowód uiszczenia wpisu od odwołania", "dowód przekazania kopii odwołania Zamawiającemu",
               "odpis z KRS Odwołującego", "korespondencja z Zamawiającym", "umowa konsorcjum"]


# --------------------------------------------------------------------------- rendering ctx


class Ctx:
    """Per-document helper: rng, chosen font/styles and convenience builders."""

    def __init__(self, rng: random.Random, font: str | None = None, base_size: float | None = None):
        self.rng = rng
        fam = fonts()
        self.font = font or rng.choice(fam)
        self.bold = self.font + "-Bold"
        self.size = base_size or rng.choice([9.5, 10, 10.5, 11, 11.5])
        self.lead = self.size * rng.choice([1.25, 1.3, 1.4])
        self.date_body = rng.choice(DATE_STYLES_BODY)
        self.nip_style = rng.choice(NIP_STYLES)
        self.krs_style = rng.choice(["plain", "plain", "plain", "space"])
        self.regon_style = rng.choice(["plain", "plain", "space"])
        self.bzp_style = rng.choice(["compact", "space", "space"])
        self.ted_style = rng.choice(["plain", "plain", "ojs", "ojs_long"])
        self._ted_cache: dict[str, str] = {}

    # ---- styles
    def style(self, name: str = "body", **kw) -> ParagraphStyle:
        base = dict(fontName=self.font, fontSize=self.size, leading=self.lead, alignment=TA_LEFT)
        presets = {
            "body": {},
            "just": dict(alignment=TA_JUSTIFY, spaceAfter=self.size * 0.35),
            "right": dict(alignment=TA_RIGHT),
            "center": dict(alignment=TA_CENTER),
            "title": dict(fontName=self.bold, fontSize=self.size + 6, leading=self.size + 10,
                          alignment=TA_CENTER, spaceBefore=8, spaceAfter=8),
            "h": dict(fontName=self.bold, fontSize=self.size + 1, leading=self.lead + 2, spaceBefore=6, spaceAfter=3),
            "small": dict(fontSize=self.size - 2, leading=self.size),
            "bold": dict(fontName=self.bold),
        }
        base.update(presets.get(name, {}))
        base.update(kw)
        return ParagraphStyle(name + str(id(kw)), **base)

    def P(self, text: str, style: str = "body", **kw) -> Paragraph:
        return Paragraph(text, self.style(style, **kw))

    def gap(self, h: float = 4) -> Spacer:
        return Spacer(1, h * mm)

    def table(self, rows: list[list[Any]], widths: list[float] | None = None, grid: bool = True,
              header: bool = False, shade: Any = None, pad: float = 3) -> Table:
        cell = self.style("body", fontSize=self.size - 0.5, leading=self.lead - 0.5)
        data = [[c if not isinstance(c, str) else Paragraph(c, cell) for c in r] for r in rows]
        t = Table(data, colWidths=widths, hAlign="LEFT")
        st = [("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("LEFTPADDING", (0, 0), (-1, -1), pad), ("RIGHTPADDING", (0, 0), (-1, -1), pad),
              ("TOPPADDING", (0, 0), (-1, -1), pad * 0.7), ("BOTTOMPADDING", (0, 0), (-1, -1), pad * 0.7)]
        if grid:
            st.append(("GRID", (0, 0), (-1, -1), 0.5, colors.grey))
        if header:
            st.append(("BACKGROUND", (0, 0), (-1, 0), shade or colors.HexColor("#dde4ee")))
        elif shade is not None:
            st.append(("BACKGROUND", (0, 0), (0, -1), shade))
        t.setStyle(TableStyle(st))
        return t

    # ---- value formatting
    def d(self, date: dt.date | None, style: str | None = None) -> str:
        return fmt_date(date, style or self.date_body) if date else ""

    def nip(self, v: str) -> str:
        return fmt_nip(v, self.nip_style)

    def krs(self, v: str) -> str:
        return fmt_krs(v, self.krs_style)

    def regon(self, v: str) -> str:
        return fmt_regon(v, self.regon_style)

    def bzp(self, v: str) -> str:
        return fmt_bzp(v, self.bzp_style)

    def ted(self, v: str) -> str:
        if v not in self._ted_cache:
            self._ted_cache[v] = fmt_ted(v, self.ted_style, self.rng)
        return self._ted_cache[v]

    def id_parts(self, e: Entity, labels: tuple[str, str, str] = ("KRS", "NIP", "REGON"), sep: str = ": ") -> list[str]:
        out = []
        if e.krs:
            out.append(f"{labels[0]}{sep}{self.krs(e.krs)}")
        if e.nip:
            out.append(f"{labels[1]}{sep}{self.nip(e.nip)}")
        if e.regon:
            out.append(f"{labels[2]}{sep}{self.regon(e.regon)}")
        return out

    def zarzut(self, z: Zarzut, kind: str, dated: bool = True) -> str:
        opts = ZARZUT_TEXT[z.powod_id][kind]
        return fill(self.rng.choice(opts), z.date if dated else None, self.date_body)

    def filler(self, n: int) -> list[str]:
        return self.rng.sample(FILLER, min(n, len(FILLER)))

    def attorneys_line(self, case: Case, style: str = "short") -> str:
        return ", ".join(a.with_title(style) for a in case.attorneys)

    def proc_parts(self, case: Case) -> list[tuple[str, str]]:
        """Label/value pairs for procurement identifiers that exist."""
        out = []
        if case.nr:
            out.append(("nr", case.nr))
        if case.bzp:
            out.append(("bzp", self.bzp(case.bzp)))
        if case.ted:
            out.append(("ted", self.ted(case.ted)))
        return out


# --------------------------------------------------------------------------- PDF output


class NumberedCanvas(rl_canvas.Canvas):
    """Canvas that knows the total page count (for 'Strona X z Y')."""

    footer_fmt: str | None = "Strona {p} z {n}"
    footer_font: str = "Helvetica"
    footer_size: float = 8
    footer_align: str = "center"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._saved: list[dict] = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._saved)
        for st in self._saved:
            self.__dict__.update(st)
            if self.footer_fmt:
                self.setFont(self.footer_font, self.footer_size)
                txt = self.footer_fmt.format(p=self._pageNumber, n=n)
                w, _ = self._pagesize
                if self.footer_align == "right":
                    self.drawRightString(w - 20 * mm, 12 * mm, txt)
                else:
                    self.drawCentredString(w / 2, 12 * mm, txt)
            super().showPage()
        super().save()


def canvas_class(ctx: Ctx, fmt: str | None, align: str = "center"):
    return type("NC", (NumberedCanvas,), {"footer_fmt": fmt, "footer_font": ctx.font,
                                          "footer_size": ctx.size - 2, "footer_align": align})


def build_simple(path: str | Path, story: list, ctx: Ctx, pagesize=A4, margins=(22, 20, 22, 22),
                 footer: str | None = "Strona {p} z {n}", footer_align: str = "center",
                 on_page: Callable | None = None, title: str = "") -> None:
    l, r, t, b = margins
    doc = SimpleDocTemplate(str(path), pagesize=pagesize, leftMargin=l * mm, rightMargin=r * mm,
                            topMargin=t * mm, bottomMargin=b * mm, title=title, author="")
    kw = {}
    if on_page:
        kw = dict(onFirstPage=on_page, onLaterPages=on_page)
    doc.build(story, canvasmaker=canvas_class(ctx, footer, footer_align), **kw)


# --------------------------------------------------------------------------- templates


@dataclass
class Template:
    name: str
    render: Callable[[Case, Ctx, Path], None]  # writes the PDF
    overrides: dict = field(default_factory=dict)  # case sampling probabilities
    split: str = "dev"


def load_template_module(mod) -> Template:
    return Template(name=mod.NAME, render=mod.render, overrides=getattr(mod, "OVERRIDES", {}))


def deep(x):
    return copy.deepcopy(x)
