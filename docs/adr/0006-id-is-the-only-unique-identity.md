# A PIR is identified only by a system Id

Modify, delete, and print-one need a stable handle. List position is not stable. A unique user label is the wrong concept: many Events can share the same description (a weekly class), and many Contacts can share the same person name.

The PIM assigns a monotonic integer Id at creation, persists it, and never reuses it after delete. Search (type, contains, time, and/or/not) is how the user finds PIRs; it is not a second identity. There is no unique Label.

**Status**: accepted
