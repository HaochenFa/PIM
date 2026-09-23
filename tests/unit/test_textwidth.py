"""Display-column width: ASCII, CJK, clipping, wrap."""

import unittest

from view.textwidth import caret_column, clip, display_width, input_window, pad, wrap


class DisplayWidthTests(unittest.TestCase):
    def test_ascii_matches_len(self):
        self.assertEqual(display_width("Ada"), 3)

    def test_cjk_is_two_columns(self):
        self.assertEqual(display_width("香港"), 4)
        self.assertEqual(display_width("A港"), 3)

    def test_clip_ascii_matches_previous_layout(self):
        name = "abcdefghijklmnopqrstuvwxyz extra"
        self.assertEqual(clip(name, 24), "abcdefghijklmnopqrstu...")

    def test_clip_cjk_does_not_split_a_wide_character_over_budget(self):
        self.assertEqual(display_width(clip("香港香港", 5)), 5)
        self.assertTrue(clip("香港香港", 5).endswith("..."))

    def test_pad_exact_width(self):
        self.assertEqual(display_width(pad("Ada", 8)), 8)

    def test_caret_column_counts_cjk_width(self):
        self.assertEqual(caret_column("香港a", 0), 0)
        self.assertEqual(caret_column("香港a", 1), 2)
        self.assertEqual(caret_column("香港a", 2), 4)
        self.assertEqual(caret_column("香港a", 3), 5)

    def test_input_window_keeps_caret_inside_width(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        visible, x = input_window(text, 25, 8)
        self.assertLessEqual(display_width(visible), 8)
        self.assertGreaterEqual(x, 0)
        self.assertLess(x, 8)
        self.assertTrue(visible.endswith("z") or "z" in visible)

    def test_wrap_splits_on_columns(self):
        self.assertEqual(wrap("abcdef", 3), ["abc", "def"])
        self.assertEqual(wrap("ab\ncd", 10), ["ab", "cd"])
