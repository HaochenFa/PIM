"""Shared six-PIR test fixture used by the search, integration, and e2e tests.

Ids 1-6: a Note; a Task with a deadline and one without; an Event with a
1-day relative, an at-start relative, and an absolute alarm; and two Contacts
both named Ada (one with only a mobile, one with only an address).
"""

from model import PIM, AbsoluteAlarm, RelativeAlarm

START = "2026-09-14T18:30:00+08:00"
DEADLINE = "2026-11-20T20:00:00+08:00"
ABSOLUTE = "2026-09-13T09:00:00+08:00"


def make_fixture() -> PIM:
    pim = PIM()
    pim.create_note("Shopping: Milk")
    pim.create_task("Submit PIM", DEADLINE)
    pim.create_task("Inbox")
    pim.create_event(
        "COMP3211 lecture",
        START,
        [
            RelativeAlarm(1, "day"),
            RelativeAlarm(0, "minute"),
            AbsoluteAlarm(ABSOLUTE),
        ],
    )
    pim.create_contact("Ada", mobile="12345678")
    pim.create_contact("Ada", address="HK")
    return pim
