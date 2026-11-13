"""Tests for Pomodoro application orchestration and publishers."""

from tests.fakes import RecordingPublisher
from ticktask.application.publishers import NoOpTimerStatePublisher
from ticktask.application.timers import (
    DEFAULT_TIMER_SEQUENCE,
    PomodoroController,
    TimerSnapshot,
)
from ticktask.domain.timer import TimerKind, TimerSpec


def make_controller(
    *,
    timers: list[TimerSpec] | None = None,
    publisher: RecordingPublisher | NoOpTimerStatePublisher | None = None,
    clock_state: list[float] | None = None,
    auto_start: bool | None = None,
) -> tuple[PomodoroController, RecordingPublisher, list[float]]:
    clock_state = [0.0] if clock_state is None else clock_state
    active_publisher = RecordingPublisher() if publisher is None else publisher
    specs = (
        timers
        if timers is not None
        else [
            TimerSpec(TimerKind.FOCUS, 5),
            TimerSpec(TimerKind.SHORT_BREAK, 2),
        ]
    )
    controller = PomodoroController(
        specs, active_publisher, clock=lambda: clock_state[0]
    )
    if isinstance(active_publisher, RecordingPublisher):
        recorder = active_publisher
    else:
        recorder = RecordingPublisher()
    if auto_start is False:
        controller.toggle_auto_start()
    return controller, recorder, clock_state


def test_default_timer_sequence_matches_pomodoro_cycle() -> None:
    assert len(DEFAULT_TIMER_SEQUENCE) == 6
    assert [spec.kind for spec in DEFAULT_TIMER_SEQUENCE] == [
        TimerKind.FOCUS,
        TimerKind.SHORT_BREAK,
        TimerKind.FOCUS,
        TimerKind.SHORT_BREAK,
        TimerKind.FOCUS,
        TimerKind.LONG_BREAK,
    ]
    assert DEFAULT_TIMER_SEQUENCE[0].seconds == 25 * 60
    assert DEFAULT_TIMER_SEQUENCE[-1].seconds == 15 * 60


def test_timer_snapshot_exposes_current_spec() -> None:
    snapshot = TimerSnapshot(
        timers=(TimerSpec(TimerKind.FOCUS, 30),),
        current_index=0,
        remaining_seconds=30,
        running=False,
        auto_start=True,
    )
    assert snapshot.current_spec is snapshot.timers[0]


def test_controller_exposes_initial_snapshot() -> None:
    controller, _, _ = make_controller()
    snapshot = controller.snapshot

    assert snapshot.running is False
    assert snapshot.auto_start is True
    assert snapshot.current_index == 0
    assert snapshot.current_spec.kind is TimerKind.FOCUS
    assert snapshot.remaining_seconds == 5


def test_controller_running_property_reflects_toggle() -> None:
    controller, _, _ = make_controller()

    assert controller.running is False
    controller.toggle_run()
    assert controller.running is True
    controller.toggle_run()
    assert controller.running is False


def test_toggle_run_publishes_snapshots() -> None:
    controller, publisher, _ = make_controller()

    controller.toggle_run()
    controller.toggle_run()

    assert [snap.running for snap in publisher.snapshots] == [True, False]


def test_toggle_auto_start_publishes_updated_flag() -> None:
    controller, publisher, _ = make_controller()

    controller.toggle_auto_start()
    controller.toggle_auto_start()

    assert [snap.auto_start for snap in publisher.snapshots] == [False, True]


def test_advance_publishes_next_interval() -> None:
    controller, publisher, _ = make_controller()

    controller.advance()

    assert publisher.snapshots[-1].current_index == 1
    assert publisher.snapshots[-1].current_spec.kind is TimerKind.SHORT_BREAK


def test_advance_while_running_starts_next_timer() -> None:
    controller, _, _ = make_controller()
    controller.toggle_run()

    controller.advance()

    assert controller.running is True
    assert controller.snapshot.current_index == 1
    assert controller.snapshot.current_spec.kind is TimerKind.SHORT_BREAK


def test_restart_resets_current_interval_and_preserves_running_state() -> None:
    controller, publisher, clock = make_controller()
    controller.toggle_run()
    clock[0] += 3

    controller.restart()

    assert controller.running is True
    assert controller.snapshot.remaining_seconds == 5
    assert publisher.snapshots[-1].running is True


def test_pause_and_restart_stops_and_resets_interval() -> None:
    controller, publisher, clock = make_controller()
    controller.toggle_run()
    clock[0] += 3

    controller.pause_and_restart()

    assert controller.running is False
    assert controller.snapshot.running is False
    assert controller.snapshot.remaining_seconds == 5
    assert publisher.snapshots[-1].running is False


def test_tick_does_nothing_when_not_running() -> None:
    controller, publisher, _ = make_controller()

    completed = controller.tick()

    assert completed is False
    assert publisher.snapshots == []


def test_tick_advances_after_completion_and_keeps_running() -> None:
    controller, publisher, clock = make_controller()
    controller.toggle_run()
    clock[0] += 6

    completed = controller.tick()

    assert completed is True
    assert controller.running is True
    assert controller.snapshot.current_index == 1
    assert controller.snapshot.running is True
    assert publisher.snapshots[-1].current_index == 1


def test_tick_completion_with_auto_start_disabled_pauses() -> None:
    controller, publisher, clock = make_controller()
    controller.toggle_auto_start()
    controller.toggle_run()
    clock[0] += 6

    completed = controller.tick()

    assert completed is True
    assert controller.running is False
    assert controller.snapshot.running is False
    assert controller.snapshot.current_index == 1
    assert publisher.snapshots[-1].running is False
    assert publisher.snapshots[-1].auto_start is False


def test_publish_current_sends_snapshot_to_publisher() -> None:
    controller, publisher, _ = make_controller()

    controller.publish_current()

    assert len(publisher.snapshots) == 1
    assert publisher.snapshots[0].current_spec.kind is TimerKind.FOCUS


def test_noop_publisher_lifecycle_and_skip_publish() -> None:
    publisher = NoOpTimerStatePublisher()
    publisher.start()
    controller = PomodoroController(
        [TimerSpec(TimerKind.FOCUS, 5)], publisher, clock=lambda: 0.0
    )

    controller.publish_current()  # no-op path: getattr _is_noop
    controller.toggle_run()  # also calls publish_current
    assert controller.running is True
    publisher.publish(controller.snapshot)
    publisher.close()
