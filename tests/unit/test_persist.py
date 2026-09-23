"""Save/load round-trip, extension, dirty load, corrupt file."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from model import (
    DirtyLoadError,
    ExtensionError,
    FileFormatError,
    PIM,
    ValidationError,
    parse_datetime,
)
from model.pimfile import read_pim_file, write_pim_file
from tests.fixture import make_fixture


class PersistTests(unittest.TestCase):
    """US10/US11 save and load of the PIM File: round-trip, extension, dirty load, corrupt input."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_save_appends_pim_and_round_trips(self):
        """US10/US11: save appends `.pim`; load restores all 6 PIRs, fields, and alarms, and is clean."""
        pim = make_fixture()
        pim.save(self.dir / "demo")
        path = self.dir / "demo.pim"
        self.assertTrue(path.is_file())
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["format"], "pim/v1")
        loaded = PIM()
        loaded.load(path)
        self.assertEqual([pir.id for pir in loaded.all()], [1, 2, 3, 4, 5, 6])
        self.assertEqual(loaded.get(1).text, "Shopping: Milk")
        self.assertIsNone(loaded.get(3).deadline)
        event = loaded.get(4)
        self.assertEqual(event.start, parse_datetime("2026-09-14T18:30:00+08:00"))
        self.assertEqual(len(event.alarms), 3)
        self.assertEqual(event.alarms[0].kind_label().split()[0], "relative")
        self.assertEqual(
            event.effective_alarm_times()[2],
            parse_datetime("2026-09-13T09:00:00+08:00"),
        )
        self.assertEqual(loaded.get(5).mobile, "12345678")
        self.assertFalse(loaded.is_dirty())
        self.assertEqual(Path(loaded.bound_path()), path)

    def test_next_id_survives_delete_then_save_load(self):
        """After delete, save, and load, the next Id is at least 7; the deleted Id 2 is never reused."""
        pim = make_fixture()
        pim.delete(2)
        pim.save(self.dir / "keep.pim")
        loaded = PIM()
        loaded.load(self.dir / "keep.pim")
        created = loaded.create_note("after")
        self.assertGreaterEqual(created.id, 7)
        self.assertNotEqual(created.id, 2)

    def test_load_rejects_other_extension_without_parsing(self):
        """Loading a `.json` file raises ExtensionError; the Working Collection stays empty."""
        other = self.dir / "demo.json"
        other.write_text("not json that would fail", encoding="utf-8")
        pim = PIM()
        with self.assertRaises(ExtensionError):
            pim.load(other)
        self.assertEqual(pim.all(), [])

    def test_bad_json_does_not_clobber_memory(self):
        """A corrupt file raises FileFormatError; the Working Collection keeps its 6 PIRs."""
        pim = make_fixture()
        path = self.dir / "bad.pim"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(FileFormatError):
            pim.load(path, force=True)
        self.assertEqual(len(pim.all()), 6)
        self.assertEqual(pim.get(1).text, "Shopping: Milk")

    def test_unknown_format_does_not_clobber_memory(self):
        """An unknown `format` (pim/v0) raises FileFormatError; the Working Collection keeps 6 PIRs."""
        pim = make_fixture()
        path = self.dir / "old.pim"
        path.write_text('{"format": "pim/v0", "next_id": 1, "pirs": []}', encoding="utf-8")
        with self.assertRaises(FileFormatError):
            pim.load(path, force=True)
        self.assertEqual(len(pim.all()), 6)

    def test_file_event_with_overflowing_alarm_does_not_load(self):
        """A1 via file: an Event whose relative alarm overflows is a FileFormatError; memory survives."""
        pim = make_fixture()
        path = self.dir / "overflow.pim"
        event = {
            "id": 1,
            "type": "event",
            "description": "bad",
            "start": "2026-09-14T18:30:00+08:00",
            "alarms": [{"kind": "relative", "amount": 999999999, "unit": "week"}],
        }
        path.write_text(
            json.dumps({"format": "pim/v1", "next_id": 2, "pirs": [event]}), encoding="utf-8"
        )
        with self.assertRaises(FileFormatError):
            pim.load(path, force=True)
        self.assertEqual(len(pim.all()), 6)

    def test_file_with_non_list_alarms_does_not_load(self):
        """A3 via file: `"alarms": 5` is a FileFormatError, not a TypeError; memory survives."""
        pim = make_fixture()
        path = self.dir / "alarms.pim"
        event = {
            "id": 1,
            "type": "event",
            "description": "bad",
            "start": "2026-09-14T18:30:00+08:00",
            "alarms": 5,
        }
        path.write_text(
            json.dumps({"format": "pim/v1", "next_id": 2, "pirs": [event]}), encoding="utf-8"
        )
        with self.assertRaises(FileFormatError):
            pim.load(path, force=True)
        self.assertEqual(len(pim.all()), 6)

    def test_non_utf8_file_does_not_load(self):
        """A4: bytes that are not UTF-8 raise FileFormatError, not UnicodeDecodeError; memory survives."""
        pim = make_fixture()
        path = self.dir / "latin1.pim"
        path.write_bytes(b'{"format": "pim/v1", "next_id": 1, "pirs": [], "x": "\xff\xfe"}')
        with self.assertRaises(FileFormatError) as ctx:
            pim.load(path, force=True)
        self.assertEqual(ctx.exception.status_message(), "not a PIM file: file is not UTF-8 text")
        self.assertEqual(len(pim.all()), 6)

    def test_load_while_dirty_without_force_fails(self):
        """Load while dirty raises DirtyLoadError and keeps edits; forced load restores the file, clean."""
        pim = make_fixture()
        path = self.dir / "ok.pim"
        pim.save(path)
        pim.modify(1, {"text": "changed"})
        self.assertTrue(pim.is_dirty())
        with self.assertRaises(DirtyLoadError):
            pim.load(path)
        self.assertEqual(pim.get(1).text, "changed")
        pim.load(path, force=True)
        self.assertEqual(pim.get(1).text, "Shopping: Milk")
        self.assertFalse(pim.is_dirty())

    def test_save_clears_dirty(self):
        """Creating a PIR sets the dirty flag; a successful save clears it."""
        pim = PIM()
        pim.create_note("x")
        self.assertTrue(pim.is_dirty())
        pim.save(self.dir / "x.pim")
        self.assertFalse(pim.is_dirty())

    def test_missing_file_is_format_error(self):
        """Loading a PIM File that does not exist raises FileFormatError."""
        pim = PIM()
        with self.assertRaises(FileFormatError):
            pim.load(self.dir / "missing.pim")

    def test_duplicate_id_and_bad_schema(self):
        """Duplicate Ids, non-int next_id, non-object root, or unknown type raise FileFormatError."""
        pim = PIM()
        pim.create_note("keep")
        dup = self.dir / "dup.pim"
        dup.write_text(
            '{"format":"pim/v1","next_id":3,"pirs":['
            '{"id":1,"type":"note","text":"a"},'
            '{"id":1,"type":"note","text":"b"}]}',
            encoding="utf-8",
        )
        with self.assertRaises(FileFormatError):
            pim.load(dup, force=True)
        self.assertEqual(pim.get(1).text, "keep")

        bad = self.dir / "bad-schema.pim"
        bad.write_text('{"format":"pim/v1","next_id":"x","pirs":[]}', encoding="utf-8")
        with self.assertRaises(FileFormatError):
            pim.load(bad, force=True)

        not_obj = self.dir / "list.pim"
        not_obj.write_text("[]", encoding="utf-8")
        with self.assertRaises(FileFormatError):
            pim.load(not_obj, force=True)

        unknown = self.dir / "type.pim"
        unknown.write_text(
            '{"format":"pim/v1","next_id":2,"pirs":[{"id":1,"type":"series"}]}',
            encoding="utf-8",
        )
        with self.assertRaises(FileFormatError):
            pim.load(unknown, force=True)

    def test_pirs_must_be_a_list(self):
        """A PIM File whose `pirs` is an object, not a list, raises FileFormatError."""
        path = self.dir / "pirs.pim"
        path.write_text('{"format":"pim/v1","next_id":1,"pirs":{}}', encoding="utf-8")
        with self.assertRaises(FileFormatError):
            read_pim_file(path)

    def test_invalid_pir_in_file_is_format_error(self):
        """A Note with whitespace-only `text` in the file raises FileFormatError."""
        path = self.dir / "blank.pim"
        path.write_text(
            '{"format":"pim/v1","next_id":2,"pirs":[{"id":1,"type":"note","text":"  "}]}',
            encoding="utf-8",
        )
        with self.assertRaises(FileFormatError):
            read_pim_file(path)

    def test_next_id_must_be_positive(self):
        """A PIM File with `next_id` 0 raises FileFormatError."""
        path = self.dir / "zero.pim"
        path.write_text('{"format":"pim/v1","next_id":0,"pirs":[]}', encoding="utf-8")
        with self.assertRaises(FileFormatError):
            read_pim_file(path)

    def test_next_id_is_raised_above_max_id(self):
        """A stale `next_id` of 1 with a PIR of Id 5 is raised to 6 on read; Id 5 is kept."""
        path = self.dir / "bump.pim"
        path.write_text(
            '{"format":"pim/v1","next_id":1,"pirs":[{"id":5,"type":"note","text":"keep"}]}',
            encoding="utf-8",
        )
        next_id, pirs = read_pim_file(path)
        self.assertEqual(next_id, 6)
        self.assertEqual(pirs[0].id, 5)

    def test_blank_or_bare_pim_path_is_rejected_without_writing(self):
        """save("") and save(".pim") raise ValidationError; no `..pim` or `.pim.pim` appears."""
        pim = PIM()
        pim.create_note("keep")
        for bad in ("", "   ", ".pim", str(self.dir / ".PIM")):
            with self.assertRaises(ValidationError) as ctx:
                pim.save(bad)
            self.assertEqual(ctx.exception.status_message(), "file name is required")
        with self.assertRaises(ValidationError):
            pim.load(self.dir / ".pim", force=True)
        self.assertEqual(list(self.dir.iterdir()), [])
        self.assertTrue(pim.is_dirty())
        self.assertIsNone(pim.bound_path())

    def test_ids_in_file_must_be_positive_integers(self):
        """Ids -3, 0, 1.7, "3", and true are FileFormatError, not coerced; memory survives."""
        pim = make_fixture()
        for bad_id in (-3, 0, 1.7, "3", True):
            path = self.dir / "ids.pim"
            payload = {"format": "pim/v1", "next_id": 9, "pirs": [{"id": bad_id, "type": "note", "text": "x"}]}
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(FileFormatError, msg=repr(bad_id)):
                pim.load(path, force=True)
        self.assertEqual(len(pim.all()), 6)

    def test_next_id_must_be_an_integer(self):
        """next_id of 1.5, "5", or true is FileFormatError rather than a silent int()."""
        for bad in (1.5, "5", True):
            path = self.dir / "next.pim"
            path.write_text(json.dumps({"format": "pim/v1", "next_id": bad, "pirs": []}), encoding="utf-8")
            with self.assertRaises(FileFormatError, msg=repr(bad)):
                read_pim_file(path)

    def test_earliest_accepted_start_round_trips(self):
        """An Event at 0001-01-01 09:00 HKT, the earliest safe hour, saves and loads back unchanged."""
        pim = PIM()
        event = pim.create_event("ancient", "0001-01-01 09:00")
        path = self.dir / "ancient.pim"
        pim.save(path)
        loaded = PIM()
        loaded.load(path)
        self.assertEqual(loaded.get(event.id).start, event.start)

    def test_write_failure_unlinks_temp_and_reraises(self):
        """A failed atomic replace re-raises OSError, even when removing the temp file also fails."""
        pim = PIM()
        pim.create_note("x")
        path = self.dir / "fail.pim"
        with patch("model.pimfile.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                pim.save(path)
        with patch("model.pimfile.os.replace", side_effect=OSError("disk full")):
            with patch("model.pimfile.os.unlink", side_effect=OSError("gone")):
                with self.assertRaises(OSError):
                    write_pim_file(path, 2, pim.all())


if __name__ == "__main__":
    unittest.main()
