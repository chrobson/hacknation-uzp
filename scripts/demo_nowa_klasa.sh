#!/usr/bin/env bash
# Demo rozszerzalności: nowa klasa dokumentu albo nowe pole = zmiana w pliku YAML, zero zmian w kodzie.
#   bash scripts/demo_nowa_klasa.sh
# 1. pismo spoza 3 klas zadania -> {}
# 2. poziom 1: klasa z samych pytań do modelu językowego (examples/klasy_llm, wymaga klucza w .env)
# 3. poziom 2: ta sama klasa na regułach (examples/klasy, bez modelu, bez sieci)
# 4. nowe pole w istniejącej klasie: kopia config/classes + 2 linie YAML w przelew.yaml
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
IN=examples/klasy/przyklady
show() { cat "$1"; echo; }

echo "== 1. Klasy podstawowe: pismo KIO (wezwanie do uzupełnienia braków) nie jest żadną z 3 klas zadania"
bash start.sh --no-evidence --input "$IN" --output "$OUT/1"
show "$OUT/1/sprawa1/pismo_kio.json"

echo "== 2. Poziom 1: + examples/klasy_llm/wezwanie_llm.yaml (jedna kotwica + 5 pytań type: llm, bez regexów)"
sed -n '/^classify:/,$p' examples/klasy_llm/wezwanie_llm.yaml
bash start.sh --no-evidence --classes-dir examples/klasy_llm --input "$IN" --output "$OUT/2"
show "$OUT/2/sprawa1/pismo_kio.json"

echo "== 3. Poziom 2: + examples/klasy/wezwanie_do_uzupelnienia.yaml (te same informacje z reguł: 0 wywołań modelu)"
bash start.sh --no-evidence --llm off --classes-dir examples/klasy --input "$IN" --output "$OUT/3"
show "$OUT/3/sprawa1/pismo_kio.json"

echo "== 4. Nowe pole w istniejącej klasie: przelew_bankowy.cel (reguła słownikowa) w kopii config/classes"
cp -R config/classes "$OUT/klasy"
# dwie linie YAML: pole w szablonie wyniku i jego reguła
sed -i.bak -e 's/^  przelew_bankowy:$/&\
    cel: null/' -e 's/^fields:$/&\
  przelew_bankowy.cel: {type: keyword_map, map: {wpis: ['"'"'wpis\\w*\\s+od\\s+odwołani'"'"'], oplata_skarbowa: ['"'"'opłat\\w*\\s+skarbow'"'"']}}/' \
    "$OUT/klasy/przelew.yaml"
diff config/classes/przelew.yaml "$OUT/klasy/przelew.yaml" || true
mkdir -p "$OUT/in4/sprawa"
cp data/train/przyklad_01/potwierdzenie_przelewu.pdf "$OUT/in4/sprawa/"
bash start.sh --no-evidence --llm off --classes "$OUT/klasy" --input "$OUT/in4" --output "$OUT/4"
show "$OUT/4/sprawa/potwierdzenie_przelewu.json"
