"""Designed terminal UI: regions, wizards, in-process Alarm Alerts."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue

from controller.app import HELP
from model.pir import HKT, format_datetime
from view.stdin_reader import start_stdin_reader

MENU = (
    "create  search  clear  modify  print  print all  delete  "
    "save  save as  load  dismiss  help  quit"
)
YES = {"y", "yes"}
NO = {"n", "no"}
SAVE = {"save", "s"}
DISCARD = {"discard", "d"}
CANCEL = {"cancel", "c"}


class Terminal:
    def __init__(self, app, stdin=None, stdout=None, now=None):
        self.app = app
        self.stdin = stdin if stdin is not None else sys.stdin
        self.stdout = stdout if stdout is not None else sys.stdout
        self._now = now  # optional injected clock for tests
        self.queue: Queue = Queue()
        self.dismissed: set[tuple[int, int]] = set()
        self._prompts: list[tuple[str, object]] = []
        self._running = False
        self._last_snapshot = None

    def run(self):
        start_stdin_reader(self.queue, self.stdin)
        self._running = True
        self.app.status = "Enter help for commands."
        self._paint(force=True)
        while self._running:
            due_changed = self._paint(force=False)
            try:
                line = self.queue.get(timeout=0.5)
            except Empty:
                if due_changed:
                    continue
                continue
            if line is None:
                self._running = False
                break
            try:
                self._handle_line(line)
            except Exception:
                self.app.status = "command failed"
            self._paint(force=True)

    def _now_dt(self) -> datetime:
        if self._now is not None:
            return self._now() if callable(self._now) else self._now
        return datetime.now(HKT)

    def visible_due(self):
        return [item for item in self.app.due_alarms(self._now_dt()) if item.key() not in self.dismissed]

    def _snapshot(self):
        due = self.visible_due()
        return (
            self.app.pim.bound_path(),
            self.app.pim.is_dirty(),
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
        text = "\n".join(self._layout()) + "\n"
        if self.stdout.isatty():
            self.stdout.write("\033[2J\033[H")
        self.stdout.write(text)
        self.stdout.flush()

    def _prompt_label(self) -> str:
        if self._prompts:
            return self._prompts[-1][0]
        return "> "

    def ask(self, prompt: str, handler):
        self._prompts.append((prompt, handler))

    def _handle_line(self, line: str):
        if self._prompts:
            _prompt, handler = self._prompts.pop()
            handler(line)
            return
        self._handle_command(line)

    def _handle_command(self, line: str):
        raw = line.strip()
        if not raw:
            return
        lower = raw.casefold()
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
        if not self.app.pim.is_dirty():
            self._running = False
            return
        self.ask("unsaved changes: save / discard / cancel: ", self._on_quit_dirty)

    def _on_quit_dirty(self, line: str):
        choice = line.strip().casefold()
        if choice in CANCEL:
            self.app.status = "quit cancelled"
            return
        if choice in DISCARD:
            self._running = False
            return
        if choice in SAVE:
            if self.app.pim.bound_path():
                if self.app.save():
                    self._running = False
                return
            self.ask("path: ", lambda path: self._save_as(path.strip(), then_quit=True))
            return
        self.app.status = "enter save, discard, or cancel"
        self.ask("unsaved changes: save / discard / cancel: ", self._on_quit_dirty)

    def _save(self):
        if self.app.pim.bound_path():
            self.app.save()
            return
        self.ask("path: ", lambda path: self._save_as(path.strip()))

    def _save_as(self, path: str, then_quit=False, then=None):
        if not path:
            self.app.status = "path is required"
            return
        candidate = Path(path)
        if candidate.suffix.casefold() != ".pim":
            candidate = Path(str(candidate) + ".pim")
        bound = self.app.pim.bound_path()
        if candidate.exists() and (bound is None or Path(bound) != candidate):

            def confirm(answer: str):
                if answer.strip().casefold() in YES:
                    self._commit_save(str(candidate), then_quit, then)
                else:
                    self.app.status = "save as cancelled"

            self.ask(f"overwrite {candidate}? [y/n]: ", confirm)
            return
        self._commit_save(str(candidate), then_quit, then)

    def _commit_save(self, path: str, then_quit, then):
        if not self.app.save(path):
            return
        if then_quit:
            self._running = False
        if then:
            then()

    def _load(self, path: str):
        if not path:
            self.app.status = "path is required"
            return
        if self.app.pim.is_dirty():
            self.ask(
                "unsaved changes: save / discard / cancel: ",
                lambda answer: self._on_load_dirty(answer, path),
            )
            return
        self.app.load(path)

    def _on_load_dirty(self, line: str, path: str):
        choice = line.strip().casefold()
        if choice in CANCEL:
            self.app.status = "load cancelled"
            return
        if choice in DISCARD:
            self.app.load(path, force=True)
            return
        if choice in SAVE:
            if self.app.pim.bound_path():
                if self.app.save():
                    self.app.load(path)
                return
            self.ask("path: ", lambda dest: self._save_as(dest.strip(), then=lambda: self.app.load(path)))
            return
        self.app.status = "enter save, discard, or cancel"
        self.ask(
            "unsaved changes: save / discard / cancel: ",
            lambda answer: self._on_load_dirty(answer, path),
        )

    def _start_create(self, type_name: str | None):
        if not type_name:
            self.ask("type (note/task/event/contact): ", lambda value: self._start_create(value.strip().casefold()))
            return
        if type_name == "note":
            self.ask("text: ", lambda value: self.app.create_note(value))
        elif type_name == "task":
            data = {}

            def description(value):
                data["description"] = value
                self.ask("deadline (optional, empty skips): ", deadline)

            def deadline(value):
                self.app.create_task(data["description"], value.strip() or None)

            self.ask("description: ", description)
        elif type_name == "event":
            data = {}

            def description(value):
                data["description"] = value
                self.ask("start: ", start)

            def start(value):
                data["start"] = value
                self._collect_alarms([], lambda alarms: self.app.create_event(data["description"], data["start"], alarms))

            self.ask("description: ", description)
        elif type_name == "contact":
            data = {}

            def name(value):
                data["name"] = value
                self.ask("address (optional): ", address)

            def address(value):
                data["address"] = value.strip() or None
                self.ask("mobile (optional): ", mobile)

            def mobile(value):
                self.app.create_contact(data["name"], data["address"], value.strip() or None)

            self.ask("name: ", name)
        else:
            self.app.status = f"unknown PIR type: {type_name}"

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
            raw = value.strip()
            if raw == "0":
                alarms.append({"kind": "relative", "amount": 0, "unit": "minute"})
                self._collect_alarms(alarms, on_done)
                return
            self.ask("unit (minute/hour/day/week): ", lambda unit: unit_done(raw, unit))

        def unit_done(raw_amount, unit):
            alarms.append({"kind": "relative", "amount": raw_amount, "unit": unit.strip()})
            self._collect_alarms(alarms, on_done)

        def at(value: str):
            alarms.append({"kind": "absolute", "at": value.strip()})
            self._collect_alarms(alarms, on_done)

        self.ask("alarm kind (relative/absolute): ", kind)

    def _start_modify(self):
        pir = self.app.selected()
        if pir is None:
            self.app.status = "no PIR selected"
            return
        if pir.type_name == "note":
            self.ask(f"text [{pir.text}]: ", lambda value: self._modify({"text": value} if value != "" else {}))
        elif pir.type_name == "task":
            fields = {}

            def description(value):
                if value != "":
                    fields["description"] = value
                shown = format_datetime(pir.deadline) if pir.deadline else "none"
                self.ask(f"deadline [{shown}] (empty keeps, none clears): ", deadline)

            def deadline(value):
                if value != "":
                    fields["deadline"] = value
                self._modify(fields)

            self.ask(f"description [{pir.description}]: ", description)
        elif pir.type_name == "event":
            fields = {}

            def description(value):
                if value != "":
                    fields["description"] = value
                self.ask(f"start [{format_datetime(pir.start)}]: ", start)

            def start(value):
                if value != "":
                    fields["start"] = value
                self.ask("replace alarms? [y/n]: ", alarms_q)

            def alarms_q(value):
                answer = value.strip().casefold()
                if answer in NO or answer == "":
                    self._modify(fields)
                    return
                if answer in YES:
                    self._collect_alarms([], lambda alarms: self._modify({**fields, "alarms": alarms}))
                    return
                self.app.status = "enter y or n"
                self.ask("replace alarms? [y/n]: ", alarms_q)

            self.ask(f"description [{pir.description}]: ", description)
        elif pir.type_name == "contact":
            fields = {}

            def name(value):
                if value != "":
                    fields["name"] = value
                shown = pir.address or "none"
                self.ask(f"address [{shown}] (empty keeps, none clears): ", address)

            def address(value):
                if value != "":
                    fields["address"] = value
                shown = pir.mobile or "none"
                self.ask(f"mobile [{shown}] (empty keeps, none clears): ", mobile)

            def mobile(value):
                if value != "":
                    fields["mobile"] = value
                self._modify(fields)

            self.ask(f"name [{pir.name}]: ", name)

    def _modify(self, fields: dict):
        self.app.modify(fields)

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
        bound = self.app.pim.bound_path() or "untitled"
        dirty = "*" if self.app.pim.is_dirty() else ""
        title = f"PIM  {bound}{dirty}"
        due = self.visible_due()
        alarm_lines = ["ALARMS"]
        if due:
            for item in due:
                when = format_datetime(item.at)
                alarm_lines.append(
                    f"  {item.status:<7}  Id {item.event_id}  {item.description}  {when}"
                )
            alarm_lines.append("  (dismiss)")
        else:
            alarm_lines.append("  (none)")
        search = "search" if self.app.has_criterion() else "all"
        rows = [f"Current Result ({search})", "    #   Id  Type      Name                      Time"]
        selected_id = self.app.selected_id()
        result = self.app.current_result()
        if not result:
            rows.append("    (empty)")
        for index, pir in enumerate(result, 1):
            mark = ">" if pir.id == selected_id else " "
            name = pir.display_name.replace("\n", " ")
            if len(name) > 24:
                name = name[:21] + "..."
            time_text = format_datetime(pir.relevant_time()) if pir.relevant_time() else ""
            rows.append(f"{mark} {index:3d}  {pir.id:3d}  {pir.type_name:<8}  {name:<24}  {time_text}")
        detail = ["DETAIL"]
        selected = self.app.selected()
        if selected is None:
            detail.append("  (no selection)")
        else:
            for key, value in selected.detail_lines():
                detail.append(f"  {key}: {value}")
        if self.app.print_text:
            detail.append("PRINT")
            for line in self.app.print_text.splitlines():
                detail.append(f"  {line}")
        divider = "-" * 76
        return [
            title,
            divider,
            *alarm_lines,
            divider,
            *rows,
            divider,
            *detail,
            divider,
            self.app.status or "",
            MENU,
            self._prompt_label(),
        ]
