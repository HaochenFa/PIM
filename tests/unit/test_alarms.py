"""due_alarms with injected now; relative/absolute coexistence."""

import unittest

from model import AbsoluteAlarm, PIM, RelativeAlarm, parse_datetime
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
        before = pim.is_dirty()
        pim.due_alarms(parse_datetime("2020-01-01T00:00:00+08:00"))
        self.assertEqual(pim.is_dirty(), before)

    def test_relative_zero_is_at_start(self):
        pim = PIM()
        event = pim.create_event(
            "at start",
            "2026-09-14T18:30:00+08:00",
            [RelativeAlarm(0, "minute")],
        )
        self.assertEqual(event.effective_alarm_times()[0], event.start)


if __name__ == "__main__":
    unittest.main()
