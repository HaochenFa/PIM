"""Create, validate, and modify the four PIR types."""

import unittest
from datetime import datetime, timedelta
from unittest import mock
from zoneinfo import ZoneInfoNotFoundError

from model import (
    AbsoluteAlarm,
    Contact,
    Event,
    FileFormatError,
    Note,
    ParseError,
    PIMError,
    RelativeAlarm,
    Task,
    ValidationError,
    parse_datetime,
)
from model.pir import (
    HKT,
    PIR,
    _hong_kong_zone,
    format_datetime,
    minute_floor,
    optional_text,
    parse_optional_datetime,
    pir_class,
    pir_from_json,
    require_text,
)


class ParseDatetimeTests(unittest.TestCase):
    """Datetime parsing: Hong Kong Time default, minute floor, missing values, range, ISO form."""
    def test_bare_datetime_uses_hong_kong_time(self):
        """A datetime string without an offset gets Hong Kong Time, with seconds set to zero."""
        dt = parse_datetime("2026-11-20T20:00")
        self.assertEqual(dt.tzinfo, HKT)
        self.assertEqual(dt.minute, 0)
        self.assertEqual(dt.second, 0)

    def test_date_only_is_midnight_hkt(self):
        """A date-only string parses to midnight Hong Kong Time on that date."""
        dt = parse_datetime("2026-11-20")
        self.assertEqual(dt, datetime(2026, 11, 20, 0, 0, tzinfo=HKT))

    def test_missing_zone_database_falls_back_to_fixed_utc_plus_8(self):
        """Without a time-zone database, Hong Kong Time is a fixed UTC+8 zone instead of a crash."""
        with mock.patch("model.pir.ZoneInfo", side_effect=ZoneInfoNotFoundError("Asia/Hong_Kong")):
            zone = _hong_kong_zone()
        self.assertEqual(zone.utcoffset(None), timedelta(hours=8))
        self.assertEqual(zone.tzname(None), "HKT")

    def test_invalid_datetime_is_validation_error(self):
        """An unparseable datetime string raises ValidationError."""
        with self.assertRaises(ValidationError):
            parse_datetime("not-a-date")

    def test_zulu_suffix_is_utc(self):
        """A trailing Z is read as UTC: the parsed datetime has a zero UTC offset."""
        dt = parse_datetime("2026-09-14T10:00:00Z")
        self.assertEqual(dt.utcoffset().total_seconds(), 0)

    def test_naive_datetime_object_gets_hong_kong_time(self):
        """A naive datetime object is given Hong Kong Time as its timezone."""
        naive = parse_datetime(datetime(2026, 9, 14, 18, 30))
        self.assertEqual(naive.tzinfo, HKT)

    def test_none_token_and_non_string_are_required_errors(self):
        """A required datetime given as 'none' or as a non-string raises ValidationError."""
        with self.assertRaises(ValidationError):
            parse_datetime("none")
        with self.assertRaises(ValidationError):
            parse_datetime(123)

    def test_naive_instant_is_rejected_by_minute_floor(self):
        """minute_floor rejects a naive (timezone-less) datetime with ValidationError."""
        with self.assertRaises(ValidationError):
            minute_floor(datetime(2026, 1, 1))

    def test_optional_datetime_blank_or_none_is_missing(self):
        """An optional datetime given as None, 'none', or whitespace is missing (None)."""
        self.assertIsNone(parse_optional_datetime(None))
        self.assertIsNone(parse_optional_datetime("none"))
        self.assertIsNone(parse_optional_datetime("  "))

    def test_format_datetime_is_iso_seconds(self):
        """format_datetime renders an HKT datetime as ISO 8601 with seconds and +08:00."""
        dt = parse_datetime("2026-09-13T09:00:00+08:00")
        self.assertEqual(format_datetime(dt), "2026-09-13T09:00:00+08:00")

    def test_instant_that_overflows_hong_kong_time_is_rejected(self):
        """9999-12-31T23:59-10:00 is past year 9999 in HKT; parse raises ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            parse_datetime("9999-12-31T23:59-10:00")
        self.assertEqual(ctx.exception.status_message(), "datetime out of range")
        with self.assertRaises(ValidationError):
            parse_datetime("0001-01-01T00:00+14:00")
        self.assertEqual(parse_datetime("9999-12-31T23:59").year, 9999)


    def test_instant_before_year_one_in_utc_is_rejected_even_in_hkt(self):
        """Bare 0001-01-01 00:10 HKT is before year 1 in UTC; parse raises instead of saving an unloadable file."""
        with self.assertRaises(ValidationError):
            parse_datetime("0001-01-01 00:10")
        self.assertEqual(parse_datetime("0001-01-01 09:00").year, 1)

class FieldHelperTests(unittest.TestCase):
    """Text field helpers: whitespace stripping and required vs optional values."""
    def test_require_text_strips_and_rejects_non_string(self):
        """require_text strips whitespace and raises ValidationError for a non-string value."""
        self.assertEqual(require_text(" x ", "text"), "x")
        with self.assertRaises(ValidationError):
            require_text(1, "text")

    def test_optional_text_stringifies_or_clears(self):
        """optional_text converts a non-string value to its string and returns None for None."""
        self.assertEqual(optional_text(7), "7")
        self.assertIsNone(optional_text(None))


class ErrorMessageTests(unittest.TestCase):
    """Domain errors: each exposes one English status-line message."""
    def test_domain_errors_have_english_status_messages(self):
        """PIMError, ParseError, and FileFormatError give the expected English status messages."""
        self.assertEqual(PIMError("boom").status_message(), "boom")
        self.assertIn("search syntax error", ParseError("x").status_message())
        self.assertIn("not a PIM file", FileFormatError("x").status_message())


class PIRBaseTests(unittest.TestCase):
    """Abstract PIR base class: hooks each PIR type must provide and default field lookups."""
    def test_abstract_hooks_are_not_implemented(self):
        """Each abstract hook on the bare PIR base class raises NotImplementedError."""
        pir = PIR(1)
        with self.assertRaises(NotImplementedError):
            pir.display_name
        with self.assertRaises(NotImplementedError):
            pir.text_fields()
        with self.assertRaises(NotImplementedError):
            pir._apply({})
        with self.assertRaises(NotImplementedError):
            pir.to_json()
        with self.assertRaises(NotImplementedError):
            pir.detail_lines()

    def test_default_field_lookups_are_empty(self):
        """The bare PIR base has no text value, no time values, and no relevant time."""
        pir = PIR(1)
        self.assertIsNone(pir.text_value("text"))
        self.assertEqual(pir.time_values("deadline"), [])
        self.assertIsNone(pir.relevant_time())


class PirJsonTests(unittest.TestCase):
    """PIR type lookup and rebuilding each PIR type from its PIM File JSON object."""
    def test_pir_class_lookup(self):
        """pir_class maps a type name, ignoring case, to its class; an unknown type gives None."""
        self.assertIs(pir_class("NOTE"), Note)
        self.assertIsNone(pir_class("series"))

    def test_pir_from_json_reconstructs_each_type(self):
        """pir_from_json rebuilds a Note, Task, Event, and Contact with their field values."""
        self.assertEqual(pir_from_json({"id": 1, "type": "note", "text": "hi"}).text, "hi")
        task = pir_from_json({"id": 2, "type": "task", "description": "d"})
        self.assertIsNone(task.deadline)
        event = pir_from_json(
            {
                "id": 3,
                "type": "event",
                "description": "e",
                "start": "2026-09-14T18:30:00+08:00",
                "alarms": [],
            }
        )
        self.assertEqual(event.alarms, [])
        self.assertEqual(pir_from_json({"id": 4, "type": "contact", "name": "Ada"}).name, "Ada")

    def test_pir_from_json_rejects_bad_objects(self):
        """pir_from_json raises FileFormatError for a non-object or an object without an Id."""
        with self.assertRaises(FileFormatError):
            pir_from_json([])
        with self.assertRaises(FileFormatError):
            pir_from_json({"type": "note"})


class NoteTests(unittest.TestCase):
    """Note PIR (US1/US2): required text, Display Name, modify, details, and JSON."""
    def test_create_requires_non_empty_body(self):
        """A Note's text becomes its Display Name; whitespace-only text raises ValidationError."""
        note = Note(1, "Shopping: Milk")
        self.assertEqual(note.display_name, "Shopping: Milk")
        with self.assertRaises(ValidationError):
            Note(2, "   ")

    def test_display_name_is_first_line(self):
        """A multi-line Note uses only the first line of its text as the Display Name."""
        note = Note(1, "line one\nline two")
        self.assertEqual(note.display_name, "line one")

    def test_modify_text_keeps_id(self):
        """Modifying a Note's text replaces the text and keeps the same Id."""
        note = Note(1, "old")
        note.modify({"text": "new"})
        self.assertEqual(note.id, 1)
        self.assertEqual(note.text, "new")

    def test_detail_lines_and_json(self):
        """Note details start with the Id; JSON and the display field give the text body."""
        note = Note(1, "body")
        self.assertEqual(note.detail_lines()[0], ("Id", "1"))
        self.assertEqual(note.to_json()["text"], "body")
        self.assertEqual(note.display_field("text"), "body")
        note.modify({"text": "body"})
        self.assertEqual(note.text, "body")


class TaskTests(unittest.TestCase):
    """Task PIR (US3): required description, optional deadline, modify, and display."""
    def test_deadline_may_be_omitted(self):
        """A Task created without a deadline has no deadline (None)."""
        task = Task(1, "Inbox")
        self.assertIsNone(task.deadline)

    def test_missing_description_fails(self):
        """A Task with an empty description raises ValidationError."""
        with self.assertRaises(ValidationError):
            Task(1, "")

    def test_none_clears_deadline(self):
        """Modifying a Task's deadline to 'none' clears the deadline to None."""
        task = Task(1, "Submit PIM", "2026-11-20T20:00:00+08:00")
        task.modify({"deadline": "none"})
        self.assertIsNone(task.deadline)

    def test_display_name_and_deadline_field(self):
        """Task shows description and deadline ('none' if unset); deadline is its relevant time."""
        inbox = Task(1, "Inbox")
        self.assertEqual(inbox.display_name, "Inbox")
        self.assertEqual(inbox.display_field("deadline"), "none")
        due = Task(2, "Submit", "2026-11-20T20:00:00+08:00")
        self.assertEqual(due.relevant_time(), due.deadline)
        self.assertTrue(due.display_field("deadline").startswith("2026-11-20"))
        self.assertIn("deadline", dict(due.detail_lines()))
        due.modify({"description": "work2", "deadline": "2026-11-21T20:00:00+08:00"})
        self.assertEqual(due.description, "work2")


class EventTests(unittest.TestCase):
    """Event PIR (US4): required start, relative/absolute alarms, Effective Alarm Times, modify."""
    def test_zero_alarms_allowed(self):
        """An Event created without alarms is valid and has an empty alarm list."""
        event = Event(1, "lecture", "2026-09-14T18:30:00+08:00")
        self.assertEqual(event.alarms, [])

    def test_relative_after_start_rejected(self):
        """A relative alarm with a negative amount (after start) raises ValidationError."""
        with self.assertRaises(ValidationError):
            RelativeAlarm(-1, "hour")

    def test_relative_effective_times_move_with_start(self):
        """Moving the start shifts relative Effective Alarm Times; the absolute one stays fixed."""
        event = Event(
            4,
            "COMP3211 lecture",
            "2026-09-14T18:30:00+08:00",
            [
                RelativeAlarm(1, "day"),
                RelativeAlarm(0, "minute"),
                AbsoluteAlarm("2026-09-13T09:00:00+08:00"),
            ],
        )
        original_absolute = event.effective_alarm_times()[2]
        event.modify({"start": "2026-09-21T18:30:00+08:00"})
        times = event.effective_alarm_times()
        self.assertEqual(times[0], parse_datetime("2026-09-20T18:30:00+08:00"))
        self.assertEqual(times[1], parse_datetime("2026-09-21T18:30:00+08:00"))
        self.assertEqual(times[2], original_absolute)

    def test_missing_start_fails(self):
        """An Event with no start raises ValidationError."""
        with self.assertRaises(ValidationError):
            Event(1, "lecture", None)

    def test_display_name_relevant_time_and_alarm_field(self):
        """Event: description is Display Name, start is relevant time, alarms show 'none'."""
        event = Event(1, "lecture", "2026-09-14T18:30:00+08:00")
        self.assertEqual(event.display_name, "lecture")
        self.assertEqual(event.relevant_time(), event.start)
        self.assertEqual(event.display_field("alarms"), "none")
        self.assertEqual(dict(event.detail_lines())["alarms"], "(none)")
        self.assertIsNone(event.text_value("name"))
        self.assertEqual(event.time_values("deadline"), [])

    def test_detail_lines_list_each_alarm(self):
        """Event details list each alarm as alarm[i]; the alarms field shows the alarm count."""
        event = Event(
            4,
            "COMP3211 lecture",
            "2026-09-14T18:30:00+08:00",
            [RelativeAlarm(1, "day"), AbsoluteAlarm("2026-09-13T09:00:00+08:00")],
        )
        labels = dict(event.detail_lines())
        self.assertIn("alarm[0]", labels)
        self.assertIn("alarm[1]", labels)
        armed = Event(
            5,
            "lecture",
            "2026-09-14T18:30:00+08:00",
            [RelativeAlarm(0, "minute")],
        )
        self.assertEqual(armed.display_field("alarms"), "1 alarm(s)")

    def test_alarms_must_be_a_list(self):
        """A3: alarms given as a number or a string raise ValidationError, on create and modify."""
        with self.assertRaises(ValidationError) as ctx:
            Event(1, "lecture", "2026-09-14T18:30:00+08:00", 5)
        self.assertEqual(ctx.exception.status_message(), "alarms must be a list")
        with self.assertRaises(ValidationError):
            Event(1, "lecture", "2026-09-14T18:30:00+08:00", "none")
        event = Event(1, "lecture", "2026-09-14T18:30:00+08:00")
        with self.assertRaises(ValidationError):
            event.modify({"alarms": 5})
        self.assertEqual(event.alarms, [])

    def test_modify_replaces_or_clears_alarms(self):
        """Modify with alarms None clears them; a full modify sets description, start, alarms."""
        event = Event(7, "plain", "2026-09-14T18:30:00+08:00")
        event.modify({"alarms": None})
        self.assertEqual(event.alarms, [])
        event.modify(
            {
                "description": "plain2",
                "start": "2026-09-15T18:30:00+08:00",
                "alarms": [RelativeAlarm(0, "minute")],
            }
        )
        self.assertEqual(event.description, "plain2")
        self.assertEqual(len(event.alarms), 1)


class ContactTests(unittest.TestCase):
    """Contact PIR (US5): required Name, optional address and mobile, fixed type, modify."""
    def test_name_required_address_and_mobile_optional(self):
        """A Contact needs a non-blank Name; address and mobile are None when omitted."""
        contact = Contact(1, "Ada")
        self.assertIsNone(contact.address)
        self.assertIsNone(contact.mobile)
        with self.assertRaises(ValidationError):
            Contact(2, "  ")

    def test_type_cannot_change(self):
        """Modifying a Contact's type raises ValidationError; its type and Name are unchanged."""
        contact = Contact(1, "Ada")
        with self.assertRaises(ValidationError):
            contact.modify({"type": "note"})
        self.assertEqual(contact.type_name, "contact")
        self.assertEqual(contact.name, "Ada")

    def test_display_name_and_text_fields(self):
        """A Contact's Name is its Display Name; mobile and address are exposed; no text field."""
        contact = Contact(5, "Ada", "HK", "123")
        self.assertEqual(contact.display_name, "Ada")
        self.assertEqual(contact.text_value("mobile"), "123")
        self.assertIsNone(contact.text_value("text"))
        self.assertEqual(dict(contact.detail_lines())["address"], "HK")

    def test_none_clears_optional_fields(self):
        """Modifying address and mobile to 'none' clears them; a later modify sets them again."""
        contact = Contact(5, "Ada", "HK", "123")
        contact.modify({"name": "Ada L", "address": "none", "mobile": "none"})
        self.assertIsNone(contact.address)
        self.assertIsNone(contact.mobile)
        contact.modify({"address": "Island", "mobile": "999"})
        self.assertEqual(contact.address, "Island")


if __name__ == "__main__":
    unittest.main()
