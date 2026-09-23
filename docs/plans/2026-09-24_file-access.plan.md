# Store and load: make the `.pim` file easy to export and import

**Status:** implemented on `fix/pim-file-access` (2026-09-24). This file is the design record plus what actually landed. US10 and US11 were already met; this pass fixes one path bug and makes the existing commands easier to find. It is not a new feature.

Appendix B, MVC, stdlib-only, and the command vocabulary (ADR-0016) stay locked. The keys are accelerators under ADR-0018.

---

## Why

A group member read US10/US11 as "export" (save to a folder the user picks) and "import" (open a `.pim` file) and could not find the import. A check showed:

- **Load had no key.** Save had `w`. Load was only reachable by pressing `:` and typing `load <path>`, and neither the footer nor the `?` overlay said so.
- **`~` was not expanded.** `save as ~/Desktop/work` created a folder literally named `~` under the working directory. This happened because the atomic write runs `mkdir(parents=True)` on the parent. `load ~/…` could not find the file.
- **The status echoed the path as typed**, e.g. `Saved work.pim`, so the user could not see which folder the file went to.

A Finder-style file dialog is out of scope. The brief asks for a command-line system, and AGENTS.md forbids a GUI, tkinter, and `osascript`. Typing the path at a prompt is the command-line counterpart of a file dialog. The documents now say so explicitly, so a marker does not read the missing dialog as a gap.

---

## Outcome

Three code commits, one docs commit, and this record:

1. **`fix(model): expand ~ in PIM File paths`**
   - `_named_path` in `model/pimfile.py` applies `os.path.expanduser`. It uses the `os.path` version rather than `Path.expanduser`, which raises on an unknown `~user`.
   - Every save, load, and overwrite check goes through `_named_path`, so the one change covers them all.
   - Unit tests patch `HOME`. `model/` coverage stays at 100%.
2. **`feat(view): add o (load) and W (save as) keys`**
   - `o` runs `load` and `W` runs `save as`. Both reuse the existing path prompt, the dirty save/discard/cancel rule, and the overwrite confirmation.
   - Prompts now read `save as path: ` or `load path: ` instead of a bare `path: `.
   - The idle footer lists `w save  o load`. `d dismiss` stays on the alarm banner and in `?`.
3. **`feat(controller): show the absolute path after save and load`**
   - `Saved …`, `Loaded …`, and `cannot save …` use `os.path.abspath`.
   - `bound_path()` and the title bar are unchanged.
4. **`docs(PIM): describe path forms and file keys for store and load`** updates:
   - `docs/PRODUCT.md` (Persistence, Interaction table)
   - `docs/ACCEPTANCE.md` (US10/US11)
   - `docs/deliverables/SRS.md` (FR-29, FR-34, FR-38)
   - `docs/deliverables/DESIGN.md`
   - `USER.md`
   - `REQUIREMENTS.md`

`python -m unittest` passes (298 tests), with `model/` line coverage at 100%.

---

## Manual check (macOS)

- **Line UI**, run with `PIM_NO_CURSES=1` and `HOME` redirected to a temporary folder: `save as ~/Desktop/pimtest`, then `load ~/Desktop/pimtest.pim` after discarding unsaved changes, then `load ~/x.json`, which was rejected. No `~` folder appeared.
- **Curses UI**, driven in a pseudo-terminal: the footer shows `o load`, `o` then a path loads the file, and `W` then a path writes a copy.
- **Still to do by hand** before recording the demo: the same `W` / `o` steps with `python pim.py` on a real Desktop.

---

## What this is not

This record adds none of the following:

- a file dialog;
- a `python pim.py <file>` start-up argument;
- recent-files history;
- any change to the PIM File format.

The ACCEPTANCE §6 demo is still typed as `save as demo.pim`.
