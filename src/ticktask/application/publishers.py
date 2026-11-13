"""Dependency-free publisher implementations."""

from ticktask.application.timers import TimerSnapshot


class NoOpTimerStatePublisher:
    """Discard timer snapshots when tray integration is disabled."""

    _is_noop: bool = True

    def start(self) -> None:
        """Provide the same lifecycle surface as the real publisher."""

    def publish(self, snapshot: TimerSnapshot) -> None:
        """Accept a snapshot without performing output."""

    def close(self) -> None:
        """Provide the same lifecycle surface as the real publisher."""


__all__: list[str] = ["NoOpTimerStatePublisher"]
