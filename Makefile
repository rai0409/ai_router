.PHONY: test lint typecheck check format

test:
	python -m pytest -q

lint:
	python -m ruff check .

format:
	python -m ruff format .

typecheck:
	python -m mypy .

check: lint typecheck test
