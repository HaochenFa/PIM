"""coverage_report countable lines: only real docstrings are omitted."""

import textwrap
import unittest

from coverage_report import _countable_lines


class CountableLineTests(unittest.TestCase):
    def test_skips_module_class_function_docstrings_not_mid_block_strings(self):
        """`_countable_lines` excludes only real module/class/function docstrings, not other string literals."""
        source = textwrap.dedent(
            '''\
            """mod"""
            x = 1
            """not a docstring"""
            class C:
                """cls"""
                y = 2
                def f(self):
                    """fn"""
                    "also not"
                    return 1
            '''
        )
        self.assertEqual(_countable_lines(source), {2, 3, 4, 6, 7, 9, 10})


if __name__ == "__main__":
    unittest.main()
