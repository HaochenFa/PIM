# Folder browser for load and save-as paths

**Status:** implemented on `feat/file-browser` (2026-09-24), stacked on `fix/pim-file-access` (`docs/plans/2026-09-24_file-access.plan.md`). This file is the design record plus what actually landed. The decision is ADR-0019.

Appendix B, MVC, stdlib-only, the command vocabulary (ADR-0016), and the line UI stay locked. This is View HCI for US10/US11, like the calendar picker, not a new product feature.

---

## Why

After `o` / `W` and `~` paths landed, the group asked for a way to pick a location "like macOS Finder".

- **Calling Finder was rejected.** The only routes are `osascript` or tkinter's `filedialog`. Both are GUI windows, the brief asks for a command-line system, and ADR-0004 and AGENTS.md forbid them.
- **A browser drawn in the terminal with stdlib `curses` was accepted.** The group chose it knowing it earns no extra marks under the brief. Its value is demo quality and making import obvious.

---

## Design

- **`view/file_browser.py` `FileBrowser`** holds no curses code and is unit-tested over a temporary folder tree. It is a cursor over one folder:
  - It lists `../` (except at the filesystem root), then subfolders, then `.pim` files, sorted with casefold. Hidden entries and other extensions are skipped.
  - Save mode adds a first row, "+ New file in this folder…".
  - A folder that cannot be read sets `error` instead of raising.
- **Same answer as typing.** Enter on a `.pim` file returns its absolute path, which goes through `Terminal._handle_line` exactly like a typed answer or a calendar answer. The dirty rule, overwrite confirmation, `.pim` check, and `~` expansion therefore stay where they were.
- **One helper for every path prompt.** `Terminal._ask_path(mode, handler)` backs `o`, bare `load`, `W`, bare `save as`, untitled `w`, and "save" in the dirty chooser. The browser starts in the Bound File's folder, else the working directory. `load <path>` with an argument never opens it.
- **Curses side:**
  - `_handle_browser_key` runs before the picker and chooser handlers.
  - The browser's state is part of the redraw snapshot.
  - The composer shows the highlighted path, clipped from the left (new `textwidth.clip_left`).
  - The overlay fits its contents (at least 10 rows, at most 20) and scrolls with `visible_list_window`.
- **Keys:**
  - Arrows / `j` `k`, `PgUp` `PgDn`, `Home` `End` / `g` `G` move.
  - Enter opens or picks; `⌫` / `←` go up; `→` opens.
  - `~` goes home.
  - `/` or Tab switch to the typed field, pre-filled with `/` or the current folder.
  - Esc cancels.
  - Ctrl-U (new, in the text field) clears everything before the caret.

---

## Outcome

1. `feat(view): add a folder browser widget for path prompts`
2. `feat(view): browse folders for the o and W path prompts`
3. `docs(PIM): record the folder browser for load and save-as paths`: ADR-0019 and the PRODUCT, ACCEPTANCE, SRS (new FR-38a), DESIGN, ARCHITECTURE, class diagram, USER, DEVELOPER, and REQUIREMENTS documents
4. `chore(PIM): point AGENTS.md at ADR-0019`
5. This record

`python -m unittest` passes, and `model/` line coverage stays at 100%. The model is unchanged.

---

## Manual check (macOS)

Checked in tmux, with `HOME` set to a temporary folder:

- **80×24:**
  - `o` → into `courses/` → Enter on `comp.pim` loads it; the status shows `Loaded <absolute path>`.
  - Create a Note → `W` → "+ New file in this folder…" → type `mywork` → Enter writes `mywork.pim` in the browsed folder.
- **60×12 (the minimum size):** the overlay fits, and a 25-folder list scrolls with `G` / `g`.

**Still to do by hand:** the same steps in Terminal.app on a real home folder before recording the demo.

---

## What this is not

- No GUI or Finder dialog, no `osascript`, no tkinter.
- No file previews, sizes, or dates in the list; no search, multi-select, delete, or rename in the browser.
- No change to the line UI, e2e scripts, or the ACCEPTANCE §6 demo, which still types `save as demo.pim`.
