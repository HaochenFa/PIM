"""Daemon thread that only enqueues stdin lines. Never touches model.PIM."""

from threading import Thread


def start_stdin_reader(queue, stdin):
    """Daemon thread: enqueue each line; enqueue None on EOF. Never touches model.PIM."""
    def run():
        while True:
            line = stdin.readline()
            if line == "":
                queue.put(None)
                # TTY Ctrl-D is per-read EOF; keep listening so the dirty prompt can be answered.
                if stdin.isatty():
                    continue
                return
            if line.endswith("\n"):
                line = line[:-1]
            queue.put(line)

    thread = Thread(target=run, name="stdin-reader", daemon=True)
    thread.start()
    return thread
