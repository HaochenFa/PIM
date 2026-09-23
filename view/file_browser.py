"""Folder browser for the load and save-as path prompts (US10 / US11).

The full-screen View shows this instead of a bare ``path:`` field. Like the
calendar picker, it only produces the same path string the typed prompt
accepts, so the dirty rule, overwrite confirmation, `.pim` check, and `~`
expansion stay in one place. No curses here, so it is unit-testable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

LOAD = "load"
SAVE = "save"

PARENT = "parent"
FOLDER = "folder"
FILE = "file"
NEW_FILE = "new"


@dataclass(frozen=True)
class Entry:
    """One row: the parent link, a folder, a `.pim` file, or "new file here"."""

    kind: str
    name: str

    def label(self) -> str:
        """Row text: folders end in `/`."""
        if self.kind == PARENT:
            return "../"
        if self.kind == FOLDER:
            return self.name + "/"
        if self.kind == NEW_FILE:
            return "+ New file in this folder…"
        return self.name


class FileBrowser:
    """Cursor over one folder's subfolders and `.pim` files.

    ``mode`` is ``LOAD`` or ``SAVE``. Save adds a "new file here" row that
    hands over to the typed path field. Hidden entries are skipped. A folder
    that cannot be read shows ``error`` and an empty list instead of raising.
    """

    def __init__(self, mode: str, start: str | os.PathLike[str]):
        self.mode = mode
        self.cwd = Path(start).absolute()
        self.entries: list[Entry] = []
        self.index = 0
        self.error = ""
        self.refresh()

    @property
    def title(self) -> str:
        """Heading for the overlay."""
        return "Load a .pim file" if self.mode == LOAD else "Save as — pick a folder or file"

    def refresh(self) -> None:
        """Re-read ``cwd``: `../` (unless at the root), folders, then `.pim` files."""
        entries: list[Entry] = []
        if self.mode == SAVE:
            entries.append(Entry(NEW_FILE, ""))
        if self.cwd.parent != self.cwd:
            entries.append(Entry(PARENT, ".."))
        self.error = ""
        folders: list[str] = []
        files: list[str] = []
        try:
            with os.scandir(self.cwd) as found:
                for item in found:
                    if item.name.startswith("."):
                        continue
                    try:
                        if item.is_dir():
                            folders.append(item.name)
                        elif item.is_file() and item.name.casefold().endswith(".pim"):
                            files.append(item.name)
                    except OSError:
                        continue
        except OSError:
            self.error = "cannot read this folder"
        entries.extend(Entry(FOLDER, name) for name in sorted(folders, key=str.casefold))
        entries.extend(Entry(FILE, name) for name in sorted(files, key=str.casefold))
        self.entries = entries
        self.index = min(self.index, max(0, len(entries) - 1))

    def current(self) -> Entry | None:
        """Highlighted row, or None if the list is empty."""
        if not self.entries:
            return None
        return self.entries[self.index]

    def move(self, delta: int) -> None:
        """Move the highlight by ``delta`` rows, without wrapping."""
        if self.entries:
            self.index = max(0, min(len(self.entries) - 1, self.index + delta))

    def jump(self, last: bool) -> None:
        """Highlight the first or last row."""
        self.index = len(self.entries) - 1 if last and self.entries else 0

    def go_up(self) -> None:
        """Open the parent folder and highlight the folder we came from."""
        if self.cwd.parent == self.cwd:
            return
        came_from = self.cwd.name
        self._enter(self.cwd.parent)
        for index, entry in enumerate(self.entries):
            if entry.kind == FOLDER and entry.name == came_from:
                self.index = index
                break

    def go_home(self) -> None:
        """Open the user's home folder."""
        self._enter(Path(os.path.expanduser("~")))

    def activate(self) -> str | None:
        """Act on the highlighted row.

        A folder or `../` is opened and None is returned. A `.pim` file returns
        its absolute path for the prompt handler. The "new file" row also
        returns None; the View then switches to the typed field (see
        ``typed_start``).
        """
        entry = self.current()
        if entry is None:
            return None
        if entry.kind == PARENT:
            self.go_up()
            return None
        if entry.kind == FOLDER:
            self._enter(self.cwd / entry.name)
            return None
        if entry.kind == FILE:
            return str(self.cwd / entry.name)
        return None

    def wants_typing(self) -> bool:
        """True when the highlighted row is "new file here"."""
        entry = self.current()
        return entry is not None and entry.kind == NEW_FILE

    def typed_start(self) -> str:
        """Text to pre-fill when switching to the typed path field: this folder."""
        return os.path.join(str(self.cwd), "")

    def state(self) -> tuple:
        """Hashable view state, so the curses loop redraws only on change."""
        return (self.mode, str(self.cwd), self.index, len(self.entries), self.error)

    def _enter(self, folder: Path) -> None:
        self.cwd = folder
        self.index = 0
        self.refresh()
