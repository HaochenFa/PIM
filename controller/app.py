"""One completed user action → model.PIM. Holds Current Result and selection."""

from __future__ import annotations

from model import PIM, PIMError, ValidationError, parse_criterion
from controller.errors import message_for


def format_pir(pir) -> str:
    return "\n".join(f"{key}: {value}" for key, value in pir.detail_lines())


class App:
    def __init__(self, pim: PIM):
        self.pim = pim
        self._criterion = None
        self._result = []
        self._selected_id = None
        self.status = ""
        self.print_text = ""
        self._refresh()

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

    def create_note(self, text):
        return self._create(lambda: self.pim.create_note(text), "Note")

    def create_task(self, description, deadline=None):
        return self._create(lambda: self.pim.create_task(description, deadline), "Task")

    def create_event(self, description, start, alarms=None):
        return self._create(lambda: self.pim.create_event(description, start, alarms), "Event")

    def create_contact(self, name, address=None, mobile=None):
        return self._create(lambda: self.pim.create_contact(name, address, mobile), "Contact")

    def modify(self, fields):
        pir = self.selected()
        if pir is None:
            self.status = "no PIR selected"
            return None
        try:
            updated = self.pim.modify(pir.id, fields)
        except PIMError as exc:
            self.status = message_for(exc)
            return None
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
