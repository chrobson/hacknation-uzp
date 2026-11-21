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
