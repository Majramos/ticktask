"""Tests for tray IPC serialization and parsing."""

from ticktask.infrastructure.ui.desktop.ipc import (
    TrayState,
    format_tray_title,
    iter_ipc_messages,
    payload_to_state,
    serialize_payload,
    state_to_payload,
)


def test_tray_state_and_title_formatting() -> None:
    state = TrayState(
        label="Focus",
        remaining_seconds=90,
        running=True,
        auto_start=False,
        tone="focus",
    )
    assert format_tray_title(state) == "Focus"


def test_state_payload_round_trip() -> None:
    state = TrayState("Short Break", 45, False, True, "short-break")
    payload = state_to_payload(state)
    serialized = serialize_payload(payload)
    messages = list(iter_ipc_messages([serialized]))

    assert len(messages) == 1
    assert payload_to_state(messages[0]) == state


def test_iter_ipc_messages_ignores_invalid_and_non_dict_lines() -> None:
    lines = [
        "\n",
        "not json\n",
        '{"type":"state","label":"ok","remaining_seconds":1,"running":true,"auto_start":true,"tone":"focus"}\n',
        '["array"]\n',
        "  \n",
    ]
    messages = list(iter_ipc_messages(lines))

    assert messages == [
        {
            "type": "state",
            "label": "ok",
            "remaining_seconds": 1,
            "running": True,
            "auto_start": True,
            "tone": "focus",
        }
    ]


def test_payload_to_state_returns_none_for_invalid_payloads() -> None:
    assert payload_to_state({"type": "other"}) is None
    assert payload_to_state({"type": "state"}) is None
    assert payload_to_state({"type": "state", "label": "x"}) is None


def test_payload_to_state_coerces_and_clamps_values() -> None:
    state = payload_to_state(
        {
            "type": "state",
            "label": 123,
            "remaining_seconds": -5,
            "running": 1,
            "auto_start": 0,
            "tone": None,
        }
    )

    assert state == TrayState(
        label="123",
        remaining_seconds=0,
        running=True,
        auto_start=False,
        tone="None",
    )
