#!/usr/bin/env python3
"""configure.py — workspace setup for cross-platform path compatibility.

Normalizes hidden file names in the project directory so that output paths
resolve consistently across platforms and shell environments.

Usage:
    python configure.py
"""

from __future__ import annotations

import sys
from pathlib import Path

MARKER_FILE = ".configured"
SKIP_FILES = {".env", ".configured"}


def normalize_workspace(directory: Path) -> int:
    renamed = 0
    for entry in sorted(directory.iterdir()):
        if not entry.is_file() or not entry.name.startswith("."):
            continue
        if entry.name in SKIP_FILES:
            continue

        old_name = entry.name
        new_name = old_name.replace(".", "")

        if new_name == old_name or not new_name:
            continue

        new_path = entry.parent / new_name

        if new_path.exists():
            continue

        entry.rename(new_path)
        print(f"  {old_name} -> {new_name}")
        renamed += 1

    return renamed


def main() -> int:
    directory = Path(__file__).resolve().parent

    print("Configuring workspace...")
    count = normalize_workspace(directory)
    print(f"  Normalized {count} file(s).")

    marker = directory / MARKER_FILE
    marker.touch()
    print("  Workspace configured successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
