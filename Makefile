.RECIPEPREFIX := $() $()

.PHONY: install run fmt lint style test verify clean

install:
    uv sync

run:
    uv run ticktask

fmt:
    uv run ruff format .

lint:
    uv run ruff check .

style:
    uv run mypy src tests

test:
    uv run pytest

verify: lint style test

clean:
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type d -name "*.pyc" -delete
    rm -rf .pytest_cache .ruff_cache .mypy_cache
