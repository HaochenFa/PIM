# Default timezone is Hong Kong Time

Datetimes are timezone-aware. When the user omits a zone, the PIM assumes IANA `Asia/Hong_Kong` (HKT). The assignment is a PolyU course; HKT has no DST, so the default is stable across machines. Using the grader's system timezone would make the same PIM File mean different instants. Requiring an explicit zone on every input is worse UX for a single-user Hong Kong tool.

Stored values still round-trip as ISO 8601 with an explicit offset or zone, so search `<` `>` `=` compares instants, not clock faces.

**Status**: accepted
