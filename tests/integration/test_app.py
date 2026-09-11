"""controller.App against model.PIM: Current Result, status, atomic failure."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from controller.app import App, HELP, format_pir
from model import PIM, parse_datetime
from tests.fixture import make_fixture


def ids_of(app: App):
    """Ids in Current Result, in list order."""
    return [pir.id for pir in app.current_result()]


class AppCreateModifyDeleteTests(unittest.TestCase):
    def test_create_four_types_selects_and_lists_them(self):
        app = App(PIM())
        note = app.create("note", {"text": "Shopping: Milk"})
        self.assertEqual(note.id, 1)
        self.assertEqual(app.selected_id(), 1)
        self.assertIn("Created Note Id 1", app.status)
        task = app.create("task", {"description": "Inbox"})
        self.assertIsNone(task.deadline)
        event = app.create(
            "event",
            {"description": "lecture", "start": "2026-09-14T18:30:00+08:00"},
        )
        self.assertEqual(event.alarms, [])
        contact = app.create("contact", {"name": "Ada"})
        self.assertEqual(ids_of(app), [1, 2, 3, 4])
        self.assertEqual(app.selected_id(), contact.id)
        self.assertTrue(app.is_dirty())
        self.assertIsNone(app.bound_path())

    def test_failed_create_sets_status_and_does_not_mutate(self):
        app = App(PIM())
        self.assertIsNone(app.create("note", {"text": "  "}))
        self.assertIn("required", app.status.casefold())
        self.assertEqual(ids_of(app), [])
        self.assertFalse(app.is_dirty())
        self.assertIsNone(app.create("series", {"text": "x"}))
        self.assertEqual(app.status, "unknown PIR type: series")
        self.assertEqual(app.pim.all(), [])

    def test_modify_keeps_id_empty_fields_are_noop(self):
        app = App(make_fixture())
        app.select_id(1)
        updated = app.modify({"text": "Shopping: Bread"})
        self.assertEqual(updated.id, 1)
        self.assertEqual(app.pim.get(1).text, "Shopping: Bread")
        self.assertIn("Modified Id 1", app.status)
        app.select_id(1)
        same = app.modify({})
        self.assertEqual(app.status, "No changes")
        self.assertIs(same, app.pim.get(1))
        app.select_id(3)
        app.modify({"description": "Inbox"})
        self.assertEqual(app.status, "No changes")

    def test_modify_without_selection_or_unknown_type_change_fails(self):
        app = App(make_fixture())
        self.assertIsNone(app.modify({"text": "x"}))
        self.assertEqual(app.status, "no PIR selected")
        app.select_id(1)
        self.assertIsNone(app.modify({"type": "task"}))
        self.assertEqual(app.pim.get(1).type_name, "note")
        self.assertEqual(app.pim.get(1).text, "Shopping: Milk")

    def test_delete_selected_and_missing_selection(self):
        app = App(make_fixture())
        self.assertFalse(app.delete_selected())
        self.assertEqual(app.status, "no PIR selected")
        app.select_id(2)
        self.assertTrue(app.delete_selected())
        self.assertIsNone(app.selected())
        self.assertNotIn(2, ids_of(app))
        created = app.create("note", {"text": "after"})
        self.assertGreaterEqual(created.id, 7)
        self.assertNotEqual(created.id, 2)


class AppSearchPrintSelectTests(unittest.TestCase):
    def test_search_replaces_current_result_clear_restores_all(self):
        app = App(make_fixture())
        app.search("type = contact && name contains \"ada\"")
        self.assertEqual(ids_of(app), [5, 6])
        self.assertTrue(app.has_criterion())
        self.assertIsNone(app.selected_id())
        self.assertEqual(app.status, "2 match(es)")
        app.clear_search()
        self.assertEqual(ids_of(app), [1, 2, 3, 4, 5, 6])
        self.assertFalse(app.has_criterion())
        self.assertEqual(app.status, "Search cleared")

    def test_illegal_criterion_leaves_current_result(self):
        app = App(make_fixture())
        app.search("type = note")
        self.assertEqual(ids_of(app), [1])
        app.select_row(1)
        app.search("type =")
        self.assertEqual(ids_of(app), [1])
        self.assertEqual(app.selected_id(), 1)
        self.assertIn("search syntax error", app.status)

    def test_select_row_is_not_identity(self):
        app = App(make_fixture())
        app.search("type = contact")
        app.select_row(1)
        self.assertEqual(app.selected_id(), 5)
        app.select_row("2")
        self.assertEqual(app.selected_id(), 6)
        app.select_row("x")
        self.assertEqual(app.status, "row number must be an integer")
        app.select_row(9)
        self.assertEqual(app.status, "no row 9 in Current Result")
        app.select_id(99)
        self.assertIn("no PIR with Id", app.status)
        app.select_id(4)
        self.assertEqual(app.selected_id(), 4)

    def test_print_all_uses_current_result_not_the_collection(self):
        app = App(make_fixture())
        app.search("type = note")
        text = app.print_all()
        self.assertIn("Shopping: Milk", text)
        self.assertNotIn("Submit PIM", text)
        self.assertIn("Printed 1 PIR(s) in Current Result", app.status)
        app.select_id(1)
        one = app.print_selected()
        self.assertEqual(one, format_pir(app.pim.get(1)))
        self.assertIn("Printed Id 1", app.status)
        app.clear_print()
        self.assertEqual(app.print_text, "")

    def test_print_without_selection_fails(self):
        app = App(make_fixture())
        self.assertIsNone(app.print_selected())
        self.assertEqual(app.status, "no PIR selected")

    def test_print_all_empty_current_result(self):
        app = App(PIM())
        text = app.print_all()
        self.assertEqual(text, "(Current Result is empty)")

    def test_selection_cleared_when_pir_leaves_search_hits(self):
        app = App(make_fixture())
        app.select_id(1)
        app.search("type = task")
        self.assertIsNone(app.selected_id())
        app.search('text contains "Milk"')
        app.select_id(1)
        self.assertEqual(app.selected_id(), 1)
        app.modify({"text": "Bread"})
        self.assertIsNone(app.selected_id())
        self.assertEqual(ids_of(app), [])

    def test_due_alarms_passthrough_and_help_constant(self):
        app = App(make_fixture())
        now = parse_datetime("2026-09-13T09:00:00+08:00")
        due = app.due_alarms(now)
        self.assertTrue(due)
        self.assertIn("create", HELP)


class AppPersistTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_save_appends_pim_and_load_round_trips(self):
        app = App(make_fixture())
        target = app.save_target(self.dir / "demo")
        self.assertTrue(str(target).endswith(".pim"))
        self.assertTrue(app.save(self.dir / "demo"))
        self.assertFalse(app.is_dirty())
        self.assertTrue(Path(app.bound_path()).exists())
        other = App(PIM())
        self.assertTrue(other.load(self.dir / "demo.pim"))
        self.assertEqual(ids_of(other), [1, 2, 3, 4, 5, 6])
        self.assertTrue(other.status.startswith("Loaded "))

    def test_save_without_bound_file_fails(self):
        app = App(PIM())
        app.create("note", {"text": "x"})
        self.assertFalse(app.save())
        self.assertIn("save as", app.status)

    def test_load_rejects_other_extension_and_corrupt_file(self):
        app = App(make_fixture())
        other = self.dir / "demo.json"
        other.write_text("{}", encoding="utf-8")
        before = [pir.id for pir in app.pim.all()]
        self.assertFalse(app.load(other, force=True))
        self.assertEqual([pir.id for pir in app.pim.all()], before)
        bad = self.dir / "bad.pim"
        bad.write_text("{nope", encoding="utf-8")
        self.assertFalse(app.load(bad, force=True))
        self.assertEqual(app.pim.get(1).text, "Shopping: Milk")

    def test_dirty_load_without_force_fails_force_discards(self):
        app = App(make_fixture())
        path = self.dir / "ok.pim"
        self.assertTrue(app.save(path))
        app.select_id(1)
        app.modify({"text": "changed"})
        app.print_all()
        self.assertFalse(app.load(path))
        self.assertEqual(app.pim.get(1).text, "changed")
        self.assertTrue(app.load(path, force=True))
        self.assertEqual(app.pim.get(1).text, "Shopping: Milk")
        self.assertFalse(app.has_criterion())
        self.assertIsNone(app.selected_id())
        self.assertEqual(app.print_text, "")

    def test_would_overwrite_only_another_existing_file(self):
        app = App(PIM())
        existing = self.dir / "a.pim"
        existing.write_text("{}", encoding="utf-8")
        self.assertTrue(app.would_overwrite(existing))
        app.create("note", {"text": "x"})
        app.save(existing)
        self.assertFalse(app.would_overwrite(existing))
        other = self.dir / "b.pim"
        other.write_text("{}", encoding="utf-8")
        self.assertTrue(app.would_overwrite(other))
        missing = self.dir / "missing.pim"
        self.assertFalse(app.would_overwrite(missing))

    def test_would_overwrite_falls_back_when_resolve_fails(self):
        app = App(make_fixture())
        path = self.dir / "x.pim"
        app.save(path)
        other = self.dir / "y.pim"
        other.write_text("{}", encoding="utf-8")
        with patch("controller.app.Path.resolve", side_effect=OSError("nope")):
            self.assertTrue(app.would_overwrite(other))
            self.assertFalse(app.would_overwrite(path))


if __name__ == "__main__":
    unittest.main()
