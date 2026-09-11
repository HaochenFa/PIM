# View runs an in-process event loop with a 500ms tick

In-app Alarm Alerts must appear while the user is sitting at the prompt, without a second OS process and without blocking the main thread on `input()`. The View owns a daemon stdin-reader thread that only enqueues lines, and a main loop that calls `Queue.get(timeout=0.5)` then `PIM.due_alarms(now)`.

500ms is fine: alarm granularity is a minute, and a tick is cheap. The loop must not repaint the whole screen every tick — only when the due set, dismissed set, Working Collection, Bound File, or input actually changed. `model` stays synchronous; `now` is injected; only the main thread calls `model`.

**Status**: accepted
