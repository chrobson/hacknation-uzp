"""Odwołanie: the Odwołujący's representative (person, law firm, e-mail) in layouts seen in real filings."""

from pathlib import Path

import pytest

from odw.classify import classify
from odw.config import load_classes
from odw.fields import find_lawfirm
from odw.pipeline import extract
from odw.textio import Document

CLS = {c.name: c for c in load_classes()}
HEAD = "Gdańsk, 12.03.2026 r.\nPrezes Krajowej Izby Odwoławczej\nul. Postępu 17A, 02-676 Warszawa\n"
ZAM = "Zamawiający: Gmina Lipno, ul. Polna 1, 87-600 Lipno\nadres e-mail: a@lipno.example\n"
BODY = ("ODWOŁANIE\nDziałając w imieniu Odwołującego wnoszę odwołanie wobec czynności Zamawiającego polegających na:\n"
        "1) odrzuceniu oferty Odwołującego (02.03.2026 r.);\nZarzut nr 1 – naruszenia art. 226 Pzp.\n")


def rep(odw_block: str, tail: str = "") -> dict:
    doc = Document(Path("x.pdf"), [HEAD + odw_block + ZAM + BODY + tail])
    assert classify(doc, list(CLS.values())).name == "odwolanie"
    return extract(doc, CLS["odwolanie"])["Odwolujacy"][0]


def test_representative_label_on_its_own_line_with_title():
    r = rep("Odwołujący: Alfa sp. z o.o., ul. Leśna 2, 00-001 Warszawa\nPełnomocnik\n"
            "Imię i nazwisko: r.pr. Barbara Włodarczyk\nKancelaria: Kancelaria Radcy Prawnego Barbara Włodarczyk, "
            "ul. Kościuszki 91, 42-040 Rzeszów\nE-mail: kancelaria@wlodarczyk.example\n")
    assert r["pelnomocnik"]["imie_nazwisko"] == "Barbara Włodarczyk"
    assert r["pelnomocnik"]["nazwa"] == "Kancelaria Radcy Prawnego Barbara Włodarczyk"
    assert r["pelnomocnik"]["mail"] == "kancelaria@wlodarczyk.example"
    assert r["przez-pelnomocnika"] == 1


def test_przedstawiciel_label_and_mail_by_surname():
    r = rep("Odwołujący:\nImpel S.A.\nul. Słonimskiego 1; 50-304 Wrocław\nKRS 0000004185\n"
            "Adres poczty elektronicznej: a.pikon@impel.example\nPrzedstawiciel (imię i nazwisko): Angelika Pikoń\n")
    assert r["pelnomocnik"]["imie_nazwisko"] == "Angelika Pikoń"
    assert r["pelnomocnik"]["mail"] == "a.pikon@impel.example"
    assert r["przez-pelnomocnika"] == 1


def test_w_imieniu_ktorego_dziala_and_genitive_firm():
    r = rep("Odwołujący: P.U.H. ECO Jan Lis, ul. Kościuszki 65, 28-130 Stopnica\n"
            "w imieniu którego działa adwokat Karol Ziemba z Kancelarii Prawnej\n"
            "Jakóbik i Ziemba , 25-512 Kielce, ul. Warszawska 7/27A\nadres e-mail: Karol.Ziemba@kancelariajiz.example\n")
    assert r["pelnomocnik"]["imie_nazwisko"] == "Karol Ziemba"
    assert r["pelnomocnik"]["nazwa"] == "Kancelaria Prawna Jakóbik i Ziemba"
    assert r["pelnomocnik"]["mail"] == "Karol.Ziemba@kancelariajiz.example"


def test_declined_name_split_across_lines():
    r = rep("Odwołujący: Beta sp. z o.o., ul. Leśna 2, 00-001 Warszawa, reprezentowana przez pełnomocnika – "
            "radcę prawnego Cezarego\nBartoszewicza, z kancelarii działającej pod firmą Kancelaria Adwokacka\n"
            "Spółka z ograniczoną odpowiedzialnością (ul. Łąkowa 86/26, 77-318 Opole)\n")
    assert r["pelnomocnik"]["imie_nazwisko"] == "Cezary Bartoszewicz"
    assert r["pelnomocnik"]["nazwa"] == "Kancelaria Adwokacka Spółka z ograniczoną odpowiedzialnością"


def test_attachment_power_of_attorney_means_representative():
    r = rep("Odwołujący: Gamma sp. z o.o., ul. Leśna 2, 00-001 Warszawa\n",
            "w imieniu Odwołującego:\nZałączniki:\n1) odpis z KRS;\n2) Pełnomocnictwo i opłata skarbowa\n")
    assert r["przez-pelnomocnika"] == 1
    r = rep("Odwołujący: Gamma sp. z o.o., ul. Leśna 2, 00-001 Warszawa\n",
            "W imieniu Odwołującego:\nJan Lis — Wiceprezes Zarządu\nZałączniki:\n1. Pełnomocnictwo;\n")
    assert r["przez-pelnomocnika"] == 0


def test_costs_of_representation_are_not_a_representative():
    r = rep("Odwołujący: Delta sp. z o.o., ul. Leśna 2, 00-001 Warszawa\n",
            "Wnoszę o zasądzenie kosztów, w tym wynagrodzenia pełnomocnika.\n")
    assert r["przez-pelnomocnika"] == 0


@pytest.mark.parametrize("seg,expected", [
    (":\nAdamczyk, Saganowski Radcowie Prawni\nAl. Solidarności 113/57, 00-140 Warszawa\n", "Adamczyk, Saganowski Radcowie Prawni"),
    (": radcę prawnego Tomasza Srokosza\nadres dla doręczeń: Andersen Tax & Legal\nSrokosz i Wspólnicy Sp.k.\nul. Chorzowska 1",
     "Andersen Tax & Legal Srokosz i Wspólnicy Sp.k."),
    (" pełnomocnika:\nadwokata Michała Wojciechowskiego\nz kancelarii prawnej\nDomański Zakrzewski Palinka sp. k.\nadres do doręczeń:",
     "Domański Zakrzewski Palinka sp. k."),
    ("\nImię i nazwisko radca prawny Halina Walczak\nKancelaria Kancelaria Adwokacka i Partnerzy\nAdres ul. Marszałkowska 1",
     "Kancelaria Adwokacka i Partnerzy"),
    (" Odwołującego:\nr. pr. Katarzyna Michalak\nMichalak Legal Kancelaria Radcy Prawnego\nul. Jagiellońska 9",
     "Michalak Legal Kancelaria Radcy Prawnego"),
    (": Jan Kowalski – Prezes Zarządu\nZamawiający: Gmina", None),
])
def test_find_lawfirm(seg, expected):
    assert find_lawfirm(seg) == expected
