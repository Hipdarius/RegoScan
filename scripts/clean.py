"""Cross-platform cleanup for local test/lint caches."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache"}
SKIP_DIRS = {".git", ".venv", "node_modules", ".next", ".pio"}


def main() -> int:
    for dirpath, dirnames, _filenames in os.walk(ROOT, topdown=True, onerror=lambda _e: None):
        for name in list(dirnames):
            path = Path(dirpath) / name
            if name in DIR_NAMES:
                shutil.rmtree(path, ignore_errors=True)
                dirnames.remove(name)
            elif name in SKIP_DIRS:
                dirnames.remove(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
