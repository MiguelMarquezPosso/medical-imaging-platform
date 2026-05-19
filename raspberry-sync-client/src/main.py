"""Entry point — supervises the watcher, retry loop and connectivity probe.

Flow per file:
    1. Watcher (or initial scan, or periodic retry) finds a .dicom file.
    2. Compute sha256, enqueue in the local SQLite state store (dedup).
    3. When the network is reachable, drain the queue:
        - read the file
        - AES-256-GCM encrypt with AAD = device_id
        - POST to /sync/upload with X-Sync-Device-Id + optional X-Sync-Signature
        - on 201/204 / 409 (duplicate) → mark uploaded; if DELETE_AFTER_UPLOAD
          is true, also move to ARCHIVE_DIR
        - on 4xx (non-409) → move to QUARANTINE_DIR, mark quarantined
        - on 5xx / network → mark failed, retry later (exponential backoff)
"""

from __future__ import annotations

import asyncio
import signal
from pathlib import Path

from src.core.config import Settings, get_settings
from src.core.logging import configure, get_logger
from src.services.auth_client import AuthClient
from src.services.connectivity import is_online
from src.services.crypto import SyncCrypto
from src.services.state_store import StateStore
from src.services.uploader import Uploader
from src.services.watcher import FileWatcher
from src.utils.files import move_safely, sha256_file

log = get_logger("supervisor")


class Supervisor:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=10_000)
        self._stop = asyncio.Event()
        self._state = StateStore(settings.STATE_DB)
        self._auth = AuthClient(settings)
        self._crypto = SyncCrypto(
            settings.SYNC_AES_KEY_BASE64, settings.SYNC_HMAC_KEY_BASE64
        )
        self._uploader = Uploader(settings, self._auth, self._crypto)
        self._watcher = FileWatcher(settings.WATCH_DIR, settings.WATCH_GLOB, self._queue)
        self._sem = asyncio.Semaphore(settings.MAX_CONCURRENCY)

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        self._watcher.start(loop)
        for path in self._watcher.initial_scan():
            self._enqueue_if_new(path)

        tasks = [
            asyncio.create_task(self._worker(), name="upload-worker"),
            asyncio.create_task(self._retry_loop(), name="retry-loop"),
        ]
        await self._stop.wait()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._watcher.stop()

    def shutdown(self) -> None:
        log.info("shutdown_requested")
        self._stop.set()

    # ----- queueing ----------------------------------------------------------
    def _enqueue_if_new(self, path: str) -> None:
        try:
            size = Path(path).stat().st_size
        except FileNotFoundError:
            return
        sha = sha256_file(path)
        if not self._state.enqueue(path, sha, size):
            # Already known (path PK or sha unique). The retry loop handles
            # pending/failed entries explicitly; don't re-queue 'uploaded' files.
            return
        log.info("file_queued", path=path, size=size)
        try:
            self._queue.put_nowait(path)
        except asyncio.QueueFull:
            log.warning("queue_full_dropping_event", path=path)

    # ----- worker ------------------------------------------------------------
    async def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                path = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            asyncio.create_task(self._handle_one(path))

    async def _handle_one(self, path: str) -> None:
        async with self._sem:
            if not await is_online(str(self._settings.API_BASE_URL)):
                log.info("offline_deferring", path=path)
                return  # retry loop will pick it up
            try:
                data = await asyncio.to_thread(self._read_file, path)
            except FileNotFoundError:
                log.warning("file_gone_before_upload", path=path)
                return

            try:
                result = await self._uploader.upload(data)
            except Exception as exc:  # noqa: BLE001
                # 4xx -> quarantine; 5xx/network -> retry later
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status and 400 <= status < 500 and status != 409:
                    try:
                        quarantined = move_safely(path, self._settings.QUARANTINE_DIR)
                    except (FileNotFoundError, PermissionError):
                        quarantined = path
                    self._state.mark_quarantined(path, f"{status}: {exc}")
                    log.error("upload_quarantined", path=path, error=str(exc), moved_to=quarantined)
                else:
                    self._state.mark_failed(path, str(exc))
                    log.warning("upload_failed_will_retry", path=path, error=str(exc))
                return

            self._state.mark_uploaded(path)
            if self._settings.DELETE_AFTER_UPLOAD:
                try:
                    archived = move_safely(path, self._settings.ARCHIVE_DIR)
                    log.info("upload_ok", path=path, archived=archived, result=result)
                except (PermissionError, OSError) as exc:
                    # Upload already succeeded — do NOT revert state on archive failure.
                    log.warning(
                        "upload_ok_archive_failed",
                        path=path,
                        error=str(exc),
                        hint="medimg user lacks write/unlink on WATCH_DIR",
                    )
            else:
                log.info("upload_ok", path=path, kept_in_place=True, result=result)

    @staticmethod
    def _read_file(path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    # ----- retry loop --------------------------------------------------------
    async def _retry_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._settings.RETRY_INTERVAL_SECONDS)
                return
            except asyncio.TimeoutError:
                pass
            if not await is_online(str(self._settings.API_BASE_URL)):
                continue
            pending = self._state.list_pending(limit=100)
            for path, _sha, _size, _attempts in pending:
                if Path(path).exists():
                    try:
                        self._queue.put_nowait(path)
                    except asyncio.QueueFull:
                        break


def main() -> None:
    settings = get_settings()
    configure(settings.LOG_LEVEL)
    supervisor = Supervisor(settings)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, supervisor.shutdown)
        except NotImplementedError:
            # Windows: signal handlers via signal.signal()
            signal.signal(sig, lambda *_: supervisor.shutdown())
    try:
        loop.run_until_complete(supervisor.run())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
