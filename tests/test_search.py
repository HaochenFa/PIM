"""US7: contains, time comparison, and/or/not, fixture expectations."""

import unittest

from model import ParseError, parse_criterion
from tests.fixture import make_fixture


def ids_for(pim, text):
    return [pir.id for pir in pim.search(parse_criterion(text))]


class FixtureSearchTests(unittest.TestCase):
    def setUp(self):
        self.pim = make_fixture()

    def test_type_note(self):
        self.assertEqual(ids_for(self.pim, "type = note"), [1])

    def test_text_contains_casefold(self):
        self.assertEqual(ids_for(self.pim, 'text contains "milk"'), [1])

    def test_unqualified_contains_any_text_field(self):
        self.assertEqual(ids_for(self.pim, 'contains "ada"'), [5, 6])

    def test_name_contains_ada_matches_both_contacts(self):
        self.assertEqual(
            ids_for(self.pim, 'type = contact && name contains "ada"'),
            [5, 6],
        )

    def test_deadline_comparison_skips_missing_deadline(self):
        self.assertEqual(
            ids_for(self.pim, "deadline < 2026-11-21T00:00:00+08:00"),
            [2],
        )

    def test_deadline_space_separated_datetime(self):
        self.assertEqual(ids_for(self.pim, "deadline < 2026-11-21 00:00"), [2])

    def test_start_space_separated_offset_datetime(self):
        self.assertEqual(
            ids_for(self.pim, "start = 2026-09-14 18:30:00+08:00"),
            [4],
        )

    def test_space_separated_datetime_stops_at_and(self):
        self.assertEqual(
            ids_for(self.pim, "deadline < 2026-11-21 00:00 && type = task"),
            [2],
        )

    def test_start_equality_with_hkt(self):
        self.assertEqual(
            ids_for(self.pim, "start = 2026-09-14T18:30:00+08:00"),
            [4],
        )

    def test_alarm_is_existential(self):
        # absolute 09:00 matches; relative 1 day = 13th 18:30 is not before 18:00
        self.assertEqual(
            ids_for(self.pim, "alarm < 2026-09-13T18:00:00+08:00"),
            [4],
        )

    def test_description_contains_comp3211(self):
        self.assertEqual(
            ids_for(self.pim, 'description contains "comp3211"'),
            [4],
        )

    def test_and_or_not_and_parentheses(self):
        self.assertEqual(
            ids_for(self.pim, "type = task || type = note"),
            [1, 2, 3],
        )
        self.assertEqual(
            ids_for(self.pim, "!(type = contact)"),
            [1, 2, 3, 4],
        )
        self.assertEqual(
            ids_for(self.pim, "type = contact && name contains \"ada\" || type = note"),
            [1, 5, 6],
        )

    def test_syntax_error_raises_parse_error(self):
        with self.assertRaises(ParseError):
            parse_criterion("type =")
        with self.assertRaises(ParseError):
            parse_criterion("deadline << 2026-01-01")
        with self.assertRaises(ParseError):
            parse_criterion('text contains "unterminated')
        with self.assertRaises(ParseError):
            parse_criterion("")
        before = [pir.id for pir in self.pim.all()]
        with self.assertRaises(ParseError):
            self.pim.search(parse_criterion("???"))
        self.assertEqual([pir.id for pir in self.pim.all()], before)


class PrecedenceTests(unittest.TestCase):
    def test_not_binds_tighter_than_and(self):
        pim = make_fixture()
        # !type = note && type = task  →  (!note) && task
        self.assertEqual(ids_for(pim, "!type = note && type = task"), [2, 3])


if __name__ == "__main__":
    unittest.main()
