"""controller.App in isolation: status, Current Result, selection. PIM is mocked."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from controller.app import HELP, App, format_pir
from model import NotFound, Note, Task, ValidationError


def _pim(records=None):
    """Minimal PIM mock: empty collection unless `records` is given."""
    pim = Mock()
    items = list(records or [])
    pim.all.return_value = items
    pim.bound_path.return_value = None
    pim.is_dirty.return_value = False
    pim.due_alarms.return_value = []
    return pim


class FormatPirTests(unittest.TestCase):
    def test_one_line_per_detail_field(self):
        text = format_pir(Note(1, "Shopping: Milk"))
        self.assertEqual(text.splitlines()[0], "Id: 1")
        self.assertIn("text: Shopping: Milk", text)


class AppCreateTests(unittest.TestCase):
    def test_unknown_type_sets_status_without_calling_pim(self):
        pim = _pim()
        app = App(pim)
        self.assertIsNone(app.create("series", {"text": "x"}))
        self.assertEqual(app.status, "unknown PIR type: series")
        pim.create_note.assert_not_called()

    def test_create_note_selects_and_lists(self):
        note = Note(1, "ok")
        pim = _pim()
        pim.create_note.return_value = note
        pim.all.return_value = [note]
        pim.get.return_value = note
        app = App(pim)
        created = app.create("note", {"text": "ok"})
        self.assertIs(created, note)
        self.assertEqual(app.selected_id(), 1)
        self.assertEqual(app.status, "Created Note Id 1")
        pim.create_note.assert_called_once_with("ok")

    def test_create_failure_sets_status_and_skips_refresh(self):
        pim = _pim()
        pim.create_note.side_effect = ValidationError("text is required")
        app = App(pim)
        self.assertIsNone(app.create("note", {"text": "  "}))
        self.assertEqual(app.status, "text is required")
        self.assertIsNone(app.selected_id())

    def test_create_task_event_contact_pass_fields(self):
        pim = _pim()
        task = Task(2, "Inbox")
        pim.create_task.return_value = task
        pim.create_event.return_value = Mock(id=3)
        pim.create_contact.return_value = Mock(id=4)
        pim.all.return_value = []
        app = App(pim)
        app.create("task", {"description": "Inbox", "deadline": None})
        pim.create_task.assert_called_once_with("Inbox", None)
        app.create("event", {"description": "lec", "start": "t", "alarms": []})
        pim.create_event.assert_called_once_with("lec", "t", [])
        app.create("contact", {"name": "Ada", "address": None, "mobile": "1"})
        pim.create_contact.assert_called_once_with("Ada", None, "1")


class AppSelectionTests(unittest.TestCase):
    def test_selected_clears_stale_id_when_get_fails(self):
        pim = _pim()
        app = App(pim)
        app._selected_id = 9
        pim.get.side_effect = NotFound("no PIR with Id 9")
        self.assertIsNone(app.selected())
        self.assertIsNone(app.selected_id())

    def test_select_row_and_id_set_status(self):
        note = Note(5, "x")
        pim = _pim([note])
        pim.get.return_value = note
        app = App(pim)
        app.select_row(1)
        self.assertEqual(app.selected_id(), 5)
        self.assertEqual(app.status, "Selected Id 5")
        app.select_id(5)
        pim.get.assert_called_with(5)


class AppModifyDeleteTests(unittest.TestCase):
    def test_modify_without_selection(self):
        app = App(_pim())
        self.assertIsNone(app.modify({"text": "x"}))
        self.assertEqual(app.status, "no PIR selected")

    def test_modify_empty_fields_is_no_changes(self):
        note = Note(1, "ok")
        pim = _pim([note])
        pim.get.return_value = note
        app = App(pim)
        app.select_id(1)
        self.assertIs(app.modify({}), note)
        self.assertEqual(app.status, "No changes")
        pim.modify.assert_not_called()

    def test_modify_failure_sets_status(self):
        note = Note(1, "ok")
        pim = _pim([note])
        pim.get.return_value = note
        pim.modify.side_effect = ValidationError("text is required")
        app = App(pim)
        app.select_id(1)
        self.assertIsNone(app.modify({"text": "  "}))
        self.assertEqual(app.status, "text is required")

    def test_modify_noop_when_pim_returns_same_object(self):
        note = Note(1, "ok")
        pim = _pim([note])
        pim.get.return_value = note
        pim.modify.return_value = note
        app = App(pim)
        app.select_id(1)
        self.assertIs(app.modify({"text": "ok"}), note)
        self.assertEqual(app.status, "No changes")

    def test_delete_failure_sets_status(self):
        note = Note(1, "ok")
        pim = _pim([note])
        pim.get.return_value = note
        pim.delete.side_effect = NotFound("gone")
        app = App(pim)
        app.select_id(1)
        self.assertFalse(app.delete_selected())
        self.assertEqual(app.status, "gone")


class AppSearchSaveTests(unittest.TestCase):
    def test_search_zero_matches_still_replaces_result(self):
        pim = _pim()
        pim.search.return_value = []
        app = App(pim)
        app.search("type = note")
        self.assertEqual(app.current_result(), [])
        self.assertEqual(app.status, "0 match(es)")
        self.assertTrue(app.has_criterion())

    def test_help_constant_lists_verbs(self):
        self.assertIn("create", HELP)
        self.assertIn("print all", HELP)

    def test_save_and_load_delegate_and_set_status(self):
        pim = _pim()
        pim.bound_path.return_value = "/tmp/x.pim"
        app = App(pim)
        self.assertTrue(app.save())
        pim.save.assert_called_once_with("/tmp/x.pim")
        self.assertTrue(app.status.startswith("Saved "))
        self.assertTrue(app.load("/tmp/x.pim"))
        pim.load.assert_called_once_with("/tmp/x.pim", force=False)
        self.assertTrue(app.status.startswith("Loaded "))

    def test_bound_path_and_dirty_and_due_alarms_passthrough(self):
        pim = _pim()
        pim.bound_path.return_value = "/tmp/a.pim"
        pim.is_dirty.return_value = True
        pim.due_alarms.return_value = ["due"]
        app = App(pim)
        self.assertEqual(app.bound_path(), "/tmp/a.pim")
        self.assertTrue(app.is_dirty())
        self.assertEqual(app.due_alarms("now"), ["due"])
