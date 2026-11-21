#!/usr/bin/env bash
# Jednorazowe przygotowanie maszyny oceniającej (Ubuntu 24.04, VM UZP): wszystko, co wymaga sieci, dzieje się TUTAJ,
# żeby późniejsze `sudo bash start.sh` (komenda z RUN.md) niczego nie pobierało. Skrypt jest idempotentny.
#
#   cd /opt/solution && sudo bash scripts/vm_setup.sh
#
# 1. apt: tesseract-ocr + tesseract-ocr-pol (OCR skanów, lokalnie), curl, ca-certificates
# 2. uv + Python 3.13 + zależności z uv.lock (z Morfeuszem i tesserocr) w ./.runtime/ (niezależnie od HOME / sudo)
# 3. rozgrzewka na jednej sprawie z data/train (kompilacja bajtkodu, test OCR na skanie) i sprawdzenie .env
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
log() { printf '[vm_setup] %s\n' "$*"; }
SUDO=""; [ "$(id -u)" = 0 ] || SUDO="sudo"
RT="$HERE/.runtime"

log "1/3 pakiety systemowe (tesseract z językiem polskim)"
if ! { command -v tesseract >/dev/null && tesseract --list-langs 2>/dev/null | grep -qx pol && command -v curl >/dev/null; }; then
    $SUDO apt-get update -qq
    DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq --no-install-recommends \
        tesseract-ocr tesseract-ocr-pol curl ca-certificates >/dev/null
fi
log "    $(tesseract --version 2>&1 | head -n 1), języki: $(tesseract --list-langs 2>/dev/null | tr '\n' ' ')"

log "2/3 uv + Python 3.13 + zależności w $RT"
mkdir -p "$RT/bin"
if [ ! -x "$RT/bin/uv" ]; then
    curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="$RT/bin" sh >/dev/null
fi
export UV_PYTHON_INSTALL_DIR="$RT/python" UV_PROJECT_ENVIRONMENT="$RT/venv" UV_CACHE_DIR="$RT/cache" UV_LINK_MODE=copy
"$RT/bin/uv" sync --python 3.13 --frozen --no-dev --quiet
"$RT/venv/bin/python" -c 'import pdfplumber, yaml, pypdfium2, tesserocr; print("    zależności OK")'
"$RT/venv/bin/python" -c 'import morfeusz2; morfeusz2.Morfeusz(generate=False); print("    Morfeusz2 OK")' \
    || log "    Morfeusz2 niedostępny: imiona w mianowniku z reguł (bez wpływu na działanie)"
chmod -R a+rX "$RT"

log "3/3 rozgrzewka (sprawa tekstowa + skan) i konfiguracja"
WARM="$(mktemp -d)"; trap 'rm -rf "$WARM"' EXIT
mkdir -p "$WARM/in/sprawa"
cp data/train/przyklad_01/*.pdf "$WARM/in/sprawa/"
cp data/scans/potwierdzenia/0001/0001.pdf "$WARM/in/sprawa/skan.pdf"
"$RT/venv/bin/python" main.py --input "$WARM/in" --output "$WARM/out" --no-evidence --llm off | sed 's/^/    /'
[ "$(find "$WARM/out" -name '*.json' | wc -l)" -ge 4 ] || { log "BŁĄD: rozgrzewka nie dała wyników"; exit 1; }
grep -q '"kwota"' "$WARM/out/sprawa/skan.json" || { log "BŁĄD: OCR skanu nie zadziałał"; exit 1; }
if [ -s "$HERE/.env" ] && grep -q '^LLM_API_KEY=.\+' "$HERE/.env"; then
    log "    .env z kluczem LLM: jest ($HERE/.env)"
else
    log "    UWAGA: brak $HERE/.env z LLM_API_KEY: program zadziała w trybie regułowym (wzór: .env.example)"
fi
mkdir -p "$HERE/input" "$HERE/output"
log "gotowe. Uruchomienie (RUN.md): cd $HERE && sudo bash start.sh"
