"""controller.App in isolation: status, Current Result, selection. PIM is mocked."""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock

from controller.app import HELP, STATUS_ERR, STATUS_INFO, STATUS_OK, App, format_pir
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
        self.assertEqual(app.status_kind, STATUS_ERR)
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
        self.assertTrue(app.search("type = note"))
        self.assertEqual(app.current_result(), [])
        self.assertEqual(app.status, "0 match(es)")
        self.assertEqual(app.status_kind, STATUS_OK)
        self.assertTrue(app.has_criterion())
        self.assertEqual(app.criterion_line(), "type = note")
        self.assertIsNone(app.selected_id())

    def test_search_selects_first_hit_and_keeps_source_line(self):
        note = Note(1, "ok")
        task = Task(2, "Inbox")
        pim = _pim([note, task])
        pim.search.return_value = [task]
        pim.get.return_value = task
        app = App(pim)
        self.assertTrue(app.search("type = task"))
        self.assertEqual(app.selected_id(), 2)
        self.assertEqual(app.criterion_line(), "type = task")
        self.assertEqual(app.status_kind, STATUS_OK)

    def test_search_syntax_error_returns_false_and_keeps_list(self):
        note = Note(1, "ok")
        pim = _pim([note])
        pim.get.return_value = note
        app = App(pim)
        app.select_row(1)
        self.assertFalse(app.search("type ="))
        self.assertEqual(app.current_result(), [note])
        self.assertEqual(app.selected_id(), 1)
        self.assertIsNone(app.criterion_line())
        self.assertEqual(app.status_kind, STATUS_ERR)
        self.assertIn("search syntax error", app.status)
        pim.search.assert_not_called()

    def test_set_status_rejects_unknown_kind(self):
        app = App(_pim())
        app.set_status("hello", "loud")
        self.assertEqual(app.status, "hello")
        self.assertEqual(app.status_kind, STATUS_INFO)

    def test_clear_search_drops_criterion_line(self):
        pim = _pim()
        pim.search.return_value = []
        app = App(pim)
        app.search("type = note")
        app.clear_search()
        self.assertIsNone(app.criterion_line())
        self.assertEqual(app.status_kind, STATUS_INFO)

    def test_help_constant_lists_verbs(self):
        self.assertIn("create", HELP)
        self.assertIn("print all", HELP)

    def test_save_and_load_delegate_and_set_status(self):
        pim = _pim()
        pim.bound_path.return_value = "/tmp/x.pim"
        app = App(pim)
        self.assertTrue(app.save())
        pim.save.assert_called_once_with("/tmp/x.pim")
        self.assertEqual(app.status, "Saved /tmp/x.pim")
        self.assertTrue(app.load("/tmp/x.pim"))
        pim.load.assert_called_once_with("/tmp/x.pim", force=False)
        self.assertEqual(app.status, "Loaded /tmp/x.pim")

    def test_save_and_load_status_show_the_absolute_path(self):
        """A relative Bound File is shown resolved against the working directory."""
        pim = _pim()
        pim.bound_path.return_value = "work.pim"
        app = App(pim)
        expected = os.path.join(os.getcwd(), "work.pim")
        self.assertTrue(app.save())
        self.assertEqual(app.status, f"Saved {expected}")
        self.assertTrue(app.load("work.pim"))
        self.assertEqual(app.status, f"Loaded {expected}")

    def test_save_os_error_names_target_not_temp_file(self):
        """PermissionError from PIM.save sets `cannot save <target>.pim: <reason>`; returns False."""
        pim = _pim()
        pim.save.side_effect = PermissionError(1, "Operation not permitted", "/tmp/.pim-abc.tmp")
        app = App(pim)
        self.assertFalse(app.save("/tmp/report"))
        self.assertEqual(app.status, "cannot save /tmp/report.pim: Operation not permitted")
        self.assertEqual(app.status_kind, STATUS_ERR)
        self.assertNotIn(".tmp", app.status)
        pim.save.side_effect = OSError("disk full")
        self.assertFalse(app.save("/tmp/report.pim"))
        self.assertEqual(app.status, "cannot save /tmp/report.pim: disk full")

    def test_bound_path_and_dirty_and_due_alarms_passthrough(self):
        pim = _pim()
        pim.bound_path.return_value = "/tmp/a.pim"
        pim.is_dirty.return_value = True
        pim.due_alarms.return_value = ["due"]
        app = App(pim)
        self.assertEqual(app.bound_path(), "/tmp/a.pim")
        self.assertTrue(app.is_dirty())
        self.assertEqual(app.due_alarms("now"), ["due"])
