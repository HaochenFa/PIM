# Full-marks review against `Project Description.pdf`

Date: 2026-09-23 · Branch: `feat/tui` @ `ce68456`

## Verdict

**Not yet full marks.**

- **Code and model tests are close.** US1–US11 are implemented, 270 tests pass, `model/` line coverage is 100%, and only the standard library is used.
- **Four reproducible crash paths** break the "reliability / error handling" rubric item and ACCEPTANCE §3 ("invalid input does not crash").
- **About 15 of the 25 points** come from documents and recordings that are not in the repository yet.

## Status by brief item

| Brief item (points) | Status | Gap |
|---|---|---|
| 1 SRS (6) | ❌ missing | No SRS in DOC/DOCX/PDF. `docs/PRODUCT.md` is input for it, not the SRS itself. |
| 2 Design document (5) | ❌ missing | Needs an architecture diagram, class diagrams (fields and public methods with return type, argument names and types, exceptions), and a sequence or activity diagram of *search then update*. Each diagram needs explanatory text. `docs/ARCHITECTURE.md` has only one mermaid sequence diagram. |
| 3a Source code | ⚠️ | See **A. Crash paths** below. |
| 3b Developer manual | ⚠️ | Markdown only (the brief requires DOC/DOCX/PDF). Names no specific IDE ("any IDE"). Uses `python`, which does not exist on stock macOS; use `python3`. |
| 3c User manual | ⚠️ | Markdown only. Good content. |
| 3d Video ≤4 min MP4 | ❌ missing | Script exists in ACCEPTANCE §6. |
| 3e Requirements coverage report | ⚠️ | `REQUIREMENTS.md` has no SRS requirement-id column. The brief requires stories **and** SRS requirements. Also Markdown only. |
| 4 Unit tests + coverage (4) | ⚠️ | Coverage is fine. **None of the 214 unit tests has a docstring.** The model test files have almost no comments (0 / 0 / 2 / 0 / 0 lines in `test_{pim,pir,search,persist,alarms}.py`); only the test names describe behaviour. The brief says each test should "clearly state the functionalities it exercises (e.g., using comments)". |
| 5 Presentation PDF + ≤5 min MP4 (4) | ❌ missing | Must cover: create-PIR requirement, criterion requirement, search requirement, the MVC design, and one lesson learned. Every member shows face and student ID. |
| Honour Declaration | ❌ missing | Up to a 30% penalty. Must acknowledge GenAI use; `AGENTS.md` and `docs/plans/` make that use evident. |

## A. Crash paths (traceback + process exit)

All four reproduce through `Terminal.run()` in the line UI. They also affect the curses UI: `view/curses_ui.py` `_safe` catches only `PIMError` and `OSError`.

**This is worse than a single failed command.** Both loops call `_paint`, which calls `due_alarms`, *outside* any `try` (`view/terminal.py:113`, `view/curses_ui.py:120`). So one bad Event kills the app on the next tick. A `.pim` file holding such an Event loads "successfully" and then makes the app unusable.

| # | Repro | Exception | Fix point |
|---|---|---|---|
| A1 | `create event` → relative alarm, amount `999999999`, unit `week` | `OverflowError` | `model/pir.py:180` `RelativeAlarm.effective`. The Event is already inserted when the crash happens, so the collection is mutated. |
| A2 | `create event` with start `0001-01-01 00:10`, relative alarm `1 day` | `OverflowError` | Same function. It also crashes `search alarm < …`. |
| A3 | `load` a `.pim` file containing `"alarms": 5` | `TypeError` | `model/pir.py:402`. `alarms` must be a list. |
| A4 | `load` a non-UTF-8 `.pim` file | `UnicodeDecodeError` | `model/pimfile.py:74` catches only `JSONDecodeError`/`OSError`. Add `UnicodeDecodeError` → `FileFormatError`. |

Suggested fix, keeping it testable through `PIM`:

1. In the model, compute effective alarm times when an Event is created or modified, and turn `OverflowError` into `ValidationError`. The command then fails atomically.
2. Validate the type of `alarms`.
3. Catch `UnicodeDecodeError` in `read_pim_file`.
4. As a safety net only, add `except Exception` to both loops, so the unreachable `"command failed"` fallback in `controller/errors.py:12` can actually run.
5. Add unit tests for each repro.

## B. Minor model hygiene

- `PIM.save("")` writes a file literally named `..pim` in the current directory. A blank path should be a `ValidationError`.
- `save .pim` writes `.pim.pim`, because `Path(".pim").suffix == ""`.
- `pir_from_json` accepts `"id": -3`, and `"id": 1.7` becomes 1.
- A relative alarm `amount` of `1.9` or `true` is silently truncated to `1` (`model/pir.py:165`).
- The docstring of `App.save` (`controller/app.py:231`) says "False on … OS failure", but the method catches only `PIMError`. The View rescues the `OSError`, and the status line then shows a raw errno with the temp-file name (`[Errno 1] … /.pim-xxxx.tmp`).
- Public model methods have no parameter type hints (`create_note(self, text)`, `modify(self, pir_id, fields)`). The design document must state argument types, so the code and the document should agree.

## C. Risks to mitigate in documents (no code change)

- **US8 wording.** The brief says "print … all PIRs", but `print all` prints Current Result (a locked decision). State this explicitly in the SRS, and run `clear` before `print all` in the demo so a literal-minded grader sees every PIR.
- **Optional Task deadline / 0 Event alarms.** The brief says tasks "with … deadlines" and events "with … alarms". Justify the optional fields in the SRS.
- **Coverage method.** `coverage.txt` comes from a custom `trace`-based counter that excludes `__init__.py` and counts AST "countable" lines. Say so in the report, so that "100%" is not challenged if a grader runs `coverage.py`.
- **Platform.** `ZoneInfo("Asia/Hong_Kong")` runs when `model` is imported (`model/pir.py:13`). On a machine without a system tz database (e.g. Windows without `tzdata`), the app cannot start. This is acceptable under the one-platform rule, but the developer manual should say "macOS only".
- **Document format.** Ship PDF (or DOCX) renderings of `DEVELOPER.md`, `USER.md`, `REQUIREMENTS.md`, and ideally `coverage.txt`. Keep the `.md` files in the source tree.

## Priority order

1. Fix A1–A4 and add their tests (code-quality rubric).
2. Write the SRS with requirement ids, then add those ids to `REQUIREMENTS.md`.
3. Write the design document (three diagram kinds plus the method tables).
4. Add one-line docstrings to the model unit tests (`tests/unit/test_{pim,pir,search,persist,alarms}.py`).
5. Produce the PDF manuals, video, presentation, and Honour Declaration.

## Resolution (2026-09-23, same branch)

Fixed in code, each with tests (unit, plus e2e where user-visible):

| Item | Commit | Result |
|---|---|---|
| A1, A2 | `fix(model): reject relative alarms whose time is out of range` | Event checks every Effective Alarm Time on create, modify, and load: `alarm time is out of range`. |
| A3, A4 | `fix(model): reject non-list alarms and non-UTF-8 PIM files` | `alarms must be a list`; `file is not UTF-8 text`; memory unchanged. |
| Safety net | `fix(view): show unexpected command failures on the status line` | Both loops catch `Exception` per command and show `command failed`; `_paint` stays unwrapped on purpose. |
| B: `..pim`, `.pim.pim`, ids, amounts | `fix(model): tighten file names, ids, alarm amounts, and datetime range` | `file name is required`; ids and next_id must be positive ints; 1.9 and `true` rejected. Also `datetime out of range` for instants that overflow HKT (found while planning). |
| B: `App.save` OSError | `fix(controller): report save OS failures without temp-file names` | `cannot save <target>.pim: <reason>`. |
| B: type hints | `refactor(model): …`, `refactor(controller): …` | Public model and App signatures annotated; design tables match. |
| Test docstrings | `test(model): state the behaviour each unit test exercises` | Every model test class and method has a one-line docstring. |
| Manuals | `docs(PIM): name python3, VS Code, and macOS-only in the manuals` | python3 everywhere; VS Code named; debug section; macOS only; coverage method in `coverage.txt`; error table in `USER.md`. |
| SRS, coverage report | `docs(PIM): add SRS draft and map requirement ids in REQUIREMENTS.md` | `docs/deliverables/SRS.md` (FR-1..42, NFR-1..10); `REQUIREMENTS.md` maps stories to SRS ids. |
| Design document | `docs(PIM): add design document draft with diagrams` | `docs/deliverables/DESIGN.md` + mermaid diagrams. |
| PDFs | `chore(docs): add PDF build script and ignore dist/` | `sh docs/deliverables/build.sh` → `dist/*.pdf`. |

Still open (group deliverables, not code):

- Review and finalise the SRS and design drafts (names, student ids, and wording are the group's).
- System video (≤4 min MP4): run `clear` before `print all` so every PIR is shown.
- Presentation PDF + recording (≤5 min, each member ≥1 min with face and student ID).
- Honour Declaration at the ZIP root, acknowledging GenAI use and the contribution split.
- ZIP assembly: put `REQUIREMENTS.pdf` and `coverage.pdf` next to the source at the source root; SRS, design, and manual PDFs at the ZIP root.
