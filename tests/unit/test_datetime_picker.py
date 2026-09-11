"""Calendar date/time picker: HKT, 15-minute slots, ISO-like submit string."""

import unittest
from datetime import date, datetime

from model.pir import HKT, parse_datetime
from view.widgets import DateTimePicker, DATETIME_FORMAT
from tests.unit.test_terminal import make_terminal


def hkt(text: str) -> datetime:
    """Parse a fixture instant in Hong Kong Time."""
    return parse_datetime(text)


class DateTimePickerTests(unittest.TestCase):
    def test_value_is_what_parse_datetime_already_accepts(self):
        picker = DateTimePicker("Start", hkt("2026-09-14T18:31:00+08:00"))
        # 18:31 rounds up to 18:45
        self.assertEqual(picker.value(), "2026-09-14 18:45")
        self.assertEqual(parse_datetime(picker.value()), parse_datetime("2026-09-14T18:45:00+08:00"))

    def test_exact_quarter_hour_is_kept(self):
        picker = DateTimePicker("Start", hkt("2026-09-14T18:30:00+08:00"))
        self.assertEqual((picker.hour, picker.minute), (18, 30))

    def test_existing_instant_seeds_the_grid(self):
        initial = hkt("2026-11-20T20:00:00+08:00")
        picker = DateTimePicker("Deadline", hkt("2026-09-11T09:00:00+08:00"), initial=initial)
        self.assertEqual(picker.day, date(2026, 11, 20))
        self.assertEqual(picker.value(), "2026-11-20 20:00")

    def test_week_starts_monday(self):
        picker = DateTimePicker("Start", hkt("2026-09-14T18:30:00+08:00"))
        week = picker.weeks()[0]
        self.assertEqual(week[0].weekday(), 0)

    def test_move_month_clamps_day(self):
        picker = DateTimePicker("Start", hkt("2026-01-31T10:00:00+08:00"), initial=hkt("2026-01-31T10:00:00+08:00"))
        picker.move_month(1)
        self.assertEqual(picker.day, date(2026, 2, 28))

    def test_move_time_wraps_inside_the_day(self):
        picker = DateTimePicker("Start", hkt("2026-09-14T23:50:00+08:00"), initial=hkt("2026-09-14T23:50:00+08:00"))
        picker.move_time(15)
        self.assertEqual(picker.day, date(2026, 9, 14))
        self.assertEqual((picker.hour, picker.minute), (0, 5))

    def test_summary_is_english_not_iso(self):
        picker = DateTimePicker("Start", hkt("2026-09-14T18:30:00+08:00"), initial=hkt("2026-09-14T18:30:00+08:00"))
        self.assertIn("September", picker.month_title())
        self.assertIn("HKT", picker.summary())
        self.assertNotIn("T18:30", picker.summary())


class DatetimePromptTests(unittest.TestCase):
    def test_start_prompt_names_the_format_and_zone(self):
        app, term, _out = make_terminal()
        term._handle_line("create event")
        term._handle_line("lecture")
        label = term._prompt_label()
        self.assertIn(DATETIME_FORMAT, label)
        self.assertIn("Hong Kong Time", label)
        self.assertIsNotNone(term.current_picker())

    def test_typed_iso_still_creates_the_event(self):
        app, term, _out = make_terminal()
        term._handle_line("create event")
        term._handle_line("lecture")
        term._handle_line("2026-09-14T18:30:00+08:00")
        term._handle_line("n")
        self.assertEqual(app.calls[-1][0], "create")
        self.assertEqual(app.calls[-1][1], "event")

    def test_picker_enter_submits_hkt_clock(self):
        from view.curses_ui import CursesUI

        app, term, _out = make_terminal(now=hkt("2026-09-14T18:30:00+08:00"))
        ui = CursesUI(term, object())
        term._handle_line("create event")
        term._handle_line("lecture")
        picker = term.current_picker()
        picker.day = date(2026, 9, 16)
        picker.hour = 9
        picker.minute = 0
        ui._picker_submit(picker.value())
        # next prompt is add-an-alarm
        self.assertIsNotNone(term.current_chooser())
        term._handle_line("n")
        fields = app.calls[-1][2]
        self.assertEqual(fields["start"], "2026-09-16 09:00")

    def test_optional_deadline_skip_from_picker(self):
        from view.curses_ui import CursesUI

        app, term, _out = make_terminal()
        ui = CursesUI(term, object())
        term._handle_line("create task")
        term._handle_line("Inbox")
        picker = term.current_picker()
        self.assertFalse(picker.required)
        ui._handle_picker_key("n")
        kind, type_name, fields = app.calls[-1]
        self.assertEqual(type_name, "task")
        self.assertEqual(fields["description"], "Inbox")
        self.assertEqual(fields.get("deadline"), "none")
