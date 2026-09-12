"""Empty-prompt accelerators map characters and curses key names."""

import unittest

from view.keys import (
    CREATE,
    DELETE,
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

    def test_curses_key_names(self):
        self.assertEqual(action_for_key_name("KEY_UP"), SELECT_UP)
        self.assertEqual(action_for_key_name("KEY_DOWN"), SELECT_DOWN)
        self.assertEqual(action_for_key_name("KEY_DC"), DELETE)
        self.assertIsNone(action_for_key_name("KEY_LEFT"))
