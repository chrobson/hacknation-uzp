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

Konfiguracja: `config/llm.yaml` oraz zmienne `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` w środowisku lub w `.env` (wzór: `.env.example`).
Bez klucza, bez sieci, z `LLM_ENABLED=0` albo z `--llm off` program działa w trybie samych reguł. Po nieudanym wywołaniu (timeout, 401/429, brak sieci) model jest wyłączany do końca przebiegu.
