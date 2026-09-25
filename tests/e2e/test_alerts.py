"""In-process Alarm Alerts: OVERDUE, SOON, dismiss is View memory only."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from model import PIM, parse_datetime
from tests.e2e.harness import clock, run_script


class AlarmAlertTests(unittest.TestCase):
    def test_overdue_banner_then_dismiss_is_not_written_to_file(self):
        """An overdue Alarm Alert shows OVERDUE; dismissing it is View-only, so the saved file still reports it due."""
        now = parse_datetime("2026-09-14T18:30:00+08:00")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        dest = Path(tmp.name) / "alerts.pim"
        app, term, out = run_script(
            [
                "create event",
                "lecture",
                "2026-09-14T18:30:00+08:00",
                "y",
                "relative",
                "0",
                "n",
                "dismiss",
                f"save as {dest}",
                "quit",
            ],
            now=clock(now),
        )
        self.assertIn("OVERDUE", out)
        self.assertIn("Dismissed alarm on Id 1", out)
        self.assertEqual(term.visible_due(), [])
        self.assertIn((1, 0), term.dismissed)
        loaded = PIM()
        loaded.load(dest)
        self.assertEqual(len(loaded.get(1).alarms), 1)
        self.assertTrue(loaded.due_alarms(now))

    def test_soon_banner_within_fifteen_minutes(self):
        """An alarm within fifteen minutes of `now` shows a SOON Alarm Alert, not OVERDUE."""
        now = parse_datetime("2026-09-14T18:30:00+08:00")
        _app, _term, out = run_script(
            [
                "create event",
                "soon",
                "2026-09-14T18:45:00+08:00",
                "y",
                "relative",
                "0",
                "n",
                "quit",
                "discard",
            ],
            now=clock(now),
        )
        self.assertIn("SOON", out)
        self.assertNotIn("OVERDUE", out)

    def test_dismiss_with_no_alarm_reports_status(self):
        """`dismiss` with no Alarm Alert showing reports `no alarm to dismiss`."""
        _app, _term, out = run_script(["dismiss", "quit"])
        self.assertIn("no alarm to dismiss", out)


if __name__ == "__main__":
    unittest.main()
