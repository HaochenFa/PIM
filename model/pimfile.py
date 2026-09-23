"""UTF-8 JSON codec for a PIM File. Still part of model (US10 / US11)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from model.pir import (
    ExtensionError,
    FileFormatError,
    PIR,
    ValidationError,
    pir_from_json,
)

FORMAT = "pim/v1"


def require_pim_extension(path) -> Path:
    """Return `path` as a Path. Raises ExtensionError if the suffix is not `.pim`."""
    path = Path(path)
    if path.suffix.casefold() != ".pim":
        raise ExtensionError("path must have a .pim extension")
    return path


def append_pim_extension(path) -> Path:
    """Append `.pim` when omitted; leave an existing `.pim` suffix unchanged."""
    path = Path(path)
    if path.suffix.casefold() == ".pim":
        return path
    return Path(str(path) + ".pim")


def dump(next_id: int, pirs: list[PIR]) -> str:
    """UTF-8 JSON document for a PIM File (`format: pim/v1`)."""
    payload = {
        "format": FORMAT,
        "next_id": next_id,
        "pirs": [pir.to_json() for pir in pirs],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def write_pim_file(path, next_id: int, pirs: list[PIR]) -> Path:
    """Atomic write: temp file in the same directory, then os.replace."""
    path = append_pim_extension(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dump(next_id, pirs)
    fd, tmp = tempfile.mkstemp(prefix=".pim-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def read_pim_file(path) -> tuple[int, list[PIR]]:
    """Parse a `.pim` file. Raises FileFormatError without mutating the caller."""
    path = require_pim_extension(path)
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise FileFormatError("file is not valid JSON") from exc
    except UnicodeDecodeError as exc:
        # A ValueError, not an OSError: without this branch it escapes as a traceback.
        raise FileFormatError("file is not UTF-8 text") from exc
    except OSError as exc:
        raise FileFormatError(f"cannot read file: {exc}") from exc
    if not isinstance(payload, dict):
        raise FileFormatError("PIM File must be a JSON object")
    if payload.get("format") != FORMAT:
        raise FileFormatError("unknown format; expected pim/v1")
    try:
        next_id = int(payload["next_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FileFormatError("missing or invalid next_id") from exc
    raw_pirs = payload.get("pirs")
    if not isinstance(raw_pirs, list):
        raise FileFormatError("pirs must be a list")
    pirs: list[PIR] = []
    seen: set[int] = set()
    try:
        for item in raw_pirs:
            pir = pir_from_json(item)
            if pir.id in seen:
                raise FileFormatError(f"duplicate Id {pir.id}")
            seen.add(pir.id)
            pirs.append(pir)
    except ValidationError as exc:
        raise FileFormatError(str(exc)) from exc
    if next_id <= 0:
        raise FileFormatError("next_id must be positive")
    max_id = max(seen, default=0)
    if next_id <= max_id:
        next_id = max_id + 1
    return next_id, pirs
