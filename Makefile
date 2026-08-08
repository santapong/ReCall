# The only deploy path is `make deploy` — if it isn't here, it doesn't happen on
# demo day (docs/05). Targets needing the DB read CRDB_CONN_STRING from the env.
SHELL := /bin/bash
FUNCTION_NAME ?= recall-ingest

# One source of truth for the Python version, used by both the wheel build and the
# function's runtime — they must not drift. psycopg and pydantic ship compiled .so
# files (pq.cpython-3XX-*.so); wheels built for one minor version do not import on
# another, and the function dies at cold start before any of our code runs, with the
# real reason visible only in CloudWatch.
PY_VERSION ?= 3.12
PY_RUNTIME ?= python$(PY_VERSION)

.DEFAULT_GOAL := help

.PHONY: help sync test lint fmt probe migrate seed local-load local-e2e local-eval local-clean deploy deploy-config function-url branches-init chaos-up chaos-conn chaos-down

help:
	@grep -E '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

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
	psql -v ON_ERROR_STOP=1 "$$CRDB_CONN_STRING" -f scripts/probe.sql

migrate: ## apply numbered DDL files in infra/migrations/ in order
	@test -n "$$CRDB_CONN_STRING" || { echo "set CRDB_CONN_STRING (see .env.example)"; exit 1; }
	@# ON_ERROR_STOP + explicit exit: without both, psql returns 0 after a failed
	@# statement and the loop swallows it, so "migrate passed" and "probe passed"
	@# stop being evidence that the schema or the vector index actually exists.
	@for f in infra/migrations/*.sql; do \
		echo "== $$f"; \
		psql -v ON_ERROR_STOP=1 "$$CRDB_CONN_STRING" -f "$$f" || exit 1; \
	done

seed: ## regenerate the Orbital corpus (P1)
	uv run python infra/seed/generate.py

# --- credential-free local stack (M0') --------------------------------------
# Explicit opt-in backends, never inferred from a missing credential. Scores and
# thresholds produced here are provisional: the embedder is lexical, not semantic
# (lambda/embed.py). Nothing filmed may run on it.
LOCAL_ENV = EMBED_BACKEND=local BEDROCK_BACKEND=local

local-load: ## embed + load the corpus with the local backend (no AWS needed)
	@test -n "$$CRDB_CONN_STRING" || { echo "set CRDB_CONN_STRING (see .env.example)"; exit 1; }
	$(LOCAL_ENV) uv run python infra/seed/load.py

local-e2e: ## POST an alert through the real handler on the local stack
	@test -n "$$CRDB_CONN_STRING" || { echo "set CRDB_CONN_STRING (see .env.example)"; exit 1; }
	$(LOCAL_ENV) uv run python scripts/local_e2e.py

local-clean: ## delete rows left behind by tests and ad-hoc runs (never touches the corpus)
	@# The DB-backed suite inserts `test-<uuid>` incidents and deletes them on teardown,
	@# but a failed teardown (or an interrupted run) leaks them — and any that reached
	@# write_incident are status='resolved' with an embedding, so they are *retrievable*
	@# and turn up as memory matches. One did exactly that on the status page. Run this
	@# before filming, and before reading any retrieval number.
	@test -n "$$CRDB_CONN_STRING" || { echo "set CRDB_CONN_STRING (see .env.example)"; exit 1; }
	@psql -v ON_ERROR_STOP=1 -q "$$CRDB_CONN_STRING" -c "\
		DELETE FROM agent_runs WHERE incident_id IN (SELECT id FROM incidents \
		  WHERE external_id LIKE 'test-%' OR external_id LIKE 'LOCAL-%' \
		     OR external_id LIKE 'DEMO-%' OR external_id LIKE 'AB-%'); \
		DELETE FROM working_state WHERE incident_id IN (SELECT id FROM incidents \
		  WHERE external_id LIKE 'test-%' OR external_id LIKE 'LOCAL-%' \
		     OR external_id LIKE 'DEMO-%' OR external_id LIKE 'AB-%'); \
		DELETE FROM incidents WHERE external_id LIKE 'test-%' OR external_id LIKE 'LOCAL-%' \
		     OR external_id LIKE 'DEMO-%' OR external_id LIKE 'AB-%';"
	@psql -t -A -q "$$CRDB_CONN_STRING" -c "SELECT 'incidents remaining: ' || count(*) FROM incidents;"

local-eval: ## AC2 retrieval eval on the local stack (PROVISIONAL — see the printout)
	@test -n "$$CRDB_CONN_STRING" || { echo "set CRDB_CONN_STRING (see .env.example)"; exit 1; }
	$(LOCAL_ENV) uv run pytest tests/test_retrieval_eval.py -s

deploy: ## bundle lambda/ + prompts/ + deps into a zip, update the function AND its config
	rm -rf build && mkdir -p build/pkg
	uv pip install --target build/pkg --python-platform x86_64-manylinux2014 \
		--python-version $(PY_VERSION) --only-binary :all: 'psycopg[binary]' pydantic
	cp lambda/*.py build/pkg/
	mkdir -p build/pkg/prompts && cp prompts/system.md build/pkg/prompts/
	cd build/pkg && zip -qr ../lambda.zip . -x '__pycache__/*'
	aws lambda update-function-code --function-name $(FUNCTION_NAME) --zip-file fileb://build/lambda.zip
	@echo "== waiting for the code update to settle before reconfiguring"
	aws lambda wait function-updated --function-name $(FUNCTION_NAME)
	$(MAKE) deploy-config

deploy-config: ## timeout/memory/env/concurrency — code alone is not a working function
	@# The 3s default timeout cannot fit a loop making 2-13 Bedrock round trips, and
	@# 128MB cannot meet AC1's <5s once pydantic-core + psycopg[binary] + a TLS
	@# handshake are in the cold path. Both are deploy-time facts, so they live here
	@# rather than in a console someone has to remember to click through.
	@test -n "$$CRDB_CONN_STRING" || { echo "set CRDB_CONN_STRING (see .env.example)"; exit 1; }
	aws lambda update-function-configuration --function-name $(FUNCTION_NAME) \
		--runtime $(PY_RUNTIME) --timeout 60 --memory-size 1024 \
		--environment "Variables={CRDB_CONN_STRING=$$CRDB_CONN_STRING,BEDROCK_MODEL_ID=$$BEDROCK_MODEL_ID,BEDROCK_EMBED_MODEL_ID=$$BEDROCK_EMBED_MODEL_ID,EMBED_DIM=$$EMBED_DIM,CONFIDENCE_HIGH_MAX_DIST=$$CONFIDENCE_HIGH_MAX_DIST,CONFIDENCE_NONE_MIN_DIST=$$CONFIDENCE_NONE_MIN_DIST,DECAY_HALF_LIFE_DAYS=$$DECAY_HALF_LIFE_DAYS,RECALL_INGEST_TOKEN=$$RECALL_INGEST_TOKEN}"
	@# Bounded blast radius on an unauthenticated public URL: the ingest path spends
	@# Bedrock tokens, so cap how many can run at once (C5, named in the README).
	aws lambda put-function-concurrency --function-name $(FUNCTION_NAME) \
		--reserved-concurrent-executions 5

function-url: ## one-time: create the public Function URL (reads public by design)
	aws lambda create-function-url-config --function-name $(FUNCTION_NAME) \
		--auth-type NONE --cors '{"AllowOrigins":["*"],"AllowMethods":["GET","POST"]}' \
		|| echo "(already exists)"
	aws lambda add-permission --function-name $(FUNCTION_NAME) \
		--statement-id FunctionURLAllowPublicAccess --action lambda:InvokeFunctionUrl \
		--principal '*' --function-url-auth-type NONE 2>/dev/null || echo "(permission already granted)"
	@aws lambda get-function-url-config --function-name $(FUNCTION_NAME) --query FunctionUrl --output text

branches-init: ## one-time: create + push develop from origin/main (docs/07)
	bash scripts/branches_init.sh

chaos-up: ## AC7 rig: start + init the 3-node cluster, enable the vector-index flag
	docker compose -f infra/chaos/docker-compose.yml up -d
	@sleep 2; docker exec recall-crdb-1 cockroach init --insecure 2>/dev/null || true
	@sleep 2; docker exec recall-crdb-1 cockroach sql --insecure \
		-e "SET CLUSTER SETTING feature.vector_index.enabled = true;"
	@# Multi-host, and the kill target is the node we are actually connected to.
	@# The old single-host string (crdb-1) with `docker stop recall-crdb-2` never
	@# broke the connection, so db.with_retry's reconnect arm — the thing AC7 claims
	@# to demonstrate — could not fire and the shot proved nothing. Killing crdb-1
	@# with only crdb-1 in the string breaks it permanently instead, hence all three.
	@echo "rig up: $(CHAOS_CONN)"
	@echo "kill = docker stop recall-crdb-1  (the node the connection is on)"

CHAOS_CONN = postgresql://root@localhost:26260,localhost:26261,localhost:26262/defaultdb?sslmode=disable

chaos-conn: ## print the multi-host rig connection string (export it before the take)
	@echo '$(CHAOS_CONN)'

chaos-down: ## stop the AC7 rig and wipe its volumes
	docker compose -f infra/chaos/docker-compose.yml down -v
