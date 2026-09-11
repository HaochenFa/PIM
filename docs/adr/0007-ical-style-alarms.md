# Event alarms follow iCal TRIGGER, stored in JSON

RFC 5545 `VALARM` allows several alarms per event. Each alarm has one `TRIGGER` that is either a `DURATION` relative to the start (`RELATED=START`) or an absolute `DATE-TIME`. We copy that shape, not the `.ics` file format.

An Event holds a list of alarms, possibly empty. Each alarm is Relative (at start, or a duration before start — never after) or Absolute (an HKT/ISO instant). Search and print use the effective instant: start minus duration, or the stored instant. Changing start recomputes only Relative alarms. The PIM File remains JSON; this is not an iCalendar exporter. After-start relative offsets are omitted: an Absolute alarm already covers a custom instant after start.

**Status**: accepted
