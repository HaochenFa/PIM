# Text contains is Unicode case-insensitive

US7 requires substring contains, not fuzzy match. Case-insensitive matching is a UX choice. The definition is Python `str.casefold()` on both the field and the needle, then substring search. That is Unicode case folding, not a locale (so tests do not depend on the grader's machine). Chinese text is unchanged by casefold and still uses ordinary substring match.

**Status**: accepted
