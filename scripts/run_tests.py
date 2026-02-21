"""
OP(AI)UM — Test Runner

Runs pytest with coverage reporting.

Usage: python scripts/run_tests.py [--coverage] [--verbose]
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"


def main() -> None:
    cmd = [sys.executable, "-m", "pytest", str(TESTS)]

    if "--verbose" in sys.argv or "-v" in sys.argv:
        cmd.append("-v")

    if "--coverage" in sys.argv:
        cmd.extend([
            "--cov=src",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov",
        ])

    cmd.extend([
        "-x",           # Stop on first failure
        "--tb=short",   # Short tracebacks
        "-q",           # Quiet unless verbose
    ])

    print(f"Running tests from: {TESTS}")
    print(f"Command: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=str(ROOT))
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
