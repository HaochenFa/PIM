"""Acceptance fixture (docs/ACCEPTANCE.md section 4)."""

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
