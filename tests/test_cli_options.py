"""Tests for CLI option parsing and reset confirmation."""

from pathlib import Path

import pytest

from ticktask.infrastructure.ui.cli.options import (
    CliOptions,
    confirm_db_reset,
    parse_args,
)


def test_parse_args_defaults() -> None:
    options = parse_args([])
    assert options == CliOptions(tray=True, reset_db=False, pomodoro_only=False)


@pytest.mark.parametrize(
    ("argv", "tray"),
    [
        (["--tray"], True),
        (["--no-tray"], False),
    ],
)
def test_parse_args_tray_flag(argv: list[str], tray: bool) -> None:
    options = parse_args(argv)
    assert options.tray is tray
    assert options.reset_db is False


def test_parse_args_pomodoro_only() -> None:
    options = parse_args(["--pomodoro-only"])
    assert options.pomodoro_only is True
    assert options.reset_db is False


def test_parse_args_reset_db_alone() -> None:
    options = parse_args(["--reset-db"])
    assert options.reset_db is True
    assert options.tray is True


@pytest.mark.parametrize(
    "argv",
    [
        ["--reset-db", "--tray"],
        ["--reset-db", "--no-tray"],
        ["--reset-db", "--pomodoro-only"],
        ["--tray", "--reset-db"],
    ],
)
def test_parse_args_rejects_reset_db_with_other_options(argv: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(argv)


def test_confirm_db_reset_accepts_exact_delete(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "ticktask.db"
    monkeypatch.setattr("builtins.input", lambda _: "DELETE")
    assert confirm_db_reset(db_path) is True
    output = capsys.readouterr().out
    assert str(db_path) in output


@pytest.mark.parametrize("answer", ["delete", "DEL", "", "DELETE ", "yes"])
def test_confirm_db_reset_rejects_non_exact_answers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, answer: str
) -> None:
    monkeypatch.setattr("builtins.input", lambda _: answer)
    assert confirm_db_reset(tmp_path / "ticktask.db") is False
