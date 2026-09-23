"""Working Collection: Id stability, delete, dirty, failed create is atomic."""

import tempfile
import unittest
from pathlib import Path

from model import NotFound, PIM, ValidationError
from tests.fixture import make_fixture


class CreateAndIdTests(unittest.TestCase):
    """Working Collection: create, modify, delete, Id stability, and the dirty flag."""
    def test_four_types_receive_monotonic_ids(self):
        """The six fixture PIRs of four types get Ids 1 to 6 in creation order with their types."""
        pim = make_fixture()
        ids = [pir.id for pir in pim.all()]
        self.assertEqual(ids, [1, 2, 3, 4, 5, 6])
        self.assertEqual(pim.get(1).type_name, "note")
        self.assertEqual(pim.get(4).type_name, "event")

    def test_failed_create_does_not_consume_id_or_dirty(self):
        """A failed create raises ValidationError, stays clean; the next PIR still gets Id 1."""
        pim = PIM()
        with self.assertRaises(ValidationError):
            pim.create_note("  ")
        self.assertFalse(pim.is_dirty())
        note = pim.create_note("ok")
        self.assertEqual(note.id, 1)

    def test_duplicate_contact_names_allowed(self):
        """Two Contacts with the same Name both exist; Name is not a unique key."""
        pim = make_fixture()
        self.assertEqual(pim.get(5).name, pim.get(6).name)

    def test_modify_keeps_id(self):
        """Modifying a Task's description (US6) updates the Working Collection and keeps Id 3."""
        pim = make_fixture()
        pir = pim.modify(3, {"description": "Inbox later"})
        self.assertEqual(pir.id, 3)
        self.assertEqual(pim.get(3).description, "Inbox later")

    def test_unknown_id_fails_without_mutation(self):
        """Unknown Ids raise NotFound, non-dict changes ValidationError; all six PIRs remain."""
        pim = make_fixture()
        with self.assertRaises(NotFound):
            pim.modify(99, {"text": "x"})
        with self.assertRaises(NotFound):
            pim.get("abc")
        with self.assertRaises(ValidationError):
            pim.modify(1, ["text"])
        self.assertEqual(len(pim.all()), 6)

    def test_delete_does_not_reuse_id(self):
        """A deleted Id (US9) is no longer found, and the next created PIR never reuses that Id."""
        pim = make_fixture()
        pim.delete(2)
        with self.assertRaises(NotFound):
            pim.get(2)
        created = pim.create_note("after delete")
        self.assertGreaterEqual(created.id, 7)
        self.assertNotEqual(created.id, 2)

    def test_failed_modify_type_leaves_pir_unchanged(self):
        """Changing a PIR's type raises ValidationError; the Note keeps its type and text."""
        pim = make_fixture()
        with self.assertRaises(ValidationError):
            pim.modify(1, {"type": "task"})
        self.assertEqual(pim.get(1).type_name, "note")
        self.assertEqual(pim.get(1).text, "Shopping: Milk")

    def test_noop_modify_does_not_dirty(self):
        """An empty or same-value modify returns the same PIR; a saved collection stays clean."""
        pim = PIM()
        pim.create_note("ok")
        path = Path(tempfile.mkdtemp()) / "x.pim"
        pim.save(path)
        self.assertFalse(pim.is_dirty())
        original = pim.get(1)
        self.assertIs(pim.modify(1, {}), original)
        self.assertFalse(pim.is_dirty())
        self.assertIs(pim.modify(1, {"text": "ok"}), original)
        self.assertFalse(pim.is_dirty())

    def test_failed_modify_does_not_replace_or_dirty_a_clean_collection(self):
        """Blank-text modify raises ValidationError; Note text and clean collection unchanged."""
        pim = PIM()
        pim.create_note("ok")
        path = Path(tempfile.mkdtemp()) / "x.pim"
        pim.save(path)
        with self.assertRaises(ValidationError):
            pim.modify(1, {"text": "  "})
        self.assertEqual(pim.get(1).text, "ok")
        self.assertFalse(pim.is_dirty())


if __name__ == "__main__":
    unittest.main()
