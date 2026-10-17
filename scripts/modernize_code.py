#!/usr/bin/env python3
"""Run installed Rector, ESLint, Stylelint, and Prettier in check or fix mode."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


IGNORED_DIRECTORIES = {".git", "__pycache__", "node_modules", "vendor"}


def find_tool(root: Path, name: str) -> str | None:
    local = root / "vendor" / "bin" / name
    if name in {"eslint", "stylelint", "prettier"}:
        local = root / "node_modules" / ".bin" / name
    if local.is_file():
        return str(local)
    return shutil.which(name)


def source_files(root: Path, extensions: set[str]) -> list[Path]:
    files = []
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = [name for name in subdirectories if name not in IGNORED_DIRECTORIES]
        files.extend(
            Path(directory) / filename
            for filename in filenames
            if Path(filename).suffix.lower() in extensions
        )
    return sorted(files)


def run_tool(label: str, command: list[str]) -> bool:
    print(f"{label}: {' '.join(command)}")
    result = subprocess.run(command, check=False)
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Project or source directory to inspect")
    parser.add_argument("--write", action="store_true", help="Apply tool fixes; default mode only checks")
    args = parser.parse_args()
    root = args.directory.resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {args.directory}")

    results: list[bool] = []
    jobs = [
        ("PHP", {".php"}, "rector", ["process", str(root)] + ([] if args.write else ["--dry-run"])),
        ("JavaScript", {".js", ".mjs", ".cjs"}, "eslint", [str(root)] + (["--fix"] if args.write else [])),
        ("CSS", {".css"}, "stylelint", [str(root)] + (["--fix"] if args.write else [])),
        ("HTML", {".html", ".htm"}, "prettier", ["--write" if args.write else "--check"]),
    ]

    for label, extensions, tool_name, arguments in jobs:
        files = source_files(root, extensions)
        if not files:
            print(f"{label}: no matching files, skipped")
            continue
        tool = find_tool(root, tool_name)
        if tool is None:
            print(f"{label}: {tool_name} is not installed; skipped", file=sys.stderr)
            results.append(False)
            continue
        file_arguments = [str(path) for path in files] if tool_name == "prettier" else []
        results.append(run_tool(label, [tool, *arguments, *file_arguments]))

    if not results:
        print("No PHP, JavaScript, CSS, or HTML files found.")
        return 0
    if not all(results):
        return 1
    print("Modernization checks passed." if not args.write else "Modernization fixes completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())