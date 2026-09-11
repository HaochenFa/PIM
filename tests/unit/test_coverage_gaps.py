"""Remaining model branches so unit tests cover every countable line."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from model import (
    AbsoluteAlarm,
    Contact,
    Criterion,
    Event,
    FileFormatError,
    Note,
    ParseError,
    PIM,
    PIMError,
    RelativeAlarm,
    Task,
    TimeCompare,
    ValidationError,
    parse_criterion,
    parse_datetime,
)
from model.pimfile import read_pim_file, write_pim_file
from model.pir import (
    PIR,
    format_datetime,
    minute_floor,
    optional_text,
    parse_alarm,
    parse_optional_datetime,
    pir_class,
    pir_from_json,
    require_text,
)
from tests.fixture import make_fixture


class CriterionBranchTests(unittest.TestCase):
    def test_base_matches_is_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            Criterion().matches(Note(1, "x"))

    def test_unknown_type_field_and_operator_are_parse_errors(self):
        with self.assertRaises(ParseError):
            parse_criterion("type = series")
        with self.assertRaises(ParseError):
            parse_criterion('title contains "x"')
        with self.assertRaises(ParseError):
            parse_criterion("due < 2026-01-01")
        with self.assertRaises(ParseError):
            parse_criterion("deadline << 2026-01-01")
        with self.assertRaises(ParseError):
            TimeCompare("deadline", "!=", parse_datetime("2026-01-01T00:00:00+08:00"))
        with self.assertRaises(ParseError):
            parse_criterion("type > note")
        with self.assertRaises(ParseError):
            parse_criterion('type = "note"')
        with self.assertRaises(ParseError):
            parse_criterion("description")
        with self.assertRaises(ParseError):
            parse_criterion("&&")
        with self.assertRaises(ParseError):
            parse_criterion("deadline <")
        with self.assertRaises(ParseError):
            parse_criterion("deadline < not-a-date")
        with self.assertRaises(ParseError):
            parse_criterion("(type = note")

    def test_parentheses_double_not_and_quoted_datetime(self):
        pim = make_fixture()
        hits = pim.search(parse_criterion("!(!(type = note))"))
        self.assertEqual([pir.id for pir in hits], [1])
        hits = pim.search(parse_criterion("(type = task || type = note) && type = note"))
        self.assertEqual([pir.id for pir in hits], [1])
        hits = pim.search(parse_criterion('start = "2026-09-14T18:30:00+08:00"'))
        self.assertEqual([pir.id for pir in hits], [4])

    def test_contains_missing_field_and_escaped_string(self):
        pim = make_fixture()
        self.assertEqual(pim.search(parse_criterion('address contains "HK"')), [pim.get(6)])
        self.assertEqual(pim.search(parse_criterion('mobile contains "123"')), [pim.get(5)])
        self.assertEqual(pim.search(parse_criterion('address contains "missing"')), [])
        note = pim.create_note("say \"hi\"")
        hits = pim.search(parse_criterion(r'text contains "say \"hi\""'))
        self.assertEqual([pir.id for pir in hits], [note.id])
        pim.create_note("line\nbreak")
        hits = pim.search(parse_criterion(r'text contains "line\nbreak"'))
        self.assertTrue(hits)

    def test_unterminated_escape_and_comparison_edge_tokens(self):
        with self.assertRaises(ParseError):
            parse_criterion('contains "abc\\')
        with self.assertRaises(ParseError):
            parse_criterion("< 1")
        with self.assertRaises(ParseError):
            parse_criterion("deadline <)")
        hits = make_fixture().search(parse_criterion("deadline < 2026-11-21T00:00:00+08:00 && type = task"))
        self.assertEqual([pir.id for pir in hits], [2])

    def test_time_compare_greater_and_equal(self):
        pim = make_fixture()
        self.assertEqual(
            [pir.id for pir in pim.search(parse_criterion("deadline > 2026-11-19T00:00:00+08:00"))],
            [2],
        )
        self.assertEqual(
            [pir.id for pir in pim.search(parse_criterion("deadline = 2026-11-20T20:00:00+08:00"))],
            [2],
        )
        self.assertEqual(
            [pir.id for pir in pim.search(parse_criterion("start > 2026-09-14T00:00:00+08:00"))],
            [4],
        )


class DatetimeAndAlarmHelperTests(unittest.TestCase):
    def test_parse_datetime_zulu_naive_object_and_none_token(self):
        dt = parse_datetime("2026-09-14T10:00:00Z")
        self.assertEqual(dt.utcoffset().total_seconds(), 0)
        naive = parse_datetime(datetime(2026, 9, 14, 18, 30))
        self.assertEqual(naive.tzinfo.key, "Asia/Hong_Kong")
        with self.assertRaises(ValidationError):
            parse_datetime("none")
        with self.assertRaises(ValidationError):
            parse_datetime(123)
        with self.assertRaises(ValidationError):
            minute_floor(datetime(2026, 1, 1))

    def test_optional_datetime_and_text_helpers(self):
        self.assertIsNone(parse_optional_datetime(None))
        self.assertIsNone(parse_optional_datetime("none"))
        self.assertIsNone(parse_optional_datetime("  "))
        self.assertEqual(require_text(" x ", "text"), "x")
        with self.assertRaises(ValidationError):
            require_text(1, "text")
        self.assertEqual(optional_text(7), "7")
        self.assertIsNone(optional_text(None))

    def test_parse_alarm_from_object_dict_and_errors(self):
        rel = RelativeAlarm(1, "hour")
        self.assertIs(parse_alarm(rel), rel)
        parsed = parse_alarm({"kind": "relative", "amount": 2, "unit": "days"})
        self.assertEqual(parsed.amount, 2)
        self.assertEqual(parsed.unit, "day")
        abs_alarm = parse_alarm({"kind": "absolute", "at": "2026-09-13T09:00:00+08:00"})
        self.assertEqual(abs_alarm.kind_label(), "absolute")
        with self.assertRaises(ValidationError):
            parse_alarm("nope")
        with self.assertRaises(ValidationError):
            parse_alarm({"kind": "rrule"})
        with self.assertRaises(ValidationError):
            RelativeAlarm("x", "minute")
        with self.assertRaises(ValidationError):
            RelativeAlarm(1, None)
        with self.assertRaises(ValidationError):
            RelativeAlarm(1, "fortnight")
        zero = RelativeAlarm(0, "minute")
        self.assertEqual(zero.kind_label(), "relative at start")
        two = RelativeAlarm(2, "day")
        self.assertIn("days", two.kind_label())


class PirSurfaceTests(unittest.TestCase):
    def test_base_pir_hooks_and_display_field(self):
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
        self.assertIsNone(pir.text_value("text"))
        self.assertEqual(pir.time_values("deadline"), [])
        self.assertIsNone(pir.relevant_time())
        note = Note(1, "Shopping: Milk")
        self.assertEqual(note.display_field("text"), "Shopping: Milk")
        task = Task(2, "Inbox")
        self.assertEqual(task.display_name, "Inbox")
        self.assertEqual(task.display_field("deadline"), "none")
        task_due = Task(3, "Submit", "2026-11-20T20:00:00+08:00")
        self.assertTrue(task_due.display_field("deadline").startswith("2026-11-20"))
        event = Event(4, "lecture", "2026-09-14T18:30:00+08:00")
        self.assertEqual(event.display_name, "lecture")
        self.assertEqual(event.relevant_time(), event.start)
        self.assertEqual(event.display_field("alarms"), "none")
        armed = Event(
            5,
            "lecture",
            "2026-09-14T18:30:00+08:00",
            [RelativeAlarm(0, "minute")],
        )
        self.assertEqual(armed.display_field("alarms"), "1 alarm(s)")

    def test_detail_lines_json_and_modify_each_type(self):
        note = Note(1, "body")
        self.assertEqual(note.detail_lines()[0], ("Id", "1"))
        self.assertEqual(note.to_json()["text"], "body")
        note.modify({"text": "body"})
        self.assertEqual(note.text, "body")

        task = Task(2, "work", "2026-11-20T20:00:00+08:00")
        self.assertEqual(task.relevant_time(), task.deadline)
        self.assertIn("deadline", dict(task.detail_lines()))
        task.modify({"description": "work2", "deadline": "2026-11-21T20:00:00+08:00"})
        self.assertEqual(task.description, "work2")

        event = Event(
            4,
            "COMP3211 lecture",
            "2026-09-14T18:30:00+08:00",
            [RelativeAlarm(1, "day"), AbsoluteAlarm("2026-09-13T09:00:00+08:00")],
        )
        labels = dict(event.detail_lines())
        self.assertIn("alarm[0]", labels)
        self.assertIn("alarm[1]", labels)
        empty = Event(7, "plain", "2026-09-14T18:30:00+08:00")
        self.assertEqual(dict(empty.detail_lines())["alarms"], "(none)")
        empty.modify({"alarms": None})
        self.assertEqual(empty.alarms, [])
        empty.modify(
            {
                "description": "plain2",
                "start": "2026-09-15T18:30:00+08:00",
                "alarms": [RelativeAlarm(0, "minute")],
            }
        )
        self.assertEqual(empty.description, "plain2")
        self.assertEqual(len(empty.alarms), 1)
        self.assertIsNone(empty.text_value("name"))
        self.assertEqual(empty.time_values("deadline"), [])

        contact = Contact(5, "Ada", "HK", "123")
        self.assertEqual(contact.display_name, "Ada")
        self.assertEqual(contact.text_value("mobile"), "123")
        self.assertIsNone(contact.text_value("text"))
        contact.modify({"name": "Ada L", "address": "none", "mobile": "none"})
        self.assertIsNone(contact.address)
        self.assertIsNone(contact.mobile)
        contact.modify({"address": "Island", "mobile": "999"})
        self.assertEqual(contact.address, "Island")
        self.assertEqual(dict(contact.detail_lines())["address"], "Island")
        status = PIMError("boom").status_message()
        self.assertEqual(status, "boom")
        self.assertIn("search syntax error", ParseError("x").status_message())
        self.assertIn("not a PIM file", FileFormatError("x").status_message())

    def test_pir_from_json_and_pir_class(self):
        self.assertIs(pir_class("NOTE"), Note)
        self.assertIsNone(pir_class("series"))
        with self.assertRaises(FileFormatError):
            pir_from_json([])
        with self.assertRaises(FileFormatError):
            pir_from_json({"type": "note"})
        note = pir_from_json({"id": 1, "type": "note", "text": "hi"})
        self.assertEqual(note.text, "hi")
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
        contact = pir_from_json({"id": 4, "type": "contact", "name": "Ada"})
        self.assertEqual(contact.name, "Ada")

    def test_due_alarm_key_and_format_datetime(self):
        pim = make_fixture()
        due = pim.due_alarms(parse_datetime("2026-09-13T09:00:00+08:00"))
        self.assertTrue(due)
        self.assertEqual(due[0].key(), (due[0].event_id, due[0].alarm_index))
        self.assertTrue(format_datetime(due[0].at).startswith("2026-09-13"))


class PersistBranchTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_write_failure_unlinks_temp_and_reraises(self):
        pim = PIM()
        pim.create_note("x")
        path = self.dir / "fail.pim"
        with patch("model.pimfile.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                pim.save(path)
        with patch("model.pimfile.os.replace", side_effect=OSError("disk full")):
            with patch("model.pimfile.os.unlink", side_effect=OSError("gone")):
                with self.assertRaises(OSError):
                    write_pim_file(path, 2, pim.all())

    def test_schema_edges_on_read(self):
        not_list = self.dir / "pirs.pim"
        not_list.write_text('{"format":"pim/v1","next_id":1,"pirs":{}}', encoding="utf-8")
        with self.assertRaises(FileFormatError):
            read_pim_file(not_list)

        bad_note = self.dir / "blank.pim"
        bad_note.write_text(
            '{"format":"pim/v1","next_id":2,"pirs":[{"id":1,"type":"note","text":"  "}]}',
            encoding="utf-8",
        )
        with self.assertRaises(FileFormatError):
            read_pim_file(bad_note)

        zero = self.dir / "zero.pim"
        zero.write_text('{"format":"pim/v1","next_id":0,"pirs":[]}', encoding="utf-8")
        with self.assertRaises(FileFormatError):
            read_pim_file(zero)

        bump = self.dir / "bump.pim"
        bump.write_text(
            '{"format":"pim/v1","next_id":1,"pirs":[{"id":5,"type":"note","text":"keep"}]}',
            encoding="utf-8",
        )
        next_id, pirs = read_pim_file(bump)
        self.assertEqual(next_id, 6)
        self.assertEqual(pirs[0].id, 5)


if __name__ == "__main__":
    unittest.main()
