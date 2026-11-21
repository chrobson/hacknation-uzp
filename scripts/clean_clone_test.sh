#!/usr/bin/env bash
# Test "czystego klonu": czy jury uruchomi aplikację jedną komendą na świeżym Ubuntu (WSL) i dostanie te same wyniki.
#
#   bash scripts/clean_clone_test.sh [REF]      (domyślnie REF=HEAD; testowany jest stan zacommitowany)
#
# 1. git archive REF -> katalog ze spacją w nazwie na tym komputerze, data/train -> input/, data/scans -> input/scans/,
#    bash start.sh  (wynik referencyjny dla PDF-ów z warstwą tekstową)
# 2. to samo w kontenerze ubuntu:24.04 (bez Pythona, bez uv, bez tesseracta; tylko curl): bity exec usunięte jak po
#    rozpakowaniu zip-a, start.sh wywołany przez "bash start.sh" -> sam instaluje tesseract-ocr-pol przez apt (root),
#    uv instaluje się sam i pobiera Pythona 3.13
# 3. (FALLBACK=1, domyślnie) to samo w python:3.13-slim z ODW_NO_UV=1 -> ścieżka python3.13 + venv + pip (+ apt tesseract)
# 4. porównanie bajt po bajcie:
#    - ubuntu-uv vs python-pip: cały output (także skany; oba z tesseractem 5.x z Debiana/Ubuntu); różnica = FAIL
#    - lokalny vs kontenery: PDF-y z warstwą tekstową (wszystko poza scans/) muszą być identyczne; różnica = FAIL;
#      różnice na skanach tylko raportowane (inna wersja tesseracta / brak języka pol lokalnie)
#    - liczba skanów z niepustym wynikiem (nie "{}") w każdym przebiegu
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
tar -tf "$WORK/repo.tar" | grep -q '^data/scans/'

# Każda kopia: rozpakowane archiwum w katalogu ze spacjami + data/train skopiowane do input/ + data/scans do input/scans/
# (układ input/scans/<kategoria>/<NNNN>/<NNNN>.pdf, GT .json obok jest ignorowany) + brak output/.
prepare() {  # $1 = katalog docelowy
    mkdir -p "$1"
    tar -xf "$WORK/repo.tar" -C "$1"
    cp -R "$1/data/train/." "$1/input/"
    mkdir -p "$1/input/scans"
    cp -R "$1/data/scans/." "$1/input/scans/"
    rm -rf "$1/output"
    if grep -q $'\r' "$1/start.sh"; then echo "FAIL: start.sh w archiwum ma CRLF"; exit 1; fi
}

log "uruchomienie lokalne ($(uname -sm))"
LOCAL="$WORK/local/my repo copy"
prepare "$LOCAL"
(cd "$LOCAL" && bash start.sh)
test -d "$LOCAL/output"
N_LOCAL="$(find "$LOCAL/output" -type f -name '*.json' | wc -l | tr -d ' ')"
N_SCANS="$(find "$LOCAL/input/scans" -type f -iname '*.pdf' | wc -l | tr -d ' ')"
echo "lokalnie: $N_LOCAL plików JSON (w tym skany: $N_SCANS)"
[ "$N_LOCAL" -gt 0 ] || { echo "FAIL: brak wyników lokalnie"; exit 1; }

STATUS=0
SUMMARY=()
# Liczba skanów, dla których wynik nie jest pustym {} (OCR zadziałał i dokument został rozpoznany).
scans_nonempty() {  # $1 = katalog output
    local n=0 f
    while IFS= read -r -d '' f; do
        [ "$(tr -d '[:space:]' < "$f")" = "{}" ] || n=$((n + 1))
    done < <(find "$1/scans" -type f -name '*.json' -print0 2>/dev/null)
    printf '%s' "$n"
}
report_scans() {  # $1 = nazwa, $2 = katalog output
    local n; n="$(scans_nonempty "$2")"
    echo "skany [$1]: $n/$N_SCANS z niepustym wynikiem"
    SUMMARY+=("skany [$1]: $n/$N_SCANS niepustych")
}
report_scans local "$LOCAL/output"

# Kontener vs lokalnie: PDF-y z warstwą tekstową muszą się zgadzać bajt po bajcie, skany tylko raportujemy.
compare_local() {  # $1 = nazwa, $2 = katalog z kopią
    local n_text
    n_text="$(find "$LOCAL/output" -type f -name '*.json' -not -path "$LOCAL/output/scans/*" | wc -l | tr -d ' ')"
    if diff -r -x scans "$LOCAL/output" "$2/output" >"$WORK/diff-$1.txt"; then
        echo "OK [$1 vs lokalny]: PDF-y z warstwą tekstową identyczne bajt po bajcie ($n_text plików)"
    else
        echo "FAIL [$1 vs lokalny]: output PDF-ów z warstwą tekstową różni się:"
        head -50 "$WORK/diff-$1.txt"
        STATUS=1
    fi
    test -d "$2/output/scans" || { echo "FAIL [$1]: brak output/scans"; STATUS=1; return; }
    if diff -rq "$LOCAL/output/scans" "$2/output/scans" >"$WORK/diff-$1-scans.txt"; then
        echo "info [$1 vs lokalny]: skany identyczne"
    else
        echo "info [$1 vs lokalny]: skany różnią się w $(wc -l < "$WORK/diff-$1-scans.txt" | tr -d ' ') plikach (dozwolone: inna wersja tesseracta / brak pol lokalnie)"
        head -10 "$WORK/diff-$1-scans.txt"
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
    command -v tesseract >/dev/null && { echo "nieoczekiwanie jest tesseract"; exit 1; } || true
    mkdir -p "/home/jury/Moje Dokumenty"
    cp -R "/host/repo with spaces" "/home/jury/Moje Dokumenty/odw repo"
    cd "/home/jury/Moje Dokumenty/odw repo"
    bash start.sh
    tesseract --list-langs 2>/dev/null | grep -qx pol || { echo "FAIL: start.sh nie zainstalował tesseract-ocr-pol"; exit 1; }
    echo "kontener: $(tesseract --version 2>&1 | head -n 1)"
    rm -rf "/host/repo with spaces/output"
    cp -R output "/host/repo with spaces/output"
'
compare_local ubuntu-uv "$UB"
report_scans ubuntu-uv "$UB/output"

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
        tesseract --list-langs 2>/dev/null | grep -qx pol || { echo "FAIL: start.sh nie zainstalował tesseract-ocr-pol"; exit 1; }
        echo "kontener: $(tesseract --version 2>&1 | head -n 1)"
        rm -rf "/host/repo with spaces/output"
        cp -R output "/host/repo with spaces/output"
    '
    compare_local python-pip "$PY"
    report_scans python-pip "$PY/output"
    # Oba kontenery mają tesseract 5.x z Debiana/Ubuntu: cały output (ze skanami) musi być identyczny.
    if diff -r "$UB/output" "$PY/output" >"$WORK/diff-ub-py.txt"; then
        echo "OK [ubuntu-uv vs python-pip]: cały output identyczny bajt po bajcie (z $N_SCANS skanami)"
    else
        echo "FAIL [ubuntu-uv vs python-pip]: output różni się:"
        head -50 "$WORK/diff-ub-py.txt"
        STATUS=1
    fi
fi

log "wynik"
printf '%s\n' "${SUMMARY[@]}"
if [ "$STATUS" = 0 ]; then echo "PASS: clean clone test"; else echo "FAIL: clean clone test"; fi
exit "$STATUS"
