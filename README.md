# Odwołania2JSON

Automatyczna klasyfikacja i ekstrakcja danych z dokumentów PDF spraw odwoławczych KIO (odwołanie, pełnomocnictwo, potwierdzenie przelewu) do ustrukturyzowanego JSON.

> README produktu: instrukcja instalacji, uruchomienia (CLI), konfiguracji LLM, architektura i dodawanie nowych klas dokumentów zostaną uzupełnione wraz z implementacją.

## Struktura
```
input/     # pliki wejściowe: input/<case>/*.pdf
output/    # wyniki: output/<case>/<nazwa_pdf>.json
config/    # konfiguracja klas dokumentów, słowniki, LLM
docs/spec/ # specyfikacja modelu danych od UZP
data/      # dane treningowe
```

## Model językowy (opcjonalny dodatek do reguł)
Rdzeniem są reguły z `config/classes/*.yaml`. Model językowy uzupełnia tylko te pola, których reguły nie znalazły, i nigdy nie nadpisuje wyniku reguły.

| | |
|---|---|
| Model | `ministral-8b-2512` (Mistral AI), ok. 8 mld parametrów, open-weight, licencja Apache-2.0 |
| Endpoint | `https://api.eu.mistral.ai/v1` (region UE), API zgodne z OpenAI, klient w bibliotece standardowej |
| Pola | `OdwolanieKIO.czynnosc_powod_id` (zamknięta lista etykiet słownych, odrzucana bez słowa-dowodu w tekście), `OdwolanieKIO.czynnosc_dzien` (data musi występować w wycinku), `ZamowieniePubliczne.tytul` (tylko cytat dosłowny) |
| Wejście | wycinek pierwszego zarzutu odwołania (≤1500 znaków), a nie cały dokument |
| Klasyfikacja | wyłącznie reguły (`classify_tiebreak: false`) |

**Klucz w pliku `.env` (wzór: `.env.example`); bez klucza działa tryb regułowy.** Konfiguracja: `config/llm.yaml` oraz zmienne `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` (środowisko albo `.env`).
Bez klucza, bez sieci, z `LLM_ENABLED=0` albo z `--llm off` program działa w trybie samych reguł. Po nieudanym wywołaniu (timeout, 401/429, brak sieci) model jest wyłączany do końca przebiegu.

## OCR i wydajność
- **OCR jest lokalny**: Tesseract (`tesseract -l pol`) uruchamiany jako proces na tym samym komputerze, bez modelu językowego i bez żadnego API. Strony skanu są rozpoznawane równolegle (jeden proces na stronę, do 8 naraz).
- Brak Tesseracta z językiem polskim: `start.sh` próbuje go doinstalować (Debian/Ubuntu/WSL) albo pobrać sam model `pol`. Jeśli się nie uda, wypisuje wyraźne ostrzeżenie, a program na końcu podaje, ile skanów zostało nieodczytanych.
- Czas zmierzony na laptopie (Apple M2 Pro, LLM włączony): **206 PDF (dane treningowe + 30 skanów) w 60 s**, średnio 0,3 s/PDF. Dokument tekstowy zajmuje ok. 0,1–0,2 s, a 7-stronicowy skan ok. 5,5 s.
- Ograniczenia najgorszego przypadku: OCR maks. 12 stron na dokument i 60 s na stronę, limit 180 s na dokument (wtedy zapisywany jest wynik częściowy), a model językowy po pierwszej awarii (timeout 15 s × 2 próby) wyłącza się do końca przebiegu. Limit konkursowy (150 PDF w 45 min, średnio 18 s/PDF) jest więc spełniony z dużym zapasem.
