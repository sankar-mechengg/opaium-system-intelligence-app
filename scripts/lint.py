"""
OP(AI)UM — Lint & Format Script

Runs ruff (lint + format) and mypy (type check) on the codebase.

Usage: python scripts/lint.py [--fix]
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
TESTS = ROOT / "tests"


def run(cmd: list[str], label: str) -> int:
    print(f"\n{'=' * 40}")
    print(f"  {label}")
    print(f"{'=' * 40}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    return result.returncode


def main() -> None:
    fix = "--fix" in sys.argv
    errors = 0

    # Ruff lint
    ruff_cmd = ["ruff", "check", str(SRC), str(TESTS)]
    if fix:
        ruff_cmd.append("--fix")
    errors += run(ruff_cmd, "Ruff Lint")

    # Ruff format
    fmt_cmd = ["ruff", "format", str(SRC), str(TESTS)]
    if not fix:
        fmt_cmd.append("--check")
    errors += run(fmt_cmd, "Ruff Format")

    # MyPy type checking
    mypy_cmd = [
        "mypy",
        str(SRC),
        "--ignore-missing-imports",
        "--no-error-summary",
    ]
    errors += run(mypy_cmd, "MyPy Type Check")

    print(f"\n{'=' * 40}")
    if errors:
        print(f"  [FAILED] {errors} check(s) had issues")
    else:
        print("  [OK] All checks passed")
    print(f"{'=' * 40}")

    sys.exit(min(errors, 1))


if __name__ == "__main__":
    main()
