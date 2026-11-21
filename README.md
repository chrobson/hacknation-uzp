# Odwołania2JSON

Automatyczna klasyfikacja i ekstrakcja danych z dokumentów PDF spraw odwoławczych KIO (odwołanie, pełnomocnictwo, potwierdzenie przelewu) do ustrukturyzowanego JSON. Rdzeniem są reguły zapisane w plikach YAML; lokalny OCR czyta skany, a mały model językowy (opcjonalny) uzupełnia tylko pola, których reguły nie znalazły.

## Uruchomienie (Linux / macOS; Windows: to samo w WSL)
```bash
cp .env.example .env      # potem wklej do .env LLM_API_KEY z formularza zgłoszenia (pole z kluczem API)
bash start.sh             # czyta ./input/<sprawa>/*.pdf, zapisuje ./output/<sprawa>/<nazwa_pdf>.json
```
Bez klucza działa tryb regułowy: pełna funkcjonalność, niższa jakość pól czynności (powód, data).

**Windows**: potrzebny WSL z Ubuntu (jednorazowo w PowerShell jako administrator: `wsl --install -d Ubuntu`). Potem w terminalu Ubuntu, w katalogu projektu, te same dwie komendy, albo dwuklik / `start.bat` w katalogu projektu (uruchamia `start.sh` w WSL).
Skany wymagają Tesseracta z językiem polskim. W WSL zwykły użytkownik ma hasło do sudo, więc jeśli `start.sh` wypisze ostrzeżenie „OCR NIEDOSTĘPNY”, uruchom raz:
`sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-pol` i ponownie `bash start.sh`.

`start.sh` sam przygotowuje środowisko: uv + Python 3.13 z zależnościami przypiętymi w `uv.lock` (zapasowo: python3.13 + venv + `requirements.txt`), a do skanów Tesseract z językiem polskim (instalacja przez apt albo pobranie samego modelu `pol`).
Dokument spoza trzech klas daje plik `{}` o tej samej nazwie.

Opcje (`bash start.sh --help`): `--input`, `--output`, `--classes-dir DIR` (dodatkowe klasy YAML), `--evidence DIR` / `--no-evidence` (dowody: strona, cytat i współrzędne każdej wartości; nigdy w `output/`), `--llm on|off`, `-v`.
Na końcu przebiegu program wypisuje podsumowanie: liczbę PDF, odrzucone, użycie modelu językowego oraz ostrzeżenie, jeśli jakiś skan został nieodczytany z braku OCR.

## Wyniki (F1 wg metryki UZP)
| zbiór | reguły | reguły + LLM |
|---|---|---|
| dane treningowe UZP (45 spraw) | 1,000 | 1,000 |
| holdout z danych UZP (15 spraw, nieużywany do strojenia) | 1,000 | 1,000 |
| synth-dev (120 dokumentów o innych układach, także wielopodmiotowe) | 0,942 | 0,942 |
| skany UZP przez OCR (30 dokumentów) | 0,953 | 0,953 |
| **niezależny zbiór kontrolny** (110 dokumentów o nieznanych układach, mierzony bez wglądu w dokumenty, nieużywany do strojenia) | **0,840** | 0,840 |

Wynik 1,000 na danych UZP to dane, na których powstawały reguły; realną jakość na nowych dokumentach lepiej opisuje zbiór kontrolny i skany.

Numery rachunków są zapisywane tak, jak w dokumencie: z prefiksem `PL`, jeśli dokument go podaje (bez spacji, np. `PL61109010140000071219812874`), w przeciwnym razie 26 cyfr. Tak potwierdził UZP (21.11.2026); lokalne dane wzorcowe poprawiono skryptem `eval/gt_account_pl.py`, bo część wzorcowych JSON-ów UZP pomijała `PL`.

Dokumenty obce (ogłoszenia, wyroki KIO, SWZ, faktury, umowy, pisma podobne do klas): 0 przyjętych na 56 w naszych zbiorach (w tym 20 typowych pism z folderu sprawy KIO: nota obciążeniowa, zestawienie kosztów, uzupełnienie braków, cofnięcie odwołania, skarga, UPO), 2 przyjęte na 20 w zbiorze kontrolnym. Bramka jakości (`make gate`, 9 testów, m.in. brak regresji, 0 fałszywych przyjęć, niezależność od nazw plików, praca bez LLM, < 1 s/dokument) pilnuje każdej zmiany.

## Jak to działa
1. **Tekst**: `pdfplumber` (słowa ze współrzędnymi); PDF bez warstwy tekstowej → lokalny OCR (Tesseract `pol`, strony równolegle; przekrzywiony skan jest prostowany i czytany ponownie; typowe błędy OCR, np. „@” czytane jako „(O”, są poprawiane). Dwukolumnowe nagłówki stron są czytane kolumnami.
2. **Klasyfikacja**: każda klasa w YAML ma kotwice wymagane, ważone sygnały i próg; wspólne reguły odrzucenia (`config/reject.yaml`) wyłapują dokumenty obce. Dla skanów z błędami OCR działa dodatkowo rozmyte głosowanie słów kluczowych.
3. **Ekstrakcja**: pola opisane w YAML typami wielokrotnego użytku (`labeled`, `pattern`, `near`, `names`, `account`, `keyword_map`, `first_line`, `exists`, …), z sekcjami dokumentu, listami (np. kilku zamawiających / mocodawców) i normalizacją (daty, kwoty, NIP/KRS/REGON, mianownik imion i nazwisk: słownik SGJP przez Morfeusz2, a gdy pakietu brak, reguły końcówek).
4. **LLM (opcjonalnie)**: tylko dla pól, które reguły zostawiły puste, z zamkniętym słownikiem odpowiedzi i walidacją; awaria → reguły.
5. **Wynik**: JSON zgodny ze schematem UZP + osobno plik dowodów (strona, cytat, ramki) dla każdej wartości.

## Rozszerzalność: nowa klasa albo nowe pole = plik YAML
Kod nie zna nazw klas ani pól. Wszystko jest w `config/classes/*.yaml` (rozpoznawanie, sekcje, pola, szablon wyniku), `config/reject.yaml` i `config/dictionaries/`. Dodatkowe klasy dołącza się opcją `--classes-dir DIR`, a cały zestaw klas można podmienić opcją `--classes DIR`.

**Trzy poziomy, ten sam plik YAML:**
1. **Pytania do modelu językowego**: kilka minut pracy, bez wyrażeń regularnych. `examples/klasy_llm/wezwanie_llm.yaml` (14 linii): jedna kotwica rozpoznania i 5 pól `type: llm`. Na przykładowym piśmie KIO daje 5/5 pól (5 wywołań modelu).
2. **Reguły**: precyzja bez kosztu i bez sieci. `examples/klasy/wezwanie_do_uzupelnienia.yaml` (~40 linii) daje te same informacje (plus kwotę wpisu i braki) bez modelu.
3. **Hybryda** (tak działają 3 klasy zadania): reguły najpierw; pole `type: llm` na liście reguł danego pola jest pytane tylko wtedy, gdy reguły nic nie znalazły.

**Nowe pole w istniejącej klasie** to dwie linie YAML: wpis w `output_template` i reguła w `fields`, np.
```yaml
output_template:
  przelew_bankowy:
    cel: null
fields:
  przelew_bankowy.cel: {type: keyword_map, map: {wpis: ['wpis\w*\s+od\s+odwołani'], oplata_skarbowa: ['opłat\w*\s+skarbow']}}
```

**Demo** (4 kroki: dokument spoza klas → `{}`; klasa z pytań do modelu; ta sama klasa na regułach; nowe pole w przelewie):
```bash
bash scripts/demo_nowa_klasa.sh
```
Przykładowe klasy leżą celowo poza `config/classes`, żeby nie były aktywne podczas oceny.

**Test mutacyjny** (`bash scripts/mutation_proof.sh`): losowa zmiana nazw wszystkich klas i wszystkich kluczy wyjściowych w YAML (np. `przelew_bankowy.kwota` → `f328.f664`) daje po odwzorowaniu nazw wynik identyczny co do wartości (0 różnic w 120 dokumentach synth-dev i 196 dokumentach train), bez zmiany ani jednej linii Pythona.

**Co się konfiguruje w YAML:**
- **Rozpoznawanie** (`classify:`): `required` (choć jedna kotwica musi wystąpić), ważone `signals` (także ujemne, np. nagłówek innej klasy), `threshold`, `head_chars` (szukanie tylko w nagłówku), `fuzzy` (głosowanie słów odpornych na błędy OCR); wspólne reguły odrzucenia dokumentów obcych w `config/reject.yaml`.
- **Walidacja wartości**: typ wartości (`value: date | amount | nip | krs | regon | pesel | email | account`) normalizuje i odrzuca wartości w złym formacie (np. NIP to 10 cyfr, data jest sprawdzana jako data kalendarzowa); `reject` / `require` (wzorce, które wartość musi spełnić albo których nie może zawierać), `cast: int`; dla modelu: `choices` (zamknięta lista odpowiedzi), `verbatim` (tylko cytat występujący w tekście), `schema` (typ JSON). Osobno, sekcja `validate:` sprawdza sumy kontrolne NIP/REGON/PESEL/IBAN i formaty (tylko ostrzeżenia, opis niżej).
- **Mapowanie**: ścieżka pola w wyniku (`przelew_bankowy.kwota`, listy `Odwolujacy[]`), `output_template` (kolejność i komplet kluczy, `null` dla braków), słowniki (`config/dictionaries/czynnosc_powod.yaml`: identyfikator → opis, pole pochodne `{from: …, dictionary: …}`), `keyword_map` (słowa → kod).

| typ pola | co robi | przykład |
|---|---|---|
| `pattern` | wyrażenie regularne, grupa 1 = wartość | `{type: pattern, pattern: 'Sygn\.\s*akt\s*:?\s*(KIO\s*\d+/\d+)'}` |
| `labeled` | wartość danego typu tuż po etykiecie | `{type: labeled, value: date, labels: ['data\s+operacji']}` |
| `text_after_label` | tekst po etykiecie do linii stopu | `{type: text_after_label, labels: ['tytułem'], stop_labels: ['^\s*kwota']}` |
| `near` | wartość najbliżej słów kotwic (układ nieznany) | `{type: near, value: company, anchors: ['Odwołując\w*']}` |
| `first_line` | pierwsza linia sekcji | `{type: first_line, section: adresat}` |
| `names` | lista imion i nazwisk (w mianowniku) | `{type: names, section: pelnomocnicy, nominative: true}` |
| `account` | rachunek nadawcy / odbiorcy | `{type: account, role: sender}` |
| `keyword_map` | słowa kluczowe → kod | `{type: keyword_map, map: {wpis: ['wpis\w*']}}` |
| `exists` | wartość zależna od obecności wzorca | `{type: exists, pattern: ['CEIDG'], if_true: osoba_fizyczna}` |
| `llm` | pytanie do modelu z walidacją odpowiedzi | `{type: llm, question: 'Podaj datę pisma', value: date}` |

## Rozpoznawanie, walidacja, mapowanie: trzy pliki YAML
Wszystkie trzy rodzaje reguł są konfiguracją, nie kodem; żadna z nich nie zmienia plików w `output/`.

| Co | Gdzie | Wynik |
|---|---|---|
| **Rozpoznawanie** i ekstrakcja | `config/classes/*.yaml` (`classify:`, `fields:`) | `output/<sprawa>/*.json` |
| **Walidacja pól** | sekcja `validate:` w tym samym pliku klasy, np. `Odwolujacy[*].nip: [{check: nip}]` | ostrzeżenia `{path, check, ok, message}` w `evidence/…/*.evidence.json`, klucz `validation` |
| **Kontrola formalna sprawy** | `config/case_rules.yaml`: 5 reguł między dokumentami sprawy (wpis na rachunek UZP, opłata skarbowa 17 zł, mocodawca = Odwołujący, pełnomocnik umocowany, termin od czynności) | `evidence/<sprawa>/_sprawa.report.json` + jedna linia na sprawę w konsoli |
| **Mapowanie / eksport** | `config/mappings/rejestr_kio.yaml`: lista `{column, path, join}` | `--map rejestr_kio` → `exports/rejestr_kio.csv` (wiersz na sprawę, UTF-8 z BOM i `;`, otwiera się w Excelu) |

Sprawdzenia pól: `nip`, `regon`, `pesel` (sumy kontrolne), `krs`, `iban_pl`, `date_not_future`, `amount_range`, `regex`, `enum`. Operatory reguł sprawy: `exists`, `in`, `eq`, `fuzzy_eq`, `one_of_amounts`, `days_between_le`. Literówka w nazwie sprawdzenia lub operatora zatrzymuje program z czytelnym komunikatem przy starcie.

Walidacja tylko ostrzega i nie usuwa wartości. Dane konkursowe zawierają fikcyjne identyfikatory: w `data/train` sumę kontrolną spełnia 115/189 numerów NIP, 85/123 REGON i 43/120 rachunków (`python -m eval.validate_gt`). Odrzucanie takich wartości obniżyłoby wynik.

```bash
bash start.sh --input input --output output --map rejestr_kio
# jedna linia na sprawę: liczba spełnionych reguł i krótkie komunikaty (reguły informacyjne z prefiksem info:)
```

## Model językowy (opcjonalny dodatek do reguł)
| | |
|---|---|
| Model | `ministral-8b-2512` (Mistral AI), ok. 8 mld parametrów, open-weight, licencja Apache-2.0; przełączalny jednym wpisem `model:` w `config/llm.yaml` (np. `ministral-3b-2512`) |
| Endpoint | `https://api.eu.mistral.ai/v1` (region UE), API zgodne z OpenAI, klient w bibliotece standardowej |
| Pola | `OdwolanieKIO.czynnosc_powod_id` (zamknięta lista etykiet słownych → numer ze słownika), `OdwolanieKIO.czynnosc_dzien`, `ZamowieniePubliczne.tytul` (tylko cytat występujący dosłownie w tekście) |
| Kiedy | wyłącznie gdy żadna reguła nie dała wartości; nigdy nie nadpisuje reguły |
| Wejście | wycinek pierwszego zarzutu odwołania (≤1500 znaków), a nie cały dokument |
| Klasyfikacja | wyłącznie reguły (`classify_tiebreak: false`) |

**Ablacja (ile daje model i jaki rozmiar):**

| wariant | train | skany | synth-dev | zbiór kontrolny (bez wglądu) | wywołania modelu |
|---|---|---|---|---|---|
| same reguły (0 parametrów) | 1,000 | 0,953 | 0,942 | 0,731 | 0 |
| reguły + `ministral-3b-2512` | 1,000 | 0,953 | 0,942 | 0,747 | 5 na 300 dok. |
| reguły + `ministral-8b-2512` (domyślnie) | 1,000 | 0,953 | 0,942 | **0,754** | 5 na 300 dok. |
| sam LLM 8b (cały tekst + specyfikacja, bez reguł; 60 dok.) | — | 0,861 | 0,784 | — | 60 na 60, ok. 1000× więcej tokenów |

Pomiar na wersji rc4 (bez zmian w kodzie, tylko `model:` i `--llm`), dwa przebiegi, rozrzut 0. Model jest ostatnią deską ratunku: na naszych zbiorach pytany 5 razy na 300 dokumentów; zysk widać na trudniejszym zbiorze kontrolnym (data czynności, powód). Zmiana modelu to jedna linia `model:` w `config/llm.yaml` (albo `LLM_MODEL` w `.env`).

**Klucz w pliku `.env` (wzór: `.env.example`); bez klucza działa tryb regułowy.** Bez sieci, z `LLM_ENABLED=0` albo z `--llm off` również działają same reguły. Po nieudanym wywołaniu (timeout, 401/429, brak sieci) model jest wyłączany do końca przebiegu.

## OCR i wydajność
- **OCR jest lokalny**: Tesseract (`tesseract -l pol`) uruchamiany jako proces na tym samym komputerze, bez modelu językowego i bez żadnego API. Bez programu `tesseract` i bez uprawnień administratora (brak sudo) skany czyta biblioteka `tesserocr` (wbudowany Tesseract, instalowana z zależnościami Pythona) z modelem `pol` pobranym przez `start.sh` do `~/.local/share/tessdata`; wynik na skanach UZP jest identyczny (sprawdzone w kontenerze Ubuntu 24.04 bez sudo, `--cpus=2`).
- **Budżet czasu**: najpierw przetwarzane są wszystkie PDF-y z warstwą tekstową, każdy skan od razu dostaje plik `{}`, a OCR nadpisuje go po kolei. Gdy prognoza przekracza budżet (`ODW_BUDGET_S`, domyślnie 38 min), OCR przechodzi w tryb okrojony (3 pierwsze strony i ostatnia, jeden przebieg, bez LLM); po budżecie pozostałe skany zostają jako `{}`. Liczba wątków OCR wynika z rdzeni faktycznie dostępnych procesowi (także limitu `--cpus` w kontenerze).
- Czas zmierzony na laptopie (Apple M2 Pro, LLM włączony): **226 PDF (dane treningowe + 30 skanów) w ok. 2,5 min**: 196 PDF z warstwą tekstową w 31 s (0,16 s/PDF), 30 skanów w 123 s (ok. 4 s/skan, z prostowaniem i drugim przebiegiem OCR).
- Najgorszy przypadek: OCR maks. 12 stron na dokument i 60 s na stronę, limit 180 s na dokument (wtedy zapisywany jest wynik częściowy), model językowy po awarii sieci (15 s × 2 próby) lub odrzuconym kluczu wyłączony do końca przebiegu; przy limicie zapytań (HTTP 429/503) program czeka zgodnie z `Retry-After` (łącznie maks. 5 min). Limit konkursowy (150 PDF w 45 min) jest spełniony z dużym zapasem.

## Uruchomienie w Dockerze (alternatywa)
```bash
docker build -t odw . && docker run --rm --env-file .env -v "$PWD/input:/app/input" -v "$PWD/output:/app/output" odw
```
Obraz zawiera Tesseracta z językiem polskim; `--env-file .env` przekazuje klucz modelu językowego (bez pliku `.env` pomiń tę opcję: działają same reguły).

## Interfejs WWW (podgląd wyników)
`pip install -r gui/requirements.txt`, potem `python -m gui` i http://localhost:8000 (szczegóły, także WSL: `gui/README.md`): po lewej PDF, po prawej JSON; najechanie na pole podświetla jego miejsce w dokumencie. Działa offline, pliki nie opuszczają komputera.

## Struktura
```
start.sh, main.py   # uruchomienie
src/odw/            # silnik: textio (PDF/OCR), classify, fields (typy pól), names, normalize, evidence, llm, pipeline
config/classes/     # definicje klas (YAML): odwolanie, pelnomocnictwo, przelew
config/reject.yaml  # reguły odrzucenia dokumentów obcych
config/case_rules.yaml, config/mappings/  # kontrola formalna sprawy, eksporty CSV
config/dictionaries/, config/llm.yaml
examples/klasy/     # przykład nowej klasy (rozszerzalność)
eval/               # metryka UZP, bramka jakości, perturbacje; scripts/ (test czystego klonu, demo)
gui/                # interfejs WWW
data/               # dane treningowe UZP, skany, zbiory syntetyczne
docs/spec/          # specyfikacja modelu danych od UZP
```
