"""Newline-delimited JSON IPC for tray state transport."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TrayState:
    """Serializable timer state sent from TUI to tray sidecar."""

    label: str
    remaining_seconds: int
    running: bool
    auto_start: bool
    tone: str


def format_tray_title(state: TrayState) -> str:
    """Format live tray title text."""
    return state.label


def state_to_payload(state: TrayState) -> dict[str, Any]:
    """Build the JSON payload for a state update."""
    payload = asdict(state)
    payload["type"] = "state"
    return payload


def serialize_payload(payload: dict[str, Any]) -> str:
    """Serialize one newline-delimited IPC payload."""
    return json.dumps(payload, separators=(",", ":")) + "\n"


def iter_ipc_messages(stream: Iterable[str]) -> Iterable[dict[str, Any]]:
    """Yield decoded dictionary payloads from newline-delimited JSON."""
    for raw_line in stream:
        line = raw_line.strip()
        if not line:
            continue
        try:
            decoded = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            yield decoded


def payload_to_state(payload: dict[str, Any]) -> TrayState | None:
    """Convert payload dictionaries to ``TrayState`` values."""
    if payload.get("type") != "state":
        return None
    try:
        return TrayState(
            label=str(payload["label"]),
            remaining_seconds=max(0, int(payload["remaining_seconds"])),
            running=bool(payload["running"]),
            auto_start=bool(payload["auto_start"]),
            tone=str(payload["tone"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


__all__: list[str] = [
    "TrayState",
    "format_tray_title",
    "iter_ipc_messages",
    "payload_to_state",
    "serialize_payload",
    "state_to_payload",
]
