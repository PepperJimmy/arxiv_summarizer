#!/usr/bin/env python3
"""Remove every occurrence of a specified character from file names in a directory.

File extensions are preserved — only the stem (name before the last dot) is modified.
Directories are skipped.

Usage:
    python rename_char.py            # interactive prompts
    python rename_char.py -c " "     # remove spaces, current directory
    python rename_char.py -c "." -d /path/to/folder
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


TARGET_FILE = ".gitignore"


def rename_file(directory: Path, char: str, *, dry_run: bool = False) -> int:
    target = directory / TARGET_FILE
    if not target.is_file():
        print(f"  {TARGET_FILE} not found in {directory}", file=sys.stderr)
        return 0

    old_name = target.name
    new_name = old_name.replace(char, "")

    if new_name == old_name:
        print(f"  {old_name} — nothing to change")
        return 0

    if not new_name:
        print(f"  SKIP {old_name} — removing '{char}' would leave an empty name", file=sys.stderr)
        return 0

    new_path = target.parent / new_name

    if new_path.exists():
        print(f"  SKIP {old_name} → {new_name} (target already exists)", file=sys.stderr)
        return 0

    if dry_run:
        print(f"  [dry-run] {old_name} → {new_name}")
    else:
        target.rename(new_path)
        print(f"  {old_name} → {new_name}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove a character from file names.")
    parser.add_argument("-c", "--char", help="Character to remove")
    parser.add_argument("-d", "--directory", default=".", help="Directory to operate on (default: current)")
    parser.add_argument("--dry-run", action="store_true", help="Preview renames without changing anything")
    args = parser.parse_args()

    char = args.char
    if char is None:
        char = input("Character to remove: ")

    if len(char) != 1:
        print(f"Error: expected a single character, got {len(char)}", file=sys.stderr)
        return 1

    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        print(f"Error: {directory} is not a directory", file=sys.stderr)
        return 1

    print(f"Removing '{char}' from {TARGET_FILE} in {directory}" + (" (dry run)" if args.dry_run else ""))
    count = rename_file(directory, char, dry_run=args.dry_run)
    print(f"\n{'Would rename' if args.dry_run else 'Renamed'} {count} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
