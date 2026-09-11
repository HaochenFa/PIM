"""Save/load round-trip, extension, dirty load, corrupt file."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from model import DirtyLoadError, ExtensionError, FileFormatError, PIM, parse_datetime
from model.pimfile import read_pim_file, write_pim_file
from tests.fixture import make_fixture


class PersistTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmpdir.name)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_save_appends_pim_and_round_trips(self):
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
        pim = make_fixture()
        pim.delete(2)
        pim.save(self.dir / "keep.pim")
        loaded = PIM()
        loaded.load(self.dir / "keep.pim")
        created = loaded.create_note("after")
        self.assertGreaterEqual(created.id, 7)
        self.assertNotEqual(created.id, 2)

    def test_load_rejects_other_extension_without_parsing(self):
        other = self.dir / "demo.json"
        other.write_text("not json that would fail", encoding="utf-8")
        pim = PIM()
        with self.assertRaises(ExtensionError):
            pim.load(other)
        self.assertEqual(pim.all(), [])

    def test_bad_json_does_not_clobber_memory(self):
        pim = make_fixture()
        path = self.dir / "bad.pim"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(FileFormatError):
            pim.load(path, force=True)
        self.assertEqual(len(pim.all()), 6)
        self.assertEqual(pim.get(1).text, "Shopping: Milk")

    def test_unknown_format_does_not_clobber_memory(self):
        pim = make_fixture()
        path = self.dir / "old.pim"
        path.write_text('{"format": "pim/v0", "next_id": 1, "pirs": []}', encoding="utf-8")
        with self.assertRaises(FileFormatError):
            pim.load(path, force=True)
        self.assertEqual(len(pim.all()), 6)

    def test_load_while_dirty_without_force_fails(self):
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
        pim = PIM()
        pim.create_note("x")
        self.assertTrue(pim.is_dirty())
        pim.save(self.dir / "x.pim")
        self.assertFalse(pim.is_dirty())

    def test_missing_file_is_format_error(self):
        pim = PIM()
        with self.assertRaises(FileFormatError):
            pim.load(self.dir / "missing.pim")

    def test_duplicate_id_and_bad_schema(self):
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
        path = self.dir / "pirs.pim"
        path.write_text('{"format":"pim/v1","next_id":1,"pirs":{}}', encoding="utf-8")
        with self.assertRaises(FileFormatError):
            read_pim_file(path)

    def test_invalid_pir_in_file_is_format_error(self):
        path = self.dir / "blank.pim"
        path.write_text(
            '{"format":"pim/v1","next_id":2,"pirs":[{"id":1,"type":"note","text":"  "}]}',
            encoding="utf-8",
        )
        with self.assertRaises(FileFormatError):
            read_pim_file(path)

    def test_next_id_must_be_positive(self):
        path = self.dir / "zero.pim"
        path.write_text('{"format":"pim/v1","next_id":0,"pirs":[]}', encoding="utf-8")
        with self.assertRaises(FileFormatError):
            read_pim_file(path)

    def test_next_id_is_raised_above_max_id(self):
        path = self.dir / "bump.pim"
        path.write_text(
            '{"format":"pim/v1","next_id":1,"pirs":[{"id":5,"type":"note","text":"keep"}]}',
            encoding="utf-8",
        )
        next_id, pirs = read_pim_file(path)
        self.assertEqual(next_id, 6)
        self.assertEqual(pirs[0].id, 5)

    def test_write_failure_unlinks_temp_and_reraises(self):
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
