#!/usr/bin/env python3
"""Write a line-coverage report for model/ using only the standard library."""

from __future__ import annotations

import sys
import traceback
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "model"


def main() -> int:
    import trace as trace_mod

    tracer = trace_mod.Trace(
        count=True,
        trace=False,
        ignoredirs=[sys.prefix, sys.exec_prefix],
    )

    def run_tests():
        # Discover inside the tracer so import of model/ is counted.
        loader = unittest.defaultTestLoader
        suite = loader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
        return unittest.TextTestRunner(stream=sys.stderr, verbosity=1).run(suite)

    result = tracer.runfunc(run_tests)
    counts = defaultdict(dict)
    for (filename, lineno), n in tracer.results().counts.items():
        counts[str(Path(filename).resolve())][lineno] = n

    lines = ["Line coverage for model/ (stdlib trace)", ""]
    grand_hit = grand_total = 0
    for path in sorted(MODEL.glob("*.py")):
        if path.name == "__init__.py":
            # Re-exports only; trace does not attribute package import to this file.
            continue
        source = path.read_text(encoding="utf-8").splitlines()
        executed = counts.get(str(path.resolve()), {})
        hit = total = 0
        missing = []
        for lineno, text in enumerate(source, 1):
            if not _is_executable(text):
                continue
            total += 1
            if executed.get(lineno, 0) > 0:
                hit += 1
            else:
                missing.append(str(lineno))
        grand_hit += hit
        grand_total += total
        pct = (100.0 * hit / total) if total else 100.0
        lines.append(f"{path.name}: {hit}/{total} lines ({pct:.1f}%)")
        if missing:
            lines.append("  missed: " + ", ".join(missing))
    pct = (100.0 * grand_hit / grand_total) if grand_total else 100.0
    lines.append("")
    lines.append(f"TOTAL model/: {grand_hit}/{grand_total} lines ({pct:.1f}%)")
    report = ROOT / "coverage.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stderr.write(f"Wrote {report}\n")
    if not result.wasSuccessful():
        return 1
    return 0


def _is_executable(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped.startswith("#"):
        return False
    if stripped.startswith(('"""', "'''")) and stripped.endswith(('"""', "'''")) and len(stripped) >= 6:
        return False
    if stripped in ('"""', "'''"):
        return False
    return True


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
