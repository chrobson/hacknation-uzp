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
| synth-dev (120 dokumentów o innych układach, także wielopodmiotowe) | 0,940 | 0,940 |
| skany UZP przez OCR (30 dokumentów) | 0,817 | 0,830 |

Numery rachunków są zapisywane tak, jak w dokumencie: z prefiksem `PL`, jeśli dokument go podaje (bez spacji, np. `PL61109010140000071219812874`), w przeciwnym razie 26 cyfr. Tak potwierdził UZP (21.11.2026); lokalne dane wzorcowe poprawiono skryptem `eval/gt_account_pl.py`, bo część wzorcowych JSON-ów UZP pomijała `PL`.

Dokumenty obce (ogłoszenia, wyroki KIO, SWZ, faktury, umowy, pisma podobne do klas): 0 przyjętych na 36. Bramka jakości (`make gate`, 9 testów, m.in. brak regresji, 0 fałszywych przyjęć, niezależność od nazw plików, praca bez LLM, < 1 s/dokument) pilnuje każdej zmiany.

## Jak to działa
1. **Tekst**: `pdfplumber` (słowa ze współrzędnymi); PDF bez warstwy tekstowej → lokalny OCR (Tesseract `pol`, strony równolegle). Dwukolumnowe nagłówki stron są czytane kolumnami.
2. **Klasyfikacja**: każda klasa w YAML ma kotwice wymagane, ważone sygnały i próg; wspólne reguły odrzucenia (`config/reject.yaml`) wyłapują dokumenty obce. Dla skanów z błędami OCR działa dodatkowo rozmyte głosowanie słów kluczowych.
3. **Ekstrakcja**: pola opisane w YAML typami wielokrotnego użytku (`labeled`, `pattern`, `near`, `names`, `account`, `keyword_map`, `first_line`, `exists`, …), z sekcjami dokumentu, listami (np. kilku zamawiających / mocodawców) i normalizacją (daty, kwoty, NIP/KRS/REGON, mianownik imion i nazwisk).
4. **LLM (opcjonalnie)**: tylko dla pól, które reguły zostawiły puste, z zamkniętym słownikiem odpowiedzi i walidacją; awaria → reguły.
5. **Wynik**: JSON zgodny ze schematem UZP + osobno plik dowodów (strona, cytat, ramki) dla każdej wartości.

## Rozszerzalność: nowa klasa = jeden plik YAML
Kod nie zna nazw klas ani pól: wszystko jest w `config/classes/*.yaml` (klasyfikacja, sekcje, pola, szablon wyniku) i `config/dictionaries/`. Przykład klasy spoza zadania (wezwanie KIO do uzupełnienia braków), bez żadnej zmiany w kodzie:
```bash
bash scripts/demo_nowa_klasa.sh
# albo: bash start.sh --classes-dir examples/klasy --input examples/klasy/przyklady --output /tmp/wynik
```
Plik `examples/klasy/wezwanie_do_uzupelnienia.yaml` (~40 linii) definiuje kotwice klasyfikacji, sekcję adresata i 6 pól. Klasa celowo leży poza `config/classes`, żeby nie była aktywna podczas oceny.

## Model językowy (opcjonalny dodatek do reguł)
| | |
|---|---|
| Model | `ministral-8b-2512` (Mistral AI), ok. 8 mld parametrów, open-weight, licencja Apache-2.0; przełączalny jednym wpisem `model:` w `config/llm.yaml` (np. `ministral-3b-2512`) |
| Endpoint | `https://api.eu.mistral.ai/v1` (region UE), API zgodne z OpenAI, klient w bibliotece standardowej |
| Pola | `OdwolanieKIO.czynnosc_powod_id` (zamknięta lista etykiet słownych → numer ze słownika), `OdwolanieKIO.czynnosc_dzien`, `ZamowieniePubliczne.tytul` (tylko cytat występujący dosłownie w tekście) |
| Kiedy | wyłącznie gdy żadna reguła nie dała wartości; nigdy nie nadpisuje reguły |
| Wejście | wycinek pierwszego zarzutu odwołania (≤1500 znaków), a nie cały dokument |
| Klasyfikacja | wyłącznie reguły (`classify_tiebreak: false`) |

**Klucz w pliku `.env` (wzór: `.env.example`); bez klucza działa tryb regułowy.** Bez sieci, z `LLM_ENABLED=0` albo z `--llm off` również działają same reguły. Po nieudanym wywołaniu (timeout, 401/429, brak sieci) model jest wyłączany do końca przebiegu.

## OCR i wydajność
- **OCR jest lokalny**: Tesseract (`tesseract -l pol`) uruchamiany jako proces na tym samym komputerze, bez modelu językowego i bez żadnego API.
- Czas zmierzony na laptopie (Apple M2 Pro, LLM włączony): **206 PDF (dane treningowe + 30 skanów) w 60 s**, średnio 0,3 s/PDF; dokument tekstowy ok. 0,1–0,2 s, 7-stronicowy skan ok. 5,5 s.
- Najgorszy przypadek: OCR maks. 12 stron na dokument i 60 s na stronę, limit 180 s na dokument (wtedy zapisywany jest wynik częściowy), model językowy po pierwszej awarii (15 s × 2 próby) wyłączony do końca przebiegu. Limit konkursowy (150 PDF w 45 min) jest spełniony z dużym zapasem.

## Interfejs WWW (podgląd wyników)
`pip install -r gui/requirements.txt`, potem `python -m gui` i http://localhost:8000 (szczegóły, także WSL: `gui/README.md`): po lewej PDF, po prawej JSON; najechanie na pole podświetla jego miejsce w dokumencie. Działa offline, pliki nie opuszczają komputera.

## Struktura
```
start.sh, main.py   # uruchomienie
src/odw/            # silnik: textio (PDF/OCR), classify, fields (typy pól), names, normalize, evidence, llm, pipeline
config/classes/     # definicje klas (YAML): odwolanie, pelnomocnictwo, przelew
config/reject.yaml  # reguły odrzucenia dokumentów obcych
config/dictionaries/, config/llm.yaml
examples/klasy/     # przykład nowej klasy (rozszerzalność)
eval/               # metryka UZP, bramka jakości, perturbacje; scripts/ (test czystego klonu, demo)
gui/                # interfejs WWW
data/               # dane treningowe UZP, skany, zbiory syntetyczne
docs/spec/          # specyfikacja modelu danych od UZP
```
