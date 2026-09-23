# Load and save-as paths get a folder browser on the TTY; the typed path stays

US10/US11 only require storing to and loading from a `.pim` file. A typed path met that, but users expected to pick the location the way a desktop app lets them, and a bare `path:` field hid how to import a file at all. A native macOS dialog (Finder via `osascript`, or tkinter's `filedialog`) would be a GUI window. The brief asks for a command-line system, and ADR-0004 rules out GUI toolkits, so it is not an option.

On a TTY, every load or save-as path prompt opens a folder browser drawn with stdlib `curses`, in the same way ADR-0018 draws the calendar. It lists `../`, subfolders, and `.pim` files only, and in save mode it adds a "new file in this folder" row. `/` or Tab switches to the typed field, so absolute, relative, and `~` paths still work. Whatever is chosen reaches the prompt handler as a path string, exactly like a typed answer. The `.pim` rule (ADR-0015), overwrite confirmation, dirty save / discard / cancel, and atomic failure (ADR-0014) therefore stay in one place. `load <path>` and `save as <path>` with an argument never open it. The line UI, tests, and e2e scripts keep typing paths.

The browser is View-only: it lists folders with `os.scandir` but never opens a PIM File. Reading and writing still go only through `PIM.load` / `PIM.save`.

**Status**: accepted
