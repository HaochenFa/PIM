"""Create, validate, and modify the four PIR types."""

import unittest
from datetime import datetime

from model import (
    AbsoluteAlarm,
    Event,
    Note,
    RelativeAlarm,
    Task,
    ValidationError,
    parse_datetime,
)
from model.pir import HKT, Contact


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


if __name__ == "__main__":
    unittest.main()
