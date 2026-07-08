# The only deploy path is `make deploy` — if it isn't here, it doesn't happen on
# demo day (docs/05). Targets needing the DB read CRDB_CONN_STRING from the env.
SHELL := /bin/bash
FUNCTION_NAME ?= recall-ingest
.DEFAULT_GOAL := help

.PHONY: help sync test lint fmt probe migrate seed deploy branches-init

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

deploy: ## zip lambda/ + update the function (P2 wires dependency bundling)
	rm -rf build && mkdir -p build
	cd lambda && zip -qr ../build/lambda.zip . -x '__pycache__/*'
	aws lambda update-function-code --function-name $(FUNCTION_NAME) --zip-file fileb://build/lambda.zip

branches-init: ## one-time: create + push dev and test from origin/main (docs/07)
	bash scripts/branches_init.sh
