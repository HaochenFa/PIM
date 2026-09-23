"""Empty-prompt accelerators map characters and curses key names."""

import unittest

from view.keys import (
    CREATE,
    DELETE,
    LOAD,
    SAVE,
    SAVE_AS,
    SEARCH,
    SELECT_DOWN,
    SELECT_UP,
    action_for_char,
    action_for_key_name,
)


class AcceleratorMapTests(unittest.TestCase):
    def test_slash_is_search_and_letters_match_the_plan(self):
        self.assertEqual(action_for_char("/"), SEARCH)
        self.assertEqual(action_for_char("c"), CREATE)
        self.assertEqual(action_for_char("j"), SELECT_DOWN)
        self.assertEqual(action_for_char("k"), SELECT_UP)
        self.assertEqual(action_for_char("x"), DELETE)
        self.assertIsNone(action_for_char("s"))
        self.assertIsNone(action_for_char("cc"))

    def test_file_keys_save_save_as_and_load(self):
        """`w` saves, `W` is save as, `o` loads (opens) a PIM File."""
        self.assertEqual(action_for_char("w"), SAVE)
        self.assertEqual(action_for_char("W"), SAVE_AS)
        self.assertEqual(action_for_char("o"), LOAD)

    def test_curses_key_names(self):
        self.assertEqual(action_for_key_name("KEY_UP"), SELECT_UP)
        self.assertEqual(action_for_key_name("KEY_DOWN"), SELECT_DOWN)
        self.assertEqual(action_for_key_name("KEY_DC"), DELETE)
        self.assertIsNone(action_for_key_name("KEY_LEFT"))
