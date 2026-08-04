# The only deploy path is `make deploy` — if it isn't here, it doesn't happen on
# demo day (docs/05). Targets needing the DB read CRDB_CONN_STRING from the env.
SHELL := /bin/bash
FUNCTION_NAME ?= recall-ingest
.DEFAULT_GOAL := help

.PHONY: help sync test lint fmt probe migrate seed deploy branches-init chaos-up chaos-down

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

sync: ## install deps (uv)
	uv sync

test: ## fast suite — structural + unit tests
	uv run pytest -q

lint: ## ruff check
	uv run ruff check .

fmt: ## ruff format
	uv run ruff format .

probe: ## P0 probe: DDL + 5 rows + one <-> query on the live cluster
	@test -n "$$CRDB_CONN_STRING" || { echo "set CRDB_CONN_STRING (see .env.example)"; exit 1; }
	psql "$$CRDB_CONN_STRING" -f scripts/probe.sql

migrate: ## apply numbered DDL files in infra/migrations/ in order
	@test -n "$$CRDB_CONN_STRING" || { echo "set CRDB_CONN_STRING (see .env.example)"; exit 1; }
	@for f in infra/migrations/*.sql; do echo "== $$f"; psql "$$CRDB_CONN_STRING" -f "$$f"; done

seed: ## regenerate the Orbital corpus (P1)
	uv run python infra/seed/generate.py

deploy: ## bundle lambda/ + prompts/ + deps into a zip, update the function
	rm -rf build && mkdir -p build/pkg
	uv pip install --target build/pkg --python-platform x86_64-manylinux2014 \
		--python-version 3.13 --only-binary :all: 'psycopg[binary]' pydantic
	cp lambda/*.py build/pkg/
	mkdir -p build/pkg/prompts && cp prompts/system.md build/pkg/prompts/
	cd build/pkg && zip -qr ../lambda.zip . -x '__pycache__/*'
	aws lambda update-function-code --function-name $(FUNCTION_NAME) --zip-file fileb://build/lambda.zip

branches-init: ## one-time: create + push develop from origin/main (docs/07)
	bash scripts/branches_init.sh

chaos-up: ## AC7 rig: start + init the 3-node cluster, enable the vector-index flag
	docker compose -f infra/chaos/docker-compose.yml up -d
	@sleep 2; docker exec recall-crdb-1 cockroach init --insecure 2>/dev/null || true
	@sleep 2; docker exec recall-crdb-1 cockroach sql --insecure \
		-e "SET CLUSTER SETTING feature.vector_index.enabled = true;"
	@echo "rig up: postgresql://root@localhost:26260/defaultdb?sslmode=disable (kill = docker stop recall-crdb-2)"

chaos-down: ## stop the AC7 rig and wipe its volumes
	docker compose -f infra/chaos/docker-compose.yml down -v
