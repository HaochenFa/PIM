"""due_alarms with injected now; relative/absolute coexistence."""

import unittest

from model import AbsoluteAlarm, PIM, RelativeAlarm, ValidationError, parse_datetime
from model.pir import parse_alarm
from tests.fixture import make_fixture


class DueAlarmTests(unittest.TestCase):
    def test_overdue_at_or_before_now(self):
        pim = make_fixture()
        now = parse_datetime("2026-09-13T09:00:00+08:00")
        due = pim.due_alarms(now)
        statuses = {(item.event_id, item.alarm_index): item.status for item in due}
        self.assertEqual(statuses[(4, 2)], "OVERDUE")

    def test_soon_is_next_fifteen_minutes_exclusive_of_now(self):
        pim = PIM()
        pim.create_event(
            "soon",
            "2026-09-14T18:30:00+08:00",
            [AbsoluteAlarm("2026-09-14T18:40:00+08:00")],
        )
        now = parse_datetime("2026-09-14T18:30:00+08:00")
        due = pim.due_alarms(now)
        self.assertEqual(len(due), 1)
        self.assertEqual(due[0].status, "SOON")
        later = pim.due_alarms(parse_datetime("2026-09-14T18:20:00+08:00"))
        self.assertEqual(later, [])

    def test_soon_boundary_at_exactly_fifteen_minutes(self):
        pim = PIM()
        pim.create_event(
            "edge",
            "2026-09-14T18:30:00+08:00",
            [AbsoluteAlarm("2026-09-14T18:45:00+08:00")],
        )
        now = parse_datetime("2026-09-14T18:30:00+08:00")
        due = pim.due_alarms(now)
        self.assertEqual(due[0].status, "SOON")

    def test_due_alarms_does_not_use_wall_clock_or_mutate(self):
        pim = make_fixture()
        pim.create_event(
            "historical",
            "2020-06-01T12:00:00+08:00",
            [AbsoluteAlarm("2020-06-01T12:00:00+08:00")],
        )
        before = pim.is_dirty()
        now = parse_datetime("2020-05-31T12:00:00+08:00")
        self.assertEqual(pim.due_alarms(now), [])
        self.assertEqual(pim.is_dirty(), before)

    def test_relative_zero_is_at_start(self):
        pim = PIM()
        event = pim.create_event(
            "at start",
            "2026-09-14T18:30:00+08:00",
            [RelativeAlarm(0, "minute")],
        )
        self.assertEqual(event.effective_alarm_times()[0], event.start)

    def test_due_alarm_key_is_event_id_and_index(self):
        pim = make_fixture()
        due = pim.due_alarms(parse_datetime("2026-09-13T09:00:00+08:00"))
        self.assertTrue(due)
        self.assertEqual(due[0].key(), (due[0].event_id, due[0].alarm_index))


class AlarmSpecTests(unittest.TestCase):
    def test_parse_alarm_accepts_object_or_json_dict(self):
        rel = RelativeAlarm(1, "hour")
        self.assertIs(parse_alarm(rel), rel)
        parsed = parse_alarm({"kind": "relative", "amount": 2, "unit": "days"})
        self.assertEqual(parsed.amount, 2)
        self.assertEqual(parsed.unit, "day")
        abs_alarm = parse_alarm({"kind": "absolute", "at": "2026-09-13T09:00:00+08:00"})
        self.assertEqual(abs_alarm.kind_label(), "absolute")

    def test_parse_alarm_rejects_unknown_kind(self):
        with self.assertRaises(ValidationError):
            parse_alarm("nope")
        with self.assertRaises(ValidationError):
            parse_alarm({"kind": "rrule"})

    def test_relative_amount_and_unit_are_validated(self):
        with self.assertRaises(ValidationError):
            RelativeAlarm("x", "minute")
        with self.assertRaises(ValidationError):
            RelativeAlarm(1, None)
        with self.assertRaises(ValidationError):
            RelativeAlarm(1, "fortnight")

    def test_kind_label_for_at_start_and_plural_units(self):
        self.assertEqual(RelativeAlarm(0, "minute").kind_label(), "relative at start")
        self.assertIn("days", RelativeAlarm(2, "day").kind_label())


if __name__ == "__main__":
    unittest.main()
