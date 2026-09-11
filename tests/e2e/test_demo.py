"""ACCEPTANCE.md section 6 demo script as a scripted terminal session."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from model import PIM, parse_datetime
from tests.e2e.harness import result_ids, run_script


class DemoScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_demo_create_search_modify_print_save_and_reload(self):
        dest = self.dir / "demo"
        app, _term, out = run_script(
            [
                "create note",
                "Shopping: Milk",
                "create task",
                "Inbox",
                "",
                "create event",
                "COMP3211 lecture",
                "2026-09-14T18:30:00+08:00",
                "y",
                "relative",
                "1",
                "day",
                "y",
                "relative",
                "0",
                "y",
                "absolute",
                "2026-09-13T09:00:00+08:00",
                "n",
                "create contact",
                "Ada",
                "",
                "",
                'search type = event && description contains "COMP"',
                "1",
                "modify",
                "",
                "2026-09-21T18:30:00+08:00",
                "n",
                "print",
                f"save as {dest}",
                "quit",
            ]
        )
        self.assertEqual(result_ids(app), [3])
        event = app.pim.get(3)
        times = event.effective_alarm_times()
        self.assertEqual(times[0], parse_datetime("2026-09-20T18:30:00+08:00"))
        self.assertEqual(times[2], parse_datetime("2026-09-13T09:00:00+08:00"))
        self.assertIn("Printed Id 3", out)
        self.assertIn("relative", out)
        path = self.dir / "demo.pim"
        self.assertTrue(path.is_file())

        loaded, _term2, out2 = run_script([f"load {path}", "id 3", "quit"])
        self.assertEqual(loaded.pim.get(3).description, "COMP3211 lecture")
        self.assertIn("Loaded", out2)
        self.assertEqual(loaded.selected_id(), 3)


if __name__ == "__main__":
    unittest.main()
