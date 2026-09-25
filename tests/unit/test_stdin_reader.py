"""view.stdin_reader: enqueue lines; None on EOF; never touches the model."""

import unittest
from queue import Queue

from view.stdin_reader import start_stdin_reader


class FakeStdin:
    """File-like stdin with an optional TTY flag."""

    def __init__(self, chunks, tty=False):
        self._chunks = list(chunks)
        self._index = 0
        self._tty = tty

    def readline(self):
        """Next chunk, or empty string at EOF."""
        if self._index >= len(self._chunks):
            return ""
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk

    def isatty(self) -> bool:
        """Whether this stdin claims to be a TTY."""
        return self._tty


class StdinReaderTests(unittest.TestCase):
    def test_strips_newline_and_signals_eof(self):
        """The reader strips each line's trailing newline and enqueues `None` once `readline` returns empty."""
        queue = Queue()
        thread = start_stdin_reader(queue, FakeStdin(["help\n", "quit"]))
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(queue.get_nowait(), "help")
        self.assertEqual(queue.get_nowait(), "quit")
        self.assertIsNone(queue.get_nowait())

    def test_tty_eof_keeps_listening_for_the_next_line(self):
        """On a TTY, an empty `readline` enqueues `None` but the reader keeps listening for the next line."""
        queue = Queue()

        class TtyThenStop(FakeStdin):
            def __init__(self):
                super().__init__([], tty=True)
                self.n = 0

            def readline(self):
                self.n += 1
                if self.n == 1:
                    return ""
                if self.n == 2:
                    return "resume\n"
                raise SystemExit

        thread = start_stdin_reader(queue, TtyThenStop())
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertIsNone(queue.get_nowait())
        self.assertEqual(queue.get_nowait(), "resume")
