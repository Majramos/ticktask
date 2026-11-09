"""Tests for the Pomodoro sequence domain model."""

import uuid
from collections.abc import Callable

import pytest

from ticktask.domain.pomodoro import PomodoroSession
from ticktask.domain.timer import TimerKind, TimerSpec, TimerState


def make_specs() -> list[TimerSpec]:
    return [
        TimerSpec(TimerKind.FOCUS, 5),
        TimerSpec(TimerKind.SHORT_BREAK, 2),
        TimerSpec(TimerKind.LONG_BREAK, 3),
    ]


def make_clock() -> tuple[list[float], Callable[[], float]]:
    state: list[float] = [0.0]

    def clock() -> float:
        return state[0]

    return state, clock


def test_session_requires_at_least_one_timer_spec() -> None:
    with pytest.raises(ValueError, match="at least one timer spec"):
        PomodoroSession([])


def test_session_holds_timer_specs_and_initial_index() -> None:
    specs = make_specs()
    session = PomodoroSession(specs)

    assert session.timers == tuple(specs)
    assert session.current_index == 0
    assert session.current_spec is specs[0]


def test_session_exposes_id_factory_through_current_run_id() -> None:
    marker = uuid.UUID(int=7)
    session = PomodoroSession(make_specs(), id_factory=lambda: marker)

    assert session.current_timer.current_run_id is None
    session.start_or_resume_current()
    assert session.current_timer.current_run_id is marker


def test_current_remaining_uses_display_rounding() -> None:
    clock_state, clock = make_clock()
    session = PomodoroSession([TimerSpec(TimerKind.FOCUS, 5)], clock=clock)
    session.start_or_resume_current()
    clock_state[0] += 0.5

    assert session.current_remaining == 5


def test_start_or_resume_starts_fresh_timer_and_resumes_paused() -> None:
    _clock_state, clock = make_clock()
    session = PomodoroSession([TimerSpec(TimerKind.FOCUS, 5)], clock=clock)

    session.start_or_resume_current()
    assert session.current_timer.state is TimerState.RUNNING

    session.pause_current()
    assert session.current_timer.state is TimerState.PAUSED  # type: ignore[comparison-overlap]

    session.start_or_resume_current()
    assert session.current_timer.state is TimerState.RUNNING


def test_start_or_resume_ignores_running_timer() -> None:
    clock_state, clock = make_clock()
    session = PomodoroSession([TimerSpec(TimerKind.FOCUS, 5)], clock=clock)
    session.start_or_resume_current()
    clock_state[0] += 2
    remaining = session.current_timer.get_remaining_seconds()

    session.start_or_resume_current()
    assert session.current_timer.get_remaining_seconds() == pytest.approx(remaining)


def test_pause_current_resets_on_stop_only_via_new_timer() -> None:
    session = PomodoroSession([TimerSpec(TimerKind.FOCUS, 5)], clock=lambda: 0.0)
    started = session.current_timer
    session.pause_current()
    assert started.state is TimerState.INITIALIZED


def test_advance_moves_to_next_index_and_wraps() -> None:
    specs = make_specs()
    session = PomodoroSession(specs, clock=lambda: 0.0)

    session.advance()
    assert session.current_index == 1
    assert session.current_spec is specs[1]

    session.advance()
    session.advance()
    assert session.current_index == 0
    assert session.current_spec is specs[0]


def test_advance_replaces_current_timer() -> None:
    session = PomodoroSession(make_specs())
    original = session.current_timer

    session.advance()
    assert session.current_timer is not original
    assert session.current_timer.state is TimerState.INITIALIZED


def test_advance_with_start_boots_the_new_timer() -> None:
    session = PomodoroSession(make_specs())

    session.advance(start=True)
    assert session.current_timer.state is TimerState.RUNNING


def test_restart_current_resets_active_timer() -> None:
    clock_state, clock = make_clock()
    session = PomodoroSession([TimerSpec(TimerKind.FOCUS, 5)], clock=clock)
    session.start_or_resume_current()
    clock_state[0] += 2

    original = session.current_timer
    session.restart_current()

    assert session.current_timer is not original
    assert session.current_timer.state is TimerState.INITIALIZED
    assert session.current_index == 0


def test_restart_current_with_start_boots_timer() -> None:
    session = PomodoroSession(make_specs())

    session.restart_current(start=True)
    assert session.current_timer.state is TimerState.RUNNING


def test_tick_reports_whether_timer_completed() -> None:
    clock_state, clock = make_clock()
    session = PomodoroSession([TimerSpec(TimerKind.SHORT_BREAK, 2)], clock=clock)

    assert session.tick() is False
    session.start_or_resume_current()
    clock_state[0] += 3.0
    assert session.tick() is True
    assert session.current_timer.state is TimerState.FINISHED


def test_session_propagates_clock_to_timers() -> None:
    clock_state, clock = make_clock()
    session = PomodoroSession([TimerSpec(TimerKind.FOCUS, 5)], clock=clock)
    session.start_or_resume_current()
    clock_state[0] += 3

    assert session.current_timer.get_remaining_seconds() == pytest.approx(2.0)
