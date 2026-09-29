"""Command-line entrypoint and application composition root."""

from __future__ import annotations

import sys
from pathlib import Path

from ticktask.adapters import (
    ProjectController,
    TaskController,
    TaskManagementControllers,
)
from ticktask.adapters.repositories import SqlAlchemyUnitOfWorkFactory
from ticktask.application import (
    DEFAULT_TIMER_SEQUENCE,
    PomodoroController,
    ProjectService,
    TaskService,
    TimerStatePublisher,
)
from ticktask.application.publishers import NoOpTimerStatePublisher
from ticktask.infrastructure import (
    Database,
    DatabaseError,
    default_database_path,
)
from ticktask.infrastructure.ui.cli import CliOptions, TickTask, parse_args
from ticktask.infrastructure.ui.cli.options import (
    confirm_db_reset as _confirm_db_reset,
)

__all__: list[str] = ["CliOptions", "confirm_db_reset", "main", "parse_args"]


def confirm_db_reset(database_path: Path | None = None) -> bool:
    """Return whether the user explicitly confirms deleting the database."""
    path = database_path if database_path is not None else default_database_path()
    return _confirm_db_reset(path)


def _reset_database_interactively() -> None:
    if not sys.stdin.isatty():
        raise SystemExit(
            "--reset-db requires an interactive terminal for confirmation."
        )

    database_path = default_database_path()
    if not confirm_db_reset(database_path):
        print("Database reset cancelled.")
        return

    database = Database(database_path)
    try:
        with database:
            deleted = database.reset()
    except DatabaseError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error

    print(
        "TickTask database deleted." if deleted else "No TickTask database was found."
    )


def _run_app(*, enable_tray: bool, pomodoro_only: bool) -> None:
    publisher: TimerStatePublisher
    if enable_tray:
        from ticktask.infrastructure.ui.desktop.tray import TrayPublisher

        publisher = TrayPublisher()
    else:
        publisher = NoOpTimerStatePublisher()

    controller = PomodoroController(DEFAULT_TIMER_SEQUENCE, publisher)
    database: Database | None = None
    try:
        task_management: TaskManagementControllers | None = None
        if not pomodoro_only:
            database = Database()
            try:
                database.initialize()
            except DatabaseError as error:
                print(str(error), file=sys.stderr)
                raise SystemExit(1) from error

            unit_of_work_factory = SqlAlchemyUnitOfWorkFactory(database.session_factory)
            task_management = TaskManagementControllers(
                projects=ProjectController(ProjectService(unit_of_work_factory)),
                tasks=TaskController(TaskService(unit_of_work_factory)),
            )

        if enable_tray:
            publisher.start()

        app = TickTask(controller, task_management)
        app.run()
    finally:
        try:
            publisher.close()
        except Exception as error:
            print(f"Publisher cleanup failed: {error}", file=sys.stderr)

        if database is not None:
            try:
                database.dispose()
            except Exception as error:
                print(f"Database cleanup failed: {error}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    """Run TickTask using parsed command-line options."""
    args = parse_args(argv)
    if args.reset_db:
        _reset_database_interactively()
        return

    _run_app(enable_tray=args.tray, pomodoro_only=args.pomodoro_only)


if __name__ == "__main__":
    main()
