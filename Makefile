PY ?= .venv/bin/python
SEASONS ?= 2022-2025

.PHONY: install ingest-small ingest ingest-telemetry coverage features train evaluate reports api frontend test lint

install:
	uv venv .venv --python 3.13 && uv pip install -e ".[dev,fastf1]"
	cd frontend && npm install

ingest-small:            ## a few events of one season: quick end-to-end check
	$(PY) scripts/ingest_season.py --seasons 2024 --max-events 3 --telemetry

ingest:                  ## default research dataset (lap timing for all sessions + qualifying telemetry)
	$(PY) scripts/ingest_season.py --seasons $(SEASONS) --telemetry

coverage:
	$(PY) -m apexlens.cli coverage

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check src tests scripts
