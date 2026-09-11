"""Drive Terminal.run() with a scripted stdin and captured stdout."""

from __future__ import annotations

import io
import threading
from datetime import datetime

from controller.app import App
from model import PIM
from view import Terminal


class LineStdin:
    """File-like stdin: each scripted line, then block. Not a TTY.

    After the script, `readline` waits instead of returning EOF. Non-TTY EOF
    also quits a clean session, so a missing `quit`/`exit` alias would still
    stop the loop and a test that only checks `_running` would pass.
    """

    def __init__(self, lines):
        """`lines` are command and prompt answers without a trailing newline."""
        self._lines = [line if line.endswith("\n") else f"{line}\n" for line in lines]
        self._index = 0
        self._closed = threading.Event()

    def readline(self):
        """Next scripted line, or empty string after `close()`."""
        if self._index < len(self._lines):
            line = self._lines[self._index]
            self._index += 1
            return line
        self._closed.wait()
        return ""

    def close(self):
        """Unblock a waiting `readline` so the stdin-reader thread can exit."""
        self._closed.set()

    def isatty(self) -> bool:
        """Scripts are not an interactive TTY."""
        return False


def result_ids(app: App) -> list[int]:
    """Ids in Current Result, in list order."""
    return [pir.id for pir in app.current_result()]


def run_script(lines, now=None, pim=None, app=None, timeout: float = 8.0):
    """Run one Terminal session. Returns `(app, terminal, stdout text)`.

    `now` is an aware datetime or a zero-arg callable, injected into the View.
    The last command should leave the session able to exit (`quit`, or
    `quit` plus `discard` / `save` when dirty).
    """
    app = app if app is not None else App(pim if pim is not None else PIM())
    stdout = io.StringIO()
    stdin = LineStdin(lines)
    terminal = Terminal(app, stdin=stdin, stdout=stdout, now=now)
    caught: list[Exception] = []

    def target():
        try:
            terminal.run()
        except Exception as exc:
            caught.append(exc)

    thread = threading.Thread(target=target, name="e2e-terminal", daemon=True)
    thread.start()
    try:
        thread.join(timeout)
        if thread.is_alive():
            raise TimeoutError(
                "Terminal.run() did not exit; script may be missing quit"
            )
        if caught:
            raise caught[0]
        return app, terminal, stdout.getvalue()
    finally:
        stdin.close()


def clock(value: datetime):
    """Fixed `now` callable for Alarm Alert scripts."""

    def now():
        return value

    return now
