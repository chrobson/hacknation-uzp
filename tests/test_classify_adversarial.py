"""P0-2..P0-4: documents that look like appeals/POAs but are not, and real ones with misleading headers."""

from pathlib import Path

import pytest

from odw.classify import classify
from odw.config import load_classes
from odw.textio import Document

CLASSES = load_classes()

PARTIES = """Prezes Krajowej Izby Odwoławczej
ul. Postępu 17A, 02-676 Warszawa
Odwołujący:
Alfa Budownictwo sp. z o.o.
KRS: 0000123456, NIP: 1234567890, REGON: 123456789
Zamawiający:
Gmina Beta
NIP: 9876543210, REGON: 987654321
"""

CASES = {
    "zgloszenie_przystapienia": (
        "Warszawa, dnia 3 marca 2026 r.\n" + PARTIES + """Przystępujący:
Gamma Serwis S.A.
ZGŁOSZENIE PRZYSTĄPIENIA
do postępowania odwoławczego po stronie Zamawiającego
Działając w imieniu Gamma Serwis S.A. zgłaszam przystąpienie do postępowania odwoławczego
wywołanego odwołaniem wniesionym przez Alfa Budownictwo sp. z o.o. w dniu 1 marca 2026 r.
Zarzuty odwołania są bezzasadne. Zarzut nr 1 dotyczący odrzucenia oferty nie zasługuje na uwzględnienie.""",
        None,
    ),
    "odpowiedz_na_odwolanie": (
        PARTIES + """ODPOWIEDŹ NA ODWOŁANIE
Zamawiający wnosi o oddalenie odwołania w całości. Zarzut nr 1 jest chybiony,
ponieważ Zamawiający w dniu 2 marca 2026 r. prawidłowo odrzucił ofertę Odwołującego.""",
        None,
    ),
    "wyrok_kio": (
        """Sygn. akt: KIO 123/26
WYROK
z dnia 20 marca 2026 r.
Krajowa Izba Odwoławcza - w składzie:
Przewodniczący: Jan Kowalski
po rozpoznaniu na rozprawie odwołania wniesionego przez Odwołującego. Zarzut nr 1 nie potwierdził się.
""" + PARTIES,
        None,
    ),
    "pelnomocnictwo_z_sygnatura": (
        """Sygn. akt KIO 123/26
PEŁNOMOCNICTWO
Alfa sp. z o.o., ul. Długa 1, 00-001 Warszawa, KRS 0000123456, NIP 1234567890,
udziela pełnomocnictwa adw. Janowi Nowakowi do reprezentowania Mocodawcy przed Krajową Izbą Odwoławczą.
............................................
Anna Kowalska
Prezes Zarządu""",
        "pelnomocnictwo",
    ),
    "odwolanie_z_sygnatura": (
        "Sygn. akt KIO 123/26\nWarszawa, dnia 3 marca 2026 r.\n" + PARTIES + """ODWOŁANIE
Działając w imieniu Odwołującego wnoszę odwołanie wobec czynności Zamawiającego.
Zamawiający w dniu 1 marca 2026 r. odrzucił ofertę Odwołującego.
Zarzut nr 1 – bezpodstawnego odrzucenia oferty Odwołującego.""",
        "odwolanie",
    ),
}


@pytest.mark.parametrize("name", CASES)
def test_adversarial_classification(name):
    text, expected = CASES[name]
    assert classify(Document(Path(f"{name}.pdf"), [text]), CLASSES).name == expected
