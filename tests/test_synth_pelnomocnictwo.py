"""Power-of-attorney layouts beyond the training template (invented names; layouts seen in synthetic data)."""

from pathlib import Path

from odw.classify import classify
from odw.config import load_classes
from odw.pipeline import extract
from odw.textio import Document

CLASSES = load_classes()
PEL = next(c for c in CLASSES if c.name == "pelnomocnictwo")


def run(text: str) -> dict:
    return extract(Document(path=Path("x.pdf"), pages=[text]), PEL)


def names(items: list[dict]) -> list[str]:
    return [i["imie_nazwisko"] for i in items]


FORM = """PEŁNOMOCNICTWO DO REPREZENTACJI W POSTĘPOWANIU ODWOŁAWCZYM
MOCODAWCA
Nazwa / firma Alfa Serwis S.A.
Numer KRS 9990000001
NIP 999-00-00-002
Reprezentowany przez Jan Nowak – Członek Zarządu
PEŁNOMOCNICY
Imię i nazwisko Ewa Lis
Tytuł zawodowy radca prawny
Imię i nazwisko Adam Kot
ZAKRES
Reprezentowanie Mocodawcy w postępowaniu, w tym do: zawarcia ugody.
............................................ /podpis/
Jan Nowak
(Alfa Serwis S.A.)
"""


def test_form_layout_representatives_and_signatory_without_company_name():
    out = run(FORM)
    assert names(out["pelnomocnicy"]) == ["Ewa Lis", "Adam Kot"]
    assert names(out["mocodawca"][0]["podpisujacy"]) == ["Jan Nowak"]
    assert out["mocodawca"][0]["data"]["nazwa"] == "Alfa Serwis S.A."


TABLE = """Łódź, 2026-11-15
PEŁNOMOCNICTWO
Beta Technologie S.A., ul. Polna 1, 00-001 Warszawa (KRS 9990000003, NIP PL
9990000004), reprezentowana przez: Piotr Wrona (Prezes Zarządu);
udziela pełnomocnictwa następującym osobom:
Lp. Imię i nazwisko Tytuł zawodowy Nr wpisu PESEL
1 Marek Sowa adwokat — 80010112345
2 Anna Mewa radca prawny WA-1 —
Pełnomocnictwo obejmuje reprezentację w postępowaniu.
Mocodawca Przyjęcie pełnomocnictwa
______________________________ (podpis)
Piotr Wrona Marek Sowa
Anna Mewa
"""


def test_table_rows_with_pesel_and_two_column_signatures():
    out = run(TABLE)
    assert out["pelnomocnicy"] == [{"imie_nazwisko": "Marek Sowa", "pesel": "80010112345"},
                                   {"imie_nazwisko": "Anna Mewa", "pesel": None}]
    assert names(out["mocodawca"][0]["podpisujacy"]) == ["Piotr Wrona"]  # representatives excluded
    assert out["mocodawca"][0]["data"]["nip"] == "9990000004"  # "NIP PL" + line break


CONSORTIUM = """PEŁNOMOCNICTWO
LIDER KONSORCJUM
KOWAL-BUD Jan Kowal
ul. Długa 2, 00-002 Kraków
NIP: 9990000005
w imieniu którego działa: Jan Kowal – Właściciel
PARTNER KONSORCJUM
„Gamma Usługi” S.A.
KRS: 9990000006
NIP: 9990000007
w imieniu którego działa: Olga Sęp – Członek Zarządu
Wykonawcy wspólnie ustanawiają pełnomocnikiem/pełnomocnikami:
• Ewa Lis – r. pr.
do reprezentowania wykonawców w postępowaniu.
Za lider konsorcjum:
………………………………………………
Jan Kowal
Za partner konsorcjum:
/podpis/
Olga Sęp
"""


def test_consortium_headings_split_items_sole_trader_and_quoted_name():
    out = run(CONSORTIUM)
    lider, partner = out["mocodawca"]
    assert lider["data"] == {"imie_nazwisko": "Jan Kowal", "krs": None, "nazwa": "KOWAL-BUD Jan Kowal",
                             "nip": "9990000005", "typ": "osoba_fizyczna"}
    assert partner["data"]["nazwa"] == "„Gamma Usługi” S.A."
    assert partner["data"]["typ"] == "osoba_prawna"
    assert names(lider["podpisujacy"]) == ["Jan Kowal"]
    assert names(partner["podpisujacy"]) == ["Olga Sęp"]
    assert names(out["pelnomocnicy"]) == ["Ewa Lis"]


def test_kio_header_letter_with_case_number_is_still_a_power_of_attorney():
    text = """Delta sp. j.
NIP: 999-000-00-08 | KRS: 9990000009
Sygn. akt: KIO 1/2026
Krajowa Izba Odwoławcza
PEŁNOMOCNICTWO PROCESOWE
Działając w imieniu Delta sp. j., niniejszym upoważniamy adwokat Ewę Lis do
reprezentowania przed Krajową Izbą Odwoławczą. Pełnomocnictwo obejmuje umocowanie do: odbioru orzeczeń.
/-/ podpisano kwalifikowanym podpisem elektronicznym
(Jan Nowak)
"""
    doc = Document(path=Path("x.pdf"), pages=[text])
    assert classify(doc, CLASSES).name == "pelnomocnictwo"
    assert names(run(text)["mocodawca"][0]["podpisujacy"]) == ["Jan Nowak"]
