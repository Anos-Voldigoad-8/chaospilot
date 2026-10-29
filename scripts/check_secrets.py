#!/usr/bin/env python3
"""Fast, dependency-free secret guard for staged files.

This is a second line of defence behind gitleaks. It intentionally errs on the
side of blocking a commit: false positives can be resolved by replacing the
value with an obvious placeholder.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

BLOCKED_NAMES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.staging",
    ".env.test",
}
BLOCKED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".db", ".sqlite", ".sqlite3")
ALLOWED_FILES = {"scripts/check_secrets.py"}

# Built from fragments so this scanner does not flag itself.
PRIVATE_KEY_MARKER = "PRIVATE " + "KEY"
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private key material", re.compile(r"BEGIN [A-Z ]*" + re.escape(PRIVATE_KEY_MARKER))),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    (
        "hardcoded credential assignment",
        re.compile(
            r"(?i)(api[_-]?key|secret|token|password|passwd|pwd)"
            r"\s*[:=]\s*[\"']([A-Za-z0-9_\-]{24,})[\"']"
        ),
    ),
]
PLACEHOLDER_HINTS = (
    "your-",
    "example",
    "placeholder",
    "replace",
    "changeme",
    "<",
    "xxx",
    "${",
    "import.meta.env",
    "os.getenv",
    "os.environ",
    "settings.",
)


def staged_files() -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def staged_content(path: str) -> str:
    result = subprocess.run(
        ["git", "show", f":{path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def is_allowed_line(line: str) -> bool:
    lowered = line.lower()
    return any(hint in lowered for hint in PLACEHOLDER_HINTS)


def scan() -> list[str]:
    problems: list[str] = []
    for path in staged_files():
        name = Path(path).name
        if name in BLOCKED_NAMES or path.endswith(BLOCKED_SUFFIXES):
            problems.append(f"{path}: sensitive file must never be committed")
            continue

        content = staged_content(path)
        if not content or "\x00" in content:
            continue

        for line_number, line in enumerate(content.splitlines(), start=1):
            if is_allowed_line(line):
                continue
            for label, pattern in PATTERNS:
                if pattern.search(line):
                    problems.append(f"{path}:{line_number}: possible {label}")
                    break
    return problems


def main() -> int:
    problems = scan()
    if not problems:
        print("secret-safety-guard: no secrets found in staged files")
        return 0

    print("secret-safety-guard: commit blocked\n", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    print(
        "\nRemove the value, load it from an environment variable, and rotate the"
        " credential if it was real.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
