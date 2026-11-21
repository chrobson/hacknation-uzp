#!/usr/bin/env bash
# Odwołania2JSON: uruchomienie jedną komendą.
#   bash start.sh                     czyta ./input/<sprawa>/*.pdf, zapisuje ./output/<sprawa>/*.json
#   bash start.sh --input X --output Y
# Działa na Linux / WSL (Ubuntu) / macOS. Nie wymaga bitu wykonywalnego (wywołuj przez "bash start.sh").
# 1) uv (instalowany automatycznie, jeśli go brak) + uv.lock -> Python 3.13 i dokładnie przypięte zależności,
# 2) fallback: python3.13 z systemu + venv + pip install -r requirements.txt.
# Zmienne: ODW_NO_UV=1 wymusza ścieżkę 2 (pip).
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
