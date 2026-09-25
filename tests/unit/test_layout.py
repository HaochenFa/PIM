"""Shared Screen model, text fallback, and pane geometry."""

import unittest

from model import Note
from model.pir import parse_datetime
from view.layout import (
    MIN_HEIGHT,
    MIN_WIDTH,
    WIDE_WIDTH,
    ResultRow,
    TYPE_PIN,
    build_screen,
    card_fields,
    compute_geometry,
    format_list_header,
    format_list_row,
    list_pane_title,
    picker_time_origin,
    picker_weekday_row,
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
        """With no bound file, no due alarms, no Current Result, and no Selection, the fallback text renders each empty state."""
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
        """A bound dirty file shows a `*`, an OVERDUE banner with `(dismiss)`, a truncated `...` Note text, and a PRINT block."""
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
        """At 80 columns the list and detail panes sit side by side, not stacked, with a positive list height."""
        geo = compute_geometry(24, 80)
        self.assertFalse(geo.too_small)
        self.assertFalse(geo.stacked)
        self.assertGreater(geo.list_h, 0)
        self.assertEqual(geo.prompt_y, 23)
        self.assertEqual(geo.detail_x, geo.list_w + 1)
        self.assertEqual(geo.composer_h, 2)
        self.assertEqual(geo.status_y, 21)

    def test_selector_composer_shrinks_the_body(self):
        """A taller composer (a chooser open) raises the status row and shrinks the list pane height."""
        idle = compute_geometry(24, 80, 2)
        choosing = compute_geometry(24, 80, 3)
        self.assertEqual(choosing.composer_h, 3)
        self.assertEqual(choosing.status_y, idle.status_y - 1)
        self.assertLess(choosing.list_h, idle.list_h)

    def test_narrow_terminal_stacks_list_above_detail(self):
        """Below `WIDE_WIDTH` columns the layout stacks the list above the detail pane, both starting at column 0."""
        geo = compute_geometry(24, 70)
        self.assertFalse(geo.too_small)
        self.assertTrue(geo.stacked)
        self.assertLess(70, WIDE_WIDTH)
        self.assertEqual(geo.list_x, 0)
        self.assertEqual(geo.detail_x, 0)

    def test_tiny_terminal_is_flagged(self):
        """A terminal shorter than `MIN_HEIGHT` or narrower than `MIN_WIDTH` sets `too_small`."""
        geo = compute_geometry(MIN_HEIGHT - 1, 80)
        self.assertTrue(geo.too_small)
        geo = compute_geometry(24, MIN_WIDTH - 1)
        self.assertTrue(geo.too_small)

    def test_list_row_uses_a_type_pin_and_time_gutter(self):
        """A Current Result row shows the type pin (not the word `event`), the Display Name, and a `>` selection marker."""
        row = ResultRow(1, 4, "event", "COMP3211 lecture", "2026-09-14 18:30", "2026-09-14 18:30", True)
        line = format_list_row(row, 60, short_time_col=True)
        self.assertIn(TYPE_PIN["event"], line)
        self.assertNotIn("event", line)
        self.assertIn("COMP3211", line)
        self.assertTrue(line.startswith(">"))
        header = format_list_header(60, short_time_col=True)
        self.assertIn("Name", header)
        self.assertIn("Time", header)

    def test_missing_time_is_a_dot(self):
        """A Contact row, which has no time field, renders the time gutter as a `·` placeholder."""
        row = ResultRow(1, 5, "contact", "Ada", "", "", False)
        line = format_list_row(row, 50, short_time_col=True)
        self.assertIn("·", line)

    def test_card_fields_drop_id_and_type(self):
        """`card_fields` filters `Id` and `type` out of the detail card, keeping the remaining fields."""
        fields = card_fields((("Id", "4"), ("type", "event"), ("start", "t")))
        self.assertEqual(fields, (("start", "t"),))

    def test_list_title_includes_criterion_and_scroll(self):
        """When a search is active, both `screen.filter_label` and the list pane title show the criterion text."""
        note = Note(1, "x")
        screen = build_screen(
            bound_path=None,
            dirty=False,
            due=[],
            result=[note],
            selected_id=1,
            selected=note,
            has_criterion=True,
            print_text="",
            status="",
            prompt="> ",
            criterion_line='type = note',
        )
        self.assertEqual(screen.filter_label, "type = note")
        title = list_pane_title(screen, first=0, visible=1)
        self.assertIn("type = note", title)

    def test_time_slots_start_below_weekday_header(self):
        """The picker's time-slot row is positioned below its weekday header row."""
        self.assertGreater(picker_time_origin(10), picker_weekday_row(10))

    def test_visible_window_keeps_selection_in_view(self):
        """`visible_list_window` scrolls just enough to keep the selected row visible, and starts at 0 with no selection."""
        self.assertEqual(visible_list_window(3, 1, 10), 0)
        self.assertEqual(visible_list_window(20, 19, 5), 15)
        self.assertEqual(visible_list_window(20, None, 5), 0)
