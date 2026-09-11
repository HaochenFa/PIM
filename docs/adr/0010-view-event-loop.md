# View runs an in-process event loop with a 500ms tick

In-app Alarm Alerts must appear while the user is sitting at the prompt, without a second OS process and without blocking the main thread on `input()`.

On a TTY, ADR-0018 uses stdlib `curses`: `get_wch` with `timeout(500)`, then `PIM.due_alarms(now)`. Tests and redirected stdio keep a daemon stdin-reader thread that only enqueues lines, and a main loop that calls `Queue.get(timeout=0.5)`.

500ms is fine: alarm granularity is a minute, and a tick is cheap. The loop must not repaint the whole screen every tick — only when the due set, dismissed set, Working Collection, Bound File, or input actually changed. `model` stays synchronous; `now` is injected; only the main thread calls `model`.

**Status**: accepted (TTY loop specialised by ADR-0018)
