#!/usr/bin/env python3
"""Remove files from the vault that medimg-sync has confirmed uploaded.

Designed to run as root via /etc/cron.weekly when DELETE_AFTER_UPLOAD=false.

Reads /var/lib/medimg-sync/state.sqlite3 for rows where:
  - status = 'uploaded'
  - path is under MEDIMG_VAULT_PREFIX (default /mnt/dicom/)
  - updated_at is older than MEDIMG_VAULT_GRACE_DAYS (default 7) days

For each match: unlinks the file from the vault and deletes the SQLite row.

Env vars:
    MEDIMG_STATE_DB           default /var/lib/medimg-sync/state.sqlite3
    MEDIMG_VAULT_PREFIX       default /mnt/dicom/
    MEDIMG_VAULT_GRACE_DAYS   default 7

Usage:
    medimg-vault-cleanup            run for real
    medimg-vault-cleanup --dry-run  print what would happen, change nothing
"""

from __future__ import annotations

import os
import sqlite3
import sys
import syslog
from datetime import datetime, timedelta
from pathlib import Path

STATE_DB = os.environ.get("MEDIMG_STATE_DB", "/var/lib/medimg-sync/state.sqlite3")
VAULT_PREFIX = os.environ.get("MEDIMG_VAULT_PREFIX", "/mnt/dicom/")
GRACE_DAYS = int(os.environ.get("MEDIMG_VAULT_GRACE_DAYS", "7"))


def log(msg: str) -> None:
    syslog.syslog(msg)
    print(f"{datetime.now().isoformat(timespec='seconds')} {msg}")


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    syslog.openlog("medimg-vault-cleanup")

    if not Path(STATE_DB).exists():
        log(f"state DB not found at {STATE_DB}; nothing to do")
        return 0

    cutoff = datetime.utcnow() - timedelta(days=GRACE_DAYS)
    cutoff_iso = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    db = sqlite3.connect(STATE_DB)
    rows = db.execute(
        "SELECT path FROM files "
        "WHERE status = 'uploaded' "
        "  AND path LIKE ? "
        "  AND updated_at < ?",
        (VAULT_PREFIX + "%", cutoff_iso),
    ).fetchall()

    if not rows:
        log(f"no files to clean (grace={GRACE_DAYS}d, prefix={VAULT_PREFIX})")
        return 0

    log(f"candidates: {len(rows)} (dry_run={dry_run})")

    deleted = stale = skipped = 0
    for (path,) in rows:
        if not path.startswith(VAULT_PREFIX):
            # Defense in depth: SQL already filtered, but never delete outside the vault.
            log(f"REFUSED (outside vault): {path}")
            skipped += 1
            continue

        p = Path(path)
        if not p.exists():
            log(f"already gone: {path}")
            if not dry_run:
                db.execute("DELETE FROM files WHERE path = ?", (path,))
            stale += 1
            continue

        if dry_run:
            log(f"WOULD DELETE: {path} (size={p.stat().st_size})")
            continue

        try:
            p.unlink()
            db.execute("DELETE FROM files WHERE path = ?", (path,))
            log(f"deleted: {path}")
            deleted += 1
        except OSError as exc:
            log(f"unlink failed: {path}: {exc}")
            skipped += 1

    if not dry_run:
        db.commit()

    log(
        f"summary: deleted={deleted} stale_entries_removed={stale} "
        f"skipped={skipped} grace={GRACE_DAYS}d dry_run={dry_run}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
