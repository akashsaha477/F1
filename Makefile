PY ?= .venv/bin/python
SEASONS ?= 2022-2025

.PHONY: help install ingest-small ingest coverage features train evaluate reports pipeline api frontend \
        frontend-build test test-fast lint check docker-up docker-pipeline

help:                    ## list targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

install:                 ## Python venv (uv) + frontend dependencies
	uv venv .venv --python 3.13 && uv pip install -e ".[dev,fastf1]"
	cd frontend && npm install

ingest-small:            ## three events of one season: quick end-to-end check
	$(PY) scripts/ingest_season.py --seasons 2024 --max-events 3 --telemetry

ingest:                  ## research dataset: F1DB, lap timing for all sessions, qualifying telemetry
	$(PY) scripts/ingest_season.py --seasons $(SEASONS) --telemetry

coverage:                ## data coverage report (manifests + reports/coverage_report.md)
	$(PY) -m apexlens.cli coverage

features:                ## gold tables: corners, lap features, driver profiles, tyres, clusters
	$(PY) scripts/build_features.py

train:                   ## Model A (both horizons), walk-forward evaluation, model registry
	$(PY) scripts/train_models.py

evaluate:                ## explanation validation, ablations, Models B and F, error analysis
	$(PY) scripts/evaluate_models.py

reports:                 ## reports/*.md and generated docs
	$(PY) scripts/generate_reports.py

pipeline: ingest features train evaluate reports  ## everything, in order

api:                     ## FastAPI on :8000
	$(PY) -m uvicorn apexlens.api.main:app --host 127.0.0.1 --port 8000

frontend:                ## Vite dev server on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

test:                    ## all Python tests (real-data tests skip when data/ is absent)
	$(PY) -m pytest

test-fast:               ## Python tests without the real-data suite
	$(PY) -m pytest -m "not realdata and not network"

lint:
	$(PY) -m ruff check src tests scripts

check: lint test         ## lint + Python tests + frontend typecheck and tests
	cd frontend && npm run typecheck && npm test

docker-up:               ## API (:8000) and dashboard (:8080) in containers, using ./data
	docker compose up --build

docker-pipeline:         ## run the full pipeline in a container, writing ./data and ./reports
	docker compose --profile pipeline run --rm pipeline
