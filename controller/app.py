"""One completed user action → model.PIM. Holds Current Result and selection."""

from __future__ import annotations

from pathlib import Path

from controller.errors import message_for
from model import PIM, PIMError, ValidationError, parse_criterion
from model.pimfile import append_pim_extension


def format_pir(pir) -> str:
    return "\n".join(f"{key}: {value}" for key, value in pir.detail_lines())


_CREATE = {
    "note": lambda pim, fields: pim.create_note(fields.get("text")),
    "task": lambda pim, fields: pim.create_task(fields.get("description"), fields.get("deadline")),
    "event": lambda pim, fields: pim.create_event(
        fields.get("description"), fields.get("start"), fields.get("alarms")
    ),
    "contact": lambda pim, fields: pim.create_contact(
        fields.get("name"), fields.get("address"), fields.get("mobile")
    ),
}


class App:
    def __init__(self, pim: PIM):
        self.pim = pim
        self._criterion = None
        self._result = []
        self._selected_id = None
        self.status = ""
        self.print_text = ""
        self._refresh()

    def bound_path(self):
        return self.pim.bound_path()

    def is_dirty(self) -> bool:
        return self.pim.is_dirty()

    def save_target(self, path) -> str:
        return str(append_pim_extension(path))

    def would_overwrite(self, path) -> bool:
        target = Path(self.save_target(path))
        bound = self.pim.bound_path()
        if not target.exists():
            return False
        if bound is None:
            return True
        try:
            return target.resolve() != Path(bound).resolve()
        except OSError:
            return str(target) != str(bound)

    def clear_print(self):
        self.print_text = ""

    def current_result(self):
        return list(self._result)

    def selected(self):
        if self._selected_id is None:
            return None
        try:
            return self.pim.get(self._selected_id)
        except PIMError:
            self._selected_id = None
            return None

    def selected_id(self):
        pir = self.selected()
        return None if pir is None else pir.id

    def has_criterion(self) -> bool:
        return self._criterion is not None

    def due_alarms(self, now):
        return self.pim.due_alarms(now)

    def create(self, type_name, fields):
        factory = _CREATE.get(type_name)
        if factory is None:
            self.status = f"unknown PIR type: {type_name}"
            return None
        return self._create(lambda: factory(self.pim, fields), type_name.capitalize())

    def modify(self, fields):
        pir = self.selected()
        if pir is None:
            self.status = "no PIR selected"
            return None
        if not fields:
            self.status = "No changes"
            return pir
        try:
            updated = self.pim.modify(pir.id, fields)
        except PIMError as exc:
            self.status = message_for(exc)
            return None
        if updated is pir:
            self.status = "No changes"
            return pir
        self._refresh()
        self.status = f"Modified Id {updated.id}"
        return updated

    def delete_selected(self):
        pir = self.selected()
        if pir is None:
            self.status = "no PIR selected"
            return False
        try:
            self.pim.delete(pir.id)
        except PIMError as exc:
            self.status = message_for(exc)
            return False
        self._selected_id = None
        self._refresh()
        self.status = f"Deleted Id {pir.id}"
        return True

    def search(self, line: str):
        try:
            criterion = parse_criterion(line)
            hits = self.pim.search(criterion)
        except PIMError as exc:
            self.status = message_for(exc)
            return
        self._criterion = criterion
        self._result = hits
        self._selected_id = None
        self.status = f"{len(hits)} match(es)"

    def clear_search(self):
        self._criterion = None
        self._refresh()
        self.status = "Search cleared"

    def select_row(self, number):
        try:
            index = int(number)
        except (TypeError, ValueError):
            self.status = "row number must be an integer"
            return
        if index < 1 or index > len(self._result):
            self.status = f"no row {index} in Current Result"
            return
        self._selected_id = self._result[index - 1].id
        self.status = f"Selected Id {self._selected_id}"

    def select_id(self, pir_id):
        try:
            pir = self.pim.get(pir_id)
        except PIMError as exc:
            self.status = message_for(exc)
            return
        self._selected_id = pir.id
        self.status = f"Selected Id {pir.id}"

    def print_selected(self):
        pir = self.selected()
        if pir is None:
            self.status = "no PIR selected"
            return None
        self.print_text = format_pir(pir)
        self.status = f"Printed Id {pir.id}"
        return self.print_text

    def print_all(self):
        if not self._result:
            self.print_text = "(Current Result is empty)"
        else:
            self.print_text = "\n\n".join(format_pir(pir) for pir in self._result)
        self.status = f"Printed {len(self._result)} PIR(s) in Current Result"
        return self.print_text

    def save(self, path=None):
        try:
            if path is None:
                path = self.pim.bound_path()
                if not path:
                    raise ValidationError("no file name; use save as")
            self.pim.save(path)
        except PIMError as exc:
            self.status = message_for(exc)
            return False
        self.status = f"Saved {self.pim.bound_path()}"
        return True

    def load(self, path, force=False):
        try:
            self.pim.load(path, force=force)
        except PIMError as exc:
            self.status = message_for(exc)
            return False
        self._criterion = None
        self._selected_id = None
        self.print_text = ""
        self._refresh()
        self.status = f"Loaded {self.pim.bound_path()}"
        return True

    def _create(self, factory, label):
        try:
            pir = factory()
        except PIMError as exc:
            self.status = message_for(exc)
            return None
        self._selected_id = pir.id
        self._refresh()
        self.status = f"Created {label} Id {pir.id}"
        return pir

    def _refresh(self):
        if self._criterion is None:
            self._result = self.pim.all()
        else:
            self._result = self.pim.search(self._criterion)
        if self._selected_id is not None and all(pir.id != self._selected_id for pir in self._result):
            if self._criterion is not None:
                self._selected_id = None
            elif self._selected_id not in {pir.id for pir in self.pim.all()}:
                self._selected_id = None


HELP = (
    "Commands: create [note|task|event|contact] | search <criterion> | clear | "
    "<row> | id <n> | modify | print | print all | delete | save | save as <path> | "
    "load <path> | dismiss | help | quit"
)
