"""Daemon thread that only enqueues stdin lines. Never touches model.PIM."""

from threading import Thread


def start_stdin_reader(queue, stdin):
    def run():
        while True:
            line = stdin.readline()
            if line == "":
                queue.put(None)
                return
            if line.endswith("\n"):
                line = line[:-1]
            queue.put(line)

    thread = Thread(target=run, name="stdin-reader", daemon=True)
    thread.start()
    return thread
