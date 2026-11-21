PY ?= .venv/bin/python

.PHONY: test eval gate

test:
	$(PY) -m pytest -q

eval:
	$(PY) -m eval.run --split train --fields

gate:
	$(PY) -m eval.gate
