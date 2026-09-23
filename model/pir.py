"""PIR types, alarms, and datetime helpers.

Callers use the classes and `parse_datetime` / `format_datetime`. Matching
and persistence stay in sibling modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HKT = ZoneInfo("Asia/Hong_Kong")
SOON_WINDOW = timedelta(minutes=15)
RELATIVE_UNITS = {
    "minute": timedelta(minutes=1),
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
}
TYPE_NAMES = ("note", "task", "event", "contact")
CLEAR = "none"
KIND_TEXT = "text"
KIND_DATETIME = "datetime"
KIND_ALARMS = "alarms"


@dataclass(frozen=True)
class FieldSpec:
    """One PIR field: storage key, prompt label, kind, and whether it is required."""

    key: str
    label: str
    kind: str
    required: bool = True


class PIMError(Exception):
    """Domain rule violation. `status_message` is the specific English error."""

    def status_message(self) -> str:
        """English text for this failure."""
        return str(self)


class ValidationError(PIMError):
    """A required field is missing or a value is illegal."""


class NotFound(PIMError):
    """No PIR has this Id."""


class ParseError(PIMError):
    """Search criterion syntax is invalid."""

    def status_message(self) -> str:
        return f"search syntax error: {self}"


class DirtyLoadError(PIMError):
    """load while the collection has unsaved changes, without force."""


class FileFormatError(PIMError):
    """The path is not a readable pim/v1 JSON file."""

    def status_message(self) -> str:
        return f"not a PIM file: {self}"


class ExtensionError(PIMError):
    """The path does not use the .pim extension."""


def is_blank(value) -> bool:
    """True for None or a whitespace-only string (a missing value)."""
    return value is None or (isinstance(value, str) and value.strip() == "")


def require_text(value, field: str) -> str:
    """Return a stripped required string. Raises ValidationError if blank."""
    if is_blank(value):
        raise ValidationError(f"{field} is required")
    if not isinstance(value, str):
        raise ValidationError(f"{field} is required")
    return value.strip()


def optional_text(value) -> str | None:
    """Strip an optional string; blank becomes None."""
    if is_blank(value):
        return None
    if not isinstance(value, str):
        return str(value)
    return value.strip()


def minute_floor(dt: datetime) -> datetime:
    """Truncate to minute. Raises ValidationError if naive."""
    if dt.tzinfo is None:
        raise ValidationError("datetime must be timezone-aware")
    return dt.replace(second=0, microsecond=0)


def parse_datetime(value) -> datetime:
    """Parse a timezone-aware instant; default zone is Hong Kong Time."""
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=HKT)
        return minute_floor(dt)
    if is_blank(value) or not isinstance(value, str):
        raise ValidationError("datetime is required")
    raw = value.strip()
    if raw.casefold() == CLEAR:
        raise ValidationError("datetime is required")
    text = raw
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    if " " in text and "T" not in text:
        text = text.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError(f"invalid datetime: {raw}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=HKT)
    return minute_floor(dt)


def parse_optional_datetime(value) -> datetime | None:
    """Parse an optional instant; blank or `none` is None."""
    if is_blank(value):
        return None
    if isinstance(value, str) and value.strip().casefold() == CLEAR:
        return None
    return parse_datetime(value)


def format_datetime(dt: datetime) -> str:
    """ISO 8601 at second resolution, timezone-aware."""
    return minute_floor(dt).isoformat(timespec="seconds")


def parse_alarm(spec) -> RelativeAlarm | AbsoluteAlarm:
    """Build a RelativeAlarm or AbsoluteAlarm from an object or JSON dict."""
    if isinstance(spec, (RelativeAlarm, AbsoluteAlarm)):
        return spec
    if not isinstance(spec, dict):
        raise ValidationError("invalid alarm")
    kind = str(spec.get("kind", "")).casefold()
    if kind == "relative":
        return RelativeAlarm(spec.get("amount"), spec.get("unit"))
    if kind == "absolute":
        return AbsoluteAlarm(spec.get("at"))
    raise ValidationError("alarm kind must be relative or absolute")


class RelativeAlarm:
    """Alarm at start, or N units before start. Effective time moves when start changes."""

    def __init__(self, amount, unit):
        try:
            amount = int(amount)
        except (TypeError, ValueError) as exc:
            raise ValidationError("relative alarm amount must be an integer") from exc
        if amount < 0:
            raise ValidationError("relative alarm cannot be after start")
        if is_blank(unit) or not isinstance(unit, str):
            raise ValidationError("relative alarm unit is required")
        unit_key = unit.strip().casefold()
        if unit_key.endswith("s") and unit_key[:-1] in RELATIVE_UNITS:
            unit_key = unit_key[:-1]
        if unit_key not in RELATIVE_UNITS:
            raise ValidationError("relative alarm unit must be minute, hour, day, or week")
        self.amount = amount
        self.unit = unit_key

    def effective(self, start: datetime) -> datetime:
        """`start` minus the stored duration (0 = at start)."""
        return start - RELATIVE_UNITS[self.unit] * self.amount

    def to_json(self) -> dict:
        """JSON object with kind, amount, and unit."""
        return {"kind": "relative", "amount": self.amount, "unit": self.unit}

    def kind_label(self) -> str:
        """Human-readable relative trigger, e.g. `relative 1 day before start`."""
        if self.amount == 0:
            return "relative at start"
        unit = self.unit if self.amount == 1 else self.unit + "s"
        return f"relative {self.amount} {unit} before start"


class AbsoluteAlarm:
    """Alarm at a stored instant. Changing start does not move it."""

    def __init__(self, at):
        self.at = parse_datetime(at)

    def effective(self, start: datetime) -> datetime:
        """The stored instant; `start` is ignored."""
        return self.at

    def to_json(self) -> dict:
        """JSON object with kind and `at`."""
        return {"kind": "absolute", "at": format_datetime(self.at)}

    def kind_label(self) -> str:
        """Always `absolute`."""
        return "absolute"


def check_alarm_times(start: datetime, alarms: list) -> None:
    """Raise ValidationError if any Effective Alarm Time falls outside the datetime range.

    A huge relative amount, or a start near year 1, makes `start - duration`
    overflow; the Event must then be rejected rather than stored.
    """
    for alarm in alarms:
        try:
            alarm.effective(start)
        except OverflowError as exc:
            raise ValidationError("alarm time is out of range") from exc


class DueAlarm:
    """One OVERDUE or SOON alarm at an injected `now`. `key` is (event Id, alarm index)."""

    def __init__(self, event_id: int, alarm_index: int, at: datetime, status: str, description: str):
        self.event_id = event_id
        self.alarm_index = alarm_index
        self.at = at
        self.status = status
        self.description = description

    def key(self) -> tuple[int, int]:
        """Dismiss identity: (event Id, alarm index)."""
        return (self.event_id, self.alarm_index)


class PIR:
    """One record. Id is identity; type_name is immutable after creation."""

    type_name: str = ""
    FIELDS: tuple[FieldSpec, ...] = ()

    def __init__(self, pir_id: int):
        self.id = pir_id

    def display_field(self, key: str) -> str:
        """Current value of `key` as a prompt hint (`none` if missing)."""
        value = getattr(self, key)
        if value is None:
            return "none"
        if key == "alarms":
            return "none" if not value else f"{len(value)} alarm(s)"
        if isinstance(value, datetime):
            return format_datetime(value)
        return str(value)

    @property
    def display_name(self) -> str:
        """Derived list label: Note first line, Task/Event description, Contact name."""
        raise NotImplementedError

    def text_fields(self) -> list[str]:
        """Text values used by unqualified `contains`."""
        raise NotImplementedError

    def text_value(self, field: str) -> str | None:
        """Named text field, or None if this type has no such field."""
        return None

    def time_values(self, field: str) -> list[datetime]:
        """Instants for a time comparison; empty if the field is missing."""
        return []

    def relevant_time(self) -> datetime | None:
        """Deadline or start for the Current Result table, else None."""
        return None

    def modify(self, fields: dict) -> None:
        """Apply updates in place. Raises ValidationError if type would change."""
        if "type" in fields and not is_blank(fields["type"]):
            wanted = str(fields["type"]).strip().casefold()
            if wanted != self.type_name:
                raise ValidationError("PIR type cannot be changed")
        self._apply(fields)

    def _apply(self, fields: dict) -> None:
        raise NotImplementedError

    def to_json(self) -> dict:
        """pim/v1 object for this PIR, including Id and type."""
        raise NotImplementedError

    def detail_lines(self) -> list[tuple[str, str]]:
        """(label, value) rows for print and the detail pane."""
        raise NotImplementedError


class Note(PIR):
    """PIR whose body is required `text`."""

    type_name = "note"
    FIELDS = (FieldSpec("text", "text", KIND_TEXT, required=True),)

    def __init__(self, pir_id: int, text):
        super().__init__(pir_id)
        self.text = require_text(text, "text")

    @property
    def display_name(self) -> str:
        return self.text.splitlines()[0]

    def text_fields(self) -> list[str]:
        return [self.text]

    def text_value(self, field: str) -> str | None:
        if field == "text":
            return self.text
        return None

    def _apply(self, fields: dict) -> None:
        new_text = self.text
        if "text" in fields:
            new_text = require_text(fields["text"], "text")
        self.text = new_text

    def to_json(self) -> dict:
        return {"id": self.id, "type": "note", "text": self.text}

    def detail_lines(self) -> list[tuple[str, str]]:
        return [("Id", str(self.id)), ("type", "note"), ("text", self.text)]


class Task(PIR):
    """PIR with required `description` and optional `deadline`."""

    type_name = "task"
    FIELDS = (
        FieldSpec("description", "description", KIND_TEXT, required=True),
        FieldSpec("deadline", "deadline", KIND_DATETIME, required=False),
    )

    def __init__(self, pir_id: int, description, deadline=None):
        super().__init__(pir_id)
        self.description = require_text(description, "description")
        self.deadline = parse_optional_datetime(deadline)

    @property
    def display_name(self) -> str:
        return self.description

    def text_fields(self) -> list[str]:
        return [self.description]

    def text_value(self, field: str) -> str | None:
        if field == "description":
            return self.description
        return None

    def time_values(self, field: str) -> list[datetime]:
        if field == "deadline" and self.deadline is not None:
            return [self.deadline]
        return []

    def relevant_time(self) -> datetime | None:
        return self.deadline

    def _apply(self, fields: dict) -> None:
        new_description = self.description
        new_deadline = self.deadline
        if "description" in fields:
            new_description = require_text(fields["description"], "description")
        if "deadline" in fields:
            new_deadline = parse_optional_datetime(fields["deadline"])
        self.description = new_description
        self.deadline = new_deadline

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "type": "task",
            "description": self.description,
            "deadline": format_datetime(self.deadline) if self.deadline else None,
        }

    def detail_lines(self) -> list[tuple[str, str]]:
        deadline = format_datetime(self.deadline) if self.deadline else "(none)"
        return [
            ("Id", str(self.id)),
            ("type", "task"),
            ("description", self.description),
            ("deadline", deadline),
        ]


class Event(PIR):
    """PIR with required `description` and `start`, and zero or more alarms."""

    type_name = "event"
    FIELDS = (
        FieldSpec("description", "description", KIND_TEXT, required=True),
        FieldSpec("start", "start", KIND_DATETIME, required=True),
        FieldSpec("alarms", "alarms", KIND_ALARMS, required=False),
    )

    def __init__(self, pir_id: int, description, start, alarms=None):
        super().__init__(pir_id)
        self.description = require_text(description, "description")
        self.start = parse_datetime(start)
        self.alarms = [parse_alarm(item) for item in (alarms or [])]
        # Reject at entry so due_alarms, print, and search never meet an overflow.
        check_alarm_times(self.start, self.alarms)

    @property
    def display_name(self) -> str:
        return self.description

    def text_fields(self) -> list[str]:
        return [self.description]

    def text_value(self, field: str) -> str | None:
        if field == "description":
            return self.description
        return None

    def time_values(self, field: str) -> list[datetime]:
        if field == "start":
            return [self.start]
        if field == "alarm":
            return [alarm.effective(self.start) for alarm in self.alarms]
        return []

    def relevant_time(self) -> datetime | None:
        return self.start

    def effective_alarm_times(self) -> list[datetime]:
        """Effective Alarm Times of every alarm, relative ones using current start."""
        return [alarm.effective(self.start) for alarm in self.alarms]

    def _apply(self, fields: dict) -> None:
        new_description = self.description
        new_start = self.start
        new_alarms = list(self.alarms)
        if "description" in fields:
            new_description = require_text(fields["description"], "description")
        if "start" in fields:
            new_start = parse_datetime(fields["start"])
        if "alarms" in fields:
            if fields["alarms"] is None:
                new_alarms = []
            else:
                new_alarms = [parse_alarm(item) for item in fields["alarms"]]
        # Validate against the new start before any attribute changes (atomic modify).
        check_alarm_times(new_start, new_alarms)
        self.description = new_description
        self.start = new_start
        self.alarms = new_alarms

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "type": "event",
            "description": self.description,
            "start": format_datetime(self.start),
            "alarms": [alarm.to_json() for alarm in self.alarms],
        }

    def detail_lines(self) -> list[tuple[str, str]]:
        lines = [
            ("Id", str(self.id)),
            ("type", "event"),
            ("description", self.description),
            ("start", format_datetime(self.start)),
        ]
        if not self.alarms:
            lines.append(("alarms", "(none)"))
        else:
            for index, alarm in enumerate(self.alarms):
                at = format_datetime(alarm.effective(self.start))
                lines.append((f"alarm[{index}]", f"{alarm.kind_label()}; effective {at}"))
        return lines


class Contact(PIR):
    """PIR with required `name` and optional `address` and `mobile`."""

    type_name = "contact"
    FIELDS = (
        FieldSpec("name", "name", KIND_TEXT, required=True),
        FieldSpec("address", "address", KIND_TEXT, required=False),
        FieldSpec("mobile", "mobile", KIND_TEXT, required=False),
    )

    def __init__(self, pir_id: int, name, address=None, mobile=None):
        super().__init__(pir_id)
        self.name = require_text(name, "name")
        self.address = optional_text(address)
        self.mobile = optional_text(mobile)

    @property
    def display_name(self) -> str:
        return self.name

    def text_fields(self) -> list[str]:
        return [value for value in (self.name, self.address, self.mobile) if value]

    def text_value(self, field: str) -> str | None:
        if field == "name":
            return self.name
        if field == "address":
            return self.address
        if field == "mobile":
            return self.mobile
        return None

    def _apply(self, fields: dict) -> None:
        new_name = self.name
        new_address = self.address
        new_mobile = self.mobile
        if "name" in fields:
            new_name = require_text(fields["name"], "name")
        if "address" in fields:
            new_address = optional_text(fields["address"])
            if isinstance(fields["address"], str) and fields["address"].strip().casefold() == CLEAR:
                new_address = None
        if "mobile" in fields:
            new_mobile = optional_text(fields["mobile"])
            if isinstance(fields["mobile"], str) and fields["mobile"].strip().casefold() == CLEAR:
                new_mobile = None
        self.name = new_name
        self.address = new_address
        self.mobile = new_mobile

    def to_json(self) -> dict:
        return {
            "id": self.id,
            "type": "contact",
            "name": self.name,
            "address": self.address,
            "mobile": self.mobile,
        }

    def detail_lines(self) -> list[tuple[str, str]]:
        return [
            ("Id", str(self.id)),
            ("type", "contact"),
            ("name", self.name),
            ("address", self.address or "(none)"),
            ("mobile", self.mobile or "(none)"),
        ]


def pir_class(type_name: str):
    """PIR subclass for `type_name`, or None if unknown."""
    name = type_name.casefold()
    for cls in (Note, Task, Event, Contact):
        if cls.type_name == name:
            return cls
    return None


def pir_from_json(data: dict) -> PIR:
    """Reconstruct a PIR from a pim/v1 object. Raises FileFormatError if invalid."""
    if not isinstance(data, dict):
        raise FileFormatError("PIR must be an object")
    try:
        pir_id = int(data["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FileFormatError("PIR is missing a valid id") from exc
    type_name = str(data.get("type", "")).casefold()
    if type_name == "note":
        return Note(pir_id, data.get("text"))
    if type_name == "task":
        return Task(pir_id, data.get("description"), data.get("deadline"))
    if type_name == "event":
        return Event(pir_id, data.get("description"), data.get("start"), data.get("alarms"))
    if type_name == "contact":
        return Contact(pir_id, data.get("name"), data.get("address"), data.get("mobile"))
    raise FileFormatError(f"unknown PIR type: {data.get('type')!r}")
