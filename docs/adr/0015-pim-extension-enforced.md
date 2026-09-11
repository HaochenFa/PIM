# Save and load require the `.pim` extension

US10 and US11 require storing and loading a file with extension `.pim`. Save appends `.pim` if the user omits it. Load rejects any other extension before parsing. Save to the Bound File overwrites without asking. Save-as onto an existing path asks for confirmation. This is the assignment’s file type, not a new format (the bytes inside remain JSON).

**Status**: accepted
