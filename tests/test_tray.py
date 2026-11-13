"""Tests for tray sidecar integration."""

from __future__ import annotations

import io
import json
import subprocess
import sys
from collections.abc import Callable
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from ticktask.application.timers import TimerSnapshot
from ticktask.domain.timer import TimerKind, TimerSpec
from ticktask.infrastructure.ui.desktop.ipc import TrayState

# Ensure tray module is importable even when pystray backends are unavailable.
sys.modules.setdefault("pystray", MagicMock())

from ticktask.infrastructure.ui.desktop import tray as tray_mod


class FakeStdin:
    def __init__(self) -> None:
        self.buffer = io.StringIO()
        self.closed = False
        self.fail_writes = False

    def write(self, value: str) -> int:
        if self.fail_writes:
            raise BrokenPipeError("broken")
        return self.buffer.write(value)

    def flush(self) -> None:
        if self.fail_writes:
            raise BrokenPipeError("broken")

    def close(self) -> None:
        self.closed = True


class FakeProcess:
    def __init__(self, *, alive: bool = True, fail_writes: bool = False) -> None:
        self.stdin = FakeStdin()
        self.stdin.fail_writes = fail_writes
        self._alive = alive
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    def poll(self) -> int | None:
        return None if self._alive else 0

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls += 1
        self._alive = False
        return 0

    def terminate(self) -> None:
        self.terminated = True
        self._alive = False

    def kill(self) -> None:
        self.killed = True
        self._alive = False


class FakeIcon:
    def __init__(self) -> None:
        self.icon: Any = None
        self.title: str = ""
        self.visible: bool = False
        self.stopped = False

    def run(self, setup: Any = None) -> None:
        if setup is not None:
            setup(self)

    def stop(self) -> None:
        self.stopped = True


def test_publish_sends_state_payload_to_sidecar() -> None:
    process = FakeProcess()
    publisher = tray_mod.TrayPublisher(
        process_factory=cast(
            Callable[..., subprocess.Popen[str]], lambda *a, **k: process
        )
    )

    state = TrayState("Focus", 10, True, False, "focus")
    publisher.publish_state(state)
    publisher.wait_for_pending_sends()

    payload = json.loads(process.stdin.buffer.getvalue().strip())
    assert payload["type"] == "state"
    assert payload["label"] == "Focus"
    assert payload["remaining_seconds"] == 10
    assert payload["running"] is True
    assert payload["auto_start"] is False

    publisher.close()


def test_publish_timer_snapshot_maps_application_state() -> None:
    process = FakeProcess()
    publisher = tray_mod.TrayPublisher(
        process_factory=cast(
            Callable[..., subprocess.Popen[str]], lambda *a, **k: process
        )
    )
    snapshot = TimerSnapshot(
        timers=(TimerSpec(TimerKind.SHORT_BREAK, 300),),
        current_index=0,
        remaining_seconds=299,
        running=False,
        auto_start=True,
    )

    publisher.publish(snapshot)
    publisher.wait_for_pending_sends()

    payload = json.loads(process.stdin.buffer.getvalue().strip())
    assert payload["label"] == "Short Break"
    assert payload["tone"] == "short-break"
    publisher.close()


def test_start_is_idempotent_and_creates_worker_once() -> None:
    created: list[FakeProcess] = []

    def factory(*args: Any, **kwargs: Any) -> FakeProcess:
        process = FakeProcess()
        created.append(process)
        return process

    publisher = tray_mod.TrayPublisher(
        process_factory=cast(Callable[..., subprocess.Popen[str]], factory)
    )
    publisher.start()
    publisher.start()

    assert len(created) == 1
    assert publisher.is_running is True
    publisher.close()


def test_publish_disables_after_repeated_start_failures() -> None:
    calls = 0

    def factory(*args: Any, **kwargs: Any) -> FakeProcess:
        nonlocal calls
        calls += 1
        return FakeProcess(alive=False)

    publisher = tray_mod.TrayPublisher(
        process_factory=cast(Callable[..., subprocess.Popen[str]], factory)
    )
    state = TrayState("Focus", 10, True, True, "focus")

    for _ in range(5):
        publisher.publish_state(state)

    assert calls == 3
    assert publisher._disabled is True


def test_write_failure_stops_process_without_disable() -> None:
    process = FakeProcess(fail_writes=True)
    publisher = tray_mod.TrayPublisher(
        process_factory=cast(
            Callable[..., subprocess.Popen[str]], lambda *a, **k: process
        )
    )
    publisher.start()
    publisher.publish_state(TrayState("Focus", 10, True, True, "focus"))
    publisher.wait_for_pending_sends()

    assert publisher._process is None
    assert publisher._disabled is False
    publisher.close()


def test_close_handles_dead_process_and_idempotent_cleanup() -> None:
    process = FakeProcess(alive=False)
    publisher = tray_mod.TrayPublisher(
        process_factory=cast(
            Callable[..., subprocess.Popen[str]], lambda *a, **k: process
        )
    )
    publisher.start()
    publisher.close()
    publisher.close()


def test_context_manager_closes_publisher(
    capsys: pytest.CaptureFixture[str],
) -> None:
    process = FakeProcess()
    with tray_mod.TrayPublisher(
        process_factory=cast(
            Callable[..., subprocess.Popen[str]], lambda *a, **k: process
        )
    ):
        pass
    assert "Tray publisher cleanup failed" not in capsys.readouterr().err


def test_reap_process_terminates_and_kills_on_timeout() -> None:
    process = FakeProcess()
    calls = {"wait": 0}

    def wait(timeout: float | None = None) -> int:
        calls["wait"] += 1
        if calls["wait"] == 1:
            raise subprocess.TimeoutExpired(cmd="tray", timeout=timeout or 0)
        if calls["wait"] == 2:
            raise subprocess.TimeoutExpired(cmd="tray", timeout=timeout or 0)
        process._alive = False
        return 0

    process.wait = wait  # type: ignore[method-assign]
    tray_mod.TrayPublisher._reap_process(cast(subprocess.Popen[str], process))

    assert process.terminated is True
    assert process.killed is True


def test_process_tray_messages_applies_state_and_stops_on_shutdown() -> None:
    icon = FakeIcon()
    rendered: list[tuple[str, str, bool]] = []

    def factory(tone: str, time_text: str, running: bool) -> str:
        rendered.append((tone, time_text, running))
        return f"{tone}:{time_text}"

    stream = [
        json.dumps(
            {
                "type": "state",
                "label": "Focus",
                "remaining_seconds": 65,
                "running": True,
                "auto_start": True,
                "tone": "focus",
            }
        )
        + "\n",
        json.dumps(
            {
                "type": "state",
                "label": "Focus",
                "remaining_seconds": 64,
                "running": True,
                "auto_start": True,
                "tone": "focus",
            }
        )
        + "\n",
        json.dumps({"type": "shutdown"}) + "\n",
    ]

    tray_mod._process_tray_messages(
        icon,
        stream=stream,
        icon_image_factory=factory,
        initial_icon_key=("focus", "0m", False),
    )

    assert icon.visible is True
    assert icon.stopped is True
    assert icon.title == "Focus"
    assert rendered == [("focus", "01:05", True)]


def test_process_tray_messages_handles_render_and_stop_errors(
    capsys: pytest.CaptureFixture[str],
) -> None:
    icon = FakeIcon()

    def broken_factory(*args: Any) -> Any:
        raise RuntimeError("render failed")

    def broken_stop() -> None:
        raise RuntimeError("stop failed")

    icon.stop = broken_stop  # type: ignore[method-assign]
    stream = [
        json.dumps(
            {
                "type": "state",
                "label": "Focus",
                "remaining_seconds": 10,
                "running": False,
                "auto_start": True,
                "tone": "focus",
            }
        )
        + "\n"
    ]

    tray_mod._process_tray_messages(
        icon,
        stream=stream,
        icon_image_factory=broken_factory,
        initial_icon_key=("focus", "0s", False),
    )

    err = capsys.readouterr().err
    assert "icon render failed" in err
    assert "icon stop failed" in err


def test_run_tray_sidecar_uses_injected_factories() -> None:
    icon = FakeIcon()

    def icon_factory(name: str, icon_image: Any, title: str) -> FakeIcon:
        assert name == "ticktask"
        assert title == "TickTask"
        return icon

    tray_mod.run_tray_sidecar(
        stream=[],
        icon_factory=icon_factory,
        icon_image_factory=lambda *args: "image",
    )
    assert icon.stopped is True


def test_apply_tray_state_updates_title_even_when_render_skipped() -> None:
    icon = FakeIcon()
    state = TrayState("Focus", 10, True, True, "focus")
    updated = tray_mod._apply_tray_state(
        icon,
        state,
        lambda *args: "img",
        render_icon=False,
    )
    assert updated is True
    assert icon.title == "Focus"
