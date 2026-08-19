# TickTask

<div align="center">

![Python Badge](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=fff&style=flat)
![Gitlab Pipeline Status](https://gitlab.com/majramos/ticktask/badges/main/pipeline.svg)
![Gitlab Release](https://gitlab.com/majramos/ticktask/-/badges/release.svg)
![Gitlab Coverage](https://gitlab.com/majramos/ticktask/badges/main/coverage.svg)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

</div>

Pomodoro-style terminal task manager built with [Textual](https://textual.textualize.io/)

Ticktask combines a Pomodoro timer, project selection, task creation, task completion and task archiving in a terminal UI. It can also run as a timer-only app.

## Requirements

- Python `>=3.13`
- [`uv`](https://docs.astral.sh/uv/) recommended, pr `pip`

## Setup & Installation

This project uses uv for ultra-fast Python package and project management.

1. Install uv (if you haven't already):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
2. Clone and Sync:
```bash
git clone https://gitlab.com/majramos/ticktask.git
cd ticktask
uv sync
```

With `pip`:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## How to use

To run using the managed virtual environment:

Run via uv run:
```bash
uv run ticktask
```

Run timer-only mode:
```bash
uv run ticktask --pomodoro-only
```

## Documentation
- [Documentation Inde](docs/index.md)
- [Usage and CLI flags](docs/usage.md)
- [Keyboard shortcuts](docs/shortcuts.md)
- [Task workflows](docs/workflows.md)
- [Docker guide](docs/docker.md)
- [Development notes](docs/development.md)
- [Architecture](docs/architecture.md)

## Development Checks
```bash
uv sync --group dev
uv run ruff check
uv run mypy
uv run pytest
```
