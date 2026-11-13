"""System tray sidecar integration for TickTask."""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
from collections.abc import Callable, Iterable
from functools import partial
from types import TracebackType
from typing import Any, Protocol, Self, cast

from pystray import Icon

from ticktask.adapters.presenters import format_seconds, timer_label
from ticktask.application.timers import TimerSnapshot
from ticktask.infrastructure.ui.desktop.icons import (
    build_icon_image,
    compact_icon_time_text,
)
from ticktask.infrastructure.ui.desktop.ipc import (
    TrayState,
    format_tray_title,
    iter_ipc_messages,
    payload_to_state,
    serialize_payload,
    state_to_payload,
)

_MAX_START_FAILURES: int = 3
_SHUTDOWN_SENTINEL: Any = object()


class SupportsTrayIcon(Protocol):
    """Protocol for pystray-compatible icon objects."""

    icon: Any
    title: str
    visible: bool

    def run(self, setup: Callable[[Any], None] | None = None) -> None:
        """Run icon event loop."""

    def stop(self) -> None:
        """Stop icon event loop."""


class TrayPublisher:
    """Sidecar process manager for publishing tray timer updates."""

    def __init__(
        self,
        *,
        python_executable: str | None = None,
        process_factory: Callable[..., subprocess.Popen[str]] = subprocess.Popen,
    ) -> None:
        self.python_executable: str = python_executable or sys.executable
        self.process_factory: Callable[..., subprocess.Popen[str]] = process_factory
        self._process: subprocess.Popen[str] | None = None
        self._start_failures: int = 0
        self._disabled: bool = False
        self._cleanup_thread: threading.Thread | None = None
        self._send_queue: queue.Queue[Any] = queue.Queue()
        self._worker_thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the tray sidecar if it isn't already running."""
        if self.is_running or self._disabled:
            return
        self._process = self.process_factory(
            [
                self.python_executable,
                "-m",
                "ticktask.infrastructure.ui.desktop.tray",
            ],
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        if self._worker_thread is None:
            self._worker_thread = threading.Thread(
                target=self._send_loop,
                daemon=True,
            )
            self._worker_thread.start()

    @property
    def is_running(self) -> bool:
        """Return `True` when the sidecar process is alive."""
        return (process := self._process) is not None and process.poll() is None

    def publish_state(self, state: TrayState) -> None:
        """Enqueue one state update if the sidecar is alive."""
        running = self.is_running
        if not running and not self._disabled:
            self.start()
            running = self.is_running
        if not running:
            if not self._disabled:
                self._start_failures += 1
                if self._start_failures >= _MAX_START_FAILURES:
                    self._disabled = True
            return
        self._start_failures = 0
        self._send_queue.put(state)

    def publish(self, snapshot: TimerSnapshot) -> None:
        """Publish an application timer snapshot to the tray sidecar."""
        kind = snapshot.current_spec.kind
        self.publish_state(
            TrayState(
                label=timer_label(kind),
                remaining_seconds=snapshot.remaining_seconds,
                running=snapshot.running,
                auto_start=snapshot.auto_start,
                tone=kind.value,
            )
        )

    def close(self) -> None:
        """Gracefully stop the sidecar process."""
        if self._cleanup_thread is not None:
            self._cleanup_thread.join()
            self._cleanup_thread = None
        self._send_queue.put(_SHUTDOWN_SENTINEL)
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=2.0)
            self._worker_thread = None
        self._stop_process(send_shutdown=True)

    def wait_for_pending_sends(self, timeout: float = 2.0) -> None:
        """Block until all queued sends are written (for testing)."""
        if self._worker_thread is not None:
            self._send_queue.join()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.close()
        except Exception as error:  # noqa: BLE001 -- best-effort cleanup
            print(f"Tray publisher cleanup failed: {error}", file=sys.stderr)

    def _send_loop(self) -> None:
        while True:
            item = self._send_queue.get()
            try:
                if item is _SHUTDOWN_SENTINEL:
                    break
                self._send_payload(state_to_payload(item))
            finally:
                self._send_queue.task_done()

    def _send_payload(self, payload: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            return
        if not self._write_payload(self._process, payload):
            self._stop_process(send_shutdown=False, blocking=False)

    def _stop_process(
        self,
        *,
        send_shutdown: bool,
        blocking: bool = True,
    ) -> None:
        process = self._process
        if process is None:
            return
        self._process = None

        if process.poll() is None:
            if send_shutdown:
                self._write_payload(process, {"type": "shutdown"})
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except (BrokenPipeError, OSError, ValueError):
                    pass

        if blocking:
            self._reap_process(process)
        else:
            self._cleanup_thread = threading.Thread(
                target=self._reap_process,
                args=(process,),
                daemon=True,
            )
            self._cleanup_thread.start()

    @staticmethod
    def _reap_process(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1.0)

    @staticmethod
    def _write_payload(
        process: subprocess.Popen[str],
        payload: dict[str, Any],
    ) -> bool:
        if process.stdin is None:
            return False
        try:
            process.stdin.write(serialize_payload(payload))
            process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            return False
        return True


def _default_icon_factory(
    name: str,
    icon_image: Any,
    title: str,
) -> SupportsTrayIcon:
    """Create a pystray icon instance lazily."""
    return cast(SupportsTrayIcon, Icon(name, icon_image, title))


def _apply_tray_state(
    icon: SupportsTrayIcon,
    state: TrayState,
    icon_image_factory: Callable[[str, str, bool], Any],
    *,
    render_icon: bool = True,
) -> bool:
    icon_updated = not render_icon
    if render_icon:
        time_text = format_seconds(state.remaining_seconds)
        try:
            icon.icon = icon_image_factory(state.tone, time_text, state.running)
            icon_updated = True
        except Exception as error:  # noqa: BLE001 -- pystray raises anything
            print(
                f"tray: icon render failed: {type(error).__name__}: {error}",
                file=sys.stderr,
            )
    try:
        icon.title = format_tray_title(state)
    except Exception as error:  # noqa: BLE001 -- pystray raises anything
        print(
            f"tray: title update failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
    return icon_updated


def _process_tray_messages(
    icon: SupportsTrayIcon,
    *,
    stream: Iterable[str],
    icon_image_factory: Callable[[str, str, bool], Any],
    initial_icon_key: tuple[str, str, bool],
) -> None:
    icon.visible = True
    current_icon_key = initial_icon_key
    try:
        for payload in iter_ipc_messages(stream):
            if payload.get("type") == "shutdown":
                break
            state = payload_to_state(payload)
            if state is not None:
                next_icon_key = _tray_icon_key(state)
                icon_updated = _apply_tray_state(
                    icon,
                    state,
                    icon_image_factory,
                    render_icon=next_icon_key != current_icon_key,
                )
                if icon_updated:
                    current_icon_key = next_icon_key
    finally:
        try:
            icon.stop()
        except Exception as error:  # noqa: BLE001 -- best-effort cleanup
            print(
                f"tray: icon stop failed: {type(error).__name__}: {error}",
                file=sys.stderr,
            )


def _tray_icon_key(state: TrayState) -> tuple[str, str, bool]:
    time_text = format_seconds(state.remaining_seconds)
    return state.tone, compact_icon_time_text(time_text), state.running


def run_tray_sidecar(
    *,
    stream: Iterable[str] | None = None,
    icon_factory: Callable[[str, Any, str], SupportsTrayIcon] | None = None,
    icon_image_factory: Callable[[str, str, bool], Any] = build_icon_image,
) -> None:
    """Run the tray sidecar event loop."""
    input_stream = sys.stdin if stream is None else stream
    initial_tone = "focus"
    initial_time_text = "00:00"
    initial_running = False
    icon = (icon_factory or _default_icon_factory)(
        "ticktask",
        icon_image_factory(initial_tone, initial_time_text, initial_running),
        "TickTask",
    )
    setup = partial(
        _process_tray_messages,
        stream=input_stream,
        icon_image_factory=icon_image_factory,
        initial_icon_key=(
            initial_tone,
            compact_icon_time_text(initial_time_text),
            initial_running,
        ),
    )
    icon.run(setup=setup)


def main() -> None:
    """Run the tray sidecar when the module is launched as a script."""
    run_tray_sidecar()


if __name__ == "__main__":
    main()


__all__: list[str] = [
    "SupportsTrayIcon",
    "TrayPublisher",
    "TrayState",
    "build_icon_image",
    "compact_icon_time_text",
    "format_tray_title",
    "iter_ipc_messages",
    "main",
    "payload_to_state",
    "run_tray_sidecar",
    "serialize_payload",
    "state_to_payload",
]
