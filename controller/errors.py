"""Map domain exceptions to one English status-line message."""

from model import PIMError


def message_for(exc: BaseException) -> str:
    """One English status-line message. Never a traceback."""
    if isinstance(exc, PIMError):
        return exc.status_message()
    if isinstance(exc, OSError):
        return str(exc)
    return "command failed"
