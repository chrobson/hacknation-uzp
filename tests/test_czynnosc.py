"""Challenged act (czynność): dates of cited acts are not the act's date, petitum 'wnoszę o' is not the charge."""

from pathlib import Path

from odw.config import load_classes
from odw.pipeline import extract
from odw.textio import Document

CLS = {c.name: c for c in load_classes(Path(__file__).parents[1] / "config/classes")}["odwolanie"]
HEAD = ("Warszawa, 20 marca 2025 r.\nKrajowa Izba Odwoławcza\nul. Postępu 17a, 02-676 Warszawa\n\n"
        "Odwołujący:\nAlfa Budownictwo sp. z o.o.\nul. Prosta 5, 00-850 Warszawa\n\n"
        "Zamawiający:\nGmina Rudnik Wielki\nul. Rynek 1, 37-300 Rudnik\n\nODWOŁANIE\n")


def _kio(body: str) -> dict:
    return extract(Document(Path("a.pdf"), [HEAD + body]), CLS)["OdwolanieKIO"]


def test_statute_date_is_not_the_act_date():
    out = _kio("Na podstawie art. 513 ustawy z dnia 11 września 2019 r. Prawo zamówień publicznych wnoszę "
               "odwołanie od czynności Zamawiającego polegającej na wyborze oferty najkorzystniejszej.\n"
               "Informacja o wyborze została przekazana w dniu 14 marca 2025 r.\n")
    assert out["czynnosc_dzien"] == "2025-03-14"


def test_out_of_window_date_gives_null_not_statute():
    out = _kio("Na podstawie ustawy z dnia 23 kwietnia 1964 r. Kodeks cywilny wnoszę odwołanie od czynności "
               "Zamawiającego polegającej na wyborze oferty najkorzystniejszej.\n")
    assert out["czynnosc_dzien"] is None


def test_unlabelled_date_before_act_verb():
    out = _kio("Wnoszę odwołanie na czynność odtajnienia oferty.\nZamawiający 17.03.2025 r. poinformował Wykonawcę.\n")
    assert out["czynnosc_dzien"] == "2025-03-17"


def test_zaniechanie_czynnosci_odrzucenia_and_petitum_skipped():
    out = _kio("W związku z zarzutami wnoszę o uwzględnienie odwołania i nakazanie modyfikacji SWZ.\n"
               "Odwołujący zaskarża zaniechanie czynności odrzucenia oferty wykonawcy Beta.\n"
               "Zaskarżam zaniechanie czynności odrzucenia oferty wykonawcy Beta, o czym poinformowano w dniu "
               "14 marca 2025 r.\n")
    assert out["czynnosc_powod_id"] == 7


def test_projektowane_postanowienia_umowne():
    out = _kio("Wnoszę odwołanie wobec czynności polegającej na ustaleniu treści Specyfikacji Warunków Zamówienia, "
               "w tym wzoru umowy stanowiącego załącznik nr 4 do SWZ.\n")
    assert out["czynnosc_powod_id"] == 12
