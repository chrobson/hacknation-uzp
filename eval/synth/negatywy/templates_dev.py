"""DEV templates of negative documents (expected output {}).

Each template: fn(c: Ctx, path: Path) -> None, renders one PDF. They deliberately reuse vocabulary of the
three positive classes (Odwołujący, Zamawiający, Krajowa Izba Odwoławcza, pełnomocnik, rachunek, kwota, NIP, KRS,
Sygn. akt, zarzut) so keyword classifiers are tempted. Blind templates live outside the repo.
"""

from __future__ import annotations

from pathlib import Path

from eval.synth.common_negatywy import (
    Ctx, Doc, address, company_block, fmt_account, fmt_amount, fmt_date, fmt_nip, rand_date, rand_digits,
    title_prefix,
)

KIO_ADDR = "Krajowa Izba Odwoławcza\nul. Postępu 17a\n02-676 Warszawa"

PRZEPISY = [
    "art. 16 pkt 1 ustawy Pzp", "art. 226 ust. 1 pkt 5 ustawy Pzp", "art. 224 ust. 6 ustawy Pzp",
    "art. 239 ust. 1 ustawy Pzp", "art. 109 ust. 1 pkt 8 ustawy Pzp", "art. 128 ust. 1 ustawy Pzp",
    "art. 253 ust. 1 ustawy Pzp", "art. 226 ust. 1 pkt 8 ustawy Pzp", "art. 99 ust. 4 ustawy Pzp",
]


def argument(c: Ctx, n: int = 3) -> list[str]:
    r = c.rng
    pool = [
        f"Zamawiający prawidłowo ocenił ofertę wykonawcy {c.wyk2.nazwa}, a twierdzenia Odwołującego o naruszeniu "
        f"{r.choice(PRZEPISY)} nie znajdują oparcia w dokumentacji postępowania.",
        "Wyjaśnienia złożone przez wykonawcę były wyczerpujące, poparte kalkulacją kosztów i dowodami, "
        "co wyklucza uznanie ceny oferty za rażąco niską.",
        f"Postanowienia Specyfikacji Warunków Zamówienia w zakresie warunku udziału w postępowaniu zostały "
        f"sformułowane jasno, a termin na ich zaskarżenie upłynął w dniu {fmt_date(r, rand_date(r))}.",
        "Okoliczność, na którą powołuje się Odwołujący, nie miała wpływu na wynik postępowania, "
        "wobec czego nawet ewentualne uchybienie nie mogłoby skutkować uwzględnieniem odwołania (art. 554 ust. 1 pkt 1 Pzp).",
        "Wykonawca wykazał doświadczenie w realizacji co najmniej dwóch dostaw o wartości nie mniejszej niż "
        f"{fmt_amount(r, r.choice([500000, 750000, 1200000]))} brutto każda, co potwierdzają złożone referencje.",
        "Zastrzeżenie tajemnicy przedsiębiorstwa zostało skutecznie uzasadnione, gdyż informacje mają wartość "
        "gospodarczą i podjęto działania w celu utrzymania ich w poufności.",
        f"Zarzut dotyczący czynności z dnia {fmt_date(r, c.d)} jest spóźniony, ponieważ termin na wniesienie odwołania "
        "wynosi 10 dni od dnia przesłania informacji przy użyciu środków komunikacji elektronicznej.",
        "Dowody przedstawione przez Odwołującego mają charakter wyłącznie polemiczny i nie podważają "
        "rzetelności oceny dokonanej przez komisję przetargową.",
        "Zgodnie z utrwalonym orzecznictwem Izby, ciężar dowodu spoczywa na stronie, która z danego faktu wywodzi skutki prawne (art. 534 ust. 1 Pzp).",
    ]
    r.shuffle(pool)
    return pool[:n]


def parties(d: Doc, c: Ctx, przystepujacy=False, sygn_first=True, label_style="colon"):
    r = c.rng

    def lab(t):
        return f"{t}:" if label_style == "colon" else t.upper()

    blocks = []
    blocks.append((lab("Odwołujący"), company_block(c, c.wyk) +
                   ([f"reprezentowany przez: {title_prefix(r)}{c.osoba}"] if r.random() < 0.5 else [])))
    blocks.append((lab("Zamawiający"), company_block(c, c.zam)))
    if przystepujacy:
        blocks.append((lab("Wykonawca zgłaszający przystąpienie"),
                       company_block(c, c.wyk2) + [f"reprezentowany przez pełnomocnika: {title_prefix(r)}{c.osoba2}",
                                                   f"adres do korespondencji: {c.mail}"]))
    if r.random() < 0.5:
        d.table([[a, "\n".join(b)] for a, b in blocks], widths=[150, 320], grid=False, style="p")
    else:
        for a, b in blocks:
            d.para(a, "b")
            d.lines(b)


def head(d: Doc, c: Ctx, sygn_in_head: bool):
    r = c.rng
    d.para(f"{c.miasto}, {fmt_date(r, c.d)}", "right")
    if sygn_in_head:
        d.para(f"Sygn. akt: {c.sygn}", "b")
    d.lines(KIO_ADDR.split("\n") if r.random() < 0.7 else ["Do Prezesa Krajowej Izby Odwoławczej"], "right")


# ---------------------------------------------------------------------------------------------- templates


def przystapienie(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    sy = r.random() < 0.5
    head(d, c, sygn_in_head=sy)
    parties(d, c, przystepujacy=True)
    if not sy:
        d.para(f"dot. odwołania o sygn. akt {c.sygn}")
    strona = r.choice(["Zamawiającego", "Odwołującego"])
    d.h1(r.choice(["PRZYSTĄPIENIE", "ZGŁOSZENIE PRZYSTĄPIENIA"]) + f"\ndo postępowania odwoławczego po stronie {strona}")
    d.para(f"Działając w imieniu wykonawcy {c.wyk2.nazwa}, na podstawie art. 525 ust. 1 ustawy z dnia 11 września 2019 r. "
           f"– Prawo zamówień publicznych, zgłaszam przystąpienie do postępowania odwoławczego wszczętego odwołaniem "
           f"wniesionym przez {c.wyk.nazwa} w dniu {fmt_date(r, c.d)} w postępowaniu o udzielenie zamówienia publicznego "
           f"pn. „{c.tytul}”, nr referencyjny {c.postep}, ogłoszonym w Biuletynie Zamówień Publicznych pod numerem {c.bzp}.")
    d.h2("Interes w przystąpieniu")
    if strona == "Zamawiającego":
        d.para(f"Oferta Przystępującego została uznana za najkorzystniejszą. Uwzględnienie odwołania prowadziłoby do "
               f"unieważnienia czynności: {c.czynnosc.lower()}, a w konsekwencji do pozbawienia Przystępującego możliwości "
               f"uzyskania zamówienia. Przystępujący ma zatem interes w rozstrzygnięciu na korzyść strony, do której przystępuje.")
        d.para("Przystępujący wnosi o oddalenie odwołania w całości oraz o dopuszczenie dowodów wskazanych w treści pisma.")
    else:
        d.para("Przystępujący złożył ofertę w postępowaniu i zajmuje kolejne miejsce w rankingu ofert. Uwzględnienie "
               "odwołania otworzy Przystępującemu drogę do uzyskania zamówienia, co przesądza o jego interesie.")
        d.para("Przystępujący popiera zarzuty i wnioski odwołania w całości i wnosi o jego uwzględnienie.")
    for a in argument(c, 2):
        d.para(a)
    d.para(f"Kopia przystąpienia została przekazana Zamawiającemu oraz Odwołującemu w dniu {fmt_date(r, c.d)} "
           f"drogą elektroniczną.")
    d.para("Załączniki:\n1. pełnomocnictwo,\n2. dowód przekazania kopii przystąpienia Zamawiającemu i Odwołującemu,\n"
           "3. odpis z KRS Przystępującego.", "small")
    d.para(f"\n………………………………\n{title_prefix(r)}{c.osoba2}", "right")
    d.build(path)


def odpowiedz_na_odwolanie(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    head(d, c, sygn_in_head=r.random() < 0.6)
    parties(d, c)
    d.h1("ODPOWIEDŹ NA ODWOŁANIE")
    d.para(f"Zamawiający – {c.zam.nazwa}, działając na podstawie art. 521 ustawy Pzp, w odpowiedzi na odwołanie "
           f"wniesione w dniu {fmt_date(r, c.d)} przez {c.wyk.nazwa} w postępowaniu nr {c.postep} pn. „{c.tytul}”, wnosi o:")
    d.lines(["1) oddalenie odwołania w całości,",
             "2) zasądzenie od Odwołującego na rzecz Zamawiającego kosztów postępowania odwoławczego, "
             f"w tym kosztów zastępstwa procesowego w kwocie {fmt_amount(r, 3600)},",
             "3) dopuszczenie dowodów z dokumentacji postępowania."])
    d.h2("Uzasadnienie")
    for i in range(1, r.randint(3, 4)):
        d.para(f"Ad. zarzutu nr {i}", "b")
        for a in argument(c, 2):
            d.para(a)
    d.para("Mając powyższe na uwadze, wnoszę jak na wstępie.")
    d.para(f"\nW imieniu Zamawiającego\n{title_prefix(r)}{c.osoba}\n(pełnomocnik Zamawiającego)", "right")
    d.build(path)


def pismo_procesowe(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    head(d, c, sygn_in_head=r.random() < 0.4)
    parties(d, c, przystepujacy=r.random() < 0.5)
    d.h1(r.choice(["PISMO PROCESOWE ODWOŁUJĄCEGO", "Pismo procesowe Odwołującego\nzawierające stanowisko w sprawie",
                   "DALSZE PISMO PROCESOWE"]))
    d.para(f"Działając w imieniu Odwołującego, w nawiązaniu do odpowiedzi na odwołanie z dnia {fmt_date(r, rand_date(r))} "
           f"oraz przystąpienia wykonawcy {c.wyk2.nazwa}, podtrzymuję wszystkie zarzuty i wnioski odwołania oraz "
           f"przedstawiam dodatkowe stanowisko i dowody.")
    for k in range(r.randint(2, 3)):
        d.h2(f"{['I', 'II', 'III'][k]}. " + r.choice(["Odnośnie zarzutu zaniechania odrzucenia oferty",
                                                       "Odnośnie rażąco niskiej ceny", "Odnośnie tajemnicy przedsiębiorstwa",
                                                       "Odnośnie argumentacji Przystępującego"]))
        for a in argument(c, 2):
            d.para(a.replace("Zamawiający prawidłowo", "Zamawiający nieprawidłowo"))
    d.h2("Wnioski dowodowe")
    d.lines([f"– opinia prywatna z dnia {fmt_date(r, rand_date(r))},", "– oferty cenowe podwykonawców,",
             "– korespondencja e-mail z dnia " + fmt_date(r, rand_date(r)) + "."])
    d.para(f"\n{title_prefix(r)}{c.osoba}\npełnomocnik Odwołującego", "right")
    d.build(path)


def wezwanie_kio_braki(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    d.para("PREZES\nKRAJOWEJ IZBY ODWOŁAWCZEJ", "b")
    d.para(f"Warszawa, dnia {fmt_date(r, c.d)}", "right")
    d.para(f"Sygn. akt {c.sygn}" if r.random() < 0.5 else f"Znak sprawy: KIO/W/{r.randint(100, 9999)}/26")
    d.lines([c.kancelaria, f"{title_prefix(r)}{c.osoba}", address(r, c.miasto), c.mail], "right")
    d.h1(r.choice(["WEZWANIE", "WEZWANIE DO UZUPEŁNIENIA BRAKÓW FORMALNYCH ODWOŁANIA"]))
    d.para(f"Prezes Krajowej Izby Odwoławczej, działając na podstawie art. 516 ust. 3 w zw. z art. 519 ust. 1 ustawy Pzp, "
           f"wzywa Odwołującego – {c.wyk.nazwa} (NIP {fmt_nip(r, c.wyk.nip)}) – do usunięcia braków formalnych odwołania "
           f"wniesionego w dniu {fmt_date(r, c.d)} w postępowaniu pn. „{c.tytul}” prowadzonym przez {c.zam.nazwa}, "
           f"w terminie 3 dni od dnia doręczenia wezwania, poprzez:")
    kwota = r.choice([7500, 10000, 15000, 20000])
    items = [
        "przedłożenie pełnomocnictwa do reprezentowania Odwołującego, udzielonego przez osoby uprawnione zgodnie "
        "z odpisem z Krajowego Rejestru Sądowego, wraz z dowodem uiszczenia opłaty skarbowej,",
        f"przedłożenie dowodu uiszczenia wpisu od odwołania w wysokości {fmt_amount(r, kwota)} na rachunek bankowy "
        f"Urzędu Zamówień Publicznych nr {fmt_account(r, c.rach)}, z podaniem w tytule przelewu nazwy Odwołującego "
        f"i numeru postępowania {c.postep},",
        "wskazanie numeru KRS albo numeru w innym właściwym rejestrze,",
        "przedłożenie dowodu przekazania kopii odwołania Zamawiającemu.",
    ]
    r.shuffle(items)
    d.lines([f"{i + 1}) {t}" for i, t in enumerate(items[:r.randint(2, 4)])])
    d.para("Nieusunięcie braków w wyznaczonym terminie skutkuje zwróceniem odwołania (art. 519 ust. 2 ustawy Pzp).")
    d.para(f"\nz up. Prezesa Krajowej Izby Odwoławczej\n{c.osoba3}\nStarszy specjalista", "right")
    d.build(path, footer="Urząd Zamówień Publicznych, ul. Postępu 17a, 02-676 Warszawa, tel. 22 458 77 01")


def wezwanie_zamawiajacego(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    d.lines(company_block(c, c.zam), "small")
    d.para(f"{c.miasto}, {fmt_date(r, c.d)}", "right")
    d.para(f"Znak sprawy: {c.postep}")
    d.lines(["Wykonawca:"] + company_block(c, c.wyk), "right")
    d.h1(r.choice(["Wezwanie do złożenia podmiotowych środków dowodowych",
                   "WEZWANIE DO UZUPEŁNIENIA DOKUMENTÓW", "Wezwanie do złożenia wyjaśnień"]))
    d.para(f"dotyczy: postępowania o udzielenie zamówienia publicznego pn. „{c.tytul}” (ogłoszenie nr {c.bzp})")
    d.para(f"Zamawiający, działając na podstawie {r.choice(['art. 126 ust. 1', 'art. 128 ust. 1', 'art. 223 ust. 1'])} "
           f"ustawy Pzp, wzywa Wykonawcę do złożenia/uzupełnienia następujących dokumentów w terminie do dnia "
           f"{fmt_date(r, rand_date(r))}, godz. {r.choice(['10:00', '12:00', '14:00'])}:")
    rows = [["Lp.", "Dokument", "Podstawa"],
            ["1", "Odpis lub informacja z Krajowego Rejestru Sądowego (KRS)", "Rozdział VIII pkt 2.1 SWZ"],
            ["2", "Pełnomocnictwo dla osoby podpisującej ofertę – brak umocowania w złożonych dokumentach", "art. 128 Pzp"],
            ["3", "Wykaz dostaw wraz z dowodami należytego wykonania", "Rozdział VIII pkt 2.4 SWZ"],
            ["4", "Zaświadczenie ZUS o niezaleganiu z opłacaniem składek", "§ 2 ust. 1 pkt 3 rozporządzenia"],
            ["5", "Dokument potwierdzający wniesienie wadium w kwocie " + fmt_amount(r, r.choice([5000, 12000, 30000])),
             "Rozdział XI SWZ"]]
    keep = [rows[0]] + r.sample(rows[1:], r.randint(2, 5))
    for i, row in enumerate(keep[1:], 1):
        row[0] = str(i)
    d.table(keep, widths=[30, 300, 140], header=True)
    d.para("Dokumenty należy złożyć za pośrednictwem Platformy e-Zamówienia, w formie elektronicznej lub w postaci "
           "elektronicznej opatrzonej podpisem zaufanym lub podpisem osobistym.")
    d.para("Pouczenie: na czynności Zamawiającego przysługują środki ochrony prawnej określone w Dziale IX ustawy Pzp, "
           "w tym odwołanie do Prezesa Krajowej Izby Odwoławczej.", "small")
    d.para(f"\n{c.osoba}\nKierownik Zamawiającego", "right")
    d.build(path)


def wyrok_kio(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    sygn_style = r.random()
    if sygn_style < 0.6:
        d.para(f"Sygn. akt: {c.sygn}", "b")
    d.h1("WYROK")
    d.para(f"z dnia {fmt_date(r, c.d, 'words_r')}", "center")
    if sygn_style >= 0.6:
        d.para(f"(sygn. akt {c.sygn})", "center")
    d.para("Krajowa Izba Odwoławcza – w składzie:")
    d.lines([f"Przewodniczący: {c.osoba3}", f"Protokolant: {c.osoba2}"])
    d.para(f"po rozpoznaniu na rozprawie w Warszawie w dniu {fmt_date(r, c.d, 'words_r')} odwołania wniesionego do Prezesa "
           f"Krajowej Izby Odwoławczej w dniu {fmt_date(r, rand_date(r), 'words_r')} przez wykonawcę {c.wyk.nazwa} "
           f"z siedzibą w {c.miasto} w postępowaniu prowadzonym przez Zamawiającego: {c.zam.nazwa}, przy udziale wykonawcy "
           f"{c.wyk2.nazwa} zgłaszającego przystąpienie do postępowania odwoławczego po stronie Zamawiającego,")
    d.para("orzeka:", "b")
    uwz = r.random() < 0.5
    kw = r.choice([7500, 10000, 15000, 20000])
    d.lines([("1. Uwzględnia odwołanie i nakazuje Zamawiającemu unieważnienie czynności wyboru najkorzystniejszej oferty "
              "oraz powtórzenie czynności badania i oceny ofert." if uwz else "1. Oddala odwołanie."),
             f"2. Kosztami postępowania obciąża {'Zamawiającego' if uwz else 'Odwołującego'} i:",
             f"2.1. zalicza w poczet kosztów postępowania odwoławczego kwotę {fmt_amount(r, kw)} "
             f"(słownie: {['siedem tysięcy pięćset', 'dziesięć tysięcy', 'piętnaście tysięcy', 'dwadzieścia tysięcy'][[7500, 10000, 15000, 20000].index(kw)]} złotych "
             "zero groszy) uiszczoną przez Odwołującego tytułem wpisu od odwołania,",
             f"2.2. zasądza od {'Zamawiającego na rzecz Odwołującego' if uwz else 'Odwołującego na rzecz Zamawiającego'} "
             f"kwotę {fmt_amount(r, kw + 3600)} tytułem zwrotu kosztów wpisu i wynagrodzenia pełnomocnika."])
    d.para("Stosownie do art. 579 ust. 1 i art. 580 ust. 1 i 2 ustawy Pzp na niniejszy wyrok – w terminie 14 dni od dnia "
           "jego doręczenia – przysługuje skarga za pośrednictwem Prezesa Krajowej Izby Odwoławczej do Sądu Okręgowego "
           "w Warszawie – sądu zamówień publicznych.", "small")
    d.para(f"Przewodniczący: ……………………", "right")
    d.pagebreak()
    if r.random() < 0.5:
        d.para(f"Sygn. akt: {c.sygn}", "b")
    d.h2("UZASADNIENIE")
    d.para(f"Zamawiający – {c.zam.nazwa} (NIP {fmt_nip(r, c.zam.nip)}) – prowadzi w trybie podstawowym postępowanie "
           f"o udzielenie zamówienia publicznego pn. „{c.tytul}”, nr referencyjny {c.postep}. Ogłoszenie o zamówieniu "
           f"zostało opublikowane w Biuletynie Zamówień Publicznych pod nr {c.bzp}.")
    d.para(f"Odwołujący wniósł odwołanie wobec czynności Zamawiającego: {c.czynnosc.lower()}, zarzucając naruszenie "
           f"{r.choice(PRZEPISY)} oraz {r.choice(PRZEPISY)}. Odwołujący wnosił o nakazanie Zamawiającemu powtórzenia "
           "czynności badania i oceny ofert.")
    d.para("Izba ustaliła i zważyła, co następuje:", "b")
    for a in argument(c, r.randint(4, 7)):
        d.para(a)
    d.para("Mając powyższe na uwadze, orzeczono jak w sentencji. O kosztach postępowania orzeczono stosownie do jego "
           "wyniku na podstawie art. 557 ustawy Pzp oraz rozporządzenia Prezesa Rady Ministrów z dnia 31 grudnia 2020 r.")
    d.build(path, header=f"Sygn. akt {c.sygn}" if r.random() < 0.3 else None)


def postanowienie_kio(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    d.para(f"Sygn. akt: {c.sygn}" if r.random() < 0.7 else f"{c.sygn}", "b")
    d.h1("POSTANOWIENIE")
    d.para(f"z dnia {fmt_date(r, c.d)}", "center")
    d.para(f"Krajowa Izba Odwoławcza w składzie: Przewodniczący: {c.osoba3}")
    kw = r.choice([7500, 10000, 15000, 20000])
    d.para(f"po rozpoznaniu na posiedzeniu niejawnym bez udziału stron w dniu {fmt_date(r, c.d)} w Warszawie odwołania "
           f"wniesionego przez wykonawcę {c.wyk.nazwa} (KRS {c.wyk.krs or rand_digits(r, 10)}) w postępowaniu prowadzonym "
           f"przez {c.zam.nazwa}, pn. „{c.tytul}”,")
    d.para("postanawia:", "b")
    powod = r.choice(["wycofania odwołania", "uwzględnienia przez Zamawiającego w całości zarzutów przedstawionych w odwołaniu"])
    d.lines([f"1. umorzyć postępowanie odwoławcze wobec {powod};",
             f"2. nakazać zwrot z rachunku bankowego Urzędu Zamówień Publicznych na rzecz Odwołującego kwoty "
             f"{fmt_amount(r, kw * (0.9 if 'wycof' in powod else 1.0))} uiszczonej tytułem wpisu od odwołania."])
    d.h2("Uzasadnienie")
    d.para(f"W dniu {fmt_date(r, rand_date(r))} do Prezesa Krajowej Izby Odwoławczej wpłynęło odwołanie, w którym "
           f"Odwołujący zarzucił Zamawiającemu naruszenie {r.choice(PRZEPISY)}. Odwołanie wniósł pełnomocnik "
           f"{title_prefix(r)}{c.osoba}, działający na podstawie pełnomocnictwa z dnia {fmt_date(r, rand_date(r))}.")
    d.para(f"Pismem z dnia {fmt_date(r, rand_date(r))} Odwołujący oświadczył, że "
           + ("cofa odwołanie." if 'wycof' in powod else "wobec uwzględnienia zarzutów nie podtrzymuje wniosków.")
           + " W tej sytuacji Izba umorzyła postępowanie na podstawie art. 568 pkt 1 ustawy Pzp.")
    d.para("Na niniejsze postanowienie przysługuje skarga do Sądu Okręgowego w Warszawie – sądu zamówień publicznych.", "small")
    d.para("Przewodniczący: ……………………", "right")
    d.build(path)


def faktura(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    nr = f"FV/{r.randint(1, 400)}/{c.d.month:02d}/{c.d.year}"
    d.h1(r.choice(["FAKTURA VAT", "Faktura", "FAKTURA nr " + nr]))
    d.table([["Numer faktury", nr], ["Data wystawienia", fmt_date(r, c.d)],
             ["Data sprzedaży", fmt_date(r, c.d)], ["Miejsce wystawienia", c.miasto]], widths=[140, 200], grid=False)
    sp = [c.kancelaria, address(r, c.miasto), f"NIP: {fmt_nip(r, rand_digits(r, 10))}"]
    nb = company_block(c, c.wyk)
    d.table([["Sprzedawca", "Nabywca"], ["\n".join(sp), "\n".join(nb)]], widths=[235, 235], header=True)
    net = r.choice([3000, 3600, 4500, 7200, 12000, 18500])
    vat = round(net * 0.23, 2)
    rows = [["Lp.", "Nazwa usługi", "Ilość", "Cena netto", "VAT", "Wartość brutto"],
            ["1", f"Zastępstwo procesowe przed Krajową Izbą Odwoławczą, sygn. akt {c.sygn} – postępowanie {c.postep}",
             "1", fmt_amount(r, net), "23%", fmt_amount(r, net + vat)]]
    if r.random() < 0.5:
        rows.append(["2", "Sporządzenie odwołania i pełnomocnictwa – zwrot kosztów opłaty skarbowej", "1",
                     fmt_amount(r, 17), "zw.", fmt_amount(r, 17)])
    d.table(rows, widths=[25, 205, 35, 70, 35, 100], header=True)
    tot = net + vat + (17 if len(rows) > 2 else 0)
    d.para(f"Razem do zapłaty: {fmt_amount(r, tot)}", "b")
    d.para(f"Sposób płatności: przelew, termin płatności: {fmt_date(r, rand_date(r))}")
    d.para(f"Numer rachunku: {fmt_account(r, c.rach)}")
    d.para(f"W tytule przelewu prosimy podać numer faktury: {nr}", "small")
    d.para("\nOsoba upoważniona do wystawienia faktury: " + c.osoba, "small")
    d.build(path)


def umowa_pomoc_prawna(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    d.h1(f"UMOWA O ŚWIADCZENIE POMOCY PRAWNEJ\nnr {r.randint(1, 99)}/{c.d.year}")
    d.para(f"zawarta w dniu {fmt_date(r, c.d)} w {c.miasto} pomiędzy:")
    d.lines(company_block(c, c.wyk) + [f"reprezentowaną przez {c.osoba2} – Prezesa Zarządu,",
                                       "zwaną dalej „Klientem”,"])
    d.para("a")
    d.lines([c.kancelaria, address(r, c.miasto), f"NIP {fmt_nip(r, rand_digits(r, 10))}",
             f"reprezentowaną przez {title_prefix(r)}{c.osoba}, zwaną dalej „Kancelarią”."])
    pars = [
        ("Przedmiot umowy", f"Klient zleca, a Kancelaria przyjmuje do prowadzenia sprawę dotyczącą postępowania o udzielenie "
                            f"zamówienia publicznego pn. „{c.tytul}” prowadzonego przez {c.zam.nazwa}, w tym przygotowanie "
                            f"i wniesienie odwołania do Prezesa Krajowej Izby Odwoławczej oraz reprezentację na rozprawie."),
        ("Pełnomocnictwo", "W celu wykonania umowy Klient udzieli wskazanym przez Kancelarię adwokatom i radcom prawnym "
                           "pełnomocnictwa procesowego w odrębnym dokumencie. Niniejsza umowa nie stanowi pełnomocnictwa."),
        ("Wynagrodzenie", f"Za wykonanie umowy Klient zapłaci Kancelarii wynagrodzenie ryczałtowe w kwocie "
                          f"{fmt_amount(r, r.choice([6000, 8000, 12000]))} netto, powiększone o podatek VAT, płatne przelewem "
                          f"na rachunek bankowy Kancelarii nr {fmt_account(r, c.rach)} w terminie 7 dni od daty doręczenia faktury."),
        ("Koszty", f"Wpis od odwołania w wysokości {fmt_amount(r, r.choice([7500, 10000, 15000, 20000]))} oraz opłatę "
                   "skarbową od pełnomocnictwa (17 zł) Klient uiszcza we własnym zakresie."),
        ("Poufność", "Kancelaria zobowiązuje się do zachowania w tajemnicy wszelkich informacji uzyskanych w związku z wykonywaniem umowy."),
        ("Postanowienia końcowe", "Zmiany umowy wymagają formy pisemnej pod rygorem nieważności. W sprawach nieuregulowanych "
                                  "stosuje się przepisy Kodeksu cywilnego."),
    ]
    for i, (t, body) in enumerate(pars, 1):
        d.para(f"§ {i}" + (f". {t}" if r.random() < 0.6 else ""), "center")
        d.para(body)
    d.table([["KLIENT", "KANCELARIA"], [f"\n\n……………………\n{c.osoba2}", f"\n\n……………………\n{c.osoba}"]],
            widths=[235, 235], grid=False, style="center")
    d.build(path)


def umowa_zamowienie(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    d.h1(f"UMOWA nr {c.postep}/U/{r.randint(1, 50)}")
    d.para(f"zawarta w dniu {fmt_date(r, c.d)} r. w {c.miasto} w wyniku przeprowadzenia postępowania o udzielenie "
           f"zamówienia publicznego w trybie podstawowym bez negocjacji (ogłoszenie nr {c.bzp}) pomiędzy:")
    d.para("Zamawiającym:", "b")
    d.lines(company_block(c, c.zam) + [f"reprezentowanym przez: {c.osoba3}"])
    d.para("a Wykonawcą:", "b")
    d.lines(company_block(c, c.wyk) + [f"reprezentowanym przez: {c.osoba2}"])
    wart = r.choice([186000, 420500, 999000, 1250000])
    pars = [f"Przedmiotem umowy jest: {c.tytul}, zgodnie z opisem przedmiotu zamówienia stanowiącym załącznik nr 1.",
            f"Wynagrodzenie Wykonawcy wynosi {fmt_amount(r, wart)} brutto. Zapłata nastąpi przelewem na rachunek "
            f"Wykonawcy nr {fmt_account(r, c.rach2)}, wskazany na fakturze, w terminie 30 dni.",
            "Wykonawca zapłaci Zamawiającemu karę umowną w wysokości 0,2% wynagrodzenia brutto za każdy dzień zwłoki.",
            f"Wykonawca wniósł zabezpieczenie należytego wykonania umowy w wysokości {fmt_amount(r, wart * 0.05)}.",
            "Zmiana umowy jest dopuszczalna w przypadkach określonych w art. 455 ustawy Pzp.",
            "Spory wynikłe z umowy rozstrzyga sąd właściwy dla siedziby Zamawiającego."]
    for i, p in enumerate(pars, 1):
        d.para(f"§ {i}", "center")
        d.para(p)
    d.table([["ZAMAWIAJĄCY", "WYKONAWCA"]], widths=[235, 235], grid=False, style="center")
    d.build(path)


def odpis_krs(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    comp = c.wyk if r.random() < 0.7 else c.wyk2
    krs = comp.krs or rand_digits(r, 10)
    d.para("CENTRALNA INFORMACJA KRAJOWEGO REJESTRU SĄDOWEGO", "center")
    d.h1("ODPIS AKTUALNY\nZ REJESTRU PRZEDSIĘBIORCÓW")
    d.para(f"Stan na dzień {fmt_date(r, c.d, 'dot')} godz. {r.randint(8, 20):02d}:{r.randint(0, 59):02d}:{r.randint(0, 59):02d}", "center")
    d.table([["Numer KRS:", krs], ["Data rejestracji w KRS:", fmt_date(r, rand_date(r, start=rand_date(r).replace(year=2012)), 'dot')],
             ["Ostatni wpis:", f"Nr wpisu {r.randint(5, 40)}, Data dokonania wpisu {fmt_date(r, rand_date(r), 'dot')}"],
             ["Sąd:", f"SĄD REJONOWY W {c.miasto.upper()}, WYDZIAŁ GOSPODARCZY KRAJOWEGO REJESTRU SĄDOWEGO"]],
            widths=[150, 320], grid=False)
    d.h2("Dział 1")
    d.table([["Rubryka 1 – Dane podmiotu", ""],
             ["1. Oznaczenie formy prawnej", "SPÓŁKA AKCYJNA" if "S.A." in comp.nazwa else "SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ"],
             ["2. Numer REGON/NIP", f"REGON: {comp.regon or rand_digits(r, 9)}, NIP: {comp.nip or rand_digits(r, 10)}"],
             ["3. Firma, pod którą spółka działa", comp.nazwa.upper()],
             ["Rubryka 2 – Siedziba i adres", ""],
             ["1. Siedziba", f"kraj POLSKA, woj. —, miejsc. {c.miasto.upper()}"],
             ["2. Adres", address(r, c.miasto).upper()]], widths=[200, 270])
    d.h2("Dział 2")
    d.table([["Rubryka 1 – Organ uprawniony do reprezentacji", ""],
             ["1. Nazwa organu", "ZARZĄD"],
             ["2. Sposób reprezentacji", r.choice(["DO REPREZENTOWANIA SPÓŁKI UPRAWNIONY JEST PREZES ZARZĄDU SAMODZIELNIE.",
                                                   "DWÓCH CZŁONKÓW ZARZĄDU ŁĄCZNIE ALBO CZŁONEK ZARZĄDU ŁĄCZNIE Z PROKURENTEM."])],
             ["Skład organu", ""],
             ["1. Nazwisko / Imiona", c.osoba2.split()[-1].upper() + " / " + c.osoba2.split()[0].upper()],
             ["2. Funkcja", "PREZES ZARZĄDU"],
             ["1. Nazwisko / Imiona", c.osoba3.split()[-1].upper() + " / " + c.osoba3.split()[0].upper()],
             ["2. Funkcja", "CZŁONEK ZARZĄDU"],
             ["Rubryka 4 – Prokurenci", ""],
             ["1. Nazwisko / Imiona", c.osoba.split()[-1].upper() + " / " + c.osoba.split()[0].upper()],
             ["2. Rodzaj prokury", "PROKURA SAMOISTNA"]], widths=[200, 270])
    d.h2("Dział 3")
    d.table([["Rubryka 1 – Przedmiot działalności", ""],
             ["1. Przedmiot przeważającej działalności", f"{r.choice(['62, 01, Z', '46, 51, Z', '71, 12, Z'])}, DZIAŁALNOŚĆ ZWIĄZANA Z OPROGRAMOWANIEM"]],
             widths=[200, 270])
    d.para(f"Data wygenerowania wydruku: {fmt_date(r, c.d, 'dot')}. Odpis pobrany na podstawie art. 4 ust. 4aa ustawy "
           "o Krajowym Rejestrze Sądowym ma moc dokumentu urzędowego.", "small")
    d.build(path, page_numbers=True, footer=f"KRS {krs}")


def ogloszenie_bzp(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    nr = c.bzp.split("/")[-1].replace("BZP", "BZP ") if r.random() < 0.5 else c.bzp
    d.para(f"Ogłoszenie nr {c.bzp.replace('/', ' / ') if r.random() < 0.5 else c.bzp} z dnia {c.d.isoformat()}", "b")
    d.h1(r.choice(["Ogłoszenie o zamówieniu\nUsługi", "Ogłoszenie o zamówieniu\nDostawy", "Ogłoszenie o wyniku postępowania\nDostawy"]))
    d.para(c.tytul, "b")
    d.h2("SEKCJA I – ZAMAWIAJĄCY")
    d.lines(["1.1.) Rola zamawiającego", "Postępowanie prowadzone jest samodzielnie przez zamawiającego",
             f"1.2.) Nazwa zamawiającego: {c.zam.nazwa}",
             f"1.4) Krajowy Numer Identyfikacyjny: REGON {c.zam.regon or rand_digits(r, 9)}",
             f"1.5) Adres zamawiającego: {address(r, c.miasto)}",
             f"1.5.9.) Adres poczty elektronicznej: zamowienia@{r.choice(['gmina', 'szpital', 'zgk', 'mpk'])}.example",
             "1.6.) Rodzaj zamawiającego: " + r.choice(["Zamawiający publiczny – jednostka sektora finansów publicznych",
                                                        "Zamawiający publiczny – spółka prawa handlowego"])])
    d.h2("SEKCJA II – INFORMACJE PODSTAWOWE")
    d.lines([f"2.1.) Ogłoszenie dotyczy: Zamówienia publicznego", f"2.2.) Ogłoszenie zawiera informacje: {nr}",
             f"2.3.) Nazwa zamówienia albo umowy ramowej: {c.tytul}",
             f"2.5.) Numer ogłoszenia: {c.bzp}", f"2.7.) Identyfikator postępowania: ocds-148610-{rand_digits(r, 8)}",
             f"2.8.) Numer referencyjny postępowania: {c.postep}"])
    d.h2("SEKCJA III – UDOSTĘPNIANIE DOKUMENTÓW ZAMÓWIENIA I KOMUNIKACJA")
    d.para("3.1.) Adres strony internetowej prowadzonego postępowania: https://ezamowienia.gov.pl/mp-client/search/list/"
           f"ocds-148610-{rand_digits(r, 8)}")
    d.h2("SEKCJA VIII – PROCEDURA")
    d.lines([f"8.1.) Termin składania ofert: {c.d.isoformat()} {r.choice(['10:00', '11:00', '12:00'])}",
             f"8.4.) Termin otwarcia ofert: {c.d.isoformat()} {r.choice(['10:30', '11:30', '12:30'])}",
             f"8.5.) Wadium: {fmt_amount(r, r.choice([5000, 10000, 25000]))}",
             "8.8.) Środki ochrony prawnej: Odwołanie wnosi się do Prezesa Krajowej Izby Odwoławczej."])
    d.build(path, page_numbers=True)


def wyciag_swz(c: Ctx, path: Path):
    r = c.rng
    d = Doc(r)
    d.para(f"Znak sprawy: {c.postep}", "right")
    d.h1(f"SPECYFIKACJA WARUNKÓW ZAMÓWIENIA\n(wyciąg)")
    d.para(f"Zamawiający: {c.zam.nazwa}, {address(r, c.miasto)}, NIP {fmt_nip(r, c.zam.nip)}")
    d.para(f"Nazwa postępowania: {c.tytul}")
    rozd = [
        ("Rozdział VI. Warunki udziału w postępowaniu",
         "O udzielenie zamówienia mogą ubiegać się wykonawcy, którzy w okresie ostatnich trzech lat wykonali co najmniej "
         f"dwie dostawy o wartości nie mniejszej niż {fmt_amount(r, 300000)} brutto każda."),
        ("Rozdział IX. Pełnomocnictwa",
         "Jeżeli w imieniu wykonawcy działa osoba, której umocowanie nie wynika z odpisu z KRS, wykonawca składa wraz "
         "z ofertą pełnomocnictwo w formie elektronicznej. Wykonawcy wspólnie ubiegający się o zamówienie ustanawiają "
         "pełnomocnika do reprezentowania ich w postępowaniu."),
        ("Rozdział XI. Wadium",
         f"Wadium w wysokości {fmt_amount(r, r.choice([5000, 15000]))} wnosi się przelewem na rachunek Zamawiającego "
         f"nr {fmt_account(r, c.rach)} z dopiskiem w tytule: „Wadium – {c.postep}”."),
        ("Rozdział XXII. Pouczenie o środkach ochrony prawnej",
         "Odwołanie przysługuje na niezgodną z przepisami ustawy czynność Zamawiającego. Odwołanie wnosi się do Prezesa "
         "Krajowej Izby Odwoławczej w terminie 10 dni od dnia przesłania informacji o czynności Zamawiającego. "
         "Odwołujący przekazuje kopię odwołania Zamawiającemu przed upływem terminu do wniesienia odwołania."),
    ]
    if r.random() < 0.5:
        r.shuffle(rozd)
    for t, b in rozd:
        d.h2(t)
        d.para(b)
    d.build(path, page_numbers=True)


TEMPLATES = {
    "przystapienie": przystapienie,
    "odpowiedz_na_odwolanie": odpowiedz_na_odwolanie,
    "pismo_procesowe": pismo_procesowe,
    "wezwanie_kio_braki": wezwanie_kio_braki,
    "wezwanie_zamawiajacego": wezwanie_zamawiajacego,
    "wyrok_kio": wyrok_kio,
    "postanowienie_kio": postanowienie_kio,
    "faktura": faktura,
    "umowa_pomoc_prawna": umowa_pomoc_prawna,
    "umowa_zamowienie": umowa_zamowienie,
    "odpis_krs": odpis_krs,
    "ogloszenie_bzp": ogloszenie_bzp,
    "wyciag_swz": wyciag_swz,
}
