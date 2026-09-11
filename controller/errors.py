"""Map domain exceptions to one English status-line message."""

from model import (
    DirtyLoadError,
    ExtensionError,
    FileFormatError,
    NotFound,
    ParseError,
    PIMError,
    ValidationError,
)


def message_for(exc: BaseException) -> str:
    if isinstance(exc, ParseError):
        return f"search syntax error: {exc}"
    if isinstance(exc, DirtyLoadError):
        return str(exc)
    if isinstance(exc, ExtensionError):
        return str(exc)
    if isinstance(exc, FileFormatError):
        return f"not a PIM file: {exc}"
    if isinstance(exc, NotFound):
        return str(exc)
    if isinstance(exc, ValidationError):
        return str(exc)
    if isinstance(exc, PIMError):
        return str(exc)
    return "command failed"
