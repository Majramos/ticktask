"""Tests for command-line entrypoint composition."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, ClassVar

import pytest

from ticktask import main as main_mod
from ticktask.infrastructure import Database, DatabaseError


class StubApp:
    created: ClassVar[list[StubApp]] = []
    ran = 0

    def __init__(self, controller: Any, task_management: Any = None) -> None:
        self.controller = controller
        self.task_management = task_management
        self.__class__.created.append(self)

    def run(self) -> None:
        self.__class__.ran += 1


@pytest.fixture(autouse=True)
def reset_stub_app() -> None:
    StubApp.created = []
    StubApp.ran = 0


def test_confirm_db_reset_delegates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    called: dict[str, Any] = {}

    def fake_confirm(path: Path) -> bool:
        called["path"] = path
        return True

    monkeypatch.setattr(main_mod, "_confirm_db_reset", fake_confirm)
    path = tmp_path / "x.db"
    assert main_mod.confirm_db_reset(path) is True
    assert called["path"] == path


def test_confirm_db_reset_uses_default_path(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = Path("/tmp/default.db")
    monkeypatch.setattr(main_mod, "default_database_path", lambda: expected)
    monkeypatch.setattr(main_mod, "_confirm_db_reset", lambda path: path == expected)
    assert main_mod.confirm_db_reset() is True


def test_reset_db_requires_interactive_terminal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    with pytest.raises(SystemExit, match="interactive terminal"):
        main_mod._reset_database_interactively()


def test_reset_db_cancelled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(main_mod, "confirm_db_reset", lambda _p: False)
    monkeypatch.setattr(main_mod, "default_database_path", lambda: Path("/tmp/x.db"))
    main_mod._reset_database_interactively()
    assert "cancelled" in capsys.readouterr().out


def test_reset_db_success_and_missing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(main_mod, "confirm_db_reset", lambda _p: True)

    db_path = tmp_path / "ticktask.db"
    monkeypatch.setattr(main_mod, "default_database_path", lambda: db_path)

    class TrackingDatabase(Database):
        pass

    monkeypatch.setattr(main_mod, "Database", TrackingDatabase)
    main_mod._reset_database_interactively()
    assert "No TickTask database was found." in capsys.readouterr().out

    db_path.write_text("data")
    monkeypatch.setattr(main_mod, "confirm_db_reset", lambda _p: True)
    main_mod._reset_database_interactively()
    assert "deleted" in capsys.readouterr().out


def test_reset_db_database_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(main_mod, "confirm_db_reset", lambda _p: True)
    monkeypatch.setattr(main_mod, "default_database_path", lambda: Path("/tmp/x.db"))

    class BrokenDatabase:
        def __init__(self, path: Path) -> None:
            pass

        def __enter__(self) -> object:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def reset(self) -> bool:
            raise DatabaseError("nope")

    monkeypatch.setattr(main_mod, "Database", BrokenDatabase)
    with pytest.raises(SystemExit) as exc_info:
        main_mod._reset_database_interactively()
    assert exc_info.value.code == 1
    assert "nope" in capsys.readouterr().err


def test_main_reset_db_path(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"n": 0}
    monkeypatch.setattr(
        main_mod, "parse_args", lambda _a: main_mod.CliOptions(True, True, False)
    )

    def fake_reset() -> None:
        called["n"] += 1

    monkeypatch.setattr(main_mod, "_reset_database_interactively", fake_reset)
    main_mod.main([])
    assert called["n"] == 1


def test_main_runs_app(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, Any] = {}
    monkeypatch.setattr(
        main_mod, "parse_args", lambda _a: main_mod.CliOptions(False, False, True)
    )

    def fake_run(*, enable_tray: bool, pomodoro_only: bool) -> None:
        called["tray"] = enable_tray
        called["pomodoro"] = pomodoro_only

    monkeypatch.setattr(main_mod, "_run_app", fake_run)
    main_mod.main([])
    assert called == {"tray": False, "pomodoro": True}


def test_run_app_pomodoro_only_without_tray(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_mod, "TickTask", StubApp)
    main_mod._run_app(enable_tray=False, pomodoro_only=True)

    assert StubApp.ran == 1
    assert len(StubApp.created) == 1
    assert StubApp.created[0].task_management is None


def test_run_app_with_database_and_task_management(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(main_mod, "TickTask", StubApp)

    class FakeDatabase:
        disposed = 0

        def __init__(self, path: Path | None = None) -> None:
            self.session_factory = object()

        def initialize(self) -> None:
            return None

        def dispose(self) -> None:
            self.__class__.disposed += 1

    monkeypatch.setattr(main_mod, "Database", FakeDatabase)
    main_mod._run_app(enable_tray=False, pomodoro_only=False)

    assert StubApp.created[0].task_management is not None
    assert FakeDatabase.disposed == 1


def test_run_app_database_initialize_error_exits(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(main_mod, "TickTask", StubApp)

    class FakeDatabase:
        def __init__(self, path: Path | None = None) -> None:
            self.session_factory = object()

        def initialize(self) -> None:
            raise DatabaseError("schema broken")

        def dispose(self) -> None:
            return None

    monkeypatch.setattr(main_mod, "Database", FakeDatabase)
    with pytest.raises(SystemExit) as exc_info:
        main_mod._run_app(enable_tray=False, pomodoro_only=False)
    assert exc_info.value.code == 1
    assert "schema broken" in capsys.readouterr().err


def test_run_app_reports_cleanup_failures(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr(main_mod, "TickTask", StubApp)

    class BrokenPublisher:
        def start(self) -> None:
            return None

        def publish(self, snapshot: Any) -> None:
            return None

        def close(self) -> None:
            raise RuntimeError("pub close")

    class BrokenDatabase:
        def __init__(self, path: Path | None = None) -> None:
            self.session_factory = object()

        def initialize(self) -> None:
            return None

        def dispose(self) -> None:
            raise RuntimeError("db dispose")

    monkeypatch.setattr(main_mod, "NoOpTimerStatePublisher", BrokenPublisher)
    monkeypatch.setattr(main_mod, "Database", BrokenDatabase)

    main_mod._run_app(enable_tray=False, pomodoro_only=False)
    err = capsys.readouterr().err
    assert "Publisher cleanup failed" in err
    assert "Database cleanup failed" in err


def test_run_app_starts_tray_publisher_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_mod, "TickTask", StubApp)

    class FakeTrayPublisher:
        started = 0
        closed = 0

        def start(self) -> None:
            self.__class__.started += 1

        def publish(self, snapshot: Any) -> None:
            return None

        def close(self) -> None:
            self.__class__.closed += 1

    # TrayPublisher is imported lazily inside _run_app
    import sys
    import types

    fake_tray_module = types.ModuleType("ticktask.infrastructure.ui.desktop.tray")
    fake_tray_module.TrayPublisher = FakeTrayPublisher  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules, "ticktask.infrastructure.ui.desktop.tray", fake_tray_module
    )

    main_mod._run_app(enable_tray=True, pomodoro_only=True)

    assert FakeTrayPublisher.started == 1
    assert FakeTrayPublisher.closed == 1
