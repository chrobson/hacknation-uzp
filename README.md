# Odwołania2JSON (HackNation 2026, zadanie UZP)

> Automatyczna zamiana dokumentów PDF ze spraw odwoławczych KIO na kanoniczny model JSON.
> Partner: **Urząd Zamówień Publicznych**. Nagroda: **20 000 zł brutto** (jedna, dla zwycięzcy).
> Źródło zadania: https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026

## Podsumowanie zadania

Aplikacja przyjmuje dokumenty PDF składające się na sprawę odwoławczą:
- **odwołanie**,
- **pełnomocnictwo** (jedno lub więcej),
- **potwierdzenie przelewu** (wpis lub opłata skarbowa).

Dla każdego dokumentu:
1. rozpoznaje jego rodzaj,
2. wyodrębnia informacje biznesowe,
3. zapisuje JSON zgodny ze specyfikacją w `docs/spec/*.json`.

Dokumenty, które nie należą do żadnej z obsługiwanych klas (np. ogłoszenie TED w `docs/spec/szablon-aplikacja/input/case1/negatywny przyklad.pdf`), muszą zostać odrzucone.

## ⚠️ Aktualizacje 21.11 (Discord, FAQ UZP v1.0, zmiany README w repo UZP o 12:06 i 12:14)

| Temat | Ustalenie |
|---|---|
| **LLM** | Tylko modele **open source / open-weight**, które da się też zainstalować lokalnie. W trakcie hackathonu UZP **poleca korzystać z nich przez API**. Dostawca API musi być **firmą z serwerami w UE/EOG**. Dopuszczalne: (1) darmowe API z modelami OSS, (2) model wystawiony na własnym sprzęcie i udostępniony przez API, (3) płatne API z modelami OSS. |
| **Klucz API** | Rozwiązanie musi zawierać **klucz API** do użytej usługi (UZP obiecuje używać go tylko do testów). Opis użytego LLM musi być w dokumentacji technicznej. |
| **Maszyna testowa** | laptop biurowy, **16 GB RAM, Intel i7, bez GPU**. Duży model lokalny = duże ryzyko. |
| **Finał: 50% „elastyczność”** (stan README 12:14) | **1–20 pkt za „moc” modelu LLM: im MNIEJSZY model, tym WIĘCEJ punktów** + **1–20 pkt** łatwość dodawania nowych typów dokumentów i pól bez przebudowy + **1–10 pkt inne ciekawe funkcje (np. GUI)**. |
| **Dokumenty obce** | Zbiór zawiera kategorie dokumentów, które **NIE powinny być zidentyfikowane: dla nich zwrócić PUSTY plik `.json`** (nie pomijać pliku!). Szablon ma plik 0 B; dopytać, czy `{}` też jest OK. |
| **Prawdziwe dane = skany** | `docs/spec/szablon-aplikacja/input/case1/przyklad odwolanie.pdf` to **skan**: 7 stron JPEG 96 ppi, zero warstwy tekstowej, zaczernienia anonimizacji. Wszystkie 180 PDF-ów w `data/train` to tekstowe dokumenty syntetyczne. **OCR = P0**, a regexy dopasowane do syntetycznego szablonu mogą nie przenieść się na realne sprawy. |
| **Skany** | **Trzeba obsłużyć skany (OCR).** Występują w realnym problemie. |
| **Braki danych** | Niczego nie wymyślać; `null` tam, gdzie schemat dopuszcza brak wartości. |
| **CLI** | **Obowiązkowe**, z instrukcją uruchomienia. |
| **GUI** | Nieobowiązkowe, **dodatkowo punktowane (część z 1–10 pkt)**, ale „istotniejsza jest skuteczność identyfikacji informacji”. Ideał: wgranie PDF → analiza → podgląd JSON, widok obok siebie. |
| **Dane testowe** | Osobny, nieudostępniony zbiór; **wgląd w te dane jest możliwy na stoisku UZP**. FAQ mówi o 39 zestawach i `ground_truth.yaml`; w repo jest obecnie 60 przykładów i brak `ground_truth.yaml` (sprawdzić na stoisku). |

### Jak liczone jest F1 (odpowiedź UZP na Discordzie)
- **TP:** wartość jest w JSON i zgadza się z ground truth. **Długie stringi (np. nazwy firm): wystarczy ≥80% zgodności.**
- **TN:** wartości nie ma ani w JSON, ani w ground truth.
- **FP:** wartość jest tylko w JSON **albo** jest w obu, ale nieprawidłowa.
- **FN:** wartości nie ma w JSON, a jest w ground truth.

**Wnioski dla strategii:**
1. **Gdy pole istnieje w ground truth, zła wartość (FP) i `null` (FN) kosztują w F1 tyle samo**, bo F1 = 2TP/(2TP+FP+FN). Trafienie daje TP, więc **opłaca się podać wartość, gdy szansa trafienia jest rozsądna** (przy F1 ≈ 0,9 mniej więcej powyżej ~45%). Próg kalibrować na holdoucie.
2. **Gdy pola NIE ma w ground truth, każda wpisana wartość to czysty FP**, a `null` to TN, które nie obniża F1. Halucynacje są karane, więc wartość zwracamy tylko z dowodem w tekście (evidence).
3. **Nazwy firm: tolerancja 80%,** więc drobne różnice (cudzysłowy, „sp. z o.o.” vs „Sp. z o.o.”) nie zabijają wyniku, ale normalizacja i tak się opłaca.
4. **Mały model = punkty w finale.** Maksymalnie regexy i reguły; LLM jak najmniejszy (np. 3–8B open-weight) i tylko do pól semantycznych. Dopytać na stoisku, ile punktów dostaje rozwiązanie **bez LLM** albo z modelem <3B.
5. **OCR jest obowiązkowy i krytyczny** (przykład realnej sprawy to skan 96 ppi): tesseract z językiem `pol` (**w systemie brak, trzeba doinstalować `brew install tesseract-lang`**), wykrycie braku warstwy tekstowej, ewentualnie upscaling obrazu przed OCR. Ekstrakcja musi być odporna na błędy OCR (fuzzy etykiety, walidacja sum kontrolnych).
7. **Dokument obcy → pusty plik `.json`** o nazwie jak PDF.
6. **GUI side-by-side** (PDF obok JSON z podświetleniem źródła) daje dodatkowe punkty i od razu pokazuje transparentność.

### ✅ Oficjalne ustalenia UZP (Discord + repo, 21.11, stan 13:27): mają pierwszeństwo
- **Output ściśle według schematu**; dodatkowe pola = FP; dodatkowe pliki w `output/` obniżają wynik. Evidence wyłącznie poza `output/`.
- **Dokument obcy → pusty JSON `{}` z nazwą oryginalnego pliku.** Negatywy: `data/train/negatywne/` (12) + 4 wmieszane w przykłady (04, 10, 24, 37).
- **Klasyfikacja po treści; nazwa pliku może być dowolna.**
- **Zbiór testowy:** syntetyczne dokumenty na bazie prawdziwych spraw, **bez skanów bez warstwy tekstowej** → OCR tylko jako fallback.
- **Fuzzy 80%:** nazwa firmy pełnomocnika, tytuł przelewu, nazwa Odwołującego/Zamawiającego, tytuł zamówienia. Reszta dokładnie. **Listy po treści.**
- **Słownik powodów 1–12** (12 = „Projektowane postanowienia umowy”) w `config/dictionaries/czynnosc_powod.yaml`.
- **Brak limitu czasu;** laptop Windows + WSL z internetem; **endpoint LLM publicznie dostępny**, dostarczamy host + API key.
- Szczegóły: `docs/WYMAGANIA.md` §10.

## Wymagania obowiązkowe

| Obszar | Wymaganie |
|---|---|
| Język | **Python 3.13+** |
| Zależności | `requirements.txt` (instalacja przez `pip install -r requirements.txt`) |
| Licencje | **wyłącznie komponenty open source**, w tym otwarto-źródłowe modele językowe |
| Uruchomienie | lokalnie, **bez GPU** (laptop 16 GB RAM, i7); LLM **przez API dostawcy z UE/EOG**, model open-weight możliwy do lokalnej instalacji, **klucz API dołączony** |
| Interfejs | **CLI obowiązkowe** (+ instrukcja); GUI side-by-side opcjonalne, dodatkowo punktowane |
| Wejście | folder `./input/<case>/*.pdf` w katalogu głównym aplikacji |
| Wyjście | folder `./output/<case>/<nazwa_pliku_wejściowego>.json`, czyli **ta sama nazwa co plik wejściowy** |
| Zgłoszenie | tytuł projektu + **link do GitHub** działającego prototypu (wgranie dokumentów, odczyt wyników) |
| Opcjonalnie | dokumentacja techniczna, wyniki własnych testów jakości |

**Premiowane:**
- konfiguracja **nowych klas dokumentów bez modyfikacji kodu**, wyłącznie przez pliki konfiguracyjne,
- **transparentność** procesu ekstrakcji (skąd pochodzi każda wartość).

## Ocena

| Etap | Kryterium | Waga |
|---|---|---|
| I – preselekcja | jakość ekstrakcji, **F1** na ukrytym zbiorze testowym (≥10 realnych spraw) | **100%** |
| II – finał (**max 3 zespoły**) | F1 na zbiorze testowym | 50% |
| | elastyczność: **1–20 pkt mały model LLM** (mniejszy = lepiej) + **1–20 pkt łatwość dodawania typów i pól** + **1–10 pkt inne funkcje (np. GUI)** | 50% |

Ogólne zasady wydarzenia: pitch do 5 min + do 5 min pytań jury; jury może nie przyznać nagrody przy wyniku <50% punktów.

## Warunki wypłaty nagrody (regulamin zadania)
- Umowa przeniesienia autorskich praw majątkowych na UZP (forma pisemna), podpisana w ciągu **7 dni**, inaczej nagroda przechodzi na kolejny zespół.
- Przekazanie: **kod źródłowy, instrukcja uruchomienia, konfiguracja Docker Compose, dokumentacja** (architektura, konfiguracja ekstrakcji danej klasy dokumentów, dodawanie nowej klasy).
- Rozwiązania zewnętrzne muszą być wyraźnie wskazane w prezentacji.

## Dane

| Ścieżka | Zawartość |
|---|---|
| `data/train/przyklad_NN/` | 60 spraw treningowych: `odwolanie.pdf`, `pelnomocnictwo.pdf`, `potwierdzenie_przelewu.pdf` + oczekiwane `*.json` (w 04, 10, 24, 37 dodatkowo negatywy) |
| `data/train/negatywne/` | 12 dokumentów, które NIE mają być sklasyfikowane (oczekiwany wynik `{}`) |
| `docs/spec/czynnosc_powod_id_dict.md` | oficjalny słownik powodów 1–12 |
| `docs/spec/odwolanie.json`, `pelnomocnictwo.json`, `przelew.json` | specyfikacja modelu danych z komentarzami (reguły dla pól) |
| `docs/spec/szablon-aplikacja/` | przykładowa struktura `input`/`output` i negatywny przykład |
| `docs/UPSTREAM_README.md` | oryginalny README zadania |

Szczegóły i analiza danych: [`docs/WYMAGANIA.md`](docs/WYMAGANIA.md).

## Planowana struktura

```
config/classes/*.yaml   # definicje klas dokumentów (klasyfikacja, pola, regexy, normalizatory, podpowiedzi dla LLM)
config/llm.yaml         # endpoint i model LLM
src/                    # ingest → classify → extract → normalize → evidence → writer
eval/score.py           # F1 per pole i per klasa na data/train
input/  output/         # wymagane foldery
```

## Terminy
- Draft na HackTribe: **sob. 21.11, 20:00**
- Zgłoszenie końcowe: **niedz. 22.11, 11:00**
