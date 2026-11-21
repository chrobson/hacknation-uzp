#!/usr/bin/env bash
# Demo rozszerzalności: nowa klasa dokumentu = jeden plik YAML, zero zmian w kodzie.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="$(mktemp -d)"
echo "== 1. Klasy podstawowe: pismo KIO nie jest żadną z 3 klas zadania"
./start.sh --input examples/klasy/przyklady --output "$OUT/bez"
cat "$OUT/bez/sprawa1/pismo_kio.json"; echo
echo "== 2. Ta sama aplikacja + examples/klasy/wezwanie_do_uzupelnienia.yaml"
./start.sh --classes-dir examples/klasy --input examples/klasy/przyklady --output "$OUT/z"
cat "$OUT/z/sprawa1/pismo_kio.json"
