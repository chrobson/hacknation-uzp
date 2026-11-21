"""Shared machinery for synthetic PEŁNOMOCNICTWO (power of attorney) documents.

Everything a template needs lives here: value pools recombined from the training
ground truth, Polish name declension, value formatting variants, fonts/styles and
the PDF renderer. Templates only decide layout and wording.

Ground-truth rule: the case object *is* the ground truth. A field that a document
does not print is stored as ``None`` in the case before rendering (e.g. hidden
KRS), so templates never have to report what they printed.
"""

from __future__ import annotations

import datetime as dt
import glob
import importlib.util
import json
import os
import random
import string
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
TRAIN_DIR = REPO_ROOT / "data" / "train"
DEV_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
BLIND_ROOT = Path(os.environ.get("UZP_SYNTH_BLIND_ROOT", "/Users/mat2/orca/projects/hacknation/synth-blind"))
BLIND_TEMPLATE_DIR = BLIND_ROOT / "templates" / "pelnomocnictwo"
CLASS_NAME = "pelnomocnictwo"

# --------------------------------------------------------------------------------------
# Names and declension
# --------------------------------------------------------------------------------------

MALE_FIRST = [
    "Aleksander", "Andrzej", "Bartosz", "Cezary", "Damian", "Dariusz", "Grzegorz", "Henryk",
    "Ignacy", "Igor", "Jarosław", "Kamil", "Krzysztof", "Leszek", "Maciej", "Marek", "Michał",
    "Norbert", "Paweł", "Piotr", "Rafał", "Robert", "Ryszard", "Sebastian", "Sławomir",
    "Tadeusz", "Tomasz", "Wojciech", "Zbigniew", "Łukasz", "Jakub", "Mateusz", "Adam",
    "Jacek", "Janusz", "Jerzy", "Mirosław", "Stanisław", "Wiktor", "Konrad",
]
FEMALE_FIRST = [
    "Agnieszka", "Aleksandra", "Barbara", "Beata", "Celina", "Dorota", "Elżbieta", "Ewa",
    "Felicja", "Grażyna", "Halina", "Iwona", "Joanna", "Jolanta", "Karolina", "Katarzyna",
    "Klaudia", "Magdalena", "Marta", "Natalia", "Olga", "Oliwia", "Patrycja", "Renata",
    "Teresa", "Weronika", "Anna", "Monika", "Agata", "Justyna", "Urszula", "Sylwia",
    "Małgorzata", "Edyta", "Zofia", "Alicja", "Jadwiga", "Wanda",
]
# Surnames in masculine base form (feminine derived for -ski/-cki/-dzki).
SURNAMES = [
    "Adamczyk", "Baran", "Bartoszewicz", "Biernacki", "Borkowski", "Bąk", "Bąkiewicz",
    "Chmielewski", "Cieślak", "Czajka", "Czerwiński", "Dobrowolski", "Domański", "Dudek",
    "Dudziewicz", "Furman", "Gajewski", "Grabowski", "Górecki", "Górnicki", "Głowacz",
    "Jabłoński", "Jastrzębski", "Jaworski", "Jurgielewicz", "Kaczmarek", "Kowalczyk", "Kubiak",
    "Kucharski", "Kurek", "Kędzierski", "Lewandowski", "Lis", "Maciejewski", "Majewski",
    "Malinowski", "Marciniak", "Mazur", "Mazurkiewicz", "Michalak", "Milewski", "Najder",
    "Niedźwiecki", "Nowak", "Nowicki", "Olszewski", "Ostrowski", "Pawlak", "Pawłowski",
    "Pietrzak", "Piotrowski", "Przybylski", "Rutkowski", "Różański", "Sadowski", "Siedlecki",
    "Sikora", "Sikorski", "Sobczak", "Szewczyk", "Szulc", "Szymański", "Tomaszewski",
    "Urbański", "Walczak", "Wawrzyniak", "Wieczorek", "Wierzbicki", "Wiśniewski", "Woźniak",
    "Wróblewski", "Wysocki", "Włodarczyk", "Zajkowski", "Zalewski", "Zawadzki", "Zieliński",
    "Łukaszewski", "Kamiński", "Lewicki", "Zaręba", "Kołodziej", "Wojtczak",
]

_MALE_STEM = {"Marek": "Mark", "Leszek": "Leszk", "Paweł": "Pawł", "Jacek": "Jack", "Aleksander": "Aleksandr"}
_CASES = ("nom", "gen", "dat", "acc", "ins")


def _ends(s: str, *suf: str) -> bool:
    return any(s.endswith(x) for x in suf)


def _fem_noun(stem_a: str, case: str) -> str:
    """Decline a feminine-pattern noun ending in -a (also male 'Czajka', 'Jakub' no)."""
    s = stem_a[:-1]
    if case == "nom":
        return stem_a
    if case == "acc":
        return s + "ę"
    if case == "ins":
        return s + "ą"
    # gen / dat
    if _ends(s, "i"):  # Natalia -> Natalii
        return s + "i"
    if _ends(s, "j"):  # Alicja -> Alicji
        return s + "i"
    if _ends(s, "l"):  # Urszula -> Urszuli
        return s + "i"
    if case == "gen":
        if _ends(s, "k", "g"):
            return s + "i"
        if _ends(s, "cz", "sz", "rz", "ż", "c", "dz"):
            return s + "y"
        return s + "y"
    # dative / locative with consonant alternation
    for a, b in (("ka", "ce"), ("ga", "dze"), ("cha", "sze"), ("sta", "ście"), ("ta", "cie"),
                 ("da", "dzie"), ("ra", "rze"), ("ła", "le"), ("sa", "sie"), ("za", "zie"),
                 ("na", "nie"), ("wa", "wie"), ("ma", "mie"), ("ba", "bie"), ("pa", "pie"),
                 ("fa", "fie")):
        if stem_a.endswith(a):
            return stem_a[: -len(a)] + b
    if _ends(s, "cz", "sz", "rz", "ż", "c", "dz"):
        return s + "y"
    return s + "e"


def _male_first(name: str, case: str) -> str:
    if case == "nom":
        return name
    if name.endswith("y"):  # Ignacy, Cezary, Jerzy
        st = name[:-1]
        return {"gen": st + "ego", "acc": st + "ego", "dat": st + "emu", "ins": st + "ym"}[case]
    st = _MALE_STEM.get(name, name)
    if case in ("gen", "acc"):
        return st + "a"
    if case == "dat":
        return st + "owi"
    return st + ("iem" if _ends(st, "k", "g") else "em")


def _male_surname(sn: str, case: str) -> str | None:
    if case == "nom":
        return sn
    if _ends(sn, "ski", "cki", "dzki"):
        return sn[:-1] + {"gen": "iego", "acc": "iego", "dat": "iemu", "ins": "im"}[case]
    if sn.endswith("a"):  # Czajka, Sikora, Zaręba
        return _fem_noun(sn, case)
    if _ends(sn, "ień", "el", "ec", "ój"):  # mobile vowel - avoid
        return None
    st = sn[:-2] + "k" if (sn.endswith("ek") and len(sn) > 4) else sn
    if case in ("gen", "acc"):
        return st + "a"
    if case == "dat":
        return st + "owi"
    return st + ("iem" if _ends(st, "k", "g") else "em")


def _female_surname(sn: str, case: str) -> str | None:
    if case == "nom":
        return sn
    if _ends(sn, "ska", "cka", "dzka"):
        return sn[:-1] + {"gen": "iej", "dat": "iej", "acc": "ą", "ins": "ą"}[case]
    if sn.endswith("a"):
        return _fem_noun(sn, case)
    return sn  # consonant-final surnames do not decline for women


@dataclass
class Person:
    first: str
    last: str
    female: bool
    role: str | None = None  # function for signatories
    title: str | None = None  # 'rp' | 'adw' | None for attorneys
    bar_no: str | None = None
    pesel: str | None = None
    office: str | None = None
    email: str | None = None

    @property
    def full(self) -> str:
        return f"{self.first} {self.last}"

    def form(self, case: str = "nom", upper_last: bool = False, last_first: bool = False) -> str:
        """Name in grammatical case; falls back to nominative where unsure."""
        if self.female:
            f = _fem_noun(self.first, case) if self.first.endswith("a") else self.first
            l = _female_surname(self.last, case)
        else:
            f = _male_first(self.first, case)
            l = _male_surname(self.last, case)
        if l is None:
            f, l = self.first, self.last
        if upper_last:
            l = l.upper()
        return f"{l} {f}" if last_first else f"{f} {l}"

    def pan(self, case: str = "nom") -> str:
        if self.female:
            return {"nom": "Pani", "gen": "Pani", "dat": "Pani", "acc": "Panią", "ins": "Panią"}[case]
        return {"nom": "Pan", "gen": "Pana", "dat": "Panu", "acc": "Pana", "ins": "Panem"}[case]


def make_person(rng: random.Random, female: bool | None = None) -> Person:
    if female is None:
        female = rng.random() < 0.45
    first = rng.choice(FEMALE_FIRST if female else MALE_FIRST)
    sn = rng.choice(SURNAMES)
    if female and _ends(sn, "ski", "cki", "dzki"):
        sn = sn[:-1] + "a"
    return Person(first, sn, female)


TITLE_FORMS = {
    # title -> case -> list of variants (male, female share abbreviations)
    "rp": {
        "abbr": ["r. pr.", "r.pr.", "radca prawny", "r. pr."],
        "nom": ["radca prawny"],
        "gen": ["radcy prawnego"],
        "dat": ["radcy prawnemu"],
        "acc": ["radcę prawnego"],
        "ins": ["radcą prawnym"],
        "en": ["attorney-at-law (radca prawny)", "legal counsel"],
    },
    "adw": {
        "abbr": ["adw.", "adw.", "adwokat"],
        "nom": ["adwokat"],
        "gen": ["adwokata"],
        "dat": ["adwokatowi"],
        "acc": ["adwokata"],
        "ins": ["adwokatem"],
        "en": ["advocate (adwokat)", "attorney (adwokat)"],
    },
}


def title_str(rng: random.Random, p: Person, case: str = "abbr") -> str:
    """Title in a given case; '' when the attorney has no title."""
    if not p.title:
        return ""
    forms = TITLE_FORMS[p.title]
    if p.female and case in ("gen", "dat", "acc", "ins") and p.title == "adw":
        return "adwokat"  # 'Pani adwokat' does not decline
    return rng.choice(forms.get(case, forms["abbr"]))


def att_name(rng: random.Random, p: Person, case: str = "nom", with_title: bool = True, **kw) -> str:
    t = title_str(rng, p, "abbr" if case == "nom" else case) if with_title else ""
    n = p.form(case, **kw)
    return f"{t} {n}".strip()


# --------------------------------------------------------------------------------------
# Value formatting
# --------------------------------------------------------------------------------------

MONTHS_GEN = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia",
              "września", "października", "listopada", "grudnia"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def fmt_date(d: dt.date, style: str) -> str:
    return {
        "long": f"{d.day} {MONTHS_GEN[d.month-1]} {d.year}",
        "long_r": f"{d.day} {MONTHS_GEN[d.month-1]} {d.year} r.",
        "dots": f"{d.day:02d}.{d.month:02d}.{d.year}",
        "dots_r": f"{d.day:02d}.{d.month:02d}.{d.year} r.",
        "roman": f"{d.day} {ROMAN[d.month-1]} {d.year} r.",
        "roman_dots": f"{d.day}.{ROMAN[d.month-1]}.{d.year} r.",
        "iso": d.isoformat(),
        "en": f"{MONTHS_EN[d.month-1]} {d.day}, {d.year}",
        "en_uk": f"{d.day} {MONTHS_EN[d.month-1]} {d.year}",
    }[style]


def rand_date_style(rng: random.Random, english: bool = False) -> str:
    if english:
        return rng.choice(["en", "en_uk", "dots", "iso"])
    return rng.choice(["long", "long_r", "dots", "dots_r", "roman", "roman_dots", "iso", "long_r"])


def fmt_nip(nip: str, style: str) -> str:
    return {
        "plain": nip,
        "dash3322": f"{nip[:3]}-{nip[3:6]}-{nip[6:8]}-{nip[8:]}",
        "dash3223": f"{nip[:3]}-{nip[3:5]}-{nip[5:7]}-{nip[7:]}",
        "pl": f"PL{nip}",
        "pl_space": f"PL {nip}",
        "space3322": f"{nip[:3]} {nip[3:6]} {nip[6:8]} {nip[8:]}",
    }[style]


def rand_nip_style(rng: random.Random, allow_space: bool = False) -> str:
    opts = ["plain", "plain", "dash3322", "dash3223", "pl", "pl_space"]
    if allow_space:
        opts.append("space3322")
    return rng.choice(opts)


def fmt_krs(krs: str, style: str) -> str:
    return {"plain": krs, "space": f"{krs[:4]} {krs[4:7]} {krs[7:]}"}[style]


# --------------------------------------------------------------------------------------
# Pools from training ground truth
# --------------------------------------------------------------------------------------

CITIES = [
    ("Warszawa", "00-", "we Warszawie"), ("Kraków", "30-", "w Krakowie"), ("Łódź", "90-", "w Łodzi"),
    ("Wrocław", "50-", "we Wrocławiu"), ("Poznań", "60-", "w Poznaniu"), ("Gdańsk", "80-", "w Gdańsku"),
    ("Szczecin", "70-", "w Szczecinie"), ("Bydgoszcz", "85-", "w Bydgoszczy"), ("Lublin", "20-", "w Lublinie"),
    ("Katowice", "40-", "w Katowicach"), ("Białystok", "15-", "w Białymstoku"), ("Gdynia", "81-", "w Gdyni"),
    ("Toruń", "87-", "w Toruniu"), ("Rzeszów", "35-", "w Rzeszowie"), ("Kielce", "25-", "w Kielcach"),
    ("Olsztyn", "10-", "w Olsztynie"), ("Opole", "45-", "w Opolu"), ("Radom", "26-", "w Radomiu"),
    ("Zielona Góra", "65-", "w Zielonej Górze"), ("Płock", "09-", "w Płocku"),
]
STREETS = ["Przemysłowa", "Lipowa", "Legnicka", "Nadbystrzycka", "Kwiatowa", "Polna", "Słoneczna",
           "Długa", "Krótka", "Ogrodowa", "Kościuszki", "Mickiewicza", "Piłsudskiego", "Grunwaldzka",
           "Marszałkowska", "Zaczarowana", "Fabryczna", "Składowa", "Hallera", "Jagiellońska",
           "Al. Jerozolimskie", "Al. Solidarności", "Wojska Polskiego", "Sienkiewicza"]
SIGN_ROLES = ["Prezes Zarządu", "Wiceprezes Zarządu", "Członek Zarządu", "Prokurent",
              "Prokurent samoistny", "Wspólnik", "Komplementariusz", "Członek Zarządu",
              "Wspólnik uprawniony do reprezentacji", "Dyrektor Generalny"]
SIGN_ROLES_EN = {"Prezes Zarządu": "President of the Management Board",
                 "Wiceprezes Zarządu": "Vice-President of the Management Board",
                 "Członek Zarządu": "Member of the Management Board", "Prokurent": "Commercial Proxy",
                 "Prokurent samoistny": "Sole Commercial Proxy", "Wspólnik": "Partner",
                 "Komplementariusz": "General Partner",
                 "Wspólnik uprawniony do reprezentacji": "Authorised Partner",
                 "Dyrektor Generalny": "Managing Director"}
BRANDS = ["Belmoria", "Corvantis", "Wexford", "Quentavis", "Torvex", "Hydromel", "Elmontex",
          "Prestal", "Fendor", "Altrona", "Polvent", "Norvia", "Eltrona", "Helvix", "Nexalia",
          "Korvel", "Lumerio", "Aurelink", "Silvaro", "Tarvena", "Domilex", "Graviton", "Merkant",
          "Optivia", "Rastel", "Vendora", "Zentrix", "Kalmar", "Brontex", "Ravelo", "Bomark"]
INDUSTRIES = ["Rozwiązania", "Wyposażenie", "Usługi", "Budownictwo", "Instalacje", "Energetyka",
              "Dystrybucja Medyczna", "Farmacja", "Aparatura Medyczna", "Ciepłownictwo",
              "Instalacje Energetyczne", "Eko-Serwis", "Środowisko", "Serwis", "Facility",
              "Automatyka", "Systemy IT", "Infrastruktura", "Drogownictwo", "Logistyka", "Technologie"]
LEGAL_FORMS = ["sp. z o.o.", "S.A.", "sp. j.", "sp.j.", "sp.k.", "sp. z o.o. sp.k.", "Sp. z o.o.",
               "spółka z ograniczoną odpowiedzialnością", "spółka akcyjna", "P.S.A."]
TRADER_SUFFIX = ["BUD", "TECH", "SERWIS", "TRANS", "MED", "INSTAL", "EKO"]


def _rand_digits(rng: random.Random, n: int) -> str:
    return "".join(rng.choice(string.digits) for _ in range(n))


def synth_nip(rng: random.Random) -> str:
    w = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    while True:
        d = "999" + _rand_digits(rng, 6)
        c = sum(int(a) * b for a, b in zip(d, w)) % 11
        if c != 10:
            return d + str(c)


def synth_krs(rng: random.Random) -> str:
    return "999" + _rand_digits(rng, 7)


def synth_regon(rng: random.Random) -> str:
    return "999" + _rand_digits(rng, 6)


def synth_pesel(rng: random.Random, female: bool) -> str:
    y = rng.randint(1958, 1996)
    m = rng.randint(1, 12)
    d = rng.randint(1, 28)
    serial = rng.randint(0, 999)
    sex = rng.choice([0, 2, 4, 6, 8]) if female else rng.choice([1, 3, 5, 7, 9])
    base = f"{y % 100:02d}{m:02d}{d:02d}{serial:03d}{sex}"
    w = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    c = (10 - sum(int(a) * b for a, b in zip(base, w)) % 10) % 10
    return base + str(c)


@dataclass
class Pools:
    entities: list[dict]  # osoba_prawna: nazwa, krs, nip, regon
    traders: list[dict]  # osoba_fizyczna: nazwa, owner(first,last), nip
    procurements: list[dict]  # tytul, numer, zamawiajacy


_POOLS: Pools | None = None


def load_pools() -> Pools:
    global _POOLS
    if _POOLS is not None:
        return _POOLS
    regon: dict[str, str] = {}
    entities: dict[str, dict] = {}
    traders: list[dict] = []
    procs: list[dict] = []
    for f in sorted(glob.glob(str(TRAIN_DIR / "przyklad_*" / "odwolanie.json"))):
        d = json.load(open(f, encoding="utf-8"))
        for o in d.get("Odwolujacy") or []:
            if o.get("nip") and o.get("regon"):
                regon[o["nip"]] = o["regon"]
        zp = d.get("ZamowieniePubliczne") or {}
        zam = (d.get("Zamawiajacy") or [{}])[0]
        if zp.get("tytul") and zam.get("nazwa"):
            procs.append({"tytul": zp["tytul"], "numer": zp.get("numer_postepowania"),
                          "zamawiajacy": zam["nazwa"], "zam_nip": zam.get("nip")})
    for f in sorted(glob.glob(str(TRAIN_DIR / "przyklad_*" / "pelnomocnictwo.json"))):
        d = json.load(open(f, encoding="utf-8"))
        for m in d.get("mocodawca") or []:
            x = m["data"]
            if x["typ"] == "osoba_prawna" and x.get("krs") and x.get("nip"):
                entities[x["nip"]] = {"nazwa": x["nazwa"], "krs": x["krs"], "nip": x["nip"],
                                      "regon": regon.get(x["nip"])}
            elif x["typ"] == "osoba_fizyczna" and x.get("imie_nazwisko"):
                traders.append({"nazwa": x["nazwa"], "owner": x["imie_nazwisko"], "nip": x["nip"]})
    _POOLS = Pools(list(entities.values()), traders, procs)
    return _POOLS


# --------------------------------------------------------------------------------------
# Case sampling
# --------------------------------------------------------------------------------------

@dataclass
class Principal:
    typ: str  # osoba_prawna | osoba_fizyczna
    nazwa: str
    krs: str | None
    nip: str | None
    regon: str | None
    address: str
    city: str
    owner: Person | None = None  # for osoba_fizyczna
    signatories: list[Person] = field(default_factory=list)
    regon_shown: bool = True


@dataclass
class Case:
    principals: list[Principal]
    attorneys: list[Person]
    procurement: dict
    city: str
    city_loc: str
    date: dt.date
    kio_sygn: str | None
    consortium: bool

    def ground_truth(self) -> dict:
        moc = []
        for p in self.principals:
            moc.append({
                "data": {
                    "imie_nazwisko": p.owner.full if p.typ == "osoba_fizyczna" and p.owner else None,
                    "krs": p.krs,
                    "nazwa": p.nazwa,
                    "nip": p.nip,
                    "typ": p.typ,
                },
                "podpisujacy": [{"imie_nazwisko": s.full} for s in p.signatories],
            })
        pel = [{"imie_nazwisko": a.full, "pesel": a.pesel} for a in self.attorneys]
        return {"mocodawca": moc, "pelnomocnicy": pel}


def _address(rng: random.Random) -> tuple[str, str]:
    city, pc, _ = rng.choice(CITIES)
    st = rng.choice(STREETS)
    no = str(rng.randint(1, 180))
    if rng.random() < 0.25:
        no += f"/{rng.randint(1, 40)}"
    prefix = "" if st.startswith("Al.") else rng.choice(["ul. ", "ul. ", "ul. ", ""])
    return f"{prefix}{st} {no}, {pc}{rng.randint(1, 999):03d} {city}", city


def _synth_company_name(rng: random.Random) -> str:
    form = rng.choice(LEGAL_FORMS)
    ind = rng.choice(INDUSTRIES)
    brand = rng.choice(BRANDS)
    r = rng.random()
    if r < 0.15:
        return f"{brand.upper()} {form}"
    if r < 0.25:
        return f"„{brand} {ind}” {form}"
    return f"{brand} {ind} {form}"


def _principal_prawna(rng: random.Random, pools: Pools, p_hide_krs: float) -> Principal:
    if rng.random() < 0.5 and pools.entities:
        e = dict(rng.choice(pools.entities))
    else:
        e = {"nazwa": _synth_company_name(rng), "krs": synth_krs(rng), "nip": synth_nip(rng), "regon": None}
    addr, city = _address(rng)
    n_sig = rng.choices([1, 2, 3], [0.5, 0.42, 0.08])[0]
    sigs = []
    for i in range(n_sig):
        s = make_person(rng)
        s.role = rng.choice(SIGN_ROLES[:3] if i == 0 else SIGN_ROLES)
        sigs.append(s)
    krs = None if rng.random() < p_hide_krs else e["krs"]
    return Principal("osoba_prawna", e["nazwa"], krs, e["nip"], e.get("regon") or synth_regon(rng),
                     addr, city, None, sigs, regon_shown=rng.random() < 0.6)


def _principal_fizyczna(rng: random.Random, pools: Pools) -> Principal:
    if rng.random() < 0.3 and pools.traders:
        t = rng.choice(pools.traders)
        fn, ln = t["owner"].split(" ", 1)
        owner = Person(fn, ln, fn.endswith("a"))
        nazwa, nip = t["nazwa"], t["nip"]
    else:
        owner = make_person(rng)
        r = rng.random()
        if r < 0.5:
            nazwa = f"{rng.choice(BRANDS).upper()}-{rng.choice(TRADER_SUFFIX)} {owner.full}"
        elif r < 0.75:
            nazwa = f"{owner.full} {rng.choice(['Usługi Remontowo-Budowlane', 'Firma Handlowo-Usługowa', 'P.H.U.', 'Zakład Instalatorski'])}"
        else:
            nazwa = f"{rng.choice(['P.H.U.', 'F.H.U.', 'Przedsiębiorstwo Usługowe'])} „{rng.choice(BRANDS)}” {owner.full}"
        nip = synth_nip(rng)
    owner.role = rng.choice(["Właściciel", "Przedsiębiorca", None])
    addr, city = _address(rng)
    return Principal("osoba_fizyczna", nazwa, None, nip, synth_regon(rng), addr, city, owner, [owner],
                     regon_shown=rng.random() < 0.5)


def bar_number(rng: random.Random, title: str | None, city: str) -> str | None:
    code = {"Warszawa": "WA", "Kraków": "KR", "Łódź": "ŁD", "Wrocław": "WR", "Poznań": "PO",
            "Gdańsk": "GD", "Lublin": "LU", "Katowice": "KT", "Toruń": "TO"}.get(city, rng.choice(["WA", "KR", "GD", "PO"]))
    if title == "rp":
        return rng.choice([f"{code}-{rng.randint(1000, 9999)}", f"{code} {rng.randint(10000, 99999)}", f"{code}-{rng.randint(100, 9999)}"])
    if title == "adw":
        return rng.choice([f"{code}/Adw/{rng.randint(100, 9999)}", f"{code}/Adw/{rng.randint(100, 999)}"])
    return None


def sample_case(rng: random.Random, prefs: dict | None = None) -> Case:
    """Sample a recombined case. prefs keys: consortium, fizyczna, n_att weights,
    pesel, no_title, hide_krs, hide_nip, kio."""
    pr = {"consortium": 0.25, "fizyczna": 0.15, "n_att": [0.45, 0.42, 0.13], "pesel": 0.25,
          "no_title": 0.2, "hide_krs": 0.05, "hide_nip": 0.03, "kio": 0.35}
    pr.update(prefs or {})
    pools = load_pools()
    consortium = rng.random() < pr["consortium"]
    principals: list[Principal] = []
    n_p = 2 if consortium else 1
    for i in range(n_p):
        if rng.random() < pr["fizyczna"]:
            p = _principal_fizyczna(rng, pools)
        else:
            p = _principal_prawna(rng, pools, pr["hide_krs"])
        if rng.random() < pr["hide_nip"]:
            p.nip = None
        principals.append(p)
    # distinct principals
    if n_p == 2 and principals[0].nazwa == principals[1].nazwa:
        principals[1] = _principal_prawna(rng, pools, 0.0)
    city, _, city_loc = rng.choice(CITIES)
    n_att = rng.choices([1, 2, 3], pr["n_att"])[0]
    atts = []
    used = {s.full for p in principals for s in p.signatories}
    while len(atts) < n_att:
        a = make_person(rng)
        if a.full in used:
            continue
        used.add(a.full)
        a.title = None if rng.random() < pr["no_title"] else rng.choice(["rp", "rp", "adw"])
        a.bar_no = bar_number(rng, a.title, city) if rng.random() < 0.7 else None
        if rng.random() < pr["pesel"]:
            a.pesel = synth_pesel(rng, a.female)
        atts.append(a)
    proc = dict(rng.choice(pools.procurements))
    date = dt.date(2026, 1, 1) + dt.timedelta(days=rng.randint(0, 320))
    kio = None
    if rng.random() < pr["kio"]:
        kio = rng.choice(["KIO {n}/26", "KIO {n}/2026", "KIO {n}/26"]).format(n=rng.randint(100, 4800))
    return Case(principals, atts, proc, city, city_loc, date, kio, consortium)


# --------------------------------------------------------------------------------------
# Boilerplate text pools
# --------------------------------------------------------------------------------------

SCOPE_PL = [
    "wniesienia odwołania do Prezesa Krajowej Izby Odwoławczej oraz jego cofnięcia",
    "reprezentowania Mocodawcy na posiedzeniach i rozprawach przed Krajową Izbą Odwoławczą",
    "składania i odbierania pism procesowych, wniosków dowodowych i oświadczeń",
    "zawarcia ugody oraz zrzeczenia się roszczeń",
    "wniesienia skargi na orzeczenie Krajowej Izby Odwoławczej do sądu zamówień publicznych",
    "udzielania dalszych pełnomocnictw substytucyjnych radcom prawnym i adwokatom",
    "zgłaszania przystąpienia do postępowania odwoławczego",
    "składania oświadczeń o uwzględnieniu zarzutów lub ich cofnięciu",
    "odbioru orzeczeń i korespondencji Krajowej Izby Odwoławczej",
]
SCOPE_EN = [
    "file an appeal with the President of the National Appeal Chamber (KIO) and withdraw it",
    "represent the Principal at hearings and sessions before the National Appeal Chamber",
    "file and receive procedural pleadings, motions for evidence and statements",
    "lodge a complaint against the KIO ruling with the public procurement court",
    "grant further powers of attorney (substitution) to attorneys-at-law and advocates",
]
VALIDITY_PL = [
    "Pełnomocnictwo obowiązuje do prawomocnego zakończenia postępowania odwoławczego oraz skargowego.",
    "Pełnomocnictwo udzielone jest na czas nieokreślony i może być w każdym czasie odwołane.",
    "Pełnomocnictwo wygasa z chwilą zakończenia postępowania przed Krajową Izbą Odwoławczą.",
    "Niniejsze pełnomocnictwo obejmuje również postępowanie skargowe przed sądem okręgowym.",
]


def scope_items(rng: random.Random, english: bool = False, k: tuple[int, int] = (3, 5)) -> list[str]:
    pool = SCOPE_EN if english else SCOPE_PL
    n = min(len(pool), rng.randint(*k))
    return rng.sample(pool, n)


# --------------------------------------------------------------------------------------
# Fonts, styles, rendering
# --------------------------------------------------------------------------------------

_FONT_CANDIDATES = {
    "Carlito": ["/usr/share/fonts/truetype/crosextra/Carlito-{v}.ttf"],
    "DejaVuSans": ["/usr/share/fonts/truetype/dejavu/DejaVuSans{v}.ttf", "/Library/Fonts/DejaVuSans{v}.ttf"],
    "Arial": ["/System/Library/Fonts/Supplemental/Arial{v}.ttf", "/Library/Fonts/Arial{v}.ttf"],
    "TimesNewRoman": ["/System/Library/Fonts/Supplemental/Times New Roman{v}.ttf"],
    "Georgia": ["/System/Library/Fonts/Supplemental/Georgia{v}.ttf"],
    "Verdana": ["/System/Library/Fonts/Supplemental/Verdana{v}.ttf"],
    "CourierNew": ["/System/Library/Fonts/Supplemental/Courier New{v}.ttf"],
}
_VARIANTS = {
    "Carlito": {"": "Regular", "b": "Bold", "i": "Italic"},
    "DejaVuSans": {"": "", "b": "-Bold", "i": "-Oblique"},
}
_DEFAULT_VARIANTS = {"": "", "b": " Bold", "i": " Italic"}
_REGISTERED: list[str] | None = None


def available_fonts() -> list[str]:
    """Register every font family with Polish glyphs that exists on this machine."""
    global _REGISTERED
    if _REGISTERED is not None:
        return _REGISTERED
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping

    out = []
    for fam, pats in _FONT_CANDIDATES.items():
        var = _VARIANTS.get(fam, _DEFAULT_VARIANTS)
        for pat in pats:
            paths = {k: pat.format(v=v) for k, v in var.items()}
            if all(os.path.exists(p) for p in paths.values()):
                pdfmetrics.registerFont(TTFont(fam, paths[""]))
                pdfmetrics.registerFont(TTFont(fam + "-B", paths["b"]))
                pdfmetrics.registerFont(TTFont(fam + "-I", paths["i"]))
                addMapping(fam, 0, 0, fam)
                addMapping(fam, 1, 0, fam + "-B")
                addMapping(fam, 0, 1, fam + "-I")
                addMapping(fam, 1, 1, fam + "-B")
                out.append(fam)
                break
    if not out:
        raise RuntimeError("No TTF font with Polish glyphs found (need Carlito/DejaVu/Arial/...)")
    _REGISTERED = out
    return out


class Ctx:
    """Rendering context handed to template.build()."""

    def __init__(self, case: Case, rng: random.Random, font: str | None = None, base_size: float | None = None):
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
        self.case = case
        self.rng = rng
        fonts = available_fonts()
        self.font = font or rng.choice(fonts)
        self.bold = self.font + "-B"
        self.italic = self.font + "-I"
        sz = base_size or rng.choice([9.5, 10, 10.5, 11, 11.5])
        self.size = sz
        lead = sz * rng.uniform(1.25, 1.45)
        align = rng.choice([TA_JUSTIFY, TA_JUSTIFY, TA_LEFT])
        self.st = {
            "body": ParagraphStyle("body", fontName=self.font, fontSize=sz, leading=lead, alignment=align, spaceAfter=sz * 0.5),
            "left": ParagraphStyle("left", fontName=self.font, fontSize=sz, leading=lead, alignment=TA_LEFT),
            "right": ParagraphStyle("right", fontName=self.font, fontSize=sz, leading=lead, alignment=TA_RIGHT),
            "center": ParagraphStyle("center", fontName=self.font, fontSize=sz, leading=lead, alignment=TA_CENTER),
            "small": ParagraphStyle("small", fontName=self.font, fontSize=sz - 2, leading=(sz - 2) * 1.3, alignment=TA_LEFT),
            "title": ParagraphStyle("title", fontName=self.bold, fontSize=sz + rng.choice([4, 5, 6, 8]), leading=sz + 12,
                                    alignment=rng.choice([TA_CENTER, TA_CENTER, TA_LEFT]), spaceBefore=6, spaceAfter=10),
            "h": ParagraphStyle("h", fontName=self.bold, fontSize=sz + 0.5, leading=lead + 1, spaceBefore=sz * 0.6, spaceAfter=sz * 0.3),
            "cell": ParagraphStyle("cell", fontName=self.font, fontSize=sz - 0.5, leading=(sz - 0.5) * 1.25),
            "cellb": ParagraphStyle("cellb", fontName=self.bold, fontSize=sz - 0.5, leading=(sz - 0.5) * 1.25),
        }
        self.header: list[tuple[str, str]] = []  # (text, align) drawn on each page top
        self.footer: list[tuple[str, str]] = []
        self.pagesize = None
        self.margins: tuple[float, float, float, float] | None = None  # l, r, t, b in mm

    # paragraph helpers -------------------------------------------------------
    def P(self, text: str, style: str = "body", **kw):
        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import ParagraphStyle
        st = self.st[style]
        if kw:
            st = ParagraphStyle(style + "x", parent=st, **kw)
        return Paragraph(text, st)

    def sp(self, h: float = 6):
        from reportlab.platypus import Spacer
        return Spacer(1, h)

    def table(self, rows, col_widths=None, grid=True, header=False, zebra=False, pad=4, valign="TOP", box_only=False):
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        data = [[self.P(c, "cell") if isinstance(c, str) else c for c in r] for r in rows]
        t = Table(data, colWidths=col_widths, hAlign="LEFT")
        cmds = [("VALIGN", (0, 0), (-1, -1), valign), ("TOPPADDING", (0, 0), (-1, -1), pad),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad), ("LEFTPADDING", (0, 0), (-1, -1), pad + 1)]
        if grid:
            cmds.append(("GRID", (0, 0), (-1, -1), 0.5, colors.grey))
        elif box_only:
            cmds.append(("BOX", (0, 0), (-1, -1), 0.8, colors.black))
        if header:
            cmds.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e4e4e4")))
        if zebra:
            for i in range(1 if header else 0, len(rows), 2):
                cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f4f4f4")))
        t.setStyle(TableStyle(cmds))
        return t

    def hr(self, w: float = 0.6):
        from reportlab.platypus.flowables import HRFlowable
        return HRFlowable(width="100%", thickness=w, color="#444444", spaceBefore=3, spaceAfter=5)

    def sig_line(self) -> str:
        return self.rng.choice(["." * 44, "_" * 30, "…" * 18, "-" * 40, "/podpis/", "(podpis)",
                                "/-/ podpisano kwalifikowanym podpisem elektronicznym"])

    # value helpers -----------------------------------------------------------
    def nip(self, nip: str, style: str | None = None) -> str:
        return fmt_nip(nip, style or self.nip_style)

    @property
    def nip_style(self) -> str:
        if not hasattr(self, "_nip_style"):
            self._nip_style = rand_nip_style(self.rng)
        return self._nip_style

    def date(self, english: bool = False) -> str:
        if not hasattr(self, "_date_style"):
            self._date_style = rand_date_style(self.rng, english)
        return fmt_date(self.case.date, self._date_style)


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_pdf(build, case: Case, rng: random.Random, path: Path) -> dict:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate

    ctx = Ctx(case, rng)
    story = build(ctx)
    ps = ctx.pagesize or A4
    l, r, t, b = ctx.margins or (rng.uniform(18, 28), rng.uniform(16, 25), rng.uniform(16, 26), rng.uniform(16, 24))

    def on_page(canvas, doc):
        canvas.saveState()
        for i, (txt, al) in enumerate(ctx.header):
            canvas.setFont(ctx.font, ctx.size - 1.5)
            y = ps[1] - (t * mm) / 2 - i * (ctx.size)
            x = {"left": l * mm, "right": ps[0] - r * mm, "center": ps[0] / 2}[al]
            getattr(canvas, {"left": "drawString", "right": "drawRightString", "center": "drawCentredString"}[al])(x, y, txt)
        for i, (txt, al) in enumerate(ctx.footer):
            canvas.setFont(ctx.font, ctx.size - 2)
            y = (b * mm) / 2 - i * (ctx.size - 1)
            x = {"left": l * mm, "right": ps[0] - r * mm, "center": ps[0] / 2}[al]
            txt = txt.replace("{page}", str(doc.page))
            getattr(canvas, {"left": "drawString", "right": "drawRightString", "center": "drawCentredString"}[al])(x, y, txt)
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=ps, leftMargin=l * mm, rightMargin=r * mm,
                            topMargin=t * mm, bottomMargin=b * mm,
                            title=rng.choice(["", "Dokument", "skan", "Microsoft Word - dok1.docx"]),
                            author=rng.choice(["", "user", "Kancelaria"]), creator=rng.choice(["", "Microsoft Word", "LibreOffice"]))
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return {"font": ctx.font}


# --------------------------------------------------------------------------------------
# Template discovery
# --------------------------------------------------------------------------------------

def load_templates(split: str) -> list[Any]:
    d = DEV_TEMPLATE_DIR if split == "dev" else BLIND_TEMPLATE_DIR
    if not d.is_dir():
        raise FileNotFoundError(f"template dir missing: {d}")
    mods = []
    for f in sorted(d.glob("t*.py")):
        spec = importlib.util.spec_from_file_location(f"_pel_{split}_{f.stem}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mods.append(mod)
    if not mods:
        raise RuntimeError(f"no templates in {d}")
    return mods


def random_filename(rng: random.Random) -> str:
    r = rng.random()
    if r < 0.25:
        return "".join(rng.choice(string.ascii_lowercase + string.digits) for _ in range(12))
    if r < 0.45:
        return f"scan_{rng.randint(1, 99999):05d}"
    if r < 0.6:
        return f"IMG_{rng.randint(20260101, 20261130)}_{rng.randint(100000, 235959)}"
    if r < 0.75:
        return f"zalacznik_{rng.randint(1, 12)}_{rng.choice(string.ascii_lowercase)}{rng.randint(10, 99)}"
    if r < 0.88:
        return f"doc{rng.randint(1, 9999)}"
    return f"{rng.choice(['dokument', 'plik', 'attachment', 'skan'])}-{rng.randint(1000, 99999)}"


# --------------------------------------------------------------------------------------
# Small phrasing helpers shared by templates
# --------------------------------------------------------------------------------------

def id_parts(ctx: "Ctx", p: Principal, labels: tuple[str, str, str] = ("KRS", "NIP", "REGON"),
             regon: bool = True) -> list[str]:
    parts = []
    if p.krs:
        parts.append(f"{labels[0]} {p.krs}")
    if p.nip:
        parts.append(f"{labels[1]} {ctx.nip(p.nip)}")
    if regon and p.regon and p.regon_shown:
        parts.append(f"{labels[2]} {p.regon}")
    return parts


def plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def gend(p: Person, male: str, female: str) -> str:
    return female if p.female else male


def join_pl(items: list[str], last: str = " oraz ") -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + last + items[-1]
