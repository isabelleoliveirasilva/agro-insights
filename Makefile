.PHONY: setup etl report api test lint

setup:
	python -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt
	.venv/bin/pre-commit install

etl:
	python -m src.etl.run_all

report:
	python -m src.reports.gerar_excel

api:
	flask --app src.api.app run

test:
	pytest

lint:
	ruff check . && ruff format --check .
