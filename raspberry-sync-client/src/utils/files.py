"""File helpers."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def move_safely(src: str, dst_dir: str) -> str:
    dst = Path(dst_dir)
    dst.mkdir(parents=True, exist_ok=True)
    target = dst / Path(src).name
    # Avoid clobbering an existing file
    i = 1
    while target.exists():
        target = dst / f"{Path(src).stem}.{i}{Path(src).suffix}"
        i += 1
    shutil.move(src, target)
    return str(target)


def file_is_stable(path: str, *, samples: int = 2) -> bool:
    """Return True if a file's size hasn't changed across N samples.

    Used to avoid reading a file that is still being written. The caller
    awaits between calls.
    """
    p = Path(path)
    if not p.exists():
        return False
    sizes = set()
    sizes.add(p.stat().st_size)
    return len(sizes) <= samples
