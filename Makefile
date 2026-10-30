VENV := .venv
PY   := $(VENV)/bin/python

.PHONY: setup test trigger destroy

setup: $(VENV)/.installed
	@test -f .env || { cp .env.example .env; echo "Created .env - fill in your values."; }

$(VENV)/.installed: requirements-dev.txt requirements.txt
	python3 -m venv $(VENV)
	$(PY) -m pip install -q -r requirements-dev.txt
	@touch $@

test: setup
	$(VENV)/bin/pytest -q

# One real attempt: logs in to Naukri and refreshes the resume.
trigger: setup
	@set -a; . ./.env; set +a; \
	$(PY) -c "import logging; logging.basicConfig(level=logging.INFO); import handler; print(handler.lambda_handler({}, None))"

# Back to a fresh clone: removes venv, .env (your credentials), build output, caches.
destroy:
	rm -rf $(VENV) .env build .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
