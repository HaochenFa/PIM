"""Shared Screen model, text fallback, and pane geometry."""

import unittest

from model import Note
from model.pir import parse_datetime
from view.layout import (
    MIN_HEIGHT,
    MIN_WIDTH,
    WIDE_WIDTH,
    build_screen,
    compute_geometry,
    text_lines,
    visible_list_window,
)
from view.terminal import MENU


class FakeDue:
    """One due alarm for the banner."""

    def __init__(self):
        self.status = "OVERDUE"
        self.event_id = 4
        self.description = "lecture"
        self.at = parse_datetime("2026-09-14T18:30:00+08:00")


class ScreenBuildTests(unittest.TestCase):
    def test_empty_untitled_text_lines_match_fallback(self):
        screen = build_screen(
            bound_path=None,
            dirty=False,
            due=[],
            result=[],
            selected_id=None,
            selected=None,
            has_criterion=False,
            print_text="",
            status="",
            prompt="> ",
        )
        lines = text_lines(screen)
        self.assertTrue(lines[0].startswith("PIM  untitled"))
        self.assertIn("ALARMS", lines)
        self.assertIn("  (none)", lines)
        self.assertIn("    (empty)", lines)
        self.assertIn("  (no selection)", lines)
        self.assertIn(MENU, lines)
        self.assertEqual(lines[-1], "> ")

    def test_selection_truncation_dirty_and_print(self):
        note = Note(1, "abcdefghijklmnopqrstuvwxyz extra")
        screen = build_screen(
            bound_path="/tmp/demo.pim",
            dirty=True,
            due=[FakeDue()],
            result=[note],
            selected_id=1,
            selected=note,
            has_criterion=False,
            print_text="printed",
            status="ok",
            prompt="> ",
        )
        joined = "\n".join(text_lines(screen))
        self.assertIn("PIM  /tmp/demo.pim*", joined)
        self.assertIn("OVERDUE", joined)
        self.assertIn("(dismiss)", joined)
        self.assertIn("abc", joined)
        self.assertIn("...", joined)
        self.assertIn(">   1    1  note", joined)
        self.assertIn("PRINT", joined)


class GeometryTests(unittest.TestCase):
    def test_wide_terminal_is_side_by_side(self):
        geo = compute_geometry(24, 80)
        self.assertFalse(geo.too_small)
        self.assertFalse(geo.stacked)
        self.assertGreater(geo.list_h, 0)
        self.assertEqual(geo.prompt_y, 23)
        self.assertEqual(geo.detail_x, geo.list_w + 1)
        self.assertEqual(geo.composer_h, 2)
        self.assertEqual(geo.status_y, 21)

    def test_selector_composer_shrinks_the_body(self):
        idle = compute_geometry(24, 80, 2)
        choosing = compute_geometry(24, 80, 3)
        self.assertEqual(choosing.composer_h, 3)
        self.assertEqual(choosing.status_y, idle.status_y - 1)
        self.assertLess(choosing.list_h, idle.list_h)

    def test_narrow_terminal_stacks_list_above_detail(self):
        geo = compute_geometry(24, 70)
        self.assertFalse(geo.too_small)
        self.assertTrue(geo.stacked)
        self.assertLess(70, WIDE_WIDTH)
        self.assertEqual(geo.list_x, 0)
        self.assertEqual(geo.detail_x, 0)

    def test_tiny_terminal_is_flagged(self):
        geo = compute_geometry(MIN_HEIGHT - 1, 80)
        self.assertTrue(geo.too_small)
        geo = compute_geometry(24, MIN_WIDTH - 1)
        self.assertTrue(geo.too_small)

    def test_visible_window_keeps_selection_in_view(self):
        self.assertEqual(visible_list_window(3, 1, 10), 0)
        self.assertEqual(visible_list_window(20, 19, 5), 15)
        self.assertEqual(visible_list_window(20, None, 5), 0)
