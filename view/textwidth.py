"""Display-column width and clipping for the terminal View.

Python ``len`` counts code points. East Asian characters occupy two columns
in a terminal, so list clipping and cursor placement use this module instead.
"""

from __future__ import annotations

import unicodedata

ELLIPSIS = "..."


def char_width(char: str) -> int:
    """Return the terminal columns used by one code point.

    Combining marks are width 0. Fullwidth and wide East Asian characters
    are width 2. Control characters are width 0. Everything else is width 1.
    """
    if not char:
        return 0
    code = ord(char)
    if code < 32 or code == 127:
        return 0
    if unicodedata.combining(char):
        return 0
    if unicodedata.east_asian_width(char) in {"F", "W"}:
        return 2
    return 1


def display_width(text: str) -> int:
    """Return the terminal columns used by ``text``."""
    return sum(char_width(ch) for ch in text.replace("\n", " ").replace("\r", " "))


def clip(text: str, width: int, ellipsis: str = ELLIPSIS) -> str:
    """Return ``text`` fitted to ``width`` columns, with an ellipsis if trimmed.

    Newlines become spaces. If ``width`` is too small for the ellipsis, the
    prefix that fits is returned without it.
    """
    if width <= 0:
        return ""
    flat = text.replace("\n", " ").replace("\r", " ")
    if display_width(flat) <= width:
        return flat
    ell_w = display_width(ellipsis)
    budget = width - ell_w if ell_w < width else width
    out: list[str] = []
    used = 0
    for ch in flat:
        w = char_width(ch)
        if used + w > budget:
            break
        out.append(ch)
        used += w
    if ell_w < width:
        return "".join(out) + ellipsis
    return "".join(out)


def pad(text: str, width: int) -> str:
    """Clip or right-pad ``text`` so it occupies exactly ``width`` columns."""
    fitted = clip(text, width)
    extra = width - display_width(fitted)
    if extra > 0:
        return fitted + (" " * extra)
    return fitted


def wrap(text: str, width: int) -> list[str]:
    """Split ``text`` into lines that each fit in ``width`` columns."""
    if width <= 0:
        return [""]
    lines: list[str] = []
    for paragraph in text.replace("\r", "").split("\n"):
        rest = paragraph
        if rest == "":
            lines.append("")
            continue
        while rest:
            piece = clip(rest, width, ellipsis="")
            if not piece:
                piece = rest[0]
            lines.append(piece)
            rest = rest[len(piece) :]
    return lines
