# Day-to-day commands. `make` with no target prints this list.
#
# Everything runs from the repo's own virtualenv (.venv) and web/node_modules,
# so nothing here depends on what is installed globally.

VENV := .venv

ifeq ($(OS),Windows_NT)
VENV_BIN := $(VENV)/Scripts
PYTHON ?= py -3
else
VENV_BIN := $(VENV)/bin
PYTHON ?= python3
endif

PY      := $(VENV_BIN)/python
PIP     := $(VENV_BIN)/pip
UVICORN := $(VENV_BIN)/uvicorn
RUFF    := $(VENV_BIN)/ruff
WEB     := web

# Passwords for the offline stub server. DEV_PASSWORD signs in as an employee;
# DEV_HR_PASSWORD signs in as Human Resources and adds the HR Requests and What
# People Ask pages. Override: make stub DEV_PASSWORD=hunter2 DEV_HR_PASSWORD=hr2
DEV_PASSWORD ?= dev
DEV_HR_PASSWORD ?= hr

# make stub REFUSE=1 makes every question refuse at the similarity threshold,
# to see the escalation card. REFUSE=judge clears the threshold and has the
# coverage judge refuse instead, the other refusal card (#269).
FAKE_SCORE := $(if $(filter judge,$(REFUSE)),0.78,$(if $(REFUSE),0.50,0.78))
STUB_COVERED := $(if $(filter judge,$(REFUSE)),0,1)

.DEFAULT_GOAL := help

.PHONY: help setup stub web test test-web cov lint lint-py lint-web fmt audit build check compose acceptance loadtest clean lock openapi

help: ## Show this list
ifeq ($(OS),Windows_NT)
	@powershell -NoProfile -Command "Select-String -Path '$(MAKEFILE_LIST)' -Pattern '^[a-z][a-z-]*:.*## ' | ForEach-Object { $$parts = $$_.Line -split ':.*## ', 2; '  {0,-10} {1}' -f $$parts[0], $$parts[1] }"
else
	@grep -E '^[a-z][a-z-]*:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-10s %s\n", $$1, $$2}'
endif

setup: ## One-time: create .venv, install Python and Node dependencies
# Make-native existence check: Git Bash also sets OS=Windows_NT, so a cmd.exe
# `if not exist` recipe is not portable across shells that share that Make OS.
ifeq ($(wildcard $(VENV)/.),)
	$(PYTHON) -m venv $(VENV)
endif
	$(PIP) install -q -r requirements/dev.txt
	cd $(WEB) && npm install

stub: export APP_PASSWORD_HASH = $(shell $(PY) -c "import bcrypt; print(bcrypt.hashpw(b'$(DEV_PASSWORD)', bcrypt.gensalt()).decode())")
stub: export HR_PASSWORD_HASH = $(shell $(PY) -c "import bcrypt; print(bcrypt.hashpw(b'$(DEV_HR_PASSWORD)', bcrypt.gensalt()).decode())")
stub: export FAKE_PASSAGE_SCORE = $(FAKE_SCORE)
stub: export FAKE_COVERED = $(STUB_COVERED)
stub: export FAKE_DB_LATENCY_MS = 0
stub: ## Run the API on :8000 with a fake model and in-memory Mongo (no accounts needed)
	$(UVICORN) scripts.loadtest.server:app --port 8000 --log-level warning

web: ## Run the React app on :5173 with hot reload (proxies /api to :8000)
	cd $(WEB) && npx vite --port 5173 --strictPort

test: ## Run the Python test suite (~1 second, nothing external)
	$(PY) -m pytest

test-web: ## Vitest + RTL coverage for critical web paths (fails under 80% on included files)
	cd $(WEB) && npm test

cov: ## Tests with a coverage report; CI fails under 80%
	$(PY) -m pytest --cov --cov-report=term-missing

lint: lint-py lint-web ## Ruff on Python; ESLint and TypeScript on the web app

lint-py: ## Ruff lint and format check (make fmt fixes what it can)
	$(RUFF) check .
	$(RUFF) format --check .

lint-web: ## ESLint and TypeScript on the web app
	cd $(WEB) && npm run -s lint && npx tsc -b

fmt: ## Fix lint findings and format the Python code
	$(RUFF) check --fix .
	$(RUFF) format .

audit: ## Known vulnerabilities in the Python and npm dependency trees
	./scripts/audit.sh

# Runs inside requirements/ so the `# via -r` annotations come out the same as
# Dependabot's, which compiles there too; CI checks with the same command.
lock: ## Compile api, dev, and ingest .in files into their .txt locks (same command CI checks with)
	cd requirements && $(abspath $(VENV_BIN))/pip-compile --quiet -o api.txt api.in
	cd requirements && $(abspath $(VENV_BIN))/pip-compile --quiet -o dev.txt dev.in
	cd requirements && $(abspath $(VENV_BIN))/pip-compile --quiet -o ingest.txt ingest.in

build: ## Production build of the web app
	cd $(WEB) && npm run -s build

openapi: ## Write docs/openapi.json from app.openapi() (sorted keys, stable diff)
	$(PY) scripts/export_openapi.py

check: test test-web lint build ## What the CI workflow runs on every PR (audit runs in Security)

compose: ## Full stack in Docker against the real services in .env
	docker compose up --build

acceptance: ## Real Caddy -> Nginx -> Uvicorn client-IP and rate-limit check (Compose >= 2.24; leaves two :acceptance image tags for cache reuse)
	$(PY) scripts/test_proxy_chain.py

loadtest: ## Throughput measurement against `make stub`; see docs/load-testing.md
	$(PY) scripts/loadtest/run.py --concurrency 10 20 40 80

clean: ## Remove build and test artifacts
	rm -rf .coverage coverage.xml junit.xml htmlcov .pytest_cache .ruff_cache $(WEB)/dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
