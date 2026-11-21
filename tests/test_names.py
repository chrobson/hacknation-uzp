import json
from pathlib import Path

import pytest

from odw.names import nominative, titlecase_upper


@pytest.mark.parametrize("declined,expected", [
    ("Ryszardowi Cieślakowi", "Ryszard Cieślak"), ("Aleksandrowi Jastrzębskiemu", "Aleksander Jastrzębski"),
    ("Grzegorza Furmana", "Grzegorz Furman"), ("Pana Grzegorza Furmana", "Grzegorz Furman"),
    ("Pawła Kowalskiego", "Paweł Kowalski"), ("Leszka Nowaka", "Leszek Nowak"), ("Aleksandra Marciniaka", "Aleksander Marciniak"),
    ("Patrycję Malinowską", "Patrycja Malinowska"), ("Annie Kowalskiej", "Anna Kowalska"), ("Panią Agnieszkę Nowak", "Agnieszka Nowak"),
])
def test_declined_to_nominative(declined, expected):
    assert nominative(declined) == expected


def test_every_nominative_name_in_train_ground_truth_is_unchanged():
    root = Path(__file__).resolve().parents[1] / "data" / "train"
    names = set()
    for f in root.glob("przyklad_*/*.json"):
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if k == "imie_nazwisko" and isinstance(v, str):
                        names.add(v)
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(json.loads(f.read_text(encoding="utf-8")))
    changed = {n: nominative(n) for n in names if nominative(n) != n}
    assert len(names) > 150 and not changed


def test_titlecase_upper():
    assert titlecase_upper("Halina ZIELIŃSKA") == "Halina Zielińska"
    assert titlecase_upper("Jan KOWALSKI-NOWAK") == "Jan Kowalski-Nowak"


def test_dictionary_nominative_and_rules_fallback(monkeypatch):
    """Morfeusz2 (SGJP), when installed, handles forms the rules miss; ODW_MORFEUSZ=0 / no package = rules only."""
    from odw import names

    assert names.nominative("Iwonę Zawadzką") == "Iwona Zawadzka"  # both paths
    assert names.nominative("Aleksandra Marciniak") == "Aleksandra Marciniak"  # a woman's name stays
    assert names.nominative("Panu Tomaszowi") == "Panu Tomaszowi"  # not a full name
    if names._morfeusz() is not None:
        assert names.nominative("Pawłem Wróblem") == "Paweł Wróbel"
    monkeypatch.setattr(names, "_morfeusz", lambda: None)
    assert names.nominative("Iwonę Zawadzką") == "Iwona Zawadzka"
