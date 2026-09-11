# Requirements coverage

Appendix B user stories versus this implementation. SRS requirement ids will be filled when the typeset SRS is written; until then the story id is the requirement id.

| Appendix B | Requirement | Status |
|---|---|---|
| US1 / US2 | Create Note (body required, no title) | implemented |
| US3 | Create Task (description required, deadline optional) | implemented |
| US4 | Create Event (description and start required, 0..n alarms) | implemented |
| US5 | Create Contact (name required, address/mobile optional) | implemented |
| US6 | Modify fields; type immutable; Id unchanged | implemented |
| US7 | Search: type, contains, time, `&&` `\|\|` `!` | implemented |
| US8 | Print one PIR or Current Result (`print all`) | implemented |
| US9 | Delete a specified PIR; Ids not reused | implemented |
| US10 | Store to `.pim` | implemented |
| US11 | Load from `.pim` | implemented |
| HCI | In-process OVERDUE / SOON Alarm Alert | implemented |

Out of scope (not implemented, by product decision): GUI, recurrence, PIR links, OS notifications, third-party TUI libraries.
