# Command vocabulary is verb lines plus prompted wizards

The product requires a designed terminal (prompted create/modify, one criterion line for search) but does not name the commands. Numbered menus, single-letter keys, and verb lines all satisfy US1–US11.

Verb lines (`create`, `search`, `modify`, `print`, `print all`, `delete`, `save`, `save as`, `load`, `clear`, `dismiss`, `help`, `quit`) plus 1-based row selection and `id <n>` are the smallest set that is demoable in four minutes and maps 1:1 onto Appendix B. Multi-field create/modify, extra Event alarms, delete confirm, overwrite confirm, and dirty save/discard/cancel stay as sequential prompts, not extra command languages.

Single-letter aliases are omitted so the user manual and the prompt stay one list. Changing verbs later is a View/Controller rename; `model` is unaffected.

**Status**: accepted
