"""Colour roles for the diary View, without opening a real TTY."""

import unittest

from view.theme import (
    ERR,
    OVERDUE,
    PAGE,
    PIN_ROLES,
    SELECT,
    TONE_ROLES,
    Theme,
    _PAIR,
)


class ThemeRoleTests(unittest.TestCase):
    def test_each_role_has_a_distinct_pair(self):
        self.assertEqual(len(_PAIR), len(set(_PAIR.values())))
        self.assertEqual(PIN_ROLES["note"], "pin_note")
        self.assertEqual(TONE_ROLES["danger"], ERR)

    def test_without_curses_attr_is_only_the_extra_bits(self):
        theme = Theme(has_color=False)
        self.assertEqual(theme.attr(PAGE, 3), 3)
        self.assertFalse(theme.rich)

    def test_rich_is_256_or_more(self):
        self.assertTrue(Theme(has_color=True, colors=256).rich)
        self.assertFalse(Theme(has_color=True, colors=8).rich)
        self.assertFalse(Theme(has_color=False, colors=256).rich)

    def test_monochrome_uses_reverse_for_title_and_selection(self):
        class FakeCurses:
            A_REVERSE = 1
            A_BOLD = 2
            A_DIM = 4

        theme = Theme(has_color=False)
        theme.bind(FakeCurses)
        title = theme.attr(SELECT)
        self.assertTrue(title & FakeCurses.A_REVERSE)
        self.assertTrue(title & FakeCurses.A_BOLD)
        quiet = theme.attr("quiet")
        self.assertTrue(quiet & FakeCurses.A_DIM)
        overdue = theme.attr(OVERDUE)
        self.assertTrue(overdue & FakeCurses.A_BOLD)
        self.assertFalse(overdue & FakeCurses.A_REVERSE)
