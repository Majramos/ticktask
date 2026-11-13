"""Textual timer carousel widgets driven by application snapshots."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import HorizontalGroup
from textual.widgets import Static

from ticktask.adapters.presenters import (
    DEFAULT_TIMER_TONE_COLORS,
    TIMER_TONE_COLORS,
    format_seconds,
    timer_label,
)
from ticktask.application.timers import TimerSnapshot
from ticktask.domain.timer import TimerKind, TimerSpec


class TimerCard(Static):
    """A single card in the timer carousel."""

    STATE_CLASSES: ClassVar[tuple[str, ...]] = ("past", "future", "current")

    def __init__(
        self,
        slot_offset: int,
        *,
        id: str | None = None,
        classes: str | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes, name=name)
        self.slot_offset: int = slot_offset
        self._content: tuple[str, str, TimerKind, str] | None = None
        self._name_widget: Static | None = None
        self._value_widget: Static | None = None
        self._position_widget: Static | None = None
        self.add_class("timer-card")
        self.add_class("slot-center" if slot_offset == 0 else "slot-side")
        if abs(slot_offset) == 2:
            self.add_class("slot-far")

    def compose(self) -> ComposeResult:
        yield Static(classes="timer-name")
        yield Static(classes="timer-value")
        yield Static(classes="timer-position")

    def on_mount(self) -> None:
        self._name_widget = self.query_one(".timer-name", Static)
        self._value_widget = self.query_one(".timer-value", Static)
        self._position_widget = self.query_one(".timer-position", Static)

    def set_content(
        self,
        *,
        label: str,
        value: str,
        kind: TimerKind,
        is_past: bool,
        is_current: bool,
    ) -> None:
        """Render timer metadata and apply its visual state."""
        state = "past" if is_past else "current" if is_current else "future"
        displayed_value = "" if is_past else value
        content = (label, displayed_value, kind, state)
        previous = self._content
        if previous == content:
            return

        name_widget, value_widget, position_widget = self._content_widgets()
        if previous is None or previous[2:] != content[2:]:
            self._apply_state(state, kind)
        if previous is None or previous[0] != label:
            name_widget.update(label)
        if previous is None or previous[1] != displayed_value:
            value_widget.update(displayed_value)
        if previous is None:
            position_widget.update(self._position_label())
        self._content = content

    def set_value(self, value: str) -> None:
        """Update only the displayed timer value when card metadata is stable."""
        if self._content is None or self._content[1] == value:
            return
        self._content_widgets()[1].update(value)
        label, _, kind, state = self._content
        self._content = (label, value, kind, state)

    def _apply_state(self, state: str, kind: TimerKind) -> None:
        for state_class in self.STATE_CLASSES:
            self.remove_class(state_class)
        self.add_class(state)

        if state == "past":
            self._clear_tone_styles()
        else:
            self._apply_tone_styles(kind)

    def _position_label(self) -> str:
        if self.slot_offset < 0:
            return "Past"
        if self.slot_offset == 0:
            return "Current"
        return "Upcoming"

    def _apply_tone_styles(self, kind: TimerKind) -> None:
        colors = TIMER_TONE_COLORS.get(kind, DEFAULT_TIMER_TONE_COLORS)
        self.styles.background = colors.background
        self.styles.border = ("heavy", colors.accent)

    def _clear_tone_styles(self) -> None:
        self.styles.background = None
        self.styles.border = None

    def _content_widgets(self) -> tuple[Static, Static, Static]:
        if self._name_widget is None:
            self._name_widget = self.query_one(".timer-name", Static)
        if self._value_widget is None:
            self._value_widget = self.query_one(".timer-value", Static)
        if self._position_widget is None:
            self._position_widget = self.query_one(".timer-position", Static)
        return self._name_widget, self._value_widget, self._position_widget


class TimerCarousel(HorizontalGroup):
    """A five-slot renderer centered around the active timer."""

    OFFSETS: ClassVar[tuple[int, ...]] = (-2, -1, 0, 1, 2)

    def __init__(self, snapshot: TimerSnapshot) -> None:
        super().__init__(id="carousel")
        self._snapshot = snapshot
        self._rendered_snapshot: TimerSnapshot | None = None
        self._cards: dict[int, TimerCard] = {}

    @staticmethod
    def slot_id(offset: int) -> str:
        """Return a CSS-safe identifier for a timer slot."""
        return f"timer-slot-neg-{-offset}" if offset < 0 else f"timer-slot-{offset}"

    def compose(self) -> ComposeResult:
        for offset in self.OFFSETS:
            yield TimerCard(slot_offset=offset, id=self.slot_id(offset))

    def on_mount(self) -> None:
        self._cards = {
            offset: self.query_one(f"#{self.slot_id(offset)}", TimerCard)
            for offset in self.OFFSETS
        }
        self._refresh_cards()

    def render_snapshot(self, snapshot: TimerSnapshot) -> None:
        """Store and render a new application snapshot."""
        previous = self._rendered_snapshot
        self._snapshot = snapshot
        if not self.is_mounted:
            return
        if (
            previous is None
            or previous.timers != snapshot.timers
            or previous.current_index != snapshot.current_index
        ):
            self._refresh_cards()
            return
        if previous.remaining_seconds != snapshot.remaining_seconds:
            current_timer = snapshot.current_spec
            self._card_at(0).set_value(self._display_value(0, current_timer))
            self._rendered_snapshot = snapshot

    def _refresh_cards(self) -> None:
        if not self.is_mounted:
            return
        timer_count = len(self._snapshot.timers)
        for offset in self.OFFSETS:
            timer = self._snapshot.timers[
                (self._snapshot.current_index + offset) % timer_count
            ]
            self._card_at(offset).set_content(
                label=timer_label(timer.kind),
                value=self._display_value(offset, timer),
                kind=timer.kind,
                is_past=offset < 0,
                is_current=offset == 0,
            )
        self._rendered_snapshot = self._snapshot

    def _card_at(self, offset: int) -> TimerCard:
        card = self._cards.get(offset)
        if card is None:
            card = self.query_one(f"#{self.slot_id(offset)}", TimerCard)
            self._cards[offset] = card
        return card

    def _display_value(self, offset: int, timer: TimerSpec) -> str:
        seconds = self._snapshot.remaining_seconds if offset == 0 else timer.seconds
        return format_seconds(seconds)


__all__: list[str] = ["TimerCard", "TimerCarousel"]
