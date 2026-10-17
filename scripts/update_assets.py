#!/usr/bin/env python3
"""Preview or apply asset-reference replacements in a website directory."""

import argparse
import json
from pathlib import Path
import sys


TEXT_EXTENSIONS = {".css", ".htm", ".html", ".js"}


def load_mapping(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    replacements = data.get("assets")
    if not isinstance(replacements, dict) or not replacements:
        raise ValueError('mapping must contain a non-empty "assets" object')
    if any(not isinstance(old, str) or not isinstance(new, str) for old, new in replacements.items()):
        raise ValueError("asset mapping keys and values must be strings")
    if any(not old for old in replacements):
        raise ValueError("asset mapping keys cannot be empty")
    return replacements


def update_file(path: Path, replacements: dict[str, str], write: bool) -> int:
    original = path.read_text(encoding="utf-8")
    updated = original
    count = 0
    for old, new in replacements.items():
        occurrences = updated.count(old)
        if occurrences:
            updated = updated.replace(old, new)
            count += occurrences
    if count and write:
        path.write_text(updated, encoding="utf-8")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Directory containing the website files")
    parser.add_argument("--mapping", type=Path, required=True, help="JSON file with old-to-new asset references")
    parser.add_argument("--write", action="store_true", help="Apply changes; without this flag, only preview")
    args = parser.parse_args()

    if not args.directory.is_dir():
        parser.error(f"not a directory: {args.directory}")

    try:
        replacements = load_mapping(args.mapping)
        changed_files = 0
        total_replacements = 0
        for path in sorted(args.directory.rglob("*")):
            if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
                count = update_file(path, replacements, args.write)
                if count:
                    changed_files += 1
                    total_replacements += count
                    print(f"{'Updated' if args.write else 'Would update'} {path}: {count} replacement(s)")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"update_assets: {error}", file=sys.stderr)
        return 1

    action = "Applied" if args.write else "Found"
    print(f"{action} {total_replacements} replacement(s) in {changed_files} file(s).")
    if not args.write:
        print("Preview only; pass --write to apply these changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())