"""Pomodoro sequence domain model."""

import uuid
from collections.abc import Callable, Sequence

from ticktask.domain.timer import CountdownTimer, TimerSpec, TimerState


class PomodoroSession:
    """Sequence controller for Pomodoro timers."""

    def __init__(
        self,
        timers: Sequence[TimerSpec],
        *,
        clock: Callable[[], float] | None = None,
        id_factory: Callable[[], uuid.UUID] | None = None,
    ) -> None:
        if not timers:
            raise ValueError("PomodoroSession requires at least one timer spec.")

        self._timers: tuple[TimerSpec, ...] = tuple(timers)
        self._current_index: int = 0
        self._clock: Callable[[], float] | None = clock
        self._id_factory: Callable[[], uuid.UUID] | None = id_factory
        self._current_timer: CountdownTimer = self._new_timer()

    @property
    def timers(self) -> tuple[TimerSpec, ...]:
        return self._timers

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def current_timer(self) -> CountdownTimer:
        return self._current_timer

    @property
    def current_spec(self) -> TimerSpec:
        """Return the active timer specification."""
        return self._timers[self._current_index]

    @property
    def current_remaining(self) -> int:
        """Return the active timer's display duration."""
        return self._current_timer.get_display_seconds()

    def start_or_resume_current(self) -> None:
        """Start or resume the active timer when possible."""
        state = self._current_timer.state
        if state == TimerState.RUNNING:
            return
        if state == TimerState.PAUSED:
            self._current_timer.resume()
        else:
            self._current_timer.start()

    def pause_current(self) -> None:
        """Pause the active timer."""
        self._current_timer.pause()

    def advance(self, *, start: bool = False) -> None:
        """Select the next interval, optionally starting it."""
        self._current_index = (self._current_index + 1) % len(self._timers)
        self._replace_current_timer(start=start)

    def restart_current(self, *, start: bool = False) -> None:
        """Replace the active timer with a fresh interval."""
        self._replace_current_timer(start=start)

    def tick(self) -> bool:
        """Return whether the active timer has completed."""
        return self._current_timer.is_finished()

    def _replace_current_timer(self, *, start: bool) -> None:
        self._current_timer = self._new_timer()
        if start:
            self._current_timer.start()

    def _new_timer(self) -> CountdownTimer:
        return CountdownTimer(
            self.current_spec.seconds,
            clock=self._clock,
            id_factory=self._id_factory,
        )


__all__: list[str] = ["PomodoroSession"]
