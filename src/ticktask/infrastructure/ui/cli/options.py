"""Command-line option parsing and terminal confirmation prompts."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CliOptions:
    """Validated command-line options for launching TickTask."""

    tray: bool
    reset_db: bool
    pomodoro_only: bool


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TickTask timer")
    parser.add_argument(
        "--tray",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable system tray companion mode (default: enabled).",
    )
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Delete the local TickTask database and exit.",
    )
    parser.add_argument(
        "--pomodoro-only",
        action="store_true",
        help="Start a timer-only Pomodoro UI without project or task management.",
    )
    return parser


def _validate_options(
    parser: argparse.ArgumentParser,
    options: CliOptions,
    raw_argv: list[str],
) -> None:
    if options.reset_db and raw_argv != ["--reset-db"]:
        parser.error("--reset-db must be used by itself.")


def parse_args(argv: list[str] | None = None) -> CliOptions:
    """Parse and validate TickTask command-line options."""
    raw_argv = sys.argv[1:] if argv is None else list(argv)
    parser = _build_parser()
    namespace = parser.parse_args(raw_argv)
    options = CliOptions(
        tray=namespace.tray,
        reset_db=namespace.reset_db,
        pomodoro_only=namespace.pomodoro_only,
    )
    _validate_options(parser, options, raw_argv)
    return options


def confirm_db_reset(database_path: Path) -> bool:
    """Return whether the user explicitly confirms deleting the database."""
    print(f"This will permanently delete the TickTask database at:\n{database_path}")
    confirmation = input("Type DELETE to confirm: ")
    return confirmation == "DELETE"


__all__: list[str] = ["CliOptions", "confirm_db_reset", "parse_args"]
