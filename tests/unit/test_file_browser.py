"""view.file_browser: listing, navigation, and the path handed to the prompt."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from view.file_browser import FILE, LOAD, NEW_FILE, PARENT, SAVE, FileBrowser


class FileBrowserTests(unittest.TestCase):
    """Load and save-as browsing over a temporary folder tree."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        (self.root / "b-folder").mkdir()
        (self.root / "A-folder").mkdir()
        (self.root / ".hidden").mkdir()
        (self.root / "work.pim").write_text("{}", encoding="utf-8")
        (self.root / "Demo.PIM").write_text("{}", encoding="utf-8")
        (self.root / "notes.txt").write_text("x", encoding="utf-8")
        (self.root / ".secret.pim").write_text("{}", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def labels(self, browser):
        return [entry.label() for entry in browser.entries]

    def test_load_lists_parent_folders_then_pim_files_casefold_sorted(self):
        """`../`, folders A→b, then `.pim` files; hidden entries and other extensions are skipped."""
        browser = FileBrowser(LOAD, self.root)
        self.assertEqual(
            self.labels(browser),
            ["../", "A-folder/", "b-folder/", "Demo.PIM", "work.pim"],
        )
        self.assertEqual(browser.title, "Load a .pim file")

    def test_save_starts_with_a_new_file_row(self):
        """Save as puts "new file here" first, so Enter on open types a name in this folder."""
        browser = FileBrowser(SAVE, self.root)
        self.assertEqual(browser.entries[0].kind, NEW_FILE)
        self.assertTrue(browser.wants_typing())
        self.assertIsNone(browser.activate())
        self.assertEqual(browser.typed_start(), str(self.root.absolute()) + os.sep)

    def test_activate_folder_opens_it_and_file_returns_its_path(self):
        """Enter on a folder opens it; Enter on a `.pim` file returns the absolute path."""
        (self.root / "A-folder" / "inner.pim").write_text("{}", encoding="utf-8")
        browser = FileBrowser(LOAD, self.root)
        browser.index = 1
        self.assertIsNone(browser.activate())
        self.assertEqual(browser.cwd, self.root.absolute() / "A-folder")
        self.assertEqual(self.labels(browser), ["../", "inner.pim"])
        browser.move(1)
        self.assertEqual(browser.activate(), str(self.root.absolute() / "A-folder" / "inner.pim"))

    def test_highlighted_path_names_the_row_or_this_folder(self):
        """The composer shows the highlighted folder or file path, else the current folder."""
        browser = FileBrowser(SAVE, self.root)
        here = str(self.root.absolute())
        self.assertEqual(browser.highlighted_path(), here)
        browser.move(1)
        self.assertEqual(browser.current().kind, PARENT)
        self.assertEqual(browser.highlighted_path(), here)
        browser.move(1)
        self.assertEqual(browser.highlighted_path(), os.path.join(here, "A-folder"))
        browser.jump(last=True)
        self.assertEqual(browser.highlighted_path(), os.path.join(here, "work.pim"))

    def test_go_up_highlights_the_folder_we_left(self):
        """`../` or Backspace returns to the parent with the previous folder highlighted."""
        browser = FileBrowser(LOAD, self.root / "b-folder")
        browser.index = 0
        self.assertEqual(browser.current().kind, PARENT)
        browser.activate()
        self.assertEqual(browser.cwd, self.root.absolute())
        self.assertEqual(browser.current().label(), "b-folder/")

    def test_root_has_no_parent_row_and_go_up_stays(self):
        """At the filesystem root there is no `../`, and going up does nothing."""
        root = Path(self.root.absolute().anchor)
        browser = FileBrowser(LOAD, root)
        self.assertNotIn(PARENT, [entry.kind for entry in browser.entries])
        browser.go_up()
        self.assertEqual(browser.cwd, root)

    def test_move_and_jump_clamp_to_the_list(self):
        """Arrow moves do not wrap; Home/End jump to the first and last row."""
        browser = FileBrowser(LOAD, self.root)
        browser.move(-5)
        self.assertEqual(browser.index, 0)
        browser.move(50)
        self.assertEqual(browser.index, len(browser.entries) - 1)
        browser.jump(last=False)
        self.assertEqual(browser.index, 0)
        browser.jump(last=True)
        self.assertEqual(browser.current().kind, FILE)

    def test_unreadable_folder_shows_error_instead_of_raising(self):
        """A folder that cannot be listed sets `error` and keeps `../` so the user can leave."""
        with patch("view.file_browser.os.scandir", side_effect=PermissionError("denied")):
            browser = FileBrowser(LOAD, self.root)
        self.assertEqual(browser.error, "cannot read this folder")
        self.assertEqual(self.labels(browser), ["../"])

    def test_entry_that_cannot_be_inspected_is_skipped(self):
        """A dangling or unreadable entry is left out rather than failing the whole listing."""

        class Broken:
            name = "broken"

            def is_dir(self):
                raise OSError("gone")

        class Listing:
            def __enter__(self):
                return iter([Broken()])

            def __exit__(self, *exc):
                return False

        with patch("view.file_browser.os.scandir", return_value=Listing()):
            browser = FileBrowser(LOAD, self.root)
        self.assertEqual(self.labels(browser), ["../"])
        self.assertEqual(browser.error, "")

    def test_empty_list_has_no_current_row(self):
        """At the root of an empty listing, activate and move are harmless no-ops."""
        with patch("view.file_browser.os.scandir", side_effect=OSError("x")):
            browser = FileBrowser(LOAD, Path(self.root.absolute().anchor))
        self.assertEqual(browser.entries, [])
        self.assertIsNone(browser.current())
        self.assertIsNone(browser.activate())
        self.assertFalse(browser.wants_typing())
        browser.move(1)
        browser.jump(last=True)
        self.assertEqual(browser.index, 0)

    def test_go_home_opens_the_home_folder(self):
        """`~` in the browser opens $HOME."""
        with patch.dict("os.environ", {"HOME": str(self.root / "A-folder")}):
            browser = FileBrowser(LOAD, self.root)
            browser.go_home()
        self.assertEqual(browser.cwd, self.root / "A-folder")

    def test_state_changes_when_the_highlight_or_folder_changes(self):
        """The redraw snapshot differs after a move and after opening a folder."""
        browser = FileBrowser(LOAD, self.root)
        before = browser.state()
        browser.move(1)
        moved = browser.state()
        self.assertNotEqual(before, moved)
        browser.activate()
        self.assertNotEqual(moved, browser.state())
        self.assertEqual(browser.entries[0].kind, PARENT)


if __name__ == "__main__":
    unittest.main()
