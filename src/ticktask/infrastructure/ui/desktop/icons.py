"""Tray icon image rendering."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from PIL import Image, ImageColor, ImageDraw, ImageFont

from ticktask.adapters.presenters import DEFAULT_TIMER_TONE_COLORS, TIMER_TONE_COLORS
from ticktask.domain.timer import TimerKind

_FONT_CANDIDATES: tuple[str, ...] = (
    "DejaVuSansMono-Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "Arial Bold.ttf",
    "Helvetica.ttc",
)
_STOPPED_FILLS: tuple[tuple[int, ...], tuple[int, ...]] = (
    (15, 17, 21, 245),
    (17, 24, 39, 245),
)
_ICON_SIZE: int = 64
_TEXT_BOX_SIZE: tuple[int, int] = (60, 46)
_TEXT_STROKE_WIDTH: int = 1
_OUTER_MARGIN: int = 1
_OUTER_RADIUS: int = 13
_OUTER_BORDER_WIDTH: int = 3
_INNER_MARGIN: int = 5
_INNER_RADIUS: int = 9
_FALLBACK_FONT_SIZE: int = 14


def compact_icon_time_text(time_text: str) -> str:
    """Normalize timer text so it stays legible in tiny tray icon slots."""
    if not time_text:
        return "0s"
    try:
        minute_text, second_text = time_text.split(":", 1)
        minutes = max(0, int(minute_text))
        seconds = max(0, int(second_text))
    except (ValueError, TypeError):
        return time_text
    total_seconds = (minutes * 60) + seconds
    return f"{total_seconds // 60}m" if total_seconds >= 60 else f"{total_seconds}s"


def build_icon_image(tone: str, time_text: str, running: bool = False) -> Image.Image:
    """Return a tone-aware icon image with live timer text."""
    try:
        timer_kind = TimerKind(tone)
    except ValueError:
        timer_kind = None
    tone_colors = (
        DEFAULT_TIMER_TONE_COLORS
        if timer_kind is None
        else TIMER_TONE_COLORS[timer_kind]
    )
    accent = ImageColor.getrgb(tone_colors.accent)
    fills = _icon_fills(tone_colors.background, running=running)
    image = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    _draw_icon_background(draw, accent, fills)
    _draw_icon_text(draw, compact_icon_time_text(time_text))
    return image


def _icon_fills(
    background: str, *, running: bool
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if not running:
        return _STOPPED_FILLS
    fill = (*ImageColor.getrgb(background), 245)
    return fill, fill


def _draw_icon_background(
    draw: Any,
    accent: Any,
    fills: tuple[tuple[int, ...], tuple[int, ...]],
) -> None:
    outer_fill, inner_fill = fills
    edge = _ICON_SIZE - 1
    draw.rounded_rectangle(
        (
            _OUTER_MARGIN,
            _OUTER_MARGIN,
            edge - _OUTER_MARGIN,
            edge - _OUTER_MARGIN,
        ),
        radius=_OUTER_RADIUS,
        fill=outer_fill,
        outline=(*accent, 255),
        width=_OUTER_BORDER_WIDTH,
    )
    draw.rounded_rectangle(
        (
            _INNER_MARGIN,
            _INNER_MARGIN,
            edge - _INNER_MARGIN,
            edge - _INNER_MARGIN,
        ),
        radius=_INNER_RADIUS,
        fill=inner_fill,
    )


def _load_icon_font(draw: Any, text: str) -> Any:
    for size in range(36, 11, -1):
        for font_name in _FONT_CANDIDATES:
            candidate = _load_font_candidate(font_name, size)
            if candidate is None:
                continue
            width, height = _text_size(draw, text, candidate)
            if width <= _TEXT_BOX_SIZE[0] and height <= _TEXT_BOX_SIZE[1]:
                return candidate
    fallback = _load_font_candidate("DejaVuSansMono-Bold.ttf", _FALLBACK_FONT_SIZE)
    return fallback if fallback is not None else ImageFont.load_default()


@lru_cache(maxsize=128)
def _load_font_candidate(font_name: str, size: int) -> Any | None:
    try:
        return ImageFont.truetype(font_name, size)
    except OSError:
        return None


def _text_size(draw: Any, text: str, font: Any) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox(
        (0, 0), text, font=font, stroke_width=_TEXT_STROKE_WIDTH
    )
    return right - left, bottom - top


def _draw_icon_text(draw: Any, text: str) -> None:
    font = _load_icon_font(draw, text)
    width, height = _text_size(draw, text, font)
    draw.text(
        ((_ICON_SIZE - width) // 2, (_ICON_SIZE - height) // 2),
        text,
        fill=(241, 245, 249, 255),
        font=font,
        stroke_width=_TEXT_STROKE_WIDTH,
        stroke_fill=(2, 6, 23, 235),
    )


__all__: list[str] = ["build_icon_image", "compact_icon_time_text"]
