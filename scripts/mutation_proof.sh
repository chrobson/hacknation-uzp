#!/usr/bin/env bash
# Dowód, że kod nie zna klas ani pól: zmieniamy w YAML nazwy wszystkich klas i wszystkie klucze wyjściowe
# na losowe tokeny (odwolanie -> klasa_a, przelew_bankowy.kwota -> f328.f664), uruchamiamy ten sam program,
# mapujemy wynik z powrotem i porównujemy z normalnym przebiegiem. Regexy, etykiety i słowniki bez zmian.
#
#   bash scripts/mutation_proof.sh [FOLDER_SPRAW]     (domyślnie data/synth/dev; LLM wyłączony; STRICT=1: bez dopisywania field: do specu names)
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"; [ -x "$PY" ] || PY=python3
IN="${1:-data/synth/dev}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
export LLM_ENABLED=0

"$PY" scripts/mutation/mutate.py config/classes "$T/mut" --seed "${SEED:-$RANDOM}" ${STRICT:+--strict}
echo "== przykładowa zmutowana klasa:"
"$PY" - "$T/mut/classes" <<'EOF'
import sys, pathlib, yaml
p = sorted(pathlib.Path(sys.argv[1]).glob("*.yaml"))[-1]
r = yaml.safe_load(p.read_text(encoding="utf-8"))
print(f"  plik: {p.name}\n  name: {r['name']}\n  output_template: {r['output_template']}\n  fields: {list(r.get('fields') or {})[:4]} ...")
EOF
echo "== uruchamiam: konfiguracja normalna i zmutowana, wejście: $IN"
"$PY" main.py --input "$IN" --output "$T/norm" --no-evidence --llm off >"$T/norm.log" 2>&1 & P1=$!
"$PY" main.py --classes "$T/mut/classes" --input "$IN" --output "$T/out" --no-evidence --llm off >"$T/mut.log" 2>&1 & P2=$!
wait "$P1" || { echo "FAIL: normalny przebieg"; tail -5 "$T/norm.log"; exit 1; }
wait "$P2" || { echo "FAIL: zmutowany przebieg"; tail -5 "$T/mut.log"; exit 1; }
[ -n "$(find "$T/norm" -name '*.json' -print -quit)" ] || { echo "FAIL: brak plików wynikowych"; exit 1; }
"$PY" scripts/mutation/unmutate.py "$T/mut/reverse_map.json" "$T/out" "$T/norm"
