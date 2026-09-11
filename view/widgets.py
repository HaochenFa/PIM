"""View widgets: closed-choice selectors and prompt records.

These are data objects. The curses session paints them; the line-oriented
fallback ignores ``chooser`` and still accepts typed answers. That keeps
US1–US11 and the e2e scripts unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Choice:
    """One option in a selector.

    ``value`` is what the existing prompt handler receives (``note``, ``y``,
    ``save``, …). ``key`` is a one-character accelerator. ``tone`` is a
    colour role (``note`` / ``task`` / ``event`` / ``contact`` / ``ok`` /
    ``danger``), or None.
    """

    value: str
    label: str
    key: str | None = None
    tone: str | None = None


@dataclass(frozen=True)
class Chooser:
    """A single-pick selector: arrows move, Enter submits ``value``."""

    title: str
    options: tuple[Choice, ...]
    default: int = 0
    hint: str = "← →  Enter  Esc"

    def clamp(self, index: int) -> int:
        """Keep ``index`` inside the option list."""
        if not self.options:
            return 0
        return max(0, min(len(self.options) - 1, index))

    def move(self, index: int, delta: int) -> int:
        """Move by ``delta`` without wrapping."""
        return self.clamp(index + delta)

    def pick_key(self, char: str) -> int | None:
        """Index for a digit (1-based) or an option ``key``. None if no match."""
        if not char:
            return None
        if char.isdigit():
            number = int(char)
            if 1 <= number <= len(self.options):
                return number - 1
            return None
        folded = char.casefold()
        for index, option in enumerate(self.options):
            if option.key is not None and option.key.casefold() == folded:
                return index
        return None

    def value_at(self, index: int) -> str:
        """Handler payload for the highlighted option."""
        return self.options[self.clamp(index)].value


@dataclass
class Prompt:
    """One stacked ask(): label, callback, optional dirty kind, optional selector."""

    label: str
    handler: object
    kind: str | None = None
    chooser: Chooser | None = None


def type_chooser() -> Chooser:
    """PIR type for create. Values are the four type names."""
    return Chooser(
        title="New PIR — pick a type",
        options=(
            Choice("note", "Note", "n", "note"),
            Choice("task", "Task", "t", "task"),
            Choice("event", "Event", "e", "event"),
            Choice("contact", "Contact", "c", "contact"),
        ),
        hint="← →  1-4 or n t e c  Enter  Esc",
    )


def yes_no_chooser(title: str, *, prefer_yes: bool = False) -> Chooser:
    """Confirm. Values ``y`` / ``n`` match the existing handlers."""
    return Chooser(
        title=title,
        options=(
            Choice("y", "Yes", "y", "ok"),
            Choice("n", "No", "n", "danger"),
        ),
        default=0 if prefer_yes else 1,
        hint="← →  y / n  Enter  Esc",
    )


def alarm_kind_chooser() -> Chooser:
    """Relative or absolute. Values ``relative`` / ``absolute``."""
    return Chooser(
        title="Alarm kind",
        options=(
            Choice("relative", "Relative — before start", "r", "event"),
            Choice("absolute", "Absolute — a date and time", "a", "event"),
        ),
        hint="← →  r / a  Enter  Esc",
    )


def alarm_unit_chooser() -> Chooser:
    """Relative duration unit. Values are the model unit names."""
    return Chooser(
        title="How long before start?",
        options=(
            Choice("minute", "Minute", "m", None),
            Choice("hour", "Hour", "h", None),
            Choice("day", "Day", "d", None),
            Choice("week", "Week", "w", None),
        ),
        default=2,
        hint="← →  m h d w  Enter  Esc",
    )


def dirty_chooser(title: str) -> Chooser:
    """Unsaved changes. Values ``save`` / ``discard`` / ``cancel``."""
    return Chooser(
        title=title,
        options=(
            Choice("save", "Save", "s", "ok"),
            Choice("discard", "Discard", "d", "danger"),
            Choice("cancel", "Cancel", "c", None),
        ),
        default=2,
        hint="← →  s / d / c  Enter  Esc",
    )


def composer_height(*, chooser: Chooser | None, text_prompt: bool) -> int:
    """Rows for the bottom composer: selector, labelled field, or idle hints."""
    if chooser is not None:
        return 3
    if text_prompt:
        return 3
    return 2
