"""The one place this server keeps user content, and only for allowlisted
test accounts.

WHAT THIS IS. `specs/legal-accounts.md` §3.8 binds the shipped architecture to
**no user content server-side**: the app says so on its privacy screen in three
languages, the Play Data safety form declares it, and desktop sync is a file
the user carries between their own two devices precisely so the developer never
holds a copy. This module is the deliberate exception, gated by
`config.SYNC_ALLOWED_EMAILS`, so that phone-to-phone sync can be *tried* before
anyone decides whether to reopen §3.8 and ship it. With that allowlist empty --
which is the default and what production runs -- nothing here is reachable.

WHAT IT STORES. One opaque blob per account: the same `SyncBundle` zip the
Android app already writes for desktop sync (`data/SyncBundle.kt`, and
`coffee_agent/sync_tools.py` on the other side). The server does not parse it,
merge it or look inside it -- the merge happens on the phone, which is the only
place that can ask the user anything. That keeps this module a dumb blob store
and keeps one format, one version number, one set of merge rules.

NAMED BY A HASH OF THE `sub`, not by the `sub` itself: the account id is
pseudonymous personal data (rule 61) and a directory listing is the easiest
place in a deployment to leak one by accident -- into a backup, a log line, a
support screenshot. The hash is one-way and stable, which is all the filename
has to be.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import config


def _blob_path(sub: str) -> Path:
    digest = hashlib.sha256(sub.encode("utf-8")).hexdigest()
    return config.SYNC_DIR / f"{digest}.zip"


def load(sub: str) -> bytes | None:
    """The account's stored bundle, or None if it has never uploaded one."""
    path = _blob_path(sub)
    if not path.exists():
        return None
    return path.read_bytes()


def store(sub: str, payload: bytes) -> None:
    """Replaces the account's bundle.

    WRITTEN TO A TEMPORARY FILE AND RENAMED, never opened in place. A phone
    that loses its connection halfway through an upload would otherwise leave a
    truncated zip where its whole log used to be, and the next device to sync
    would import a corrupt bundle -- or, worse, import half of one. `os.replace`
    is atomic within a filesystem, so a reader sees either the old bundle or the
    new one.
    """
    config.SYNC_DIR.mkdir(parents=True, exist_ok=True)
    path = _blob_path(sub)
    fd, tmp = tempfile.mkstemp(dir=str(config.SYNC_DIR), suffix=".part")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def delete(sub: str) -> None:
    """Drops the account's bundle. Called by `DELETE /v1/account`, because an
    account deletion that left the user's whole coffee log on the disk would be
    the erasure request answered with a lie."""
    _blob_path(sub).unlink(missing_ok=True)
