#!/usr/bin/env bash
# Test "czystego klonu": czy jury uruchomi aplikację jedną komendą na świeżym Ubuntu (WSL) i dostanie te same wyniki.
#
#   bash scripts/clean_clone_test.sh [REF]      (domyślnie REF=HEAD; testowany jest stan zacommitowany)
#
# 1. git archive REF -> katalog ze spacją w nazwie na tym komputerze, data/train -> input/, bash start.sh  (wynik referencyjny)
# 2. to samo w kontenerze ubuntu:24.04 (bez Pythona, bez uv; tylko curl): bity exec usunięte jak po rozpakowaniu zip-a,
#    start.sh wywołany przez "bash start.sh" -> uv instaluje się sam i pobiera Pythona 3.13
# 3. (FALLBACK=1, domyślnie) to samo w python:3.13-slim z ODW_NO_UV=1 -> ścieżka python3.13 + venv + pip
# 4. diff -r wyników bajt po bajcie; dowolna różnica = FAIL
#
# Zmienne: PLATFORM (domyślnie linux/amd64, jak u jury), FALLBACK=0 pomija krok 3.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REF="${1:-HEAD}"
PLATFORM="${PLATFORM:-linux/amd64}"
FALLBACK="${FALLBACK:-1}"
IMAGE_UBUNTU="ubuntu:24.04"
IMAGE_PY="python:3.13-slim"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/odw clean clone.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
log() { printf '\n=== %s\n' "$*"; }

log "archiwum $REF ($(git -C "$REPO" rev-parse --short "$REF"))"
git -C "$REPO" archive --format=tar -o "$WORK/repo.tar" "$REF"
tar -tf "$WORK/repo.tar" | grep -q '^start.sh$'
tar -tf "$WORK/repo.tar" | grep -q '^data/train/'

# Każda kopia: rozpakowane archiwum w katalogu ze spacjami + data/train skopiowane do input/ + brak output/.
prepare() {  # $1 = katalog docelowy
    mkdir -p "$1"
    tar -xf "$WORK/repo.tar" -C "$1"
    cp -R "$1/data/train/." "$1/input/"
    rm -rf "$1/output"
    if grep -q $'\r' "$1/start.sh"; then echo "FAIL: start.sh w archiwum ma CRLF"; exit 1; fi
}

log "uruchomienie lokalne ($(uname -sm))"
LOCAL="$WORK/local/my repo copy"
prepare "$LOCAL"
(cd "$LOCAL" && bash start.sh)
test -d "$LOCAL/output"
N_LOCAL="$(find "$LOCAL/output" -type f -name '*.json' | wc -l | tr -d ' ')"
echo "lokalnie: $N_LOCAL plików JSON"
[ "$N_LOCAL" -gt 0 ] || { echo "FAIL: brak wyników lokalnie"; exit 1; }

STATUS=0
compare() {  # $1 = nazwa, $2 = katalog z kopią
    if diff -r "$LOCAL/output" "$2/output" >"$WORK/diff-$1.txt"; then
        echo "OK [$1]: output identyczny bajt po bajcie ($N_LOCAL plików)"
    else
        echo "FAIL [$1]: output różni się od lokalnego:"
        head -50 "$WORK/diff-$1.txt"
        STATUS=1
    fi
}

log "kontener $IMAGE_UBUNTU ($PLATFORM): świeże Ubuntu, bez Pythona i uv, bity exec usunięte"
UB="$WORK/ubuntu/repo with spaces"
prepare "$UB"
find "$UB" -type f -exec chmod a-x {} +
docker run --rm --platform "$PLATFORM" -v "$WORK/ubuntu:/host" "$IMAGE_UBUNTU" bash -c '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null && apt-get install -y -qq --no-install-recommends curl ca-certificates >/dev/null
    command -v python3.13 >/dev/null && { echo "nieoczekiwanie jest python3.13"; exit 1; } || true
    command -v uv >/dev/null && { echo "nieoczekiwanie jest uv"; exit 1; } || true
    mkdir -p "/home/jury/Moje Dokumenty"
    cp -R "/host/repo with spaces" "/home/jury/Moje Dokumenty/odw repo"
    cd "/home/jury/Moje Dokumenty/odw repo"
    bash start.sh
    rm -rf "/host/repo with spaces/output"
    cp -R output "/host/repo with spaces/output"
'
compare ubuntu-uv "$UB"

if [ "$FALLBACK" = 1 ]; then
    log "kontener $IMAGE_PY ($PLATFORM): ścieżka zapasowa python3.13 + pip (ODW_NO_UV=1)"
    PY="$WORK/py/repo with spaces"
    prepare "$PY"
    find "$PY" -type f -exec chmod a-x {} +
    docker run --rm --platform "$PLATFORM" -e ODW_NO_UV=1 -v "$WORK/py:/host" "$IMAGE_PY" bash -c '
        set -euo pipefail
        mkdir -p "/root/dir with spaces"
        cp -R "/host/repo with spaces" "/root/dir with spaces/odw repo"
        cd "/root/dir with spaces/odw repo"
        bash start.sh
        rm -rf "/host/repo with spaces/output"
        cp -R output "/host/repo with spaces/output"
    '
    compare python-pip "$PY"
fi

log "wynik"
if [ "$STATUS" = 0 ]; then echo "PASS: clean clone test"; else echo "FAIL: clean clone test"; fi
exit "$STATUS"
