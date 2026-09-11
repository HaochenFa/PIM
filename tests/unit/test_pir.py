"""Create, validate, and modify the four PIR types."""

import unittest
from datetime import datetime

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
    format_datetime,
    minute_floor,
    optional_text,
    parse_optional_datetime,
    pir_class,
    pir_from_json,
    require_text,
)


class ParseDatetimeTests(unittest.TestCase):
    def test_bare_datetime_uses_hong_kong_time(self):
        dt = parse_datetime("2026-11-20T20:00")
        self.assertEqual(dt.tzinfo, HKT)
        self.assertEqual(dt.minute, 0)
        self.assertEqual(dt.second, 0)

    def test_date_only_is_midnight_hkt(self):
        dt = parse_datetime("2026-11-20")
        self.assertEqual(dt, datetime(2026, 11, 20, 0, 0, tzinfo=HKT))

    def test_invalid_datetime_is_validation_error(self):
        with self.assertRaises(ValidationError):
            parse_datetime("not-a-date")

    def test_zulu_suffix_is_utc(self):
        dt = parse_datetime("2026-09-14T10:00:00Z")
        self.assertEqual(dt.utcoffset().total_seconds(), 0)

    def test_naive_datetime_object_gets_hong_kong_time(self):
        naive = parse_datetime(datetime(2026, 9, 14, 18, 30))
        self.assertEqual(naive.tzinfo, HKT)

    def test_none_token_and_non_string_are_required_errors(self):
        with self.assertRaises(ValidationError):
            parse_datetime("none")
        with self.assertRaises(ValidationError):
            parse_datetime(123)

    def test_naive_instant_is_rejected_by_minute_floor(self):
        with self.assertRaises(ValidationError):
            minute_floor(datetime(2026, 1, 1))

    def test_optional_datetime_blank_or_none_is_missing(self):
        self.assertIsNone(parse_optional_datetime(None))
        self.assertIsNone(parse_optional_datetime("none"))
        self.assertIsNone(parse_optional_datetime("  "))

    def test_format_datetime_is_iso_seconds(self):
        dt = parse_datetime("2026-09-13T09:00:00+08:00")
        self.assertEqual(format_datetime(dt), "2026-09-13T09:00:00+08:00")


class FieldHelperTests(unittest.TestCase):
    def test_require_text_strips_and_rejects_non_string(self):
        self.assertEqual(require_text(" x ", "text"), "x")
        with self.assertRaises(ValidationError):
            require_text(1, "text")

    def test_optional_text_stringifies_or_clears(self):
        self.assertEqual(optional_text(7), "7")
        self.assertIsNone(optional_text(None))


class ErrorMessageTests(unittest.TestCase):
    def test_domain_errors_have_english_status_messages(self):
        self.assertEqual(PIMError("boom").status_message(), "boom")
        self.assertIn("search syntax error", ParseError("x").status_message())
        self.assertIn("not a PIM file", FileFormatError("x").status_message())


class PIRBaseTests(unittest.TestCase):
    def test_abstract_hooks_are_not_implemented(self):
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
        pir = PIR(1)
        self.assertIsNone(pir.text_value("text"))
        self.assertEqual(pir.time_values("deadline"), [])
        self.assertIsNone(pir.relevant_time())


class PirJsonTests(unittest.TestCase):
    def test_pir_class_lookup(self):
        self.assertIs(pir_class("NOTE"), Note)
        self.assertIsNone(pir_class("series"))

    def test_pir_from_json_reconstructs_each_type(self):
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
        with self.assertRaises(FileFormatError):
            pir_from_json([])
        with self.assertRaises(FileFormatError):
            pir_from_json({"type": "note"})


class NoteTests(unittest.TestCase):
    def test_create_requires_non_empty_body(self):
        note = Note(1, "Shopping: Milk")
        self.assertEqual(note.display_name, "Shopping: Milk")
        with self.assertRaises(ValidationError):
            Note(2, "   ")

    def test_display_name_is_first_line(self):
        note = Note(1, "line one\nline two")
        self.assertEqual(note.display_name, "line one")

    def test_modify_text_keeps_id(self):
        note = Note(1, "old")
        note.modify({"text": "new"})
        self.assertEqual(note.id, 1)
        self.assertEqual(note.text, "new")

    def test_detail_lines_and_json(self):
        note = Note(1, "body")
        self.assertEqual(note.detail_lines()[0], ("Id", "1"))
        self.assertEqual(note.to_json()["text"], "body")
        self.assertEqual(note.display_field("text"), "body")
        note.modify({"text": "body"})
        self.assertEqual(note.text, "body")


class TaskTests(unittest.TestCase):
    def test_deadline_may_be_omitted(self):
        task = Task(1, "Inbox")
        self.assertIsNone(task.deadline)

    def test_missing_description_fails(self):
        with self.assertRaises(ValidationError):
            Task(1, "")

    def test_none_clears_deadline(self):
        task = Task(1, "Submit PIM", "2026-11-20T20:00:00+08:00")
        task.modify({"deadline": "none"})
        self.assertIsNone(task.deadline)

    def test_display_name_and_deadline_field(self):
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
    def test_zero_alarms_allowed(self):
        event = Event(1, "lecture", "2026-09-14T18:30:00+08:00")
        self.assertEqual(event.alarms, [])

    def test_relative_after_start_rejected(self):
        with self.assertRaises(ValidationError):
            RelativeAlarm(-1, "hour")

    def test_relative_effective_times_move_with_start(self):
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
        with self.assertRaises(ValidationError):
            Event(1, "lecture", None)

    def test_display_name_relevant_time_and_alarm_field(self):
        event = Event(1, "lecture", "2026-09-14T18:30:00+08:00")
        self.assertEqual(event.display_name, "lecture")
        self.assertEqual(event.relevant_time(), event.start)
        self.assertEqual(event.display_field("alarms"), "none")
        self.assertEqual(dict(event.detail_lines())["alarms"], "(none)")
        self.assertIsNone(event.text_value("name"))
        self.assertEqual(event.time_values("deadline"), [])

    def test_detail_lines_list_each_alarm(self):
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

    def test_modify_replaces_or_clears_alarms(self):
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
    def test_name_required_address_and_mobile_optional(self):
        contact = Contact(1, "Ada")
        self.assertIsNone(contact.address)
        self.assertIsNone(contact.mobile)
        with self.assertRaises(ValidationError):
            Contact(2, "  ")

    def test_type_cannot_change(self):
        contact = Contact(1, "Ada")
        with self.assertRaises(ValidationError):
            contact.modify({"type": "note"})
        self.assertEqual(contact.type_name, "contact")
        self.assertEqual(contact.name, "Ada")

    def test_display_name_and_text_fields(self):
        contact = Contact(5, "Ada", "HK", "123")
        self.assertEqual(contact.display_name, "Ada")
        self.assertEqual(contact.text_value("mobile"), "123")
        self.assertIsNone(contact.text_value("text"))
        self.assertEqual(dict(contact.detail_lines())["address"], "HK")

    def test_none_clears_optional_fields(self):
        contact = Contact(5, "Ada", "HK", "123")
        contact.modify({"name": "Ada L", "address": "none", "mobile": "none"})
        self.assertIsNone(contact.address)
        self.assertIsNone(contact.mobile)
        contact.modify({"address": "Island", "mobile": "999"})
        self.assertEqual(contact.address, "Island")


if __name__ == "__main__":
    unittest.main()
