import math
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, StrEnum, auto
from typing import Literal

type TimerHistoryStatus = Literal["STOPPED", "FINISHED"]


class TimerKind(StrEnum):
    FOCUS = "focus"
    SHORT_BREAK = "short-break"
    LONG_BREAK = "long-break"


@dataclass(frozen=True, slots=True)
class TimerSpec:
    kind: TimerKind
    seconds: int


@dataclass(frozen=True, slots=True)
class TimerHistoryEntry:
    run_id: uuid.UUID | None
    final_remaining: float
    status: TimerHistoryStatus


class TimerState(Enum):
    INITIALIZED = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    FINISHED = auto()


class CountdownTimer:
    def __init__(
        self,
        countdown_seconds: int,
        *,
        clock: Callable[[], float] | None = None,
        id_factory: Callable[[], uuid.UUID] | None = None,
    ) -> None:
        if countdown_seconds < 0:
            raise ValueError("Countdown time must be a non-negative integer.")

        self._clock: Callable[[], float] = (
            clock if clock is not None else time.monotonic
        )
        self._id_factory: Callable[[], uuid.UUID] = (
            id_factory if id_factory is not None else uuid.uuid4
        )

        self.initial_duration: int = countdown_seconds
        self._remaining_time: float = float(countdown_seconds)
        self._state: TimerState = TimerState.INITIALIZED
        self._last_sync_time: float | None = None
        self._current_run_id: uuid.UUID | None = None
        self._history: list[TimerHistoryEntry] = []

    @property
    def remaining_time(self) -> float:
        return self._remaining_time

    @property
    def state(self) -> TimerState:
        return self._state

    @property
    def last_sync_time(self) -> float | None:
        return self._last_sync_time

    @property
    def current_run_id(self) -> uuid.UUID | None:
        return self._current_run_id

    def start(self) -> bool:
        if self.state in (TimerState.RUNNING, TimerState.PAUSED):
            return False

        self._current_run_id = self._id_factory()
        self._remaining_time = float(self.initial_duration)
        self._last_sync_time = self._clock()
        self._state = TimerState.RUNNING

        return True

    def pause(self) -> bool:
        if self._state != TimerState.RUNNING:
            return False

        self._update_remaining()
        if self.is_finished():
            return False

        self._state = TimerState.PAUSED
        return True

    def resume(self) -> bool:
        if self._state != TimerState.PAUSED:
            return False

        if self.is_finished():
            self._state = TimerState.FINISHED
            return False

        self._last_sync_time = self._clock()
        self._state = TimerState.RUNNING
        return True

    def stop(self) -> bool:
        if self._state in (TimerState.INITIALIZED, TimerState.STOPPED):
            return False

        self._update_remaining()
        self._history.append(self._build_history_entry())
        self._state = TimerState.STOPPED
        return True

    def is_finished(self) -> bool:
        if self._state == TimerState.RUNNING:
            self._update_remaining()

        if self._remaining_time <= 0:
            if self.state != TimerState.STOPPED:
                self._state = TimerState.FINISHED
            return True
        return False

    def get_remaining_seconds(self) -> float:
        if self.state == TimerState.RUNNING:
            self._update_remaining()
        return max(0.0, self.remaining_time)

    def get_display_seconds(self) -> int:
        remaining_seconds = self.get_remaining_seconds()
        return 0 if remaining_seconds <= 0 else math.ceil(remaining_seconds)

    def get_history(self) -> list[TimerHistoryEntry]:
        return list(self._history)

    def _update_remaining(self) -> None:
        if self._state != TimerState.RUNNING or self._last_sync_time is None:
            return

        now = self._clock()
        self._remaining_time -= now - self._last_sync_time
        self._last_sync_time = now

        if self._remaining_time <= 0:
            self._remaining_time = 0.0
            self._state = TimerState.FINISHED

    def _build_history_entry(self) -> TimerHistoryEntry:
        final_remaning = max(0.0, self._remaining_time)
        status: TimerHistoryStatus = "STOPPED" if final_remaning > 0 else "FINISHED"
        return TimerHistoryEntry(
            run_id=self._current_run_id, final_remaining=final_remaning, status=status
        )


__all__: list[str] = [
    "CountdownTimer",
    "TimerHistoryEntry",
    "TimerHistoryStatus",
    "TimerKind",
    "TimerSpec",
    "TimerState",
]
