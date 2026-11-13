"""Tests for tray icon helpers."""

from PIL import Image

from ticktask.infrastructure.ui.desktop.icons import (
    build_icon_image,
    compact_icon_time_text,
)


def test_compact_icon_time_text_variants() -> None:
    assert compact_icon_time_text("") == "0s"
    assert compact_icon_time_text("00:59") == "59s"
    assert compact_icon_time_text("00:10") == "10s"
    assert compact_icon_time_text("25:00") == "25m"
    assert compact_icon_time_text("90:00") == "90m"
    assert compact_icon_time_text("bad") == "bad"


def test_compact_icon_time_text_handles_malformed_but_split_values() -> None:
    assert compact_icon_time_text("abc:def") == "abc:def"
    assert compact_icon_time_text("01:02:03") == "01:02:03"


def test_build_icon_image_returns_rgba_icon() -> None:
    image = build_icon_image("focus", "25:00", running=False)

    assert isinstance(image, Image.Image)
    assert image.size == (64, 64)
    assert image.mode == "RGBA"


def test_build_icon_image_handles_unknown_tone_and_running_state() -> None:
    stopped = build_icon_image("unknown", "00:05", running=False)
    running = build_icon_image("short-break", "00:05", running=True)

    assert stopped.size == (64, 64)
    assert running.size == (64, 64)
    assert stopped.tobytes() != running.tobytes()
