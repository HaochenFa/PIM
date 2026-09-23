"""due_alarms with injected now; relative/absolute coexistence."""

import unittest

from model import (
    AbsoluteAlarm,
    PIM,
    RelativeAlarm,
    ValidationError,
    parse_criterion,
    parse_datetime,
)
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


class AlarmRangeTests(unittest.TestCase):
    """An Event whose Effective Alarm Time would overflow is rejected atomically."""

    def test_huge_relative_amount_fails_create_without_mutation(self):
        """A1: 999999999 weeks before start overflows; create raises and nothing is inserted."""
        pim = PIM()
        with self.assertRaises(ValidationError) as ctx:
            pim.create_event(
                "overflow", "2026-09-14T18:30:00+08:00", [RelativeAlarm(999999999, "week")]
            )
        self.assertEqual(ctx.exception.status_message(), "alarm time is out of range")
        self.assertEqual(pim.all(), [])
        self.assertFalse(pim.is_dirty())
        self.assertEqual(pim.create_note("next").id, 1)

    def test_relative_alarm_before_year_one_fails_create(self):
        """A2: 1 day before 0001-01-01 00:10 is out of range; create raises ValidationError."""
        pim = PIM()
        with self.assertRaises(ValidationError):
            pim.create_event("ancient", "0001-01-01 00:10", [RelativeAlarm(1, "day")])
        self.assertEqual(pim.all(), [])

    def test_modify_start_that_pushes_alarm_out_of_range_is_atomic(self):
        """Moving start to year 1 under a 1-day relative alarm fails; the Event is unchanged."""
        pim = PIM()
        event = pim.create_event(
            "lecture", "2026-09-14T18:30:00+08:00", [RelativeAlarm(1, "day")]
        )
        before = event.to_json()
        with self.assertRaises(ValidationError):
            pim.modify(event.id, {"start": "0001-01-01 00:10"})
        self.assertEqual(pim.get(event.id).to_json(), before)

    def test_in_range_event_keeps_search_and_due_alarms_working(self):
        """After a rejected overflow, due_alarms and alarm search still run on the collection."""
        pim = PIM()
        pim.create_event("ok", "2026-09-14T18:30:00+08:00", [RelativeAlarm(0, "minute")])
        with self.assertRaises(ValidationError):
            pim.create_event("bad", "0001-01-01 00:10", [RelativeAlarm(1, "day")])
        now = parse_datetime("2026-09-14T18:30:00+08:00")
        self.assertEqual([item.event_id for item in pim.due_alarms(now)], [1])
        self.assertEqual(len(pim.search(parse_criterion("alarm < 2027-01-01"))), 1)


if __name__ == "__main__":
    unittest.main()
