# Odwołania2JSON: szczegółowe wymagania i analiza

## 1. Treść zadania (skrót z „Pełnej treści zadania konkursowego”)

**Cel:** stworzyć rozwiązanie, które automatycznie zamieni wielodokumentową sprawę administracyjną (odwołanie do KIO) w spójny, ustrukturyzowany model JSON gotowy do wykorzystania przez systemy administracji publicznej. Kluczowe informacje znajdują się zwykle na pierwszych trzech stronach dokumentów, ale są ułożone w różny sposób. Część dokumentów powstaje elektronicznie, część to skany.

**Rozwiązanie musi:**
1. przyjąć dokumenty PDF składające się na odwołanie: treść odwołania, pełnomocnictwo, potwierdzenie przelewu,
2. rozpoznać rodzaj dokumentu,
3. wyodrębnić informacje biznesowe istotne dla danego typu,
4. wygenerować JSON dla każdego dokumentu zgodny z `oczekiwane-json`.

**Moduły oczekiwane przez UZP (README repozytorium):**
- moduł przetwarzania dokumentów (analiza, klasyfikacja, ekstrakcja, budowa modelu danych),
- interfejs wykonawczy (CLI / `start.bat` / analogiczny),
- foldery `input` i `output` w katalogu głównym,
- wynik: drzewo `output/caseN/*.json`, każdy plik nazwany jak odpowiadający mu PDF.

**Kontekst wdrożeniowy:** najlepsze rozwiązania mogą stać się podstawą pilotażu w UZP. Szczególnie cenione są rozwiązania umożliwiające budowę **uniwersalnego narzędzia** do pozyskiwania ustrukturyzowanych danych z PDF.

**Wsparcie:** mentorzy techniczni i eksperci od zamówień publicznych (stoisko UZP, Discord).

## 2. Model danych (z `docs/spec`)

### odwolanie.json
```
OdwolanieKIO:
  data                 – data z nagłówka 1. strony (ISO)
  czynnosc_dzien       – data czynności uruchamiającej termin, dla PIERWSZEGO zarzutu; brak → null
  czynnosc_powod_id    – int 1–12, WYŁĄCZNIE na podstawie pierwszego zarzutu
  czynnosc_opis        – kanoniczny opis zgodny 1:1 z czynnosc_powod_id
  miejscowosc          – z nagłówka: „X, dnia …” lub „X DD.MM.RRRR”
Odwolujacy[]:          – krs, nazwa (przy konsorcjum: Lider), nip, regon,
                         przez-pelnomocnika (1/0), pelnomocnik{imie_nazwisko, nazwa, mail}
Zamawiajacy[]:         – krs, nazwa, nip, regon,
                         prowadzacy_postepowanie: null (jeden zamawiający) / 1 (lider) / 0 (pozostali)
ZamowieniePubliczne:   – numer_bzp ('YYYY/BZP ########' bez spacji po normalizacji, opcjonalnie '/##'),
                         numer_postepowania (np. 'ZP.039.2025'),
                         numer_ted ('NNNNNN-YYYY'; 'YYYY/S ###-NNNNNN' → 'NNNNNN-YYYY'),
                         tytul
```

### pelnomocnictwo.json
```
mocodawca[]:   data{imie_nazwisko (osoba fizyczna, inaczej null), krs, nazwa, nip, typ: osoba_prawna|osoba_fizyczna},
               podpisujacy[]{imie_nazwisko}
pelnomocnicy[]: imie_nazwisko (w mianowniku), pesel
```

### przelew.json
```
przelew_bankowy: data_operacji, kwota (float), na_rachunek (26 cyfr), numer_transakcji, tytul, z_rachunku
```

## 3. Analiza danych treningowych (`data/train`, 60 spraw)

- Wszystkie 180 PDF-ów ma warstwę tekstową (font Carlito), żadnego skanu. Zbiór testowy to „realne sprawy”, więc **OCR jako fallback** (tesseract `pol`) jest wskazany.
- Rozkład `czynnosc_powod_id` (11 z 12 klas obecnych):

| id | opis kanoniczny | liczba |
|---|---|---|
| 1 | Decyzja o odrzuceniu oferty | 5 |
| 2 | Ogłoszenie wyboru oferty | 5 |
| 3 | Decyzja o wykluczeniu wykonawcy | 5 |
| 4 | Publikacja specyfikacji warunków zamówienia (SWZ) | 6 |
| 5 | Modyfikacja treści SWZ | 4 |
| 6 | Odpowiedzi i wyjaśnienia do SWZ | 5 |
| 7 | Zaniechanie odrzucenia oferty | 5 |
| 8 | Zaniechanie wykluczenia wykonawcy | 7 |
| 9 | Decyzja o unieważnieniu postępowania | 9 |
| 10 | Zaniechanie unieważnienia postępowania | 4 |
| 11 | Opis przedmiotu zamówienia (OPZ) | 5 |
| 12 | **brak w danych, ustalić z mentorami** | 0 |

- Odwołujący: zawsze 1. Zamawiający: >1 w 3 sprawach.
- `numer_ted = null` w 13 sprawach, `numer_bzp = null` w 12.
- Pełnomocnictwo (liczba mocodawców, pełnomocników): (1,1)×20, (1,2)×34, (2,1)×2, (2,2)×4.
- Przelew ma stały szablon bankowy („w dniu DD-MM-RRRR z rachunku nr … w kwocie X PLN na rachunek nr … Tytuł przelewu: „…”. Numer transakcji operacji: …”).
- W `szablon-aplikacja/output/case1/przyklad odwolanie.json` jest pusty plik (sam szablon nazwy).

## 4. Pytania do mentorów UZP (zadać na początku)
1. Co oznacza `czynnosc_powod_id = 12`?
2. Jak oceniany jest negatywny przykład: brak pliku JSON, pusty JSON czy specjalny znacznik?
3. Jak liczone jest F1: per pole (exact match po normalizacji), per dokument, micro czy macro? Jak traktowane są `null` i listy?
4. Czy w zbiorze testowym będą skany? Jakie nazwy plików (czy nazwa zdradza typ)?
5. Czy „LLM po API” dopuszcza model open source uruchamiany na zewnętrznym serwerze, czy tylko lokalnie?

## 5. Plan techniczny
1. `eval/score.py`: F1 per pole i klasa na `data/train` (pierwszy plik w projekcie).
2. Ingest: pdfplumber/pypdf, a przy braku tekstu OCR.
3. Klasyfikacja: reguły z YAML (słowa kluczowe nagłówka: „ODWOŁANIE”, „Pełnomocnictwo”, „potwierdzenie transakcji”), w razie wątpliwości LLM, inaczej „nieznany”.
4. Ekstrakcja: regex + walidacja sum kontrolnych (NIP, REGON, KRS, PESEL, IBAN), daty, kwoty, BZP, TED; LLM (`temperature=0`, JSON mode, few-shot) tylko dla pól semantycznych (powód 1–12, `czynnosc_dzien`, pełnomocnik, mianownik).
5. Normalizacja i walidacja schematem; regex ma pierwszeństwo przed LLM dla identyfikatorów.
6. Evidence: `output/<case>/<plik>.evidence.json` (strona + fragment dla każdego pola). Dopytać, czy dodatkowe pliki w `output` nie przeszkadzają w ocenie; ewentualnie zapisywać je do osobnego katalogu.
7. Konfiguracja klas w YAML i demo dodania nowej klasy bez zmiany kodu (50% oceny w finale).
8. Docker Compose (aplikacja + Ollama), README, dokumentacja architektury i dodawania klasy.

## 6. Plan startu i ryzyka (uzgodnione z sesją hacknation-0c)

**Kolejność dnia (oba projekty):**
0. **Przed 20:00 złożyć drafty OBU projektów** na HackTribe. Draft jest darmowy, a po 20:00 nie można zmienić zadania.
1. **Godz. 0–1, UZP najpierw:** `eval/score.py` (F1 per pole i klasa) + baseline (pdfplumber, klasyfikacja słowami kluczowymi, przelew regexem). Daje liczbę i listę pól, które wymagają pracy.
2. Godz. 1–2: szkielet AGH (osobna sesja lub repo).
3. Godz. 2–3: subagent w worktree dokłada w UZP regexy i walidatory sum kontrolnych (NIP, REGON, PESEL, IBAN mod97, KRS) z testami.
4. **Noc:** pętla eval → poprawka (np. ralph-loop) z twardym kryterium „F1 rośnie, testy przechodzą, commit”. Sen 3–4 h.

**Biblioteki:** pdfplumber (tekst z pozycją, więc strona do evidence jest za darmo), pydantic v2 + jsonschema, rapidfuzz, ollama z `format=<JSON schema>` (structured outputs).

**Ryzyka i decyzje:**
- **Wydajność na CPU:** mały model (qwen2.5 3b/7b-instruct q4), **jedno wywołanie LLM na dokument** z jednym schematem JSON, a nie na pole. Zmierzyć czas całego zbioru.
- **`czynnosc_powod_id`** to najtrudniejsze pole (12 klas, klasy 12 brak w danych): few-shot z kanonicznymi opisami + fallback słowami kluczowymi.
- **Evidence domyślnie poza `./output`** (np. `./evidence/`), bo dodatkowe `*.json` w `output` mogą zepsuć automatyczny ewaluator. Zapis do `output` tylko flagą.
- **Rozszerzalność (50% w finale):** nowa klasa = jeden YAML (klasyfikator, pola, regexy, prompt, schemat), bez zmiany kodu. Pokazać to na żywo w pitchu.
- **Overfitting:** 10–15 spraw z `data/train` trzymać jako holdout.
- Ustalić z mentorami, jak F1 traktuje `null` i listy.
- Kod napisany przed hackathonem ujawnić w README.

**Narzędzia (po restarcie Claude Code):** w dzień grill-me (≤20 min) → to-tickets (wcześniej `/mattpocock-skills:setup-matt-pocock-skills`, tracker „local markdown”) → implement + subagenci w worktree; **w nocy ralph-loop** (eval → najsłabsze pole → poprawka → commit tylko przy wzroście F1). Na koniec verification-before-completion + `/pstack:prove-it-works`, README i slajdy przez `/pstack:unslop`. Szczegóły: `../hacknation/PLAN_PRACY.md`.

**Dodatkowe ustalenia:**
- **Środowisko:** uruchamiać przez `python3.13` (domyślny `python3` w systemie to 3.15). **Wymagana Ollama** (`brew install ollama`, `ollama pull qwen2.5:7b-instruct` i `qwen2.5:3b-instruct`).
- **Holdout:** 15 spraw z `data/train` wydzielonych jako jawny krok w `eval/` i niewidocznych dla nocnej pętli.
- **Szum F1:** zbiór testowy ma tylko ≥10 spraw, więc każdy błąd na częstym polu kosztuje dużo. Regexy z walidacją wszędzie, gdzie się da; LLM tylko tam, gdzie konieczny.
- **Ticket U12, minimalny podgląd:** wgranie PDF → odczyt JSON + evidence. Zgłoszenie wymaga „działającego prototypu (wgranie dokumentów, odczyt wyników)”. Dopytać mentorów, czy samo CLI wystarczy.


## 7. Aktualizacje z Discorda i repo UZP (21.11)

Pełna tabela ustaleń: `README.md`, sekcja „Aktualizacje 21.11”. Najważniejsze zmiany w planie:

| Było | Jest teraz |
|---|---|
| Ollama lokalnie na maszynie jury | **LLM przez API dostawcy z UE/EOG** (model open-weight), klucz API w paczce. Ollama tylko do pracy lokalnej / jako fallback. Lokalny model na 16 GB RAM/i7 bez GPU jest ryzykowny. |
| finał: 50% rozszerzalność | (README 12:14) **1–20 pkt mały model** + **1–20 pkt rozszerzalność** + **1–10 pkt inne funkcje (GUI)**. Regexy i reguły jako rdzeń; LLM możliwie mały. |
| negatyw: brak pliku? | **Pusty plik `.json`** dla dokumentów spoza obsługiwanych klas. |
| dane treningowe reprezentatywne | **Realny przykład to skan** (JPEG 96 ppi, zaczernienia); train to wyłącznie syntetyczne PDF z tekstem. OCR (tesseract `pol`, doinstalować `tesseract-lang`) = P0; testować pipeline na `przyklad odwolanie.pdf`. |
| OCR „na wszelki wypadek” | **OCR obowiązkowy**: skany są w realnych danych. |
| GUI opcjonalne (U12) | GUI **dodatkowo punktowane**; preferowany widok obok siebie: PDF i JSON. |
| sposób liczenia F1 nieznany | TP (długie stringi ≥80% zgodności), TN (brak w obu), FP (wartość tylko w JSON lub błędna), FN (brak w JSON). **Pole bez dowodu w tekście → `null` (unikamy FP przy braku w GT); pole z dowodem → podać wartość, nawet przy umiarkowanej pewności, bo błąd (FP) kosztuje tyle samo co `null` (FN).** |
| `eval/score.py` exact match | Odwzorować metrykę UZP: fuzzy ≥80% dla długich stringów (rapidfuzz `ratio`), TN liczone, FP za złą wartość. |

### Pytania do zadania na stoisku UZP (nowe)
1. Ile punktów z puli 1–20 dostaje rozwiązanie **bez LLM** albo z modelem ≤3B? Jak liczony jest rozmiar przy kilku modelach (np. osobny model do OCR)?
2. Czy OCR (tesseract) liczy się jako „model”?
3. Czy możemy obejrzeć dane testowe (dostępny jest „wgląd na stoisku”)? Ile jest skanów, jaka jakość?
4. FAQ mówi o 39 zestawach i `ground_truth.yaml`, a repo ma 60 przykładów i nie ma `ground_truth.yaml`. Która wersja danych obowiązuje?
5. Które pola są „długimi stringami” (próg 80%), a które są porównywane dokładnie?
6. Czy klasa `czynnosc_powod_id = 12` istnieje?

### Kandydaci na dostawcę API z UE (DO WERYFIKACJI: siedziba, lokalizacja serwerów, modele open-weight, cena)
- dostawcy chmurowi z UE oferujący endpointy z modelami open-weight (Llama, Qwen, Mistral, Bielik),
- własny serwer z modelem (vLLM/Ollama) u dostawcy hostingu w UE (opcja 2 z odpowiedzi UZP).
Wybrać najmniejszy model, który daje akceptowalne F1 na holdoucie. Porównać 2–3 rozmiary (np. ~3B, ~8B) w `eval`.

## 8. Pytania otwarte do UZP: STATUS (czekamy na odpowiedzi)

Zadane na Discordzie (#odwołania2json, 21.11 ok. 12:04–12:20). **Ta sekcja jest aktualnym źródłem prawdy; listy pytań w §4 i §7 zastępuje.** Odpowiedzi wpisywać w kolumnie „Odpowiedź”.

| # | Pytanie | Co już wiemy (FAQ / README UZP) | Odpowiedź | Wpływ na kod |
|---|---|---|---|---|
| Q1 | Prezentacja mówi o 39 zestawach i `ground_truth.yaml`, repo ma 60 przykładów bez tego pliku. Która wersja obowiązuje, gdzie jest `ground_truth.yaml`? | – | ⏳ | wybór danych do eval i holdoutu |
| Q2 | Które pola to „długi string” (próg 80%), a które dokładne (KRS, NIP, daty, kwoty)? Jaką miarą liczone jest 80%? | 80% dla „długich stringów, np. nazw firm” | ⏳ | metryka w `eval/score.py` (np. rapidfuzz ratio vs token_set) |
| Q3 | Jak dopasowywane są listy (kilku odwołujących / pełnomocników): po kolejności czy po treści? | – | ⏳ | kolejność elementów list w wyniku |
| Q4 | Czy zbiór testowy to realne sprawy i czy są w nim skany bez warstwy tekstowej? | FAQ: **tak, skany występują**, OCR wymagany; wgląd w dane testowe na stoisku | ⏳ (częściowo) | OCR: priorytet i jakość |
| Q5 | Czy w JSON wolno dodać cytat źródła (evidence), czy musi być ściśle zgodny z formatem? | – | ⏳ | evidence w JSON czy w osobnym pliku/katalogu |
| Q6 | Dokument obcy: brak pliku czy JSON z typem „inny”? Nazwy plików: jak PDF (README) czy jak w danych (`przelew.json` przy `potwierdzenie_przelewu.pdf`)? | README: nazwa JSON = nazwa PDF; **README 12:14: dokument obcy → PUSTY plik `.json`** | ✅ częściowo: negatyw = pusty plik (0 B? czy `{}` też OK, dopytać) | writer wyników, obsługa negatywów |
| Q7 | Jaki jest sprzęt i limit czasu przy ocenie? | README: **laptop 16 GB RAM, Intel i7, bez GPU**; limit czasu nieznany | ⏳ (częściowo) | wybór modelu, równoległość wywołań |
| Q8 | Czy maszyna testowa ma internet do naszego endpointu? | README/FAQ: LLM przez API dostawcy z UE + klucz API, co sugeruje, że **tak** | ⏳ (pośrednio tak) | fallback bez sieci (same reguły) |
| Q9 | Co oznacza kod 12 w `czynnosc_powod_id`? W danych są tylko 1–11. (Pytanie zadał też inny uczestnik o 12:04.) | – | ⏳ | słownik powodów, prompt/klasyfikator |

### Pytania jeszcze NIEZADANE (do dorzucenia na Discordzie lub na stoisku)
- Q10: Ile punktów z puli 1–20 („moc modelu”) dostaje rozwiązanie **bez LLM** albo z modelem ≤3B? Jak liczony jest rozmiar przy kilku modelach?
- Q11: Czy OCR (np. tesseract) lub model do OCR liczy się do „mocy modelu”?

### Do czasu odpowiedzi: założenia robocze
- Dane: używamy wszystkich 60 przykładów, 15 jako holdout. Jeśli pojawi się `ground_truth.yaml`, eval przełączamy na niego.
- Metryka: pola identyfikatorów, dat i kwot dokładne (po normalizacji); nazwy, tytuły i opisy fuzzy ≥80% (rapidfuzz `ratio`); listy dopasowywane po treści (najlepsze dopasowanie), a w wyniku kolejność jak w dokumencie.
- Evidence **poza** `output/` (`./evidence/`); JSON w `output/` ściśle zgodny ze schematem.
- Dokument obcy: **pusty plik `.json` (0 B)** + wpis w logu/raporcie. Nazwa JSON = nazwa PDF (zgodnie z README).
- OCR obowiązkowy w pipeline od pierwszego dnia; przykład skanu z szablonu jako test regresyjny.
- Kod 12: w słowniku jako „inny / nieznany”, nieużywany, dopóki UZP nie odpowie.
- Rdzeń bez sieci: reguły i regexy działają offline; LLM jest opcjonalną warstwą.

## 9. ODPOWIEDZI MENTORÓW UZP (stoisko, 21.11): zastępują §8

| # | Pytanie (skrót) | Odpowiedź mentora | Decyzja dla kodu |
|---|---|---|---|
| U1 | Dane testowe, skany | „Może być parę skanów, są w dobrej jakości” | OCR obowiązkowy, ale bez agresywnego preprocessingu; tesseract `pol` powinien wystarczyć |
| U2 | Punkty za mały model / bez LLM | „Im mniejszy model” (bez konkretów) | rdzeń na regexach i regułach; LLM najmniejszy, jaki utrzyma F1; porównać wariant bez LLM |
| U3 | Czy OCR liczy się do „mocy modelu” | „Może się liczyć… zależy” (niejasne) | preferować klasyczny OCR (tesseract), nie modele VLM; opisać to w dokumentacji |
| U4 | Kod 12 `czynnosc_powod_id` | **Słownik zostanie podany** | czekać na słownik (Discord); słownik powodów w YAML, łatwy do podmiany |
| U5 | Dokument obcy | „**Pusty json**”; plik o tej nazwie **musi istnieć**, porównywany jest z ground truth | zapisywać plik o nazwie PDF; treść: `{}` (pusty JSON). ⚠️ README/szablon pokazują plik 0 B: dopytać na Discordzie, który wariant przejdzie ich parser; do tego czasu `{}` |
| U6 | Które pola z progiem 80% | **80% zgodności znaków tylko dla nazwy zamawiającego**; szczegóły na Discordzie | wszystkie pozostałe pola: dokładne dopasowanie po normalizacji. Normalizacja formatów (daty ISO, NIP bez kresek, kwota jako liczba) jest krytyczna |
| U7 | Dopasowanie list | **Po treści** | kolejność elementów nie ma znaczenia; liczy się kompletność i poprawność |
| U8 | 39 zestawów vs 60 | „Jest OK, zbiór został powiększony” | używać wszystkich 60 (45 train + 15 holdout) |
| U9 | Dodatkowe pola (evidence) w JSON | **JSON ściśle zgodny ze schematem; dodatkowe pola = false positive** | **ZERO pól spoza schematu** w output |
| U10 | Nazwy plików | **Taka sama nazwa jak PDF. Dodatkowe pliki obniżają punktację** | w `output/` tylko `<nazwa_pdf>.json`; **evidence i logi wyłącznie poza `output/`** (np. `./evidence/`, `./logs/`) |
| U11 | Limit czasu | ok. **4 h** na zbiór testowy | duży zapas; nawet 7–8B przez API się zmieści. Mimo to batching i równoległość, z limitem żądań |
| U12 | Internet na laptopie testowym | **Laptop Windows z WSL, z dostępem do internetu.** Rozwiązanie uruchamiane lokalnie na laptopie; dostarczamy tylko **API key + host (endpoint) LLM** | **testować uruchomienie w WSL (Ubuntu)**: `start.sh` + `start.bat` wołający WSL lub czysty Python; ścieżki ze spacjami; tesseract instalowany w WSL (`apt install tesseract-ocr tesseract-ocr-pol`); tryb offline (same reguły) jako fallback |

### Zaktualizowane założenia (obowiązują od teraz)
1. `output/<case>/<nazwa_pdf>.json`: **jedyny plik na wejściowy PDF**, ściśle według schematu, bez pól dodatkowych.
2. Dokument obcy: plik `<nazwa_pdf>.json` z treścią `{}` (do potwierdzenia: `{}` vs 0 B).
3. Evidence: `./evidence/<case>/<nazwa_pdf>.evidence.json` (poza `output/`); w GUI side-by-side czytane stamtąd.
4. Metryka w `eval/score.py`: fuzzy ≥80% (znakowo, rapidfuzz `ratio`) **tylko** dla `Zamawiajacy[].nazwa`; reszta exact; listy dopasowywane po treści (najlepsze dopasowanie).
5. Środowisko docelowe: **Windows + WSL**. Instrukcja instalacji pod Ubuntu/WSL; w README sekcja „Uruchomienie na Windows (WSL)”.
6. Słownik `czynnosc_powod_id` w `config/dictionaries/czynnosc_powod.yaml`; po publikacji przez UZP podmienić (kod 12).

### Do dopilnowania na Discordzie
- definicja pól liczonych fuzzy (zapowiedziana),
- pełny słownik powodów (z kodem 12),
- doprecyzowanie: dokument obcy = `{}` czy plik 0 B,
- ~~czy laptop testowy ma dostęp do internetu~~: **tak** (potwierdzone).

### Potwierdzone: środowisko uruchomieniowe UZP
- Aplikacja działa **lokalnie na laptopie jury (Windows + WSL, 16 GB RAM, i7, bez GPU), z dostępem do internetu.**
- LLM jest zdalny: dostarczamy **`LLM_BASE_URL` (host/endpoint, dostawca z UE/EOG) + `LLM_API_KEY`**, np. w `.env` lub `config/llm.yaml`. Model open-weight.
- Wymagane: konfiguracja hosta i klucza bez zmiany kodu, czytelny komunikat przy braku klucza lub niedostępności API, a reguły i regexy działają nawet bez LLM.

## 10. OFICJALNE ODPOWIEDZI UZP NA DISCORDZIE + ZMIANY W REPO (21.11, 12:47–13:27): mają pierwszeństwo przed §9

**Discord (UZP: Dominik Olczak 12:47, MateuszSz 13:13–13:27):**
| Temat | Ustalenie oficjalne | Zmiana względem §9 |
|---|---|---|
| Dane | 60 przykładów jest aktualne (dorobiono kilkanaście większych); `ground_truth.yaml` usunięty, bo był scaleniem plików `.json` | bez zmian |
| **Zbiór testowy** | **Syntetyczne dokumenty wygenerowane na podstawie prawdziwych spraw. Brak skanów bez warstwy tekstowej.** | ⚠️ odwraca odpowiedź ze stoiska („parę skanów”): **OCR spada z P0 do P2** (tylko fallback) |
| Format | JSON ściśle zgodny ze schematem | bez zmian |
| **Dokument obcy** | Ostatecznie (13:27): **pusty JSON z nazwą oryginalnego pliku** | potwierdza `{}` + nazwa jak PDF (12:47 była wersja „nie zwracamy JSON-a”, poprawiona o 13:27) |
| Czas / sprzęt | Zwykły laptop, **brak limitu czasu**; nie instalują modelu lokalnie, dlatego API | limit 4 h nieaktualny |
| Sieć | Jest internet; **endpoint musi być publicznie dostępny** | |
| **Pola „długi string” (fuzzy 80%)** | **nazwa firmy pełnomocnika, tytuł przelewu, nazwa Odwołującego/Zamawiającego, tytuł zamówienia publicznego** | ⚠️ szerzej niż „tylko nazwa zamawiającego” ze stoiska |
| Listy | Dopasowywane po treści | bez zmian |
| Kod 12 | Słownik opublikowany: **12 = „Projektowane postanowienia umowy”** | zapisany w `config/dictionaries/czynnosc_powod.yaml` |

**Zmiany w repo (zsynchronizowane do `data/train`, `docs/spec`, `docs/UPSTREAM_README.md`):**
- `oczekiwane-json/czynnosc_powod_id_dict.md`: słownik 1–12. Uwaga: id 6 = **„Odpowiedzi/wyjaśnienia do SWZ”**, a w danych treningowych występuje „Odpowiedzi i wyjaśnienia do SWZ”. Wybrać wersję zgodną z ground truth (dane treningowe) i ewentualnie dopytać.
- README: **klasyfikacja na podstawie zawartości; nazwa pliku może być dowolna, nie sugerować się nią.**
- **Negatywy:** `data/train/negatywne/` (12 PDF) + wmieszane w przykłady: `przyklad_04/2025_S 112-383751.pdf`, `przyklad_10/2025-OJS107-00364525-pl-ts.pdf`, `przyklad_24/prowadzenie_postepowania_odwolawczego.pdf`, `przyklad_37/2025_BZP 00143067_01.pdf`. Oczekiwany wynik: `{}`.
  - **Trudne negatywy:** `KIO_KIO 2617-21.pdf` (wyrok/orzeczenie KIO, słownictwo jak w odwołaniu), `prowadzenie_postepowania_odwolawczego.pdf` (materiał o postępowaniu odwoławczym), ogłoszenia BZP/TED (te same identyfikatory co w odwołaniach). Klasyfikator na samych słowach kluczowych da tu FP.
  - 3 negatywy **nie mają warstwy tekstowej** (skany: decyzja Ministra Sportu ×2, pismo Ministra Sprawiedliwości). Skoro zbiór testowy nie ma skanów dokumentów właściwych, to **PDF bez tekstu → bardzo prawdopodobnie negatyw** (heurystyka; OCR tylko jako fallback).

### Zaktualizowane założenia (obowiązują od teraz, zastępują §9)
1. `output/<case>/<nazwa_pdf>.json`: jeden plik na PDF, ściśle według schematu; **dokument obcy → `{}`**.
2. **Klasyfikacja po treści, z odrzucaniem:** cechy strukturalne każdej klasy (np. odwołanie: nagłówek „ODWOŁANIE” + „Prezes Krajowej Izby Odwoławczej” + sekcje Zamawiający/Odwołujący + zarzuty; pełnomocnictwo: „Pełnomocnictwo” + „udzielam pełnomocnictwa”; przelew: „potwierdzenie transakcji/przelewu” + rachunki + kwota). Próg pewności, poniżej którego wynik to `{}`. Testować na wszystkich 16 negatywach (12 + 4 w przykładach); cel **0 FP na negatywach**.
3. PDF bez warstwy tekstowej → domyślnie `{}` (opcjonalnie OCR + klasyfikacja przy wysokiej pewności).
4. Metryka w `eval/score.py`: fuzzy ≥80% dla: `Odwolujacy[].nazwa`, `Zamawiajacy[].nazwa`, `Odwolujacy[].pelnomocnik.nazwa`, `przelew_bankowy.tytul`, `ZamowieniePubliczne.tytul`; reszta exact; listy po treści; negatywy liczone jako dokumenty z pustym GT.
5. Brak limitu czasu. Endpoint LLM publiczny (dostawca z UE), konfigurowany przez host + klucz.
6. Nazwa pliku nie może wpływać na klasyfikację (eval: losowo zmieniać nazwy plików).

### Tesseract: licencja i użycie (sprawdzone 21.11 przez API GitHuba)
- **Tesseract jest open source: Apache-2.0** (`tesseract-ocr/tesseract`). Modele językowe `tessdata_fast` (w tym `pol`): Apache-2.0. Wrapper `pytesseract`: Apache-2.0. Uwaga mentora „tesseract nie jest OS” jest nieścisła; w dokumentacji podać licencje z linkami.
- Tesseract to klasyczny silnik OCR (LSTM ~kilka MB), a nie LLM, więc nie powinien obciążać punktacji „mocy modelu”. Opisać go w dokumentacji jako osobny komponent.
- Rola w rozwiązaniu: **fallback** (zbiór testowy nie ma skanów bez warstwy tekstowej). Użycie: PDF bez tekstu → OCR → klasyfikacja; przy niskiej pewności `{}`.
- Instalacja (WSL/Ubuntu): `sudo apt install tesseract-ocr tesseract-ocr-pol`; Python: `pytesseract` + `pdf2image` (wymaga `poppler-utils`) lub `pymupdf` do renderowania stron. macOS (dev): `brew install tesseract-lang`.
- OCR musi być **opcjonalny**: brak binarki tesseract → ostrzeżenie w logu, dokument bez tekstu → `{}`, aplikacja działa dalej.
