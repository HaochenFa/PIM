"""Designed terminal UI: regions, field-driven wizards, in-process Alarm Alerts.

On a TTY this View runs a stdlib curses session. Tests and redirected
stdio keep the line-oriented fallback so stdin/stdout can be injected.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from queue import Empty, Queue

from controller.app import HELP
from controller.errors import message_for
from model import AbsoluteAlarm, PIMError, RelativeAlarm
from model.pir import KIND_ALARMS, HKT, pir_class
from view.keys import (
    CREATE,
    DELETE,
    DISMISS,
    HELP as KEY_HELP,
    MODIFY,
    PRINT,
    PRINT_ACTIONS,
    PRINT_ALL,
    QUIT,
    SAVE as KEY_SAVE,
    SEARCH,
    SELECT_DOWN,
    SELECT_FIRST,
    SELECT_LAST,
    SELECT_PAGE_DOWN,
    SELECT_PAGE_UP,
    SELECT_UP,
)
from view.layout import MENU, Screen, build_screen, text_lines
from view.stdin_reader import start_stdin_reader

YES = {"y", "yes"}
NO = {"n", "no"}
SAVE = {"save", "s"}
DISCARD = {"discard", "d"}
CANCEL = {"cancel", "c"}
DIRTY_QUIT = "dirty-quit"
DIRTY_LOAD = "dirty-load"


class Terminal:
    """Designed terminal: regions, field-driven wizards, in-process Alarm Alerts."""

    def __init__(self, app, stdin=None, stdout=None, now=None):
        """`now` is injected for tests; omitted means Hong Kong Time wall clock in the View only."""
        self.app = app
        self.stdin = stdin if stdin is not None else sys.stdin
        self.stdout = stdout if stdout is not None else sys.stdout
        self._now = now
        self.queue: Queue = Queue()
        self.dismissed: set[tuple[int, int]] = set()
        self._prompts: list[tuple[str, object, str | None]] = []
        self._running = False
        self._last_snapshot = None
        self.page_size = 10

    def _use_curses(self) -> bool:
        """True when both streams are TTYs, curses imports, and PIM_NO_CURSES is unset."""
        flag = os.environ.get("PIM_NO_CURSES", "").strip().casefold()
        if flag and flag not in {"0", "false", "no"}:
            return False
        try:
            if not self.stdin.isatty() or not self.stdout.isatty():
                return False
        except Exception:
            return False
        try:
            import curses  # noqa: F401
        except ImportError:
            return False
        return True

    def run(self):
        """Event loop. TTY uses curses; otherwise a stdin-reader thread + 500ms tick."""
        if self._use_curses():
            try:
                import curses

                from view.curses_ui import run_curses

                run_curses(self)
                return
            except (curses.error, ImportError, OSError):
                pass
        self._run_line_loop()

    def _run_line_loop(self):
        """Daemon stdin thread + Queue.get(timeout=0.5). Only this thread calls the model."""
        start_stdin_reader(self.queue, self.stdin)
        self._running = True
        self.app.status = "Enter help for commands."
        self._paint(force=True)
        while self._running:
            self._paint(force=False)
            try:
                try:
                    line = self.queue.get(timeout=0.5)
                except Empty:
                    continue
                if line is None:
                    self._handle_eof()
                    if not self._running:
                        break
                    self._paint(force=True)
                    continue
                try:
                    self._handle_line(line)
                except PIMError as exc:
                    self.app.status = message_for(exc)
                except OSError as exc:
                    self.app.status = message_for(exc)
                self._paint(force=True)
            except KeyboardInterrupt:
                # SIGINT is quit, not a silent drop of unsaved changes.
                self._handle_interrupt()
                if not self._running:
                    break
                self._paint(force=True)

    def _now_dt(self) -> datetime:
        if self._now is not None:
            return self._now() if callable(self._now) else self._now
        return datetime.now(HKT)

    def visible_due(self):
        """Due alarms minus those dismissed in this process."""
        return [item for item in self.app.due_alarms(self._now_dt()) if item.key() not in self.dismissed]

    def _snapshot(self):
        due = self.visible_due()
        return (
            self.app.bound_path(),
            self.app.is_dirty(),
            tuple((item.event_id, item.alarm_index, item.status, item.at.isoformat()) for item in due),
            tuple(sorted(self.dismissed)),
            tuple(pir.id for pir in self.app.current_result()),
            self.app.selected_id(),
            self.app.status,
            self.app.print_text,
            self._prompt_label(),
            self.app.has_criterion(),
        )

    def _paint(self, force: bool) -> bool:
        snap = self._snapshot()
        changed = snap != self._last_snapshot
        if force or changed:
            self.render()
            self._last_snapshot = snap
        return changed

    def render(self):
        """Clear and redraw regions. On a TTY the cursor stays on the prompt line."""
        lines = self._layout()
        body = "\n".join(lines[:-1])
        prompt = lines[-1] if lines else "> "
        if self.stdout.isatty():
            self.stdout.write("\033[2J\033[H")
            # Prompt is the last characters so typed input sits on that line.
            self.stdout.write(body + "\n" + prompt)
        else:
            self.stdout.write(body + "\n" + prompt + "\n")
        self.stdout.flush()

    def screen(self) -> Screen:
        """Build the shared screen model from the App and the current prompt."""
        return build_screen(
            bound_path=self.app.bound_path(),
            dirty=self.app.is_dirty(),
            due=self.visible_due(),
            result=self.app.current_result(),
            selected_id=self.app.selected_id(),
            selected=self.app.selected(),
            has_criterion=self.app.has_criterion(),
            print_text=self.app.print_text,
            status=self.app.status or "",
            prompt=self._prompt_label(),
        )

    def apply_accelerator(self, action: str) -> None:
        """Run an empty-prompt key action. Unknown names are ignored."""
        if action not in PRINT_ACTIONS:
            self.app.clear_print()
        if action == SELECT_UP:
            self._move_selection(-1)
        elif action == SELECT_DOWN:
            self._move_selection(1)
        elif action == SELECT_PAGE_UP:
            self._move_selection(-self.page_size)
        elif action == SELECT_PAGE_DOWN:
            self._move_selection(self.page_size)
        elif action == SELECT_FIRST:
            self._select_index(0)
        elif action == SELECT_LAST:
            self._select_index(len(self.app.current_result()) - 1)
        elif action == SEARCH:
            self._handle_command("search")
        elif action == CREATE:
            self._start_create(None)
        elif action == MODIFY:
            self._start_modify()
        elif action == PRINT:
            self.app.print_selected()
        elif action == PRINT_ALL:
            self.app.print_all()
        elif action == DELETE:
            self._start_delete()
        elif action == DISMISS:
            self._dismiss()
        elif action == KEY_SAVE:
            self._save()
        elif action == KEY_HELP:
            self.app.status = HELP
        elif action == QUIT:
            self._quit()

    def cancel_prompt(self) -> None:
        """Esc: drop the current wizard, but not a dirty save/discard/cancel prompt."""
        if self._is_dirty_prompt():
            self.app.status = "enter save, discard, or cancel"
            return
        if self._prompts:
            self._prompts.clear()
            self.app.status = "command cancelled"

    def _selected_index(self) -> int | None:
        selected_id = self.app.selected_id()
        if selected_id is None:
            return None
        for index, pir in enumerate(self.app.current_result()):
            if pir.id == selected_id:
                return index
        return None

    def _select_index(self, index: int) -> None:
        result = self.app.current_result()
        if not result:
            self.app.status = "Current Result is empty"
            return
        index = max(0, min(len(result) - 1, index))
        self.app.select_row(str(index + 1))

    def _move_selection(self, delta: int) -> None:
        result = self.app.current_result()
        if not result:
            self.app.status = "Current Result is empty"
            return
        current = self._selected_index()
        if current is None:
            self._select_index(0 if delta > 0 else len(result) - 1)
            return
        self._select_index(current + delta)

    def _prompt_label(self) -> str:
        if self._prompts:
            return self._prompts[-1][0]
        return "> "

    def _dirty_kind(self) -> str | None:
        if not self._prompts:
            return None
        return self._prompts[-1][2]

    def _is_dirty_prompt(self) -> bool:
        return self._dirty_kind() in {DIRTY_QUIT, DIRTY_LOAD}

    def ask(self, prompt: str, handler, kind: str | None = None):
        """Push a one-line prompt. `kind` marks dirty save/discard/cancel prompts."""
        self._prompts.append((prompt, handler, kind))

    def _handle_line(self, line: str):
        if self._prompts:
            _prompt, handler, _kind = self._prompts.pop()
            handler(line)
            return
        self._handle_command(line)

    def _handle_interrupt(self):
        if self._is_dirty_prompt():
            self.app.status = "enter save, discard, or cancel"
            return
        self._quit()

    def _handle_eof(self):
        if self._is_dirty_prompt():
            self._eof_on_dirty_prompt()
            return
        if self._prompts:
            self._prompts.clear()
            self.app.status = "command cancelled"
        self._quit()
        if self._is_dirty_prompt() and not self.stdin.isatty():
            self._eof_on_dirty_prompt()

    def _eof_on_dirty_prompt(self):
        if self.stdin.isatty():
            self.app.status = "enter save, discard, or cancel"
            return
        if self._dirty_kind() == DIRTY_LOAD:
            self.app.status = "load cancelled: unsaved changes require save, discard, or cancel"
        else:
            self.app.status = "unsaved changes; cannot quit without save, discard, or cancel"
        self._running = False

    def _handle_command(self, line: str):
        raw = line.strip()
        if not raw:
            return
        lower = raw.casefold()
        if lower not in {"print", "print all"}:
            self.app.clear_print()
        if lower in {"quit", "q", "exit"}:
            self._quit()
        elif lower == "help":
            self.app.status = HELP
        elif lower == "clear":
            self.app.clear_search()
        elif lower == "dismiss":
            self._dismiss()
        elif lower == "modify":
            self._start_modify()
        elif lower == "delete":
            self._start_delete()
        elif lower == "print":
            self.app.print_selected()
        elif lower == "print all":
            self.app.print_all()
        elif lower == "save":
            self._save()
        elif lower == "save as" or lower.startswith("save as "):
            path = raw[7:].strip()
            if path:
                self._save_as(path)
            else:
                self.ask("path: ", lambda value: self._save_as(value.strip()))
        elif lower == "load" or lower.startswith("load "):
            path = raw[4:].strip()
            if path:
                self._load(path)
            else:
                self.ask("path: ", lambda value: self._load(value.strip()))
        elif lower == "create" or lower.startswith("create "):
            type_name = raw[6:].strip().casefold()
            self._start_create(type_name or None)
        elif lower == "search" or lower.startswith("search "):
            rest = raw[6:].strip()
            if rest:
                self.app.search(rest)
            else:
                self.ask("criterion: ", lambda value: self.app.search(value))
        elif lower.startswith("id "):
            self.app.select_id(raw[3:].strip())
        elif raw.isdigit():
            self.app.select_row(raw)
        else:
            self.app.status = f"unknown command: {raw}"

    def _dismiss(self):
        due = self.visible_due()
        if not due:
            self.app.status = "no alarm to dismiss"
            return
        first = due[0]
        self.dismissed.add(first.key())
        self.app.status = f"Dismissed alarm on Id {first.event_id}"

    def _quit(self):
        if not self.app.is_dirty():
            self._running = False
            return
        self._ask_dirty(
            on_save=lambda: setattr(self, "_running", False),
            on_discard=lambda: setattr(self, "_running", False),
            on_cancel=lambda: setattr(self.app, "status", "quit cancelled"),
            kind=DIRTY_QUIT,
        )

    def _ask_dirty(self, on_save, on_discard, on_cancel, kind):
        def handler(line: str):
            choice = line.strip().casefold()
            if choice in CANCEL:
                on_cancel()
                return
            if choice in DISCARD:
                on_discard()
                return
            if choice in SAVE:
                if self.app.bound_path():
                    if self.app.save():
                        on_save()
                    return
                self.ask("path: ", lambda path: self._save_as(path.strip(), then=on_save))
                return
            self.app.status = "enter save, discard, or cancel"
            self._ask_dirty(on_save, on_discard, on_cancel, kind)

        self.ask("unsaved changes: save / discard / cancel: ", handler, kind)

    def _save(self):
        if self.app.bound_path():
            self.app.save()
            return
        self.ask("path: ", lambda path: self._save_as(path.strip()))

    def _save_as(self, path: str, then=None):
        if not path:
            self.app.status = "path is required"
            return
        if self.app.would_overwrite(path):

            def confirm(answer: str):
                if answer.strip().casefold() in YES:
                    self._commit_save(path, then)
                else:
                    self.app.status = "save as cancelled"

            self.ask(f"overwrite {self.app.save_target(path)}? [y/n]: ", confirm)
            return
        self._commit_save(path, then)

    def _commit_save(self, path: str, then):
        if not self.app.save(path):
            return
        if then:
            then()

    def _load(self, path: str):
        if not path:
            self.app.status = "path is required"
            return
        if self.app.is_dirty():
            self._ask_dirty(
                on_save=lambda: self._commit_load(path, force=False),
                on_discard=lambda: self._commit_load(path, force=True),
                on_cancel=lambda: setattr(self.app, "status", "load cancelled"),
                kind=DIRTY_LOAD,
            )
            return
        self._commit_load(path, force=False)

    def _commit_load(self, path: str, force: bool = False) -> None:
        if self.app.load(path, force=force):
            # Ids are unique only inside one collection; a loaded file may reuse them.
            self.dismissed.clear()

    def _start_create(self, type_name: str | None):
        if not type_name:
            self.ask("type (note/task/event/contact): ", lambda value: self._start_create(value.strip().casefold()))
            return
        cls = pir_class(type_name)
        if cls is None:
            self.app.status = f"unknown PIR type: {type_name}"
            return
        self._prompt_fields(cls.FIELDS, None, lambda fields: self.app.create(type_name, fields))

    def _start_modify(self):
        pir = self.app.selected()
        if pir is None:
            self.app.status = "no PIR selected"
            return

        def on_done(fields):
            updated = self.app.modify(fields)
            if updated is not None and updated is not pir and "alarms" in fields:
                self._forget_dismissed(pir.id)

        self._prompt_fields(type(pir).FIELDS, pir, on_done)

    def _forget_dismissed(self, event_id: int) -> None:
        self.dismissed = {key for key in self.dismissed if key[0] != event_id}

    def _field_prompt(self, spec, existing) -> str:
        if existing is None:
            extra = "" if spec.required else " (optional, empty skips)"
            return f"{spec.label}{extra}: "
        current = existing.display_field(spec.key)
        if spec.required:
            return f"{spec.label} [{current}]: "
        return f"{spec.label} [{current}] (empty keeps, none clears): "

    def _prompt_fields(self, specs, existing, on_done):
        pending = list(specs)
        fields = {}

        def next_field():
            if not pending:
                on_done(fields)
                return
            spec = pending.pop(0)
            if spec.kind == KIND_ALARMS:
                self._prompt_alarms(existing, fields, next_field)
                return
            self.ask(self._field_prompt(spec, existing), lambda line, spec=spec: got_value(spec, line))

        def got_value(spec, line):
            if existing is not None:
                if line == "":
                    next_field()
                    return
                fields[spec.key] = line
                next_field()
                return
            if spec.required:
                fields[spec.key] = line
            elif line.strip():
                fields[spec.key] = line.strip()
            next_field()

        next_field()

    def _prompt_alarms(self, existing, fields, then):
        def capture(alarms):
            fields["alarms"] = alarms
            then()

        if existing is None:
            self._collect_alarms([], capture)
            return

        def question(value: str):
            answer = value.strip().casefold()
            if answer in NO or answer == "":
                then()
                return
            if answer in YES:
                self._collect_alarms([], capture)
                return
            self.app.status = "enter y or n"
            self.ask("replace alarms? [y/n]: ", question)

        self.ask("replace alarms? [y/n]: ", question)

    def _collect_alarms(self, alarms: list, on_done):
        def more(value: str):
            answer = value.strip().casefold()
            if answer in NO or answer == "":
                on_done(alarms)
                return
            if answer in YES:
                self._one_alarm(alarms, on_done)
                return
            self.app.status = "enter y or n"
            self._collect_alarms(alarms, on_done)

        self.ask("add an alarm? [y/n]: ", more)

    def _one_alarm(self, alarms: list, on_done):
        def kind(value: str):
            answer = value.strip().casefold()
            if answer in {"relative", "r"}:
                self.ask("amount (0 = at start): ", amount)
            elif answer in {"absolute", "a"}:
                self.ask("at: ", at)
            else:
                self.app.status = "enter relative or absolute"
                self._one_alarm(alarms, on_done)

        def amount(value: str):
            try:
                count = int(value.strip())
            except (TypeError, ValueError):
                self.app.status = "relative alarm amount must be an integer"
                self._one_alarm(alarms, on_done)
                return
            if count < 0:
                self.app.status = "relative alarm cannot be after start"
                self._one_alarm(alarms, on_done)
                return
            if count == 0:
                alarms.append(RelativeAlarm(0, "minute"))
                self._collect_alarms(alarms, on_done)
                return
            self.ask("unit (minute/hour/day/week): ", lambda unit: unit_done(count, unit))

        def unit_done(count, unit):
            try:
                alarms.append(RelativeAlarm(count, unit.strip()))
            except PIMError as exc:
                self.app.status = message_for(exc)
                self._one_alarm(alarms, on_done)
                return
            self._collect_alarms(alarms, on_done)

        def at(value: str):
            try:
                alarms.append(AbsoluteAlarm(value.strip()))
            except PIMError as exc:
                self.app.status = message_for(exc)
                self._one_alarm(alarms, on_done)
                return
            self._collect_alarms(alarms, on_done)

        self.ask("alarm kind (relative/absolute): ", kind)

    def _start_delete(self):
        pir = self.app.selected()
        if pir is None:
            self.app.status = "no PIR selected"
            return

        def confirm(value: str):
            if value.strip().casefold() in YES:
                self.app.delete_selected()
            else:
                self.app.status = "delete cancelled"

        self.ask(f"delete Id {pir.id} {pir.type_name} {pir.display_name!r}? [y/n]: ", confirm)

    def _layout(self) -> list[str]:
        """Text fallback: one region per line, prompt last."""
        return text_lines(self.screen())
