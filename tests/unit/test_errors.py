"""controller.errors.message_for: one English status line, never a traceback."""

import unittest

from controller.errors import message_for
from model import PIMError, ValidationError


class MessageForTests(unittest.TestCase):
    def test_pim_error_uses_status_message(self):
        self.assertEqual(message_for(ValidationError("text is required")), "text is required")
        self.assertEqual(message_for(PIMError("boom")), "boom")

    def test_os_error_uses_str(self):
        self.assertEqual(message_for(OSError("disk full")), "disk full")

    def test_other_exceptions_are_generic(self):
        self.assertEqual(message_for(RuntimeError("hidden")), "command failed")
        self.assertEqual(message_for(ValueError("nope")), "command failed")
