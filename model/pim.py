"""Working Collection: create, modify, delete, search, save, load, due_alarms."""

from __future__ import annotations

import copy

from model.criterion import Criterion
from model.pimfile import read_pim_file, require_pim_extension, write_pim_file
from model.pir import (
    Contact,
    DueAlarm,
    DirtyLoadError,
    Event,
    NotFound,
    Note,
    PIR,
    SOON_WINDOW,
    Task,
    ValidationError,
    minute_floor,
    parse_datetime,
)


class PIM:
    def __init__(self):
        self._pirs: dict[int, PIR] = {}
        self._next_id = 1
        self._dirty = False
        self._bound_path: str | None = None

    def create_note(self, text) -> Note:
        pir = Note(self._next_id, text)
        return self._insert(pir)

    def create_task(self, description, deadline=None) -> Task:
        pir = Task(self._next_id, description, deadline)
        return self._insert(pir)

    def create_event(self, description, start, alarms=None) -> Event:
        pir = Event(self._next_id, description, start, alarms)
        return self._insert(pir)

    def create_contact(self, name, address=None, mobile=None) -> Contact:
        pir = Contact(self._next_id, name, address, mobile)
        return self._insert(pir)

    def modify(self, pir_id, fields) -> PIR:
        pir = self.get(pir_id)
        if not isinstance(fields, dict):
            raise ValidationError("fields must be a mapping")
        candidate = copy.copy(pir)
        candidate.modify(fields)
        if candidate.to_json() == pir.to_json():
            return pir
        self._pirs[pir.id] = candidate
        self._dirty = True
        return candidate

    def delete(self, pir_id) -> None:
        self.get(pir_id)
        del self._pirs[int(pir_id)]
        self._dirty = True

    def get(self, pir_id) -> PIR:
        try:
            key = int(pir_id)
        except (TypeError, ValueError) as exc:
            raise NotFound(f"no PIR with Id {pir_id}") from exc
        pir = self._pirs.get(key)
        if pir is None:
            raise NotFound(f"no PIR with Id {key}")
        return pir

    def all(self) -> list[PIR]:
        return [self._pirs[key] for key in sorted(self._pirs)]

    def search(self, criterion: Criterion) -> list[PIR]:
        return [pir for pir in self.all() if criterion.matches(pir)]

    def due_alarms(self, now) -> list[DueAlarm]:
        instant = minute_floor(parse_datetime(now))
        soon_end = instant + SOON_WINDOW
        due: list[DueAlarm] = []
        for pir in self.all():
            if not isinstance(pir, Event):
                continue
            for index, alarm in enumerate(pir.alarms):
                at = alarm.effective(pir.start)
                if at <= instant:
                    status = "OVERDUE"
                elif at <= soon_end:
                    status = "SOON"
                else:
                    continue
                due.append(DueAlarm(pir.id, index, at, status, pir.description))
        return due

    def save(self, path) -> None:
        written = write_pim_file(path, self._next_id, self.all())
        self._bound_path = str(written)
        self._dirty = False

    def load(self, path, *, force: bool = False) -> None:
        require_pim_extension(path)
        if self._dirty and not force:
            raise DirtyLoadError("unsaved changes; save, discard, or cancel")
        next_id, pirs = read_pim_file(path)
        self._pirs = {pir.id: pir for pir in pirs}
        self._next_id = next_id
        self._bound_path = str(require_pim_extension(path))
        self._dirty = False

    def is_dirty(self) -> bool:
        return self._dirty

    def bound_path(self) -> str | None:
        return self._bound_path

    def _insert(self, pir: PIR) -> PIR:
        self._pirs[pir.id] = pir
        self._next_id = pir.id + 1
        self._dirty = True
        return pir
