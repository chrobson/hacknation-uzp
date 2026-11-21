# RUN

Komenda (w katalogu `/opt/solution`, bez interakcji):

```bash
sudo bash start.sh
```

- Wejście: `/opt/solution/input/` (PDF-y, także w podfolderach spraw). Wynik: `/opt/solution/output/<ta sama ścieżka>.json`; dokument spoza trzech klas daje `{}`.
- Środowisko zostało przygotowane wcześniej (`sudo bash scripts/vm_setup.sh`): Python 3.13 z zależnościami w `/opt/solution/.runtime/`, Tesseract z językiem polskim z apt. Komenda niczego nie pobiera.
- Usługi zewnętrzne: wyłącznie **Mistral AI, region UE** (`https://api.eu.mistral.ai/v1`), model `ministral-8b-2512` (ok. 8 mld parametrów, open-weight, Apache-2.0), klucz w `/opt/solution/.env` (`LLM_API_KEY`). Model jest pytany tylko o pola, których reguły nie znalazły (zwykle kilka zapytań na sto dokumentów). Bez sieci lub bez klucza program działa w trybie regułowym.
- OCR jest lokalny (Tesseract), bez żadnego API.
- Czas: ok. 0,2 s na PDF z tekstem, kilka sekund na stronę skanu; globalny budżet czasu (`ODW_BUDGET_S`, domyślnie 38 min) chroni przed niekompletnym wynikiem.
