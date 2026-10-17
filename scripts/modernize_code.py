#!/usr/bin/env python3
"""Run installed Rector, ESLint, and Stylelint tools in check or fix mode."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


def find_tool(root: Path, name: str) -> str | None:
    local = root / "vendor" / "bin" / name
    if name in {"eslint", "stylelint"}:
        local = root / "node_modules" / ".bin" / name
    if local.is_file():
        return str(local)
    return shutil.which(name)


def has_files(root: Path, extensions: set[str]) -> bool:
    return any(path.is_file() and path.suffix.lower() in extensions for path in root.rglob("*"))


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
    ]

    for label, extensions, tool_name, arguments in jobs:
        if not has_files(root, extensions):
            print(f"{label}: no matching files, skipped")
            continue
        tool = find_tool(root, tool_name)
        if tool is None:
            print(f"{label}: {tool_name} is not installed; skipped", file=sys.stderr)
            results.append(False)
            continue
        results.append(run_tool(label, [tool, *arguments]))

    if not results:
        print("No PHP, JavaScript, or CSS files found.")
        return 0
    if not all(results):
        return 1
    print("Modernization checks passed." if not args.write else "Modernization fixes completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())