# Odwołania2JSON – interfejs WWW (GUI)

Lokalna aplikacja do podglądu wyników: **po lewej dokument źródłowy (PDF), po prawej wyekstrahowane dane (JSON)**.
Najechanie na pole podświetla jego miejsce w PDF, kliknięcie przewija dokument do tego fragmentu
i pokazuje cytat z kontekstem. Działa w pełni offline – pliki nie opuszczają komputera.

## Uruchomienie

Z katalogu głównego repozytorium (Python 3.11+, zalecany 3.13):

```bash
python3 -m venv gui/.venv
gui/.venv/bin/pip install -r gui/requirements.txt     # zależności pipeline'u + FastAPI/uvicorn
gui/.venv/bin/python -m gui                           # http://localhost:8000
```

Opcje: `--port 8000`, `--host 127.0.0.1`, `--open` (otwiera przeglądarkę).

Jeżeli zależności z `requirements.txt` są już zainstalowane w aktywnym środowisku, wystarczy
`pip install -r gui/requirements.txt` i `python -m gui`.

### Windows / WSL

W WSL2 uruchom dokładnie tak samo (`python3 -m gui`) i otwórz w przeglądarce Windows `http://localhost:8000`.
Jeśli przekierowanie `localhost` jest wyłączone w konfiguracji WSL, uruchom `python3 -m gui --host 0.0.0.0`
i wejdź na adres IP maszyny WSL (`hostname -I`). Natywnie w Windows: `gui\.venv\Scripts\python -m gui`.

## Jak korzystać

1. **Wgraj PDF** (przycisk albo przeciągnij pliki na okno) – jeden lub wiele plików jednej sprawy,
   albo **wybierz sprawę** z folderu `input/` (lub `data/train/`) i kliknij **Przetwórz**.
2. Zakładki u góry to dokumenty sprawy, każdy z plakietką klasy: *Odwołanie*, *Pełnomocnictwo*,
   *Potwierdzenie przelewu* albo *Nie rozpoznano* (wynik `{}` zgodnie ze specyfikacją).
3. Prawy panel – pola JSON pogrupowane jak w schemacie UZP:
   - niebieskie `s. N` – wartość zlokalizowana w PDF (najedź = podświetlenie, kliknij = przewinięcie + cytat),
   - fioletowe `wyliczone` – wartość wyliczona (np. id powodu ze słownika, flaga 0/1), bez cytatu w PDF,
   - szare `null` – pola nie znaleziono w dokumencie.
   Kliknięcie ramki w PDF zaznacza odpowiadające pole. Klawisze ↑/↓ przechodzą między polami, Esc odznacza.
4. **Pobierz JSON** – plik wynikowy dokładnie taki, jak zapisuje CLI; **Pobierz wszystkie (ZIP)** – cała sprawa.
   Widok **JSON** pokazuje surową zawartość pliku.

## Jak to działa

- Backend: FastAPI + uvicorn (`gui/app.py`), frontend: zwykły HTML/CSS/JS bez kroku budowania (`gui/static/`).
- Każdy przebieg tworzy katalog `gui/.runs/<id>/` z układem jak w CLI (`input/<sprawa>/`, `output/`, `evidence/`)
  i uruchamia **niezmieniony pipeline jako podproces**: `python main.py --input … --output … --evidence …`.
  GUI nie duplikuje logiki ekstrakcji; wyniki są identyczne z trybem wsadowym.
- Podświetlenia pochodzą z plików evidence (`<plik>.evidence.json`): strona, cytat i ramki słów we współrzędnych
  pdfplumber (punkty PDF, początek w lewym górnym rogu). Na stronie wyrenderowanej w skali `s`:
  `x = x0·s`, `y = top·s` – bez odwracania osi Y.
- Przechowywanych jest 30 ostatnich przebiegów (lista **Historia**); adres `#<id>/<nr>` pozwala wrócić do dokumentu.

Zmienne środowiskowe (opcjonalnie): `ODW_PYTHON` (interpreter pipeline'u, domyślnie bieżący),
`ODW_GUI_RUNS` (katalog przebiegów), `ODW_GUI_KEEP_RUNS` (domyślnie 30), `ODW_GUI_MAX_UPLOAD_MB` (domyślnie 50).

## Licencje komponentów zewnętrznych

PDF renderowany jest przez **[PDF.js](https://github.com/mozilla/pdf.js)** (Mozilla), dołączony lokalnie
w `gui/static/vendor/pdfjs/` (pdfjs-dist 4.10.38, build `legacy`, wraz z `cmaps/` i `standard_fonts/`),
na licencji **Apache License 2.0** – pełny tekst w `gui/static/vendor/pdfjs/LICENSE`.
