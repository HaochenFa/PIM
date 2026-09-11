# A PIR's type cannot be changed after creation

US6 allows modifying the data in an existing PIR, not converting its type. Changing Task → Event is a delete plus create: Id would change, and fields (deadline vs start vs alarms) do not map. Modify edits fields in place and keeps the Id. To get another type, the user deletes and creates.

**Status**: accepted
