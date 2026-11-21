#!/usr/bin/env bash
# Odwołania2JSON: uruchomienie jedną komendą.
#   bash start.sh                     czyta ./input/<sprawa>/*.pdf, zapisuje ./output/<sprawa>/*.json
#   bash start.sh --input X --output Y
# Działa na Linux / WSL (Ubuntu) / macOS. Nie wymaga bitu wykonywalnego (wywołuj przez "bash start.sh").
# 1) uv (instalowany automatycznie, jeśli go brak) + uv.lock -> Python 3.13 i dokładnie przypięte zależności,
# 2) fallback: python3.13 z systemu + venv + pip install -r requirements.txt.
# 0) OCR: sprawdza tesseract + język pol; na Debianie/Ubuntu (WSL) doinstalowuje go (root / sudo bez hasła), inaczej podpowiedź.
# Zmienne: ODW_NO_UV=1 wymusza ścieżkę 2 (pip), ODW_NO_OCR_INSTALL=1 wyłącza instalację tesseracta.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

log() { printf '[start.sh] %s\n' "$*" >&2; }

# Zmienne z .env (np. LLM_API_KEY); CRLF z Windows usuwany, istniejące zmienne środowiska mają pierwszeństwo.
if [ -f .env ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%$'\r'}"
        case "$line" in ''|'#'*) continue ;; esac
        key="${line%%=*}"; val="${line#*=}"
        key="${key#export }"; key="${key//[[:space:]]/}"
        [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
        if [ -z "${!key+x}" ]; then
            val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
            export "$key=$val"
        fi
    done < .env
fi

# OCR (skany bez warstwy tekstowej): tesseract z językiem polskim. Bez niego aplikacja działa dalej,
# a skany dają {} (ostrzeżenie w logu). Na Debianie/Ubuntu (WSL) instalujemy automatycznie, jeśli się da
# (root albo sudo bez hasła); w pozostałych przypadkach tylko podpowiedź. ODW_NO_OCR_INSTALL=1 wyłącza instalację.
# TESSDATA_PREFIX (np. z .env) jest respektowany przez samego tesseracta.
have_tesseract_pol() {
    command -v tesseract >/dev/null 2>&1 || return 1
    tesseract --list-langs 2>/dev/null | tr -d '\r' | grep -qx 'pol'
}

ocr_banner() {
    log "=================================================================================="
    log "!!! OCR NIEDOSTĘPNY: brak tesseracta z językiem polskim (pol).                   !!!"
    log "!!! Skany (PDF bez warstwy tekstowej) NIE zostaną odczytane i dadzą {}.          !!!"
    log "!!! Debian/Ubuntu/WSL: sudo apt-get install -y tesseract-ocr tesseract-ocr-pol   !!!"
    log "!!! macOS: brew install tesseract tesseract-lang                                 !!!"
    log "=================================================================================="
}

# model pol do ~/.local/share/tessdata (bez roota, każdy system); używa go tesseract albo zapasowo tesserocr
download_pol_model() {
    [ "${ODW_NO_OCR_INSTALL:-0}" = 1 ] && return 1
    local dir="$HOME/.local/share/tessdata" url="https://github.com/tesseract-ocr/tessdata_fast/raw/main/pol.traineddata"
    mkdir -p "$dir" || return 1
    if [ ! -s "$dir/pol.traineddata" ]; then
        log "brak modelu pol dla tesseracta, pobieram do $dir ..."
        if command -v curl >/dev/null 2>&1; then curl -fsSL -o "$dir/pol.traineddata.part" "$url" || return 1
        elif command -v wget >/dev/null 2>&1; then wget -qO "$dir/pol.traineddata.part" "$url" || return 1
        else return 1; fi
        mv "$dir/pol.traineddata.part" "$dir/pol.traineddata"
    fi
    export TESSDATA_PREFIX="$dir"
}

# tesseract jest, brakuje tylko pol: pobierz sam model
fetch_pol_model() {
    command -v tesseract >/dev/null 2>&1 || return 1
    download_pol_model && have_tesseract_pol
}

ensure_tesseract() {
    have_tesseract_pol && return 0
    fetch_pol_model && { log "OCR gotowy (model pol w $TESSDATA_PREFIX)"; return 0; }
    local what="tesseract"
    command -v tesseract >/dev/null 2>&1 && what="język polski (pol) dla tesseracta"
    case "$(uname -s)" in
        Darwin)
            log "UWAGA: brak: $what; skany (PDF bez warstwy tekstowej) dadzą {}. Aby włączyć OCR:"
            log "    brew install tesseract tesseract-lang"
            log "  albo pobierz pol.traineddata (https://github.com/tesseract-ocr/tessdata_fast/raw/main/pol.traineddata)"
            log "  do ~/.local/share/tessdata i ustaw TESSDATA_PREFIX=\"\$HOME/.local/share/tessdata\" (np. w .env)"
            return 0 ;;
        Linux) ;;
        *)
            log "UWAGA: brak: $what; skany dadzą {}. Zainstaluj tesseract z językiem polskim (pol)."
            return 0 ;;
    esac
    if ! command -v apt-get >/dev/null 2>&1; then
        log "UWAGA: brak: $what; skany dadzą {}. Zainstaluj tesseract z językiem polskim (pol) menedżerem pakietów systemu."
        return 0
    fi
    local sudo=""
    if [ "$(id -u)" != 0 ]; then
        if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
            sudo="sudo"
        else
            log "UWAGA: brak: $what; skany (PDF bez warstwy tekstowej) dadzą {}. Aby włączyć OCR, uruchom raz:"
            log "    sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-pol"
            log "  i ponownie bash start.sh. Kontynuuję bez OCR."
            return 0
        fi
    fi
    local p="${sudo:+sudo }"
    local cmd="${p}apt-get update && ${p}apt-get install -y tesseract-ocr tesseract-ocr-pol"
    if [ "${ODW_NO_OCR_INSTALL:-0}" = 1 ]; then
        log "UWAGA: brak: $what (ODW_NO_OCR_INSTALL=1, nie instaluję); skany dadzą {}. Polecenie: $cmd"
        return 0
    fi
    log "brak: $what, instaluję: $cmd ..."
    if $sudo env DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null \
        && $sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
            tesseract-ocr tesseract-ocr-pol >/dev/null; then
        if have_tesseract_pol; then
            log "OCR gotowy: $(tesseract --version 2>&1 | head -n 1)"
            return 0
        fi
    fi
    log "UWAGA: instalacja tesseracta nie powiodła się; skany dadzą {}. Spróbuj ręcznie: $cmd"
    return 0
}

ensure_tesseract || true
# Bez programu tesseract (np. brak sudo): OCR zapasowo przez bibliotekę tesserocr (wbudowany Tesseract, instalowana
# z zależnościami Pythona) z modelem pol pobranym bez roota. Program sam wypisze ostrzeżenie, jeśli skany zostaną nieodczytane.
if ! have_tesseract_pol; then
    if download_pol_model; then
        log "OCR: brak programu tesseract; skany przeczyta biblioteka tesserocr z modelem pol ($TESSDATA_PREFIX)"
    else
        ocr_banner
    fi
fi

STATE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/odwolania2json"
# Repozytorium na dysku Windows (/mnt/c/...) w WSL: venv trzymamy w systemie plików Linuksa (szybciej, bez problemów z symlinkami).
VENV_ON_LINUX_FS=0
case "$HERE" in /mnt/*) VENV_ON_LINUX_FS=1 ;; esac
path_key() { printf '%s' "$HERE" | cksum | cut -d' ' -f1; }

find_uv() {
    if command -v uv >/dev/null 2>&1; then command -v uv; return 0; fi
    for c in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv" "${XDG_BIN_HOME:-}/uv"; do
        [ -n "$c" ] && [ -x "$c" ] && { printf '%s\n' "$c"; return 0; }
    done
    return 1
}

install_uv() {
    log "brak uv, instaluję (https://astral.sh/uv) ..."
    if command -v curl >/dev/null 2>&1; then
        curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >&2
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >&2
    else
        log "brak curl i wget, nie mogę zainstalować uv"
        return 1
    fi
}

run_with_uv() {
    local uv
    uv="$(find_uv)" || { install_uv && uv="$(find_uv)"; } || return 1
    export UV_LINK_MODE=copy
    if [ "$VENV_ON_LINUX_FS" = 1 ] && [ -z "${UV_PROJECT_ENVIRONMENT:-}" ]; then
        export UV_PROJECT_ENVIRONMENT="$STATE_DIR/venv-uv-$(path_key)"
    fi
    # uv sam pobierze Pythona 3.13, jeśli nie ma go w systemie; --frozen = dokładnie wersje z uv.lock.
    "$uv" sync --python 3.13 --frozen --no-dev --quiet || return 1
    exec "$uv" run --python 3.13 --frozen --no-dev --no-sync main.py "$@"
}

find_python313() {
    for c in python3.13 python3 python; do
        if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 13) else 1)' 2>/dev/null; then
            command -v "$c"; return 0
        fi
    done
    return 1
}

run_with_pip() {
    local py venv stamp want
    py="$(find_python313)" || {
        log "BŁĄD: nie udało się użyć uv, a w systemie nie ma Pythona 3.13."
        log "Zainstaluj uv: curl -LsSf https://astral.sh/uv/install.sh | sh   (albo python3.13 + python3.13-venv) i uruchom ponownie."
        exit 1
    }
    venv="$STATE_DIR/venv-pip-$(path_key)"
    stamp="$venv/.requirements.cksum"
    want="$(cksum < requirements.txt)"
    if [ ! -x "$venv/bin/python" ] || [ "$(cat "$stamp" 2>/dev/null)" != "$want" ]; then
        log "tworzę środowisko: $venv ($py)"
        mkdir -p "$(dirname "$venv")"
        "$py" -m venv "$venv" || { log "BŁĄD: python -m venv nie działa (Ubuntu: sudo apt install python3.13-venv)"; exit 1; }
        "$venv/bin/python" -m pip install --quiet --disable-pip-version-check -r requirements.txt
        printf '%s' "$want" > "$stamp"
    fi
    exec "$venv/bin/python" main.py "$@"
}

if [ "${ODW_NO_UV:-0}" != 1 ]; then
    run_with_uv "$@" || log "uv nie zadziałał, próbuję python3.13 + pip ..."
fi
run_with_pip "$@"
