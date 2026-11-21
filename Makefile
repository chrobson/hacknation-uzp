PY ?= .venv/bin/python

.PHONY: test eval gate sync

# dev dependencies (pytest, rapidfuzz for the metric); `bash start.sh` syncs without them
sync:
	@command -v uv >/dev/null 2>&1 && uv sync --quiet || true

test: sync
	$(PY) -m pytest -q

eval: sync
	$(PY) -m eval.run --split train --fields

gate: sync
	$(PY) -m eval.gate
