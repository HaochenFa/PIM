# Backlog

What is still open before submission (20:00, 20 November 2026), and a short log of what has landed. This file replaces the dated plans that used to be in `docs/plans/`; git history and the merged pull requests keep their full text. Design decisions are in `docs/deliverables/DESIGN.md` §6.

This is not a feature wishlist. Appendix B plus the HCI in `docs/PRODUCT.md` is the whole product (`AGENTS.md`, "Non-negotiable scope"), so nothing here adds a feature.

## Open: course deliverables

These belong to the group. An agent must not claim them as done.

| Item | Brief | What is left |
|---|---|---|
| SRS | 1 (6 pts) | Group review of `docs/deliverables/SRS.md`. Add group number, member names, and student ids, then drop "draft" from the title page. |
| Design document | 2 (5 pts) | Group review of `docs/deliverables/DESIGN.md`, same title-page edits. |
| PDF build | 1, 2, 3 | `sh docs/deliverables/build.sh` renders every document and diagram to `dist/`. Rebuild after the last edit to any Markdown source. |
| System video | 3d | MP4, at most 4 minutes, following `docs/ACCEPTANCE.md` §6. Run `clear` before `print all` so every PIR is shown (SRS FR-25). |
| Presentation | 5 (4 pts) | Slides as PDF and a recording as MP4, at most 5 minutes. Every member presents at least 1 minute with face and student ID card visible. Content: one create-a-PIR requirement, one criterion requirement, one search requirement, the MVC design (DESIGN §2–3), and one lesson learned. |
| Honour Declaration | required | At the ZIP root. Acknowledge GenAI use honestly (this repository's `AGENTS.md` and history show it) and state the agreed contribution split. Missing or false: up to 30 % penalty. |
| ZIP | all | One archive. SRS, design, and manual PDFs at the root; `REQUIREMENTS.md`/`.pdf` and `coverage.txt`/`coverage.pdf` in the source root next to `pim.py`; the Honour Declaration at the ZIP root. |

## Open: checks by hand

- **Folder browser in Terminal.app** (macOS, real home folder, `python3 pim.py`). Automated tests and a tmux run cover the same steps with a temporary `HOME`.
  1. `c` → create a Note → `W` → "+ New file in this folder…" → type `pimtest` → Enter. The status line reads `Saved /Users/<you>/…/pimtest.pim`.
  2. `q` quits without asking, because nothing is unsaved. Relaunch, press `o`, and open `pimtest.pim`. The Note is back, and the status line reads `Loaded …`.
  3. `o`, then `/`, then type `~/x.json` and Enter: `path must have a .pim extension`.
  4. Create a Note so the collection is dirty, then `o`: save / discard / cancel appears first.
  5. `W` → `~` goes home; `⌫` goes up and highlights the folder you came from; Esc cancels and changes nothing.
  6. Confirm no folder named `~` was created anywhere, then delete the test file.
- **Demo script** `docs/ACCEPTANCE.md` §6 once end to end on the recording machine.

## Known UI gaps (accepted, not scheduled)

These do not break a requirement. Fix only if time allows; each must keep `python3 -m unittest` green.

- **Two Esc presses after typing in the browser.** After `/` or Tab switches the folder browser to the typed field, the first Esc clears the pre-filled text and the second cancels the prompt. Cause: `CursesUI._escape` clears a non-empty buffer before it cancels the prompt.
- **Wizard field titles.** Only search has a titled field (`Search — one criterion`). The other fields show the prompt label itself, for example `deadline [current] (empty keeps, none clears):`.
- **Calendar time list.** With focus on the time list, keys the picker does not use are ignored rather than passed on.

## Done

| Date | Work | Where |
|---|---|---|
| 2026-09-11 | Foundation: `model` / `view` / `controller` / `pim.py`, US1–US11, line interface, in-process Alarm Alerts, `coverage_report.py` | PR #1 (`ef7e800`) |
| 2026-09-11 | Unit, integration, and e2e layers; 100 % `model/` coverage; `hooks/pre-commit` gate (ADR-0017) | PR #2 (`7618f78`) |
| 2026-09-11 – 09-12 | `curses` interface (ADR-0018): panes, selectors, calendar, colour theme, search retry, idle Esc clears the filter | PR #3 (`d99c01b`) |
| 2026-09-23 | Full-marks audit against the brief. Fixed four crash paths (out-of-range alarms, non-list alarms, non-UTF-8 files, uncaught errors), blank and `.pim`-only file names, id and amount checks, OS save errors, type hints, test docstrings. Added the SRS, design document, and PDF build. | PR #3 (`d99c01b`) |
| 2026-09-24 | `~` expanded in PIM File paths; `o` load and `W` save as keys; absolute path in the save and load status | PR #4 (`de9640a`) |
| 2026-09-24 | Folder browser for load and save-as paths (ADR-0019) | PR #5 (`7f7597f`) |
| 2026-09-24 | Folded `docs/adr/` into DESIGN §6 and `docs/plans/` into this file; refreshed the deliverables | this change |
