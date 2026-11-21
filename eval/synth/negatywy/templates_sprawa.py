"""Negative documents that typically sit in a KIO case folder next to the appeal (expected output {}).

Harder than templates_dev: each one is built around the vocabulary of ONE positive class (appeal wording, a power
of attorney clause, account numbers and fee amounts), so it checks the class thresholds and config/reject.yaml.
"""

from __future__ import annotations

from pathlib import Path

from eval.synth.common_negatywy import (
    Ctx, Doc, company_block, fmt_account, fmt_amount, fmt_date, fmt_nip, rand_date, rand_digits, title_prefix,
)
from eval.synth.negatywy.templates_dev import KIO_ADDR, argument, head, parties

UZP_ACC = "60 1010 1010 0081 3622 3100 0000"


def zawiadomienie_o_odwolaniu(c: Ctx, path: Path):
    """Zamawiający informs bidders that an appeal was filed and invites them to join (quotes the appeal)."""
    r = c.rng
    d = Doc(r)
    d.lines(company_block(c, c.zam), "small")
    d.para(f"{c.miasto}, {fmt_date(r, c.d)}", "right")
    d.para(f"Znak sprawy: {c.postep}")
    d.lines(["Wykonawcy biorący udział w postępowaniu", "(wszyscy wykonawcy)"], "right")
    d.h1(r.choice(["ZAWIADOMIENIE O WNIESIENIU ODWOŁANIA", "Informacja o wniesieniu odwołania\nwraz z wezwaniem do przystąpienia"]))
    d.para(f"Zamawiający – {c.zam.nazwa}, działając na podstawie art. 524 ustawy Pzp, informuje, że w dniu "
           f"{fmt_date(r, c.d)} wykonawca {c.wyk.nazwa} (Odwołujący) wniósł do Prezesa Krajowej Izby Odwoławczej "
           f"odwołanie wobec czynności Zamawiającego: {c.czynnosc.lower()} w postępowaniu pn. „{c.tytul}”.")
    d.para("Odwołujący zarzuca Zamawiającemu naruszenie:")
    d.lines([f"1) {argument(c, 1)[0]}", f"2) {argument(c, 1)[0]}"])
    d.para("Odwołujący wnosi o uwzględnienie odwołania i nakazanie Zamawiającemu powtórzenia czynności badania i oceny ofert.")
    d.para("Wykonawcy mogą zgłosić przystąpienie do postępowania odwoławczego w terminie 3 dni od dnia otrzymania kopii "
           "odwołania, wskazując stronę, do której przystępują, i interes w uzyskaniu rozstrzygnięcia.")
    d.para("W załączeniu: kopia odwołania.", "small")
    d.para(f"\n{c.osoba3}\nKierownik Zamawiającego", "right")
    d.build(path)


def cofniecie_odwolania(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    head(d, c, sygn_in_head=True)
    parties(d, c)
    d.h1(r.choice(["COFNIĘCIE ODWOŁANIA", "Oświadczenie o cofnięciu odwołania"]))
    d.para(f"Działając w imieniu Odwołującego – {c.wyk.nazwa}, na podstawie pełnomocnictwa znajdującego się w aktach "
           f"sprawy, oświadczam, że cofam w całości odwołanie wniesione w dniu {fmt_date(r, c.d)} wobec czynności "
           f"Zamawiającego w postępowaniu nr {c.postep} pn. „{c.tytul}”.")
    d.para("Jednocześnie wnoszę o umorzenie postępowania odwoławczego oraz o zwrot 90% kwoty uiszczonego wpisu "
           f"na rachunek Odwołującego nr {fmt_account(r, rand_digits(r, 26))} (art. 568 pkt 1 w zw. z § 9 rozporządzenia).")
    d.para(f"\n{title_prefix(r)}{c.osoba}\npełnomocnik Odwołującego", "right")
    d.build(path)


def uzupelnienie_brakow(c: Ctx, path: Path):
    """The appellant's letter answering a KIO call: mentions the power of attorney and the fee transfer."""
    r = c.rng
    d = Doc(r)
    head(d, c, sygn_in_head=r.random() < 0.7)
    d.lines(["Odwołujący:"] + company_block(c, c.wyk))
    d.h1(r.choice(["UZUPEŁNIENIE BRAKÓW FORMALNYCH ODWOŁANIA", "Pismo Odwołującego – wykonanie wezwania"]))
    kwota = r.choice([7500, 10000, 15000, 20000])
    d.para(f"W odpowiedzi na wezwanie Prezesa Krajowej Izby Odwoławczej z dnia {fmt_date(r, rand_date(r))}, działając "
           f"w imieniu Odwołującego, w załączeniu przedkładam:")
    d.lines(["1) pełnomocnictwo do reprezentowania Odwołującego udzielone przez członków zarządu ujawnionych w KRS,",
             f"2) dowód uiszczenia opłaty skarbowej od pełnomocnictwa w kwocie {fmt_amount(r, 17)},",
             f"3) potwierdzenie przelewu wpisu od odwołania w kwocie {fmt_amount(r, kwota)} na rachunek Urzędu "
             f"Zamówień Publicznych nr {UZP_ACC}, wykonanego w dniu {fmt_date(r, c.d)}."])
    d.para("Wnoszę o nadanie odwołaniu dalszego biegu.")
    d.para(f"\n{title_prefix(r)}{c.osoba}", "right")
    d.build(path)


def skarga_do_sadu(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    d.para(f"{c.miasto}, {fmt_date(r, c.d)}", "right")
    d.lines(["Sąd Okręgowy w Warszawie", "XXIII Wydział Gospodarczy Odwoławczy i Zamówień Publicznych",
             "za pośrednictwem Prezesa Krajowej Izby Odwoławczej"], "right")
    d.lines(["Skarżący:"] + company_block(c, c.wyk))
    d.lines(["Przeciwnik skargi:"] + company_block(c, c.zam))
    d.h1(f"SKARGA\nna wyrok Krajowej Izby Odwoławczej z dnia {fmt_date(r, rand_date(r))}, sygn. akt {c.sygn}")
    d.para("Działając w imieniu Skarżącego, zaskarżam powyższy wyrok w całości i zarzucam mu:")
    d.lines([f"1) {argument(c, 1)[0]}", f"2) {argument(c, 1)[0]}"])
    d.para("Wnoszę o zmianę zaskarżonego wyroku i uwzględnienie odwołania w całości oraz o zasądzenie kosztów postępowania.")
    d.para(f"Wartość przedmiotu zaskarżenia: {fmt_amount(r, r.choice([1200000, 3400000]))}. Opłata od skargi została "
           "uiszczona na rachunek Sądu Okręgowego w Warszawie.")
    d.para(f"\n{title_prefix(r)}{c.osoba}\npełnomocnik Skarżącego", "right")
    d.build(path)


def wniosek_uchylenie_zakazu(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    head(d, c, sygn_in_head=True)
    d.lines(["Zamawiający (Wnioskodawca):"] + company_block(c, c.zam))
    d.lines(["Odwołujący:"] + company_block(c, c.wyk))
    d.h1("WNIOSEK O UCHYLENIE ZAKAZU ZAWARCIA UMOWY")
    d.para(f"Na podstawie art. 578 ust. 1 ustawy Pzp Zamawiający wnosi o uchylenie zakazu zawarcia umowy w postępowaniu "
           f"pn. „{c.tytul}”, nr {c.postep}, do czasu ogłoszenia przez Izbę wyroku w sprawie odwołania wniesionego przez "
           f"{c.wyk.nazwa}.")
    d.para("Niezawarcie umowy mogłoby spowodować negatywne skutki dla interesu publicznego, przewyższające korzyści "
           "związane z koniecznością ochrony interesów wykonawców.")
    d.para(f"\n{c.osoba3}\n(Kierownik Zamawiającego)", "right")
    d.build(path)


def upo_wniesienia(c: Ctx, path: Path):
    """Urzędowe poświadczenie odbioru (ePUAP) of the appeal: names the appeal and its attachments."""
    r = c.rng
    d = Doc(r)
    d.h1("Urzędowe Poświadczenie Odbioru")
    d.lines([f"Identyfikator poświadczenia: {rand_digits(r, 6)}-{rand_digits(r, 4)}",
             f"Data i czas doręczenia: {fmt_date(r, c.d, 'iso')} {r.randint(8, 16):02d}:{r.randint(0, 59):02d}:{r.randint(0, 59):02d}",
             "Adresat: Urząd Zamówień Publicznych – Krajowa Izba Odwoławcza",
             f"Nadawca: {c.wyk.nazwa}, NIP {fmt_nip(r, c.wyk.nip)}",
             "Rodzaj dokumentu: Odwołanie",
             "Załączniki:", "  odwolanie.pdf", "  pelnomocnictwo.pdf", "  potwierdzenie_przelewu.pdf",
             f"Skrót dokumentu (SHA-256): {rand_digits(r, 32)}"])
    d.para("Poświadczenie zostało wygenerowane automatycznie przez Elektroniczną Platformę Usług Administracji Publicznej.", "small")
    d.build(path)


def zestawienie_oplat(c: Ctx, path: Path):
    """A firm's table of fees paid in the case: transfer-like vocabulary, several accounts and amounts."""
    r = c.rng
    d = Doc(r)
    d.para(c.kancelaria, "b")
    d.para(f"{c.miasto}, {fmt_date(r, c.d)}", "right")
    d.h1(f"Zestawienie kosztów sprawy {c.sygn}")
    rows = [("Wpis od odwołania", r.choice([7500, 10000, 15000]), UZP_ACC),
            ("Opłata skarbowa od pełnomocnictwa", 17, fmt_account(r, rand_digits(r, 26))),
            ("Wynagrodzenie pełnomocnika", 3600, fmt_account(r, rand_digits(r, 26)))]
    d.lines([f"{i + 1}. {n}: {fmt_amount(r, a)}, rachunek odbiorcy {acc}" for i, (n, a, acc) in enumerate(rows)])
    d.para(f"Razem: {fmt_amount(r, sum(a for _, a, _ in rows))}. Koszty podlegają zwrotowi od strony przegrywającej.")
    d.para(f"Sporządził: {c.osoba}", "small")
    d.build(path)


def nota_koszty(c: Ctx, path: Path):
    """Debit note for the costs of the appeal proceedings awarded by KIO (account + amount + title)."""
    r = c.rng
    d = Doc(r)
    d.lines(company_block(c, c.zam), "small")
    d.para(f"{c.miasto}, {fmt_date(r, c.d)}", "right")
    d.h1(f"NOTA OBCIĄŻENIOWA nr {r.randint(1, 99)}/{c.d.year}")
    d.lines(["Obciążony:"] + company_block(c, c.wyk))
    d.para(f"Na podstawie wyroku Krajowej Izby Odwoławczej z dnia {fmt_date(r, rand_date(r))}, sygn. akt {c.sygn}, "
           f"obciążamy Państwa kosztami postępowania odwoławczego w kwocie {fmt_amount(r, 3600)} tytułem "
           "wynagrodzenia pełnomocnika Zamawiającego.")
    d.para(f"Prosimy o przelew na rachunek nr {fmt_account(r, rand_digits(r, 26))} w terminie 14 dni, "
           "w tytule przelewu podając numer noty.")
    d.para(f"\n{c.osoba3}\nGłówny księgowy", "right")
    d.build(path)


def informacja_o_wyborze(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    d.lines(company_block(c, c.zam), "small")
    d.para(f"{c.miasto}, {fmt_date(r, c.d)}", "right")
    d.para(f"Znak sprawy: {c.postep}")
    d.h1("INFORMACJA O WYBORZE NAJKORZYSTNIEJSZEJ OFERTY")
    d.para(f"Zamawiający informuje, że w postępowaniu pn. „{c.tytul}” jako najkorzystniejszą wybrano ofertę wykonawcy "
           f"{c.wyk2.nazwa}, NIP {fmt_nip(r, c.wyk2.nip)}, z ceną {fmt_amount(r, r.choice([480000, 1250000]))} brutto.")
    d.para(f"Oferta wykonawcy {c.wyk.nazwa} uzyskała drugą pozycję w rankingu. Na czynności Zamawiającego przysługuje "
           "odwołanie do Prezesa Krajowej Izby Odwoławczej w terminie 10 dni od dnia przesłania niniejszej informacji.")
    d.para(f"\n{c.osoba3}", "right")
    d.build(path)


def protokol_posiedzenia(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    d.para(f"Sygn. akt: {c.sygn}", "b")
    d.h1("PROTOKÓŁ\nposiedzenia i rozprawy Krajowej Izby Odwoławczej")
    d.para(f"z dnia {fmt_date(r, rand_date(r))} r. w Warszawie, w sprawie z odwołania wykonawcy {c.wyk.nazwa} "
           f"przeciwko Zamawiającemu – {c.zam.nazwa}.")
    d.lines([f"Przewodniczący: {c.osoba3}", "Protokolant: " + r.choice(["Anna Wrona", "Piotr Lis", "Ewa Kos"]),
             f"Za Odwołującego: {title_prefix(r)}{c.osoba} – pełnomocnik (pełnomocnictwo w aktach)",
             f"Za Zamawiającego: {title_prefix(r)}{c.osoba2} – pełnomocnik"])
    d.para("Pełnomocnik Odwołującego podtrzymał odwołanie w całości. Pełnomocnik Zamawiającego wniósł o oddalenie odwołania. "
           "Izba zamknęła rozprawę i odroczyła ogłoszenie wyroku.")
    d.build(path, footer=KIO_ADDR.replace("\n", ", "))


TEMPLATES = {
    "zawiadomienie_o_odwolaniu": zawiadomienie_o_odwolaniu,
    "cofniecie_odwolania": cofniecie_odwolania,
    "uzupelnienie_brakow": uzupelnienie_brakow,
    "skarga_do_sadu": skarga_do_sadu,
    "wniosek_uchylenie_zakazu": wniosek_uchylenie_zakazu,
    "upo_wniesienia": upo_wniesienia,
    "zestawienie_oplat": zestawienie_oplat,
    "nota_koszty": nota_koszty,
    "informacja_o_wyborze": informacja_o_wyborze,
    "protokol_posiedzenia": protokol_posiedzenia,
}
