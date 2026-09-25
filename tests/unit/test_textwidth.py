"""Display-column width: ASCII, CJK, clipping, wrap."""

import unittest

from view.textwidth import caret_column, clip, clip_left, display_width, input_window, pad, wrap


class DisplayWidthTests(unittest.TestCase):
    def test_ascii_matches_len(self):
        """`display_width` of plain ASCII text equals its character length."""
        self.assertEqual(display_width("Ada"), 3)

    def test_cjk_is_two_columns(self):
        """Each CJK character counts as two display columns in `display_width`."""
        self.assertEqual(display_width("香港"), 4)
        self.assertEqual(display_width("A港"), 3)

    def test_clip_left_keeps_the_end_of_a_long_path(self):
        """A path wider than the field keeps its file name and gains a leading ellipsis."""
        path = "/Users/you/Documents/courses/work.pim"
        self.assertEqual(clip_left(path, 60), path)
        self.assertEqual(clip_left(path, 15), "...ses/work.pim")
        self.assertEqual(clip_left("/文件夹/笔记.pim", 9), "...记.pim")
        self.assertEqual(clip_left(path, 0), "")
        self.assertEqual(clip_left(path, 2), "im")

    def test_clip_ascii_matches_previous_layout(self):
        """`clip` truncates ASCII text to the given width with a trailing "..." ellipsis."""
        name = "abcdefghijklmnopqrstuvwxyz extra"
        self.assertEqual(clip(name, 24), "abcdefghijklmnopqrstu...")

    def test_clip_cjk_does_not_split_a_wide_character_over_budget(self):
        """`clip` never splits a wide CJK character across the width budget; it still appends "..."."""
        self.assertEqual(display_width(clip("香港香港", 5)), 5)
        self.assertTrue(clip("香港香港", 5).endswith("..."))

    def test_pad_exact_width(self):
        """`pad` extends text to exactly the requested display width."""
        self.assertEqual(display_width(pad("Ada", 8)), 8)

    def test_caret_column_counts_cjk_width(self):
        """`caret_column` counts each preceding CJK character as two columns when locating the caret."""
        self.assertEqual(caret_column("香港a", 0), 0)
        self.assertEqual(caret_column("香港a", 1), 2)
        self.assertEqual(caret_column("香港a", 2), 4)
        self.assertEqual(caret_column("香港a", 3), 5)

    def test_input_window_keeps_caret_inside_width(self):
        """`input_window` keeps the visible slice within the width budget and the caret position inside it."""
        text = "abcdefghijklmnopqrstuvwxyz"
        visible, x = input_window(text, 25, 8)
        self.assertLessEqual(display_width(visible), 8)
        self.assertGreaterEqual(x, 0)
        self.assertLess(x, 8)
        self.assertTrue(visible.endswith("z") or "z" in visible)

    def test_wrap_splits_on_columns(self):
        """`wrap` splits text at the column width, and also at existing newlines."""
        self.assertEqual(wrap("abcdef", 3), ["abc", "def"])
        self.assertEqual(wrap("ab\ncd", 10), ["ab", "cd"])
