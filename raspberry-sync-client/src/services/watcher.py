"""Filesystem watcher that detects new `.dicom` files."""

from __future__ import annotations

import asyncio
import os
from fnmatch import fnmatch
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.core.logging import get_logger

log = get_logger("watcher")


class _Handler(FileSystemEventHandler):
    def __init__(self, queue: asyncio.Queue[str], glob: str, loop: asyncio.AbstractEventLoop) -> None:
        self._queue = queue
        self._glob = glob
        self._loop = loop

    def _emit(self, path: str) -> None:
        if not fnmatch(os.path.basename(path), self._glob):
            return
        self._loop.call_soon_threadsafe(self._queue.put_nowait, path)

    def on_created(self, event) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        self._emit(event.src_path)

    def on_moved(self, event) -> None:  # type: ignore[override]
        # Atomic-rename writers (write to .part, then os.replace) land here, not
        # on_created. Without this, inotify-friendly producers like dicom-server
        # become invisible to the watcher.
        if event.is_directory:
            return
        dest = getattr(event, "dest_path", None) or event.src_path
        self._emit(dest)


class FileWatcher:
    def __init__(self, directory: str, glob: str, queue: asyncio.Queue[str]) -> None:
        self._dir = Path(directory)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._glob = glob
        self._queue = queue
        self._observer = Observer()

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        handler = _Handler(self._queue, self._glob, loop)
        self._observer.schedule(handler, str(self._dir), recursive=False)
        self._observer.start()
        log.info("watcher_started", directory=str(self._dir), glob=self._glob)

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join(timeout=5)

    def initial_scan(self) -> list[str]:
        return [
            str(p) for p in self._dir.iterdir() if p.is_file() and fnmatch(p.name, self._glob)
        ]
