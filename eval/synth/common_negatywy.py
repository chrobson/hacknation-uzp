"""Shared helpers for the NEGATIVE-document generator (eval/synth/negatywy).

Negatives are documents that must be classified as "none" (expected output {}).
They reuse real vocabulary and identifiers recombined from the training ground truth
(company names, NIP/KRS/REGON, procurement numbers, attorneys) so that keyword-only
classifiers are tempted into false positives.

Dev-only dependencies: reportlab, pdfplumber (self-check), optionally matplotlib (DejaVu font source).
"""

from __future__ import annotations

import glob
import json
import os
import random
import string
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRAIN = ROOT / "data" / "train"
BLIND_ROOT = Path(os.environ.get("SYNTH_BLIND_ROOT", "/Users/mat2/orca/projects/hacknation/synth-blind"))

# --------------------------------------------------------------------------- value pool


@dataclass
class Company:
    nazwa: str
    nip: str | None = None
    krs: str | None = None
    regon: str | None = None


@dataclass
class Pool:
    wykonawcy: list[Company] = field(default_factory=list)
    zamawiajacy: list[Company] = field(default_factory=list)
    osoby: list[str] = field(default_factory=list)
    kancelarie: list[str] = field(default_factory=list)
    maile: list[str] = field(default_factory=list)
    tytuly: list[str] = field(default_factory=list)
    bzp: list[str] = field(default_factory=list)
    ted: list[str] = field(default_factory=list)
    postepowania: list[str] = field(default_factory=list)
    rachunki: list[str] = field(default_factory=list)
    miasta: list[str] = field(default_factory=list)
    czynnosci: list[str] = field(default_factory=list)


FALLBACK_CITIES = ["Warszawa", "Kraków", "Gdańsk", "Poznań", "Wrocław", "Łódź", "Lublin", "Katowice",
                   "Bydgoszcz", "Rzeszów", "Olsztyn", "Kielce", "Zielona Góra", "Białystok", "Opole"]
STREETS = ["ul. Postępu", "ul. Grzybowska", "al. Jerozolimskie", "ul. Marszałkowska", "ul. Długa",
           "ul. Wołoska", "ul. Kościuszki", "ul. Piłsudskiego", "ul. Żelazna", "ul. Łąkowa",
           "al. Niepodległości", "ul. Świętokrzyska", "pl. Grunwaldzki", "ul. Szczęśliwicka"]


def _uniq(xs):
    out, seen = [], set()
    for x in xs:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


@cache
def load_pool() -> Pool:
    p = Pool()
    for f in sorted(glob.glob(str(TRAIN / "przyklad_*" / "odwolanie.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for o in d.get("Odwolujacy") or []:
            p.wykonawcy.append(Company(o.get("nazwa"), o.get("nip"), o.get("krs"), o.get("regon")))
            pel = o.get("pelnomocnik") or {}
            p.osoby.append(pel.get("imie_nazwisko"))
            p.kancelarie.append(pel.get("nazwa"))
            p.maile.append(pel.get("mail"))
        for z in d.get("Zamawiajacy") or []:
            p.zamawiajacy.append(Company(z.get("nazwa"), z.get("nip"), z.get("krs"), z.get("regon")))
        zp = d.get("ZamowieniePubliczne") or {}
        p.tytuly.append(zp.get("tytul"))
        p.bzp.append(zp.get("numer_bzp"))
        p.ted.append(zp.get("numer_ted"))
        p.postepowania.append(zp.get("numer_postepowania"))
        k = d.get("OdwolanieKIO") or {}
        p.miasta.append(k.get("miejscowosc"))
        p.czynnosci.append(k.get("czynnosc_opis"))
    for f in sorted(glob.glob(str(TRAIN / "przyklad_*" / "pelnomocnictwo.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        for m in d.get("mocodawca") or []:
            p.osoby += [s.get("imie_nazwisko") for s in m.get("podpisujacy") or []]
        p.osoby += [x.get("imie_nazwisko") for x in d.get("pelnomocnicy") or []]
    for f in sorted(glob.glob(str(TRAIN / "przyklad_*" / "przelew.json"))):
        d = (json.loads(Path(f).read_text(encoding="utf-8")) or {}).get("przelew_bankowy") or {}
        p.rachunki += [d.get("na_rachunek"), d.get("z_rachunku")]
    for attr in ("osoby", "kancelarie", "maile", "tytuly", "bzp", "ted", "postepowania", "rachunki", "miasta", "czynnosci"):
        setattr(p, attr, _uniq(getattr(p, attr)))
    p.wykonawcy = [c for c in p.wykonawcy if c.nazwa]
    p.zamawiajacy = [c for c in p.zamawiajacy if c.nazwa]
    p.miasta = _uniq(p.miasta + FALLBACK_CITIES)
    if not p.wykonawcy:  # no train data available: minimal synthetic fallback
        p.wykonawcy = [Company("Belmoria Rozwiązania S.A.", "9999284065", "9999405188", "999642785")]
        p.zamawiajacy = [Company("Gmina Rudnik Wielki", "9991234567", None, "999123456")]
        p.osoby = ["Aleksandra Marciniak", "Jolanta Zajkowski", "Piotr Zalewski"]
        p.kancelarie = ["Kancelaria Adwokacka i Partnerzy"]
        p.tytuly = ["Zakup i dostawa sprzętu komputerowego"]
        p.bzp, p.ted, p.postepowania = ["2026/BZP00999778"], ["999137-2026"], ["ZP.271.93.2026"]
        p.rachunki = ["68438223049992295262834736"]
    return p


# --------------------------------------------------------------------------- formatting helpers

MIESIACE_DOP = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
                "września", "października", "listopada", "grudnia"]
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def rand_date(rng: random.Random, start=date(2026, 1, 5), span=300) -> date:
    return start + timedelta(days=rng.randrange(span))


def fmt_date(rng: random.Random, d: date, style: str | None = None) -> str:
    style = style or rng.choice(["dot", "dot_r", "words", "words_r", "roman", "iso"])
    return {
        "dot": f"{d.day:02d}.{d.month:02d}.{d.year}",
        "dot_r": f"{d.day:02d}.{d.month:02d}.{d.year} r.",
        "words": f"{d.day} {MIESIACE_DOP[d.month - 1]} {d.year}",
        "words_r": f"{d.day} {MIESIACE_DOP[d.month - 1]} {d.year} r.",
        "roman": f"{d.day} {ROMAN[d.month - 1]} {d.year} r.",
        "iso": d.isoformat(),
    }[style]


def fmt_nip(rng: random.Random, nip: str | None) -> str:
    nip = nip or "".join(rng.choice(string.digits) for _ in range(10))
    s = rng.choice(["plain", "dash", "dash2", "pl"])
    if s == "dash":
        return f"{nip[:3]}-{nip[3:6]}-{nip[6:8]}-{nip[8:]}"
    if s == "dash2":
        return f"{nip[:3]}-{nip[3:5]}-{nip[5:7]}-{nip[7:]}"
    if s == "pl":
        return f"PL{nip}"
    return nip


def fmt_account(rng: random.Random, acc: str | None) -> str:
    acc = acc or "".join(rng.choice(string.digits) for _ in range(26))
    if rng.random() < 0.6:
        g = acc[:2] + " " + " ".join(acc[i:i + 4] for i in range(2, 26, 4))
        return ("PL" + g) if rng.random() < 0.3 else g
    return acc


def fmt_amount(rng: random.Random, value: float) -> str:
    whole, gr = int(value), round((value - int(value)) * 100)
    ws = f"{whole:,}".replace(",", rng.choice([" ", ".", " "]))
    body = f"{ws},{gr:02d}" if rng.random() < 0.8 else ws
    cur = rng.choice(["zł", "PLN"])
    return f"{cur} {body}" if rng.random() < 0.2 else f"{body} {cur}"


def rand_digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.digits) for _ in range(n))


def rand_kio_sygn(rng: random.Random, year: int = 2026) -> str:
    return f"KIO {rng.randint(100, 4800)}/{str(year)[2:] if rng.random() < 0.4 else year}"


def address(rng: random.Random, city: str | None = None) -> str:
    return f"{rng.choice(STREETS)} {rng.randint(1, 180)}{rng.choice(['', '', 'A', 'B'])}, " \
           f"{rng.randint(0, 99):02d}-{rng.randint(0, 999):03d} {city or rng.choice(FALLBACK_CITIES)}"


def title_prefix(rng: random.Random) -> str:
    return rng.choice(["adw. ", "r.pr. ", "radca prawny ", "adwokat ", ""])


# --------------------------------------------------------------------------- random file names

_NAME_STYLES = [
    lambda r: "".join(r.choice("0123456789abcdef") for _ in range(12)),
    lambda r: f"scan_{r.randint(10000, 99999)}",
    lambda r: f"dokument ({r.randint(1, 9)})",
    lambda r: f"IMG{r.randint(1000, 9999)}_{r.randint(100000, 999999)}",
    lambda r: f"zal_{r.randint(1, 15)}_{''.join(r.choice(string.ascii_lowercase) for _ in range(5))}",
    lambda r: f"{r.randint(2025, 2026)}{r.randint(1, 12):02d}{r.randint(1, 28):02d}_{r.randint(100, 999)}",
    # deliberately misleading names: classification must be content-based
    lambda r: r.choice(["odwolanie", "pelnomocnictwo", "potwierdzenie_przelewu", "przelew", "odwolanie_KIO_final"])
    + f"_{r.randint(1, 99)}",
]


def random_stem(rng: random.Random) -> str:
    return rng.choice(_NAME_STYLES)(rng).replace("/", "_")


# --------------------------------------------------------------------------- PDF rendering

_FONT_CANDIDATES = [
    # (regular, bold) – first that exists wins
    ("{mpl}/fonts/ttf/DejaVuSans.ttf", "{mpl}/fonts/ttf/DejaVuSans-Bold.ttf", "DejaVuSans"),
    ("{mpl}/fonts/ttf/DejaVuSerif.ttf", "{mpl}/fonts/ttf/DejaVuSerif-Bold.ttf", "DejaVuSerif"),
    ("/usr/share/fonts/truetype/crosextra/Carlito-Regular.ttf", "/usr/share/fonts/truetype/crosextra/Carlito-Bold.ttf", "Carlito"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "ArialSys"),
    ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf", "ArialUni"),
]


@cache
def register_fonts() -> list[tuple[str, str]]:
    """Register every available Polish-capable TTF family. Returns [(regular, bold)] names."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    mpl = ""
    try:
        import matplotlib

        mpl = matplotlib.get_data_path()
    except Exception:
        pass
    extra = os.environ.get("SYNTH_FONT")  # optional "regular.ttf:bold.ttf"
    cands = list(_FONT_CANDIDATES)
    if extra:
        reg, _, bold = extra.partition(":")
        cands.insert(0, (reg, bold or reg, "UserFont"))
    out = []
    for reg, bold, name in cands:
        reg, bold = reg.format(mpl=mpl), bold.format(mpl=mpl)
        if not (Path(reg).exists() and Path(bold).exists()) or any(o[0] == name for o in out):
            continue
        pdfmetrics.registerFont(TTFont(name, reg))
        pdfmetrics.registerFont(TTFont(name + "-B", bold))
        out.append((name, name + "-B"))
    if not out:
        raise RuntimeError("No TTF font with Polish glyphs found; set SYNTH_FONT=/path/regular.ttf:/path/bold.ttf "
                           "or `pip install matplotlib` (ships DejaVu).")
    return out


class Doc:
    """Tiny wrapper over reportlab.platypus with a randomised but consistent look."""

    def __init__(self, rng: random.Random):
        from reportlab.lib.styles import ParagraphStyle

        self.rng = rng
        fam = rng.choice(register_fonts())
        self.font, self.bold = fam
        size = rng.choice([9, 9.5, 10, 10.5, 11])
        self.size = size
        self.flow = []
        lead = size * rng.choice([1.25, 1.35, 1.5])
        self.st = {
            "p": ParagraphStyle("p", fontName=self.font, fontSize=size, leading=lead, spaceAfter=size * 0.5,
                                alignment=rng.choice([0, 4])),
            "small": ParagraphStyle("s", fontName=self.font, fontSize=size - 1.5, leading=(size - 1.5) * 1.3),
            "right": ParagraphStyle("r", fontName=self.font, fontSize=size, leading=lead, alignment=2),
            "center": ParagraphStyle("c", fontName=self.font, fontSize=size, leading=lead, alignment=1),
            "h1": ParagraphStyle("h1", fontName=self.bold, fontSize=size + rng.choice([3, 4, 6]),
                                 leading=(size + 6) * 1.3, alignment=rng.choice([1, 1, 0]), spaceBefore=6, spaceAfter=8),
            "h2": ParagraphStyle("h2", fontName=self.bold, fontSize=size + 1, leading=(size + 1) * 1.35,
                                 spaceBefore=6, spaceAfter=4),
            "b": ParagraphStyle("b", fontName=self.bold, fontSize=size, leading=lead, spaceAfter=size * 0.4),
        }

    @staticmethod
    def esc(t: str) -> str:
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def para(self, text: str, style: str = "p", raw: bool = False):
        from reportlab.platypus import Paragraph

        self.flow.append(Paragraph(text if raw else self.esc(text).replace("\n", "<br/>"), self.st[style]))

    def lines(self, lines: list[str], style: str = "p"):
        self.para("\n".join(lines), style)

    def h1(self, t):
        self.para(t, "h1")

    def h2(self, t):
        self.para(t, "h2")

    def space(self, h=8):
        from reportlab.platypus import Spacer

        self.flow.append(Spacer(1, h))

    def rule(self):
        from reportlab.platypus import HRFlowable

        self.flow.append(HRFlowable(width="100%", thickness=0.6, spaceBefore=3, spaceAfter=5))

    def table(self, rows: list[list[str]], widths=None, header=False, grid=True, style="small"):
        from reportlab.lib import colors
        from reportlab.platypus import Paragraph, Table, TableStyle

        data = [[Paragraph(self.esc(str(c)).replace("\n", "<br/>"), self.st[style]) for c in r] for r in rows]
        t = Table(data, colWidths=widths, hAlign="LEFT")
        cmds = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 4)]
        if grid:
            cmds.append(("GRID", (0, 0), (-1, -1), 0.4, colors.grey))
        if header:
            cmds.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")))
        t.setStyle(TableStyle(cmds))
        self.flow.append(t)
        self.space(6)

    def pagebreak(self):
        from reportlab.platypus import PageBreak

        self.flow.append(PageBreak())

    def build(self, path: Path, header: str | None = None, footer: str | None = None, page_numbers: bool | None = None):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate

        rng = self.rng
        page_numbers = rng.random() < 0.6 if page_numbers is None else page_numbers
        m = rng.choice([18, 20, 22, 25]) * mm
        font, size = self.font, self.size

        def deco(canvas, doc):
            canvas.saveState()
            canvas.setFont(font, size - 2)
            if header:
                canvas.drawString(m, A4[1] - m * 0.6, header)
            if footer:
                canvas.drawString(m, m * 0.5, footer)
            if page_numbers:
                canvas.drawRightString(A4[0] - m, m * 0.5, f"Strona {doc.page}")
            canvas.restoreState()

        doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=m, rightMargin=m, topMargin=m, bottomMargin=m,
                                title="", author="", subject="", creator="")
        doc.build(self.flow, onFirstPage=deco, onLaterPages=deco)


# --------------------------------------------------------------------------- context for one document


@dataclass
class Ctx:
    """Recombined case values for a single negative document."""

    rng: random.Random
    wyk: Company
    wyk2: Company
    zam: Company
    osoba: str
    osoba2: str
    osoba3: str
    kancelaria: str
    mail: str
    tytul: str
    bzp: str
    ted: str
    postep: str
    rach: str
    rach2: str
    miasto: str
    sygn: str
    czynnosc: str
    d: date


def make_ctx(rng: random.Random) -> Ctx:
    p = load_pool()
    wyk, wyk2 = rng.sample(p.wykonawcy, 2) if len(p.wykonawcy) > 1 else (p.wykonawcy[0], p.wykonawcy[0])
    osoby = rng.sample(p.osoby, 3) if len(p.osoby) >= 3 else (p.osoby * 3)[:3]
    return Ctx(
        rng=rng, wyk=wyk, wyk2=wyk2, zam=rng.choice(p.zamawiajacy),
        osoba=osoby[0], osoba2=osoby[1], osoba3=osoby[2],
        kancelaria=rng.choice(p.kancelarie or ["Kancelaria Prawna i Partnerzy"]),
        mail=rng.choice(p.maile or ["biuro@kancelaria.example"]),
        tytul=rng.choice(p.tytuly), bzp=rng.choice(p.bzp), ted=rng.choice(p.ted or ["999137-2026"]),
        postep=rng.choice(p.postepowania), rach=rng.choice(p.rachunki), rach2=rng.choice(p.rachunki),
        miasto=rng.choice(p.miasta), sygn=rand_kio_sygn(rng),
        czynnosc=rng.choice(p.czynnosci or ["Wybór najkorzystniejszej oferty"]), d=rand_date(rng),
    )


def company_block(c: Ctx, comp: Company, with_ids: bool = True) -> list[str]:
    rng = c.rng
    out = [comp.nazwa, address(rng, rng.choice(load_pool().miasta))]
    if with_ids:
        ids = []
        if comp.nip:
            ids.append(f"NIP: {fmt_nip(rng, comp.nip)}")
        if comp.krs and rng.random() < 0.8:
            ids.append(f"KRS: {comp.krs}")
        if comp.regon and rng.random() < 0.6:
            ids.append(f"REGON: {comp.regon}")
        if ids:
            out.append(", ".join(ids) if rng.random() < 0.5 else "\n".join(ids))
    return out


# --------------------------------------------------------------------------- output


def write_case(out_dir: Path, case_name: str, rng: random.Random, render) -> tuple[Path, Path]:
    """render(path) draws a PDF; writes <random>.pdf (no JSON = expected {}) into out_dir/case_name."""
    case = out_dir / case_name
    case.mkdir(parents=True, exist_ok=True)
    stem = random_stem(rng)
    pdf = case / f"{stem}.pdf"
    render(pdf)
    # Negatives carry no JSON: the gate treats a PDF without <stem>.json as expected {}.
    return pdf, case / f"{stem}.json"
