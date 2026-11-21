#!/usr/bin/env bash
# Test "czystego klonu" z modelem językowym: czy start.sh na świeżym Ubuntu czyta .env, woła LLM (Mistral EU)
# i czy bez sieci kończy przebieg na samych regułach.
#
#   bash scripts/clean_clone_llm_test.sh [REF] [ENV_FILE]     (domyślnie REF=HEAD, ENV_FILE=./.env)
#
# Klucz z ENV_FILE trafia tylko do kopii roboczej w katalogu tymczasowym (usuwanej na końcu); nigdy nie jest wypisywany.
# 1. lokalnie: kopia REF + .env, bash start.sh na data/synth/dev (PDF-y z warstwą tekstową; na data/train reguły wypełniają wszystko i LLM nie jest wołany) -> wynik referencyjny z LLM
# 2. kontener ubuntu:24.04 (bez Pythona/uv/tesseracta): ta sama kopia + .env, bash start.sh
#    (a) podsumowanie „LLM: … N wywołań” z N > 0, (b) wynik = lokalny, poza polami uzupełnianymi przez LLM
# 3. ten sam kontener (docker commit) z --network none: start.sh kończy się kodem 0, podsumowanie „niedostępny” /
#    „wyłączony”, wynik = lokalny przebieg z LLM_ENABLED=0 (same reguły)
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REF="${1:-HEAD}"
ENV_FILE="${2:-$REPO/.env}"
PLATFORM="${PLATFORM:-linux/amd64}"
LLM_FIELDS="OdwolanieKIO.czynnosc_powod_id,OdwolanieKIO.czynnosc_dzien,OdwolanieKIO.czynnosc_opis,ZamowieniePubliczne.tytul"
[ -s "$ENV_FILE" ] || { echo "FAIL: brak $ENV_FILE z kluczem LLM"; exit 1; }
grep -q '^LLM_API_KEY=.\+' "$ENV_FILE" || { echo "FAIL: $ENV_FILE nie ma LLM_API_KEY"; exit 1; }

WORK="$(mktemp -d "${TMPDIR:-/tmp}/odw llm clone.XXXXXX")"
TAG="odw-llm-clone-$$"
trap 'rm -rf "$WORK"; docker rm -f "$TAG" >/dev/null 2>&1 || true; docker rmi -f "$TAG" >/dev/null 2>&1 || true' EXIT
log() { printf '\n=== %s\n' "$*"; }
STATUS=0

log "archiwum $REF ($(git -C "$REPO" rev-parse --short "$REF"))"
git -C "$REPO" archive --format=tar -o "$WORK/repo.tar" "$REF"
prepare() {  # $1 = katalog: kopia REF + .env + data/synth/dev jako input/
    mkdir -p "$1"; tar -xf "$WORK/repo.tar" -C "$1"
    cp "$ENV_FILE" "$1/.env"; chmod 600 "$1/.env"
    cp -R "$1/data/synth/dev/." "$1/input/"; rm -rf "$1/output"  # synth-dev: rules leave a few fields empty -> LLM calls
}

# porównanie JSON-ów; pola LLM pomijane (szum modelu), reszta musi być identyczna
compare() {  # $1 nazwa, $2 katalog A, $3 katalog B, $4 "skip" = pomiń pola LLM
    if python3 - "$2" "$3" "$4" "$LLM_FIELDS" <<'PY'
import json, sys
from pathlib import Path
a, b, mode, fields = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4].split(",")
def strip(d):
    if mode == "skip" and isinstance(d, dict):
        for f in fields:
            top, _, leaf = f.partition(".")
            if isinstance(d.get(top), dict):
                d[top].pop(leaf, None)
    return d
fa = sorted(p.relative_to(a) for p in a.rglob("*.json")); fb = sorted(p.relative_to(b) for p in b.rglob("*.json"))
if fa != fb:
    print("  różne zbiory plików:", set(fa) ^ set(fb)); sys.exit(1)
bad = [str(p) for p in fa if strip(json.loads((a / p).read_text())) != strip(json.loads((b / p).read_text()))]
llm_diff = sum(json.loads((a / p).read_text()) != json.loads((b / p).read_text()) for p in fa)
print(f"  plików: {len(fa)}, różnych poza polami LLM: {len(bad)}, różnych łącznie: {llm_diff}")
for p in bad[:10]: print("   ", p)
sys.exit(1 if bad else 0)
PY
    then echo "OK [$1]"; else echo "FAIL [$1]"; STATUS=1; fi
}

log "lokalnie z LLM ($(uname -sm))"
LOC="$WORK/local/repo copy"; prepare "$LOC"
(cd "$LOC" && env -u LLM_API_KEY -u LLM_MODEL -u LLM_BASE_URL -u LLM_ENABLED bash start.sh --no-evidence) | tee "$WORK/local.txt"
grep -q '^LLM: .* [1-9][0-9]* wywołań' "$WORK/local.txt" || { echo "FAIL: lokalnie brak wywołań LLM"; STATUS=1; }
log "lokalnie bez LLM (LLM_ENABLED=0)"
LOC0="$WORK/local0/repo copy"; prepare "$LOC0"
(cd "$LOC0" && LLM_ENABLED=0 bash start.sh --no-evidence) | tail -2

log "kontener ubuntu:24.04 ($PLATFORM) z .env: instalacja + przebieg z LLM"
UB="$WORK/ub/repo copy"; prepare "$UB"; find "$UB" -type f -exec chmod a-x {} +
docker run --name "$TAG" --platform "$PLATFORM" -v "$WORK/ub:/host" ubuntu:24.04 bash -c '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq >/dev/null && apt-get install -y -qq --no-install-recommends curl ca-certificates >/dev/null
    mkdir -p "/home/jury/Moje Dokumenty" && cp -R "/host/repo copy" "/home/jury/Moje Dokumenty/odw repo"
    cd "/home/jury/Moje Dokumenty/odw repo"
    bash start.sh --no-evidence | tee /host/ub.txt
    rm -rf "/host/repo copy/output" && cp -R output "/host/repo copy/output"
' 2>&1 | grep -v -i 'api_key' | tail -5
grep -h '^LLM:' "$WORK/ub/ub.txt" || true
if grep -q '^LLM: .* [1-9][0-9]* wywołań' "$WORK/ub/ub.txt"; then echo "OK (a): start.sh w kontenerze przeczytał .env i wołał LLM"
else echo "FAIL (a): w kontenerze brak wywołań LLM"; STATUS=1; fi
compare "(b) kontener z LLM vs lokalny z LLM" "$LOC/output" "$UB/output" skip

log "ten sam kontener bez sieci (--network none)"
docker commit "$TAG" "$TAG" >/dev/null
set +e
docker run --rm --network none --platform "$PLATFORM" -v "$WORK/ub:/host" "$TAG" bash -c '
    cd "/home/jury/Moje Dokumenty/odw repo" && rm -rf output && bash start.sh --no-evidence > /host/off.txt 2>/host/off.err
    code=$?; rm -rf "/host/off-output" && cp -R output "/host/off-output"; exit $code'
CODE=$?
set -e
grep -h '^LLM:' "$WORK/ub/off.txt" || true
grep -i 'llm' "$WORK/ub/off.err" | grep -v -i 'key' | head -3 || true
if [ "$CODE" = 0 ] && grep -q '^LLM: .*\(niedostępny\|wyłączony\)' "$WORK/ub/off.txt"; then
    echo "OK (c): bez sieci exit 0, komunikat o niedostępnym LLM"
else echo "FAIL (c): bez sieci exit=$CODE"; STATUS=1; fi
compare "(c) kontener bez sieci vs lokalny same reguły" "$LOC0/output" "$WORK/ub/off-output" exact

log "wynik"
if [ "$STATUS" = 0 ]; then echo "PASS: clean clone LLM test"; else echo "FAIL: clean clone LLM test"; fi
exit "$STATUS"
