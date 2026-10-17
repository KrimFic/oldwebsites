#!/usr/bin/env python3
"""Check or safely apply configured PHP, JavaScript, CSS, and HTML fixes."""

import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


IGNORED_DIRECTORIES = {".git", "__pycache__", "node_modules", "vendor"}
SOURCE_EXTENSIONS = {".php", ".js", ".mjs", ".cjs", ".css", ".html", ".htm"}
TOOLKIT_ROOT = Path(__file__).resolve().parent.parent


def find_tool(root: Path, name: str) -> str | None:
    local = root / "vendor" / "bin" / name
    roots = [root, TOOLKIT_ROOT]
    for tool_root in roots:
        local = tool_root / "vendor" / "bin" / name
        if name in {"eslint", "stylelint", "prettier"}:
            local = tool_root / "node_modules" / ".bin" / name
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


def run_command(label: str, command: list[str], cwd: Path) -> bool:
    print(f"{label}: {' '.join(command)}")
    try:
        return subprocess.run(command, cwd=cwd, check=False).returncode == 0
    except OSError as error:
        print(f"{label}: could not run command: {error}", file=sys.stderr)
        return False


def create_backup(root: Path, files: list[Path]) -> tuple[Path, dict[Path, Path]]:
    backup = Path(tempfile.mkdtemp(prefix="oldwebsites-modernize-backup-"))
    saved_files = {}
    for source in files:
        relative = source.relative_to(root)
        target = backup / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        saved_files[relative] = target
    return backup, saved_files


def restore_backup(root: Path, saved_files: dict[Path, Path]) -> None:
    for relative, backup_file in saved_files.items():
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup_file, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="Project or source directory to inspect")
    parser.add_argument("--write", action="store_true", help="Apply fixes after creating a backup")
    parser.add_argument(
        "--test-command",
        help="Required with --write; test command run from the project directory, e.g. 'npm test'",
    )
    parser.add_argument(
        "--php-target",
        choices=("8.1", "8.2", "8.3", "8.4", "8.5"),
        default="8.5",
        help="PHP upgrade target for Rector (default: 8.5)",
    )
    args = parser.parse_args()
    root = args.directory.resolve()
    if not root.is_dir():
        parser.error(f"not a directory: {args.directory}")
    if args.write and not args.test_command:
        parser.error("--write requires --test-command so changes can be validated")
    os.environ["OLDWEBSITES_PHP_TARGET"] = args.php_target

    test_command = []
    if args.test_command:
        try:
            test_command = shlex.split(args.test_command)
        except ValueError as error:
            parser.error(f"invalid --test-command: {error}")
        if not test_command:
            parser.error("--test-command cannot be empty")

    specifications = [
        ("PHP", {".php"}, "rector"),
        ("JavaScript", {".js", ".mjs", ".cjs"}, "eslint"),
        ("CSS", {".css"}, "prettier"),
        ("HTML", {".html", ".htm"}, "prettier"),
    ]
    planned_commands = []
    affected_files = []
    missing_tools = False

    for label, extensions, tool_name in specifications:
        files = source_files(root, extensions)
        if not files:
            print(f"{label}: no matching files, skipped")
            continue
        affected_files.extend(files)
        tool = find_tool(root, tool_name)
        if tool is None:
            print(f"{label}: {tool_name} is not installed; skipped", file=sys.stderr)
            missing_tools = True
            continue

        file_arguments = [str(path) for path in files]
        if tool_name == "rector":
            command = [tool, "process", *file_arguments, "--config", str(TOOLKIT_ROOT / "rector.php")]
            if not args.write:
                command.append("--dry-run")
        elif tool_name == "eslint":
            node = shutil.which("node")
            lebab = TOOLKIT_ROOT / "node_modules" / "lebab"
            if node is None or not lebab.is_dir():
                print("JavaScript: install Node.js and run npm install in the toolkit directory", file=sys.stderr)
                missing_tools = True
            else:
                converter = Path(__file__).with_name("es5_to_es6.cjs")
                mode = "--write" if args.write else "--check"
                planned_commands.append(("ES5 to ES6", [node, str(converter), mode, *file_arguments]))
            command = [tool, "--config", str(TOOLKIT_ROOT / "eslint.config.mjs"), *file_arguments]
            if args.write:
                command.append("--fix")
        elif tool_name == "prettier":
            if label == "CSS":
                node = shutil.which("node")
                postcss = TOOLKIT_ROOT / "node_modules" / "postcss"
                if node is None or not postcss.is_dir():
                    print("CSS: install Node.js and run npm install in the toolkit directory", file=sys.stderr)
                    missing_tools = True
                else:
                    converter = Path(__file__).with_name("css_migrate.mjs")
                    mapping = TOOLKIT_ROOT / "css_migrations.json"
                    mode = "--write" if args.write else "--check"
                    planned_commands.append(("CSS declaration migrations", [node, str(converter), mode, str(mapping), *file_arguments]))
            elif label == "HTML":
                node = shutil.which("node")
                parse5 = TOOLKIT_ROOT / "node_modules" / "parse5"
                if node is None or not parse5.is_dir():
                    print("HTML: install Node.js and run npm install in the toolkit directory", file=sys.stderr)
                    missing_tools = True
                else:
                    converter = Path(__file__).with_name("html5_normalize.mjs")
                    mode = "--write" if args.write else "--check"
                    mapping = TOOLKIT_ROOT / "html_migrations.json"
                    planned_commands.append(("HTML5 normalization", [node, str(converter), mode, str(mapping), *file_arguments]))
            command = [
                tool,
                "--config",
                str(TOOLKIT_ROOT / ".prettierrc.json"),
                "--write" if args.write else "--check",
                *file_arguments,
            ]
        else:
            command = [tool, *file_arguments]
        planned_commands.append((label, command))

    if missing_tools:
        print("Install and configure every required tool before running modernization.", file=sys.stderr)
        return 1
    if not affected_files:
        print("No PHP, JavaScript, CSS, or HTML files found.")
        return 0

    backup = None
    saved_files = {}
    if args.write:
        try:
            backup, saved_files = create_backup(root, affected_files)
        except OSError as error:
            print(f"Could not back up source files: {error}", file=sys.stderr)
            return 1
        print(f"Backup created at {backup}")

    for label, command in planned_commands:
        if not run_command(label, command, root):
            if args.write:
                restore_backup(root, saved_files)
                print(f"Changes rolled back. Original files are backed up at {backup}.", file=sys.stderr)
            return 1

    if args.write and not run_command("Tests", test_command, root):
        restore_backup(root, saved_files)
        print(f"Tests failed; changes rolled back. Original files are backed up at {backup}.", file=sys.stderr)
        return 1

    print("Checks passed." if not args.write else f"Fixes and tests passed. Backup retained at {backup}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())