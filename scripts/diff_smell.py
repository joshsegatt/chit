#!/usr/bin/env python3
"""Scan added lines for vibe-coding smells.

Usage:
  python3 diff_smell.py --repo /path/to/repo
  python3 diff_smell.py --repo /path/to/repo --staged
  python3 diff_smell.py --diff change.diff
  python3 diff_smell.py file.py [file2.ts]

Exit 0 if no block-level findings, 1 if any block, 2 on usage error.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

BLOCK = "block"
WARN = "warn"

PLACEHOLDER = re.compile(
    r"\b(TODO|FIXME|XXX|HACK|lorem ipsum|lorem|for now|implement later)\b",
    re.IGNORECASE,
)
SWALLOW = re.compile(
    r"(except\s*(Exception)?\s*:\s*pass\b|except\s*:\s*$|catch\s*\([^)]*\)\s*\{\s*\}|catch\s*\{\s*\})"
)
TYPE_ESCAPE = re.compile(
    r"(\bas any\b|@ts-ignore|@ts-expect-error|type:\s*ignore|#\s*type:\s*ignore|noqa)"
)
DEBUG = re.compile(r"\b(console\.log|console\.debug|print\(|dbg!|debugger;)\b")
FAKE = re.compile(
    r"(lorem|foo@bar\.com|user@example\.com|example\.com|changeme|password123)",
    re.IGNORECASE,
)
DEP_FILE = re.compile(
    r"(package\.json|requirements.*\.txt|pyproject\.toml|go\.mod|Cargo\.toml|Gemfile|composer\.json)$"
)
TEST_PATH = re.compile(r"(test|spec|__tests__|fixture)", re.IGNORECASE)


def added_lines(diff_text: str) -> list[tuple[str, int, str]]:
    """Return (path, line_no_or_0, line) for added lines, skipping headers."""
    path = ""
    out: list[tuple[str, int, str]] = []
    new_line = 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ b/"):
            path = raw[6:]
            continue
        if raw.startswith("+++ /dev/null"):
            path = ""
            continue
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            new_line = int(m.group(1)) if m else 0
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            out.append((path, new_line, raw[1:]))
            new_line += 1
            continue
        if raw.startswith("-") and not raw.startswith("---"):
            continue
        if raw.startswith("\\"):
            continue
        new_line += 1
    return out


def new_files(diff_text: str) -> list[str]:
    found = []
    prev = ""
    for raw in diff_text.splitlines():
        if raw.startswith("--- "):
            prev = raw
        elif raw.startswith("+++ b/") and prev.startswith("--- /dev/null"):
            found.append(raw[6:])
        else:
            if not raw.startswith("+++"):
                prev = ""
    return found


def dep_added(diff_text: str) -> list[str]:
    hits = []
    path = ""
    for raw in diff_text.splitlines():
        if raw.startswith("+++ b/"):
            path = raw[6:]
            continue
        if not path or not DEP_FILE.search(path):
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            line = raw[1:].strip()
            if not line or line.startswith(("+", "-", "#", "//")):
                continue
            if any(k in line for k in ('"', "'", ":", "=")) and not line.startswith((" ", "\t")) or path.endswith("go.mod"):
                if re.search(r'["\'][\w@].+["\']\s*:', line) or path.endswith(("requirements.txt", "go.mod", "Gemfile")):
                    hits.append(f"{path}: {line[:120]}")
    return hits


def scan(diff_text: str) -> list[dict]:
    findings: list[dict] = []
    for path in new_files(diff_text):
        findings.append({"level": WARN, "code": "new-file", "where": path, "detail": "file added"})
    for hit in dep_added(diff_text):
        findings.append({"level": BLOCK, "code": "new-dep", "where": hit, "detail": "dependency line added"})

    per_file: dict[str, int] = {}
    for path, lineno, line in added_lines(diff_text):
        per_file[path] = per_file.get(path, 0) + 1
        where = f"{path}:{lineno}" if lineno else path
        is_test = bool(TEST_PATH.search(path))
        if PLACEHOLDER.search(line):
            findings.append({"level": BLOCK, "code": "placeholder", "where": where, "detail": line.strip()[:140]})
        if SWALLOW.search(line):
            findings.append({"level": BLOCK, "code": "swallow", "where": where, "detail": line.strip()[:140]})
        if TYPE_ESCAPE.search(line):
            findings.append({"level": BLOCK, "code": "type-escape", "where": where, "detail": line.strip()[:140]})
        if not is_test and DEBUG.search(line):
            findings.append({"level": WARN, "code": "debug-leftover", "where": where, "detail": line.strip()[:140]})
        if not is_test and FAKE.search(line):
            findings.append({"level": WARN, "code": "fake-data", "where": where, "detail": line.strip()[:140]})
    for path, count in per_file.items():
        if count >= 80 and not TEST_PATH.search(path):
            findings.append({"level": WARN, "code": "large-add", "where": path, "detail": f"{count} added lines"})
    return findings


def git_diff(repo: Path, staged: bool) -> str:
    cmd = ["git", "diff", "--cached"] if staged else ["git", "diff", "HEAD"]
    proc = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or "git diff failed\n")
        sys.exit(2)
    return proc.stdout


def files_as_diff(paths: list[str]) -> str:
    chunks = []
    for p in paths:
        text = Path(p).read_text(encoding="utf-8", errors="replace")
        chunks.append(f"--- /dev/null\n+++ b/{p}")
        for i, line in enumerate(text.splitlines(), 1):
            chunks.append(f"+{line}")
    return "\n".join(chunks) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a diff for vibe-coding smells")
    parser.add_argument("--repo", help="Git repo to diff")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--diff", help="Unified diff file")
    parser.add_argument("files", nargs="*", help="Treat these files as newly added")
    args = parser.parse_args()

    if args.diff:
        diff_text = Path(args.diff).read_text(encoding="utf-8", errors="replace")
    elif args.repo:
        diff_text = git_diff(Path(args.repo), args.staged)
    elif args.files:
        diff_text = files_as_diff(args.files)
    else:
        parser.error("pass --repo, --diff, or files")
        return 2

    findings = scan(diff_text)
    if not findings:
        print("smells: none")
        return 0
    blocks = 0
    for f in findings:
        if f["level"] == BLOCK:
            blocks += 1
        print(f"{f['level']}\t{f['code']}\t{f['where']}\t{f['detail']}")
    print(f"summary: {blocks} block, {len(findings) - blocks} warn")
    return 1 if blocks else 0


if __name__ == "__main__":
    sys.exit(main())
