"""Closed-choice selectors: keys, defaults, payload values."""

import unittest

from view.widgets import (
    composer_height,
    dirty_chooser,
    type_chooser,
    yes_no_chooser,
)
from tests.unit.test_terminal import make_terminal


class ChooserTests(unittest.TestCase):
    def test_type_picker_digits_and_letters(self):
        chooser = type_chooser()
        self.assertEqual(chooser.pick_key("1"), 0)
        self.assertEqual(chooser.pick_key("n"), 0)
        self.assertEqual(chooser.pick_key("3"), 2)
        self.assertEqual(chooser.pick_key("e"), 2)
        self.assertEqual(chooser.pick_key("c"), 3)
        self.assertEqual(chooser.value_at(0), "note")
        self.assertEqual(chooser.value_at(3), "contact")
        self.assertIsNone(chooser.pick_key("x"))
        self.assertIsNone(chooser.pick_key("9"))

    def test_move_does_not_wrap(self):
        chooser = type_chooser()
        self.assertEqual(chooser.move(0, -1), 0)
        self.assertEqual(chooser.move(3, 1), 3)
        self.assertEqual(chooser.move(1, 1), 2)

    def test_yes_no_defaults_to_no_for_destructive_actions(self):
        chooser = yes_no_chooser("Delete?", prefer_yes=False)
        self.assertEqual(chooser.default, 1)
        self.assertEqual(chooser.value_at(chooser.default), "n")
        self.assertEqual(chooser.pick_key("y"), 0)
        self.assertEqual(chooser.pick_key("n"), 1)

    def test_dirty_chooser_values_match_handlers(self):
        chooser = dirty_chooser("Unsaved changes")
        self.assertEqual(chooser.value_at(0), "save")
        self.assertEqual(chooser.value_at(1), "discard")
        self.assertEqual(chooser.value_at(2), "cancel")
        self.assertEqual(chooser.pick_key("s"), 0)
        self.assertEqual(chooser.default, 2)

    def test_composer_is_taller_for_a_selector(self):
        self.assertEqual(composer_height(chooser=None, text_prompt=False), 2)
        self.assertEqual(composer_height(chooser=None, text_prompt=True), 3)
        self.assertEqual(composer_height(chooser=type_chooser(), text_prompt=False), 3)


class TerminalChooserTests(unittest.TestCase):
    def test_create_without_type_attaches_the_type_selector(self):
        app, term, _out = make_terminal()
        term.apply_accelerator("create")
        chooser = term.current_chooser()
        self.assertIsNotNone(chooser)
        self.assertEqual(chooser.value_at(0), "note")
        self.assertIn("type", term._prompt_label())

    def test_typed_note_still_starts_the_field_wizard(self):
        app, term, _out = make_terminal()
        term.apply_accelerator("create")
        term._handle_line("note")
        self.assertIsNone(term.current_chooser())
        self.assertIn("text", term._prompt_label())
        term._handle_line("Shopping: Milk")
        self.assertEqual(app.calls[-1], ("create", "note", {"text": "Shopping: Milk"}))

    def test_delete_selector_defaults_to_no(self):
        from model import Note

        app, term, _out = make_terminal()
        app._selected = Note(1, "x")
        term.apply_accelerator("delete")
        chooser = term.current_chooser()
        self.assertEqual(chooser.value_at(chooser.default), "n")
