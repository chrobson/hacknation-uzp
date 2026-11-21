# Synthetic evaluation data (`eval/synth`)

Generators that render synthetic PDFs with exact ground truth for the three document
classes (odwołanie, pełnomocnictwo, potwierdzenie przelewu) plus hard negatives, and a
runner that scores the production pipeline on them with `eval/score.py` (UZP rules,
WYMAGANIA §9–§10).

## Setup

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt -r eval/synth/requirements-dev.txt
```

## Split policy: dev in the repo, blind outside

| split | templates | cases | in git |
|-------|-----------|-------|--------|
| dev   | `eval/synth/<class>/templates*` | `data/synth/dev/<class>_XXX/`, `data/synth/negatives-dev/case_XXX/` | yes |
| blind | `$SYNTH_BLIND_ROOT/templates/<class>/` | `$SYNTH_BLIND_ROOT/cases/<class>_XXX/`, `$SYNTH_BLIND_ROOT/negatives/case_XXX/` | **never** |

`SYNTH_BLIND_ROOT` defaults to `/Users/mat2/orca/projects/hacknation/synth-blind`.
Blind templates use layouts the dev templates do not, so blind F1 estimates how the
extractor generalises to unseen layouts. Rules:

* Do not copy blind templates, blind PDFs, blind GT or text dumps of them into this repo
  (`.gitignore` blocks the usual `data/synth/dev/blind_*` dumps).
* Do not tune `src/` or `config/` while looking at blind cases; look only at dev failures,
  then check blind as a single number.

## Generate

Each case dir holds one `<random>.pdf` and its `<random>.json` (official schema; `{}`
for negatives). Pełnomocnictwo cases also carry `meta.json` (template id); manifests sit
at the output root. None of these is shown to the pipeline.

```bash
# dev (seeds used for the committed data)
.venv/bin/python -m eval.synth.odwolanie.generate      --split dev --n 30 --seed 1
.venv/bin/python -m eval.synth.pelnomocnictwo.generate --split dev --n 30 --seed 1
.venv/bin/python -m eval.synth.przelew.generate        --split dev --n 30 --seed 1 --clean
.venv/bin/python -m eval.synth.negatywy.generate       --split dev --n 20 --seed 1 --clean

# blind (writes to $SYNTH_BLIND_ROOT only)
.venv/bin/python -m eval.synth.odwolanie.generate      --split blind --n 30 --seed 2
.venv/bin/python -m eval.synth.pelnomocnictwo.generate --split blind --n 30 --seed 2
.venv/bin/python -m eval.synth.przelew.generate        --split blind --n 30 --seed 2 --clean
.venv/bin/python -m eval.synth.negatywy.generate       --split blind --n 20 --seed 2 --clean
```

Generation is deterministic for a given seed. Each class has a selfcheck that verifies
every GT value is present in the rendered text:

```bash
.venv/bin/python -m eval.synth.odwolanie.selfcheck data/synth/dev
.venv/bin/python -m eval.synth.pelnomocnictwo.selfcheck data/synth/dev
.venv/bin/python -m eval.synth.przelew.selfcheck   data/synth/dev
.venv/bin/python -m eval.synth.negatywy.selfcheck  data/synth/negatives-dev
```

## Score the pipeline

```bash
.venv/bin/python -m eval.synth.run --fields --worst 15          # dev + negatives-dev
.venv/bin/python -m eval.synth.run \
    --root "$SYNTH_BLIND_ROOT/cases" --root "$SYNTH_BLIND_ROOT/negatives"   # blind
```

The runner copies each PDF under a random name, runs `odw.pipeline.run`, and scores the
output against `.json` with `eval.score.score_fields`. The expected class comes from the
case dir prefix; any other dir expects `{}`. It prints classification accuracy, negatives
accepted as a class, F1 per class and, with `--fields`, F1 per field per class.

## Ground-truth conventions worth knowing

* PESEL is a string in GT (as in train `przyklad_43`); `_equal` treats str and int as different.
* `czynnosc_opis` for id 6 is "Odpowiedzi/wyjaśnienia do SWZ" (train GT), not the dictionary
  spelling "Odpowiedzi/wyjaśnienia do SWZ".
* No-attorney odwołanie: `przez-pelnomocnika = 0` and `pelnomocnik` with all fields null
  (train has no such example).
* przelew `tytul` keeps the trailing CEN reference; `numer_transakcji` is the separately
  labelled reference; an MT103 `:20:NONREF` maps to null.
