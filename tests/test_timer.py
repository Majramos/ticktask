"""Tests for framework-free countdown behavior."""

import uuid

import pytest

from ticktask.domain.timer import CountdownTimer, TimerState


def test_start_pause_resume_and_display_rounding() -> None:
    clock = [100.0]
    timer = CountdownTimer(10, clock=lambda: clock[0])

    assert timer.start() is True
    assert timer.start() is False
    clock[0] += 3.1
    assert timer.get_remaining_seconds() == pytest.approx(6.9)
    assert timer.get_display_seconds() == 7

    assert timer.pause() is True
    paused = timer.get_remaining_seconds()
    clock[0] += 5
    assert timer.get_remaining_seconds() == pytest.approx(paused)
    assert timer.pause() is False

    assert timer.resume() is True
    assert timer.resume() is False
    clock[0] += 2
    assert timer.get_remaining_seconds() == pytest.approx(paused - 2)


def test_finish_and_stop_history_is_immutable() -> None:
    clock = [50.0]
    timer = CountdownTimer(3, clock=lambda: clock[0])
    timer.start()
    clock[0] += 3.5

    assert timer.is_finished() is True
    assert timer.state is TimerState.FINISHED
    assert timer.get_remaining_seconds() == 0
    assert timer.get_display_seconds() == 0
    assert timer.stop() is True
    assert timer.stop() is False
    assert timer.is_finished() is True
    history = timer.get_history()
    assert history[0].status == "FINISHED"
    history.clear()
    assert len(timer.get_history()) == 1


def test_stop_before_completion_and_invalid_transitions() -> None:
    timer = CountdownTimer(5, clock=lambda: 0.0)

    assert timer.pause() is False
    assert timer.resume() is False
    assert timer.stop() is False
    timer.start()
    assert timer.stop() is True
    assert timer.get_history()[0].status == "STOPPED"


def test_pause_detects_expiration() -> None:
    clock = [0.0]
    timer = CountdownTimer(2, clock=lambda: clock[0])
    timer.start()
    clock[0] += 2.1

    assert timer.pause() is False
    assert timer.state is TimerState.FINISHED


@pytest.mark.parametrize("value", [1.5, 2.0])
def test_countdown_accepts_numeric_non_integer_duration(value: float) -> None:
    clock = [0.0]
    timer = CountdownTimer(value, clock=lambda: clock[0])  # type: ignore[arg-type]
    assert timer.start() is True
    assert timer.get_remaining_seconds() == pytest.approx(value)


def test_countdown_rejects_string_duration() -> None:
    with pytest.raises(TypeError):
        CountdownTimer("5")  # type: ignore[arg-type]


def test_zero_duration_finishes_immediately() -> None:
    timer = CountdownTimer(0, clock=lambda: 0.0)
    assert timer.start() is True
    assert timer.is_finished() is True
    assert timer.state is TimerState.FINISHED
    assert timer.get_display_seconds() == 0


def test_run_metadata_properties_expose_sync_and_run_id() -> None:
    marker = uuid.UUID(int=1)
    clock = [7.0]
    timer = CountdownTimer(5, clock=lambda: clock[0], id_factory=lambda: marker)

    assert timer.last_sync_time is None
    assert timer.current_run_id is None
    assert timer.start() is True
    assert timer.last_sync_time == 7.0
    assert timer.current_run_id is marker
    assert timer.remaining_time == 5.0


def test_start_from_stopped_resets_and_starts_new_run() -> None:
    clock = [0.0]
    timer = CountdownTimer(5, clock=lambda: clock[0])
    timer.start()
    clock[0] += 2
    assert timer.stop() is True
    assert timer.state is TimerState.STOPPED

    assert timer.start() is True
    assert timer.state is TimerState.RUNNING  # type: ignore[comparison-overlap]
    assert timer.get_remaining_seconds() == pytest.approx(5.0)


def test_start_from_finished_starts_new_run() -> None:
    clock = [0.0]
    timer = CountdownTimer(3, clock=lambda: clock[0])
    timer.start()
    clock[0] += 3.5
    assert timer.is_finished() is True
    assert timer.state is TimerState.FINISHED

    assert timer.start() is True
    assert timer.state is TimerState.RUNNING  # type: ignore[comparison-overlap]
    assert timer.get_remaining_seconds() == pytest.approx(3.0)


def test_stop_from_paused_transitions_to_stopped() -> None:
    clock = [0.0]
    timer = CountdownTimer(10, clock=lambda: clock[0])
    timer.start()
    clock[0] += 4
    assert timer.pause() is True
    assert timer.state is TimerState.PAUSED

    assert timer.stop() is True
    assert timer.state is TimerState.STOPPED  # type: ignore[comparison-overlap]
    assert timer.get_history()[-1].status == "STOPPED"


def test_timer_state_is_read_only() -> None:
    timer = CountdownTimer(5, clock=lambda: 0.0)
    with pytest.raises(AttributeError):
        timer.state = TimerState.RUNNING  # type: ignore[misc]
    with pytest.raises(AttributeError):
        timer.remaining_time = 99.0  # type: ignore[misc]
