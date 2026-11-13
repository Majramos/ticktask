"""Application-level Pomodoro orchestration and output snapshots."""

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ticktask.application.ports import TimerStatePublisher
from ticktask.domain.pomodoro import PomodoroSession
from ticktask.domain.timer import TimerKind, TimerSpec

DEFAULT_TIMER_SEQUENCE: tuple[TimerSpec, ...] = (
    TimerSpec(TimerKind.FOCUS, 25 * 60),
    TimerSpec(TimerKind.SHORT_BREAK, 5 * 60),
    TimerSpec(TimerKind.FOCUS, 25 * 60),
    TimerSpec(TimerKind.SHORT_BREAK, 5 * 60),
    TimerSpec(TimerKind.FOCUS, 25 * 60),
    TimerSpec(TimerKind.LONG_BREAK, 15 * 60),
)


@dataclass(frozen=True, slots=True)
class TimerSnapshot:
    """Simple timer state passed to output adapters."""

    timers: tuple[TimerSpec, ...]
    current_index: int
    remaining_seconds: int
    running: bool
    auto_start: bool

    @property
    def current_spec(self) -> TimerSpec:
        """Return the active timer specification."""
        return self.timers[self.current_index]


class PomodoroController:
    """Own timer runtime state and publish state changes through an output port."""

    def __init__(
        self,
        timers: Sequence[TimerSpec],
        publisher: TimerStatePublisher,
        *,
        clock: Callable[[], float] | None = None,
        id_factory: Callable[[], uuid.UUID] | None = None,
    ) -> None:
        self._session: PomodoroSession = PomodoroSession(
            timers, clock=clock, id_factory=id_factory
        )
        self._publisher: TimerStatePublisher = publisher
        self._running: bool = False
        self._auto_start: bool = True
        self._cached_snapshot: TimerSnapshot | None = None

    @property
    def running(self) -> bool:
        """Return whether the timer is currently running."""
        return self._running

    def _invalidate_snapshot(self) -> None:
        self._cached_snapshot = None

    @property
    def snapshot(self) -> TimerSnapshot:
        """Return the current application-facing timer state."""
        if self._cached_snapshot is None:
            self._cached_snapshot = TimerSnapshot(
                timers=self._session.timers,
                current_index=self._session.current_index,
                remaining_seconds=self._session.current_remaining,
                running=self._running,
                auto_start=self._auto_start,
            )
        return self._cached_snapshot

    def publish_current(self) -> None:
        """Publish the current snapshot without changing timer state."""
        if getattr(self._publisher, "_is_noop", False):
            return
        self._publisher.publish(self.snapshot)

    def toggle_run(self) -> None:
        """Toggle the active timer between running and paused."""
        self._invalidate_snapshot()
        if self._running:
            self._running = False
            self._session.pause_current()
        else:
            self._running = True
            self._session.start_or_resume_current()
        self.publish_current()

    def toggle_auto_start(self) -> None:
        """Toggle automatic startup of the next interval."""
        self._invalidate_snapshot()
        self._auto_start = not self._auto_start
        self.publish_current()

    def advance(self) -> None:
        """Advance to the next interval."""
        self._invalidate_snapshot()
        self._session.advance(start=self._running)
        self.publish_current()

    def restart(self) -> None:
        """Restart the current interval."""
        self._invalidate_snapshot()
        self._session.restart_current(start=self._running)
        self.publish_current()

    def pause_and_restart(self) -> None:
        """Pause timer activity and reset the current interval."""
        self._invalidate_snapshot()
        self._running = False
        self._session.restart_current(start=False)
        self.publish_current()

    def tick(self) -> bool:
        """Update timer state and advance after completion."""
        if not self._running:
            return False

        self._invalidate_snapshot()
        completed = self._session.tick()
        if completed:
            self._session.advance(start=self._auto_start)
            if not self._auto_start:
                self._running = False
            self.publish_current()
        return completed


__all__: list[str] = [
    "DEFAULT_TIMER_SEQUENCE",
    "PomodoroController",
    "TimerSnapshot",
]
