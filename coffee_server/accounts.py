"""The account record: what the server keeps, and nothing else.

WHAT THIS IS FOR. `specs/legal-accounts.md` §3.8 rule 58 rejects the phrase
"nothing is stored server-side": metering and abuse cutoff cannot work without
a record keyed to a user, and that record -- the Google `sub`, a counter, a
window, a ban flag -- is personal data under GDPR Recitals 26/30 even though it
is pseudonymous (rule 61: never call it anonymous). So the honest architecture
is "no user *content* server-side", and this module is the exact boundary of
what that exception covers.

WHAT IS DELIBERATELY ABSENT, and would be a rule 60 violation to add: email,
name, avatar, IP address, and any column that could hold a bean, a session, a
note or a photo. The `openid`-only scope the Android client requests is what
makes that absence enforceable rather than aspirational -- there is no email
here because the server is never told one.

Request payloads are NOT logged (rule 100, and `legal-android.md` rule 12): the
app's headline claim is that nothing of the user's is kept here, and a gateway
that logged request bodies would make it false while looking like a debugging
convenience.

SQLite because the whole dataset is one row per user plus counters. It is
served from a single container; if that ever becomes two, this moves to a
shared store and the WAL/`check_same_thread` choices below move with it.
"""

import sqlite3
import threading
import time
from typing import Optional

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    sub          TEXT PRIMARY KEY,
    created_at   INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,
    banned       INTEGER NOT NULL DEFAULT 0,
    ban_reason   TEXT
);

-- One row per (account, operation, UTC day). Rolls forward by insertion, so
-- there is no reset job to fail: yesterday's row simply stops being read.
CREATE TABLE IF NOT EXISTS usage (
    sub   TEXT NOT NULL,
    day   TEXT NOT NULL,
    op    TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (sub, day, op)
);

-- The sliding-window burst limiter. One row per request, pruned on read; this
-- is the only place a timestamp of an individual request exists, and it is
-- deleted as it ages out of the window.
CREATE TABLE IF NOT EXISTS rate_events (
    sub  TEXT NOT NULL,
    op   TEXT NOT NULL,
    at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS rate_events_idx ON rate_events (sub, op, at);
"""


class QuotaExceededError(Exception):
    """Daily cap reached. Retryable tomorrow, not now."""


class RateLimitedError(Exception):
    """Burst limit reached. Retryable in seconds."""


class AccountBannedError(Exception):
    """Abuse cutoff. The account exists and is refused."""


_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(config.ACCOUNT_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def touch(sub: str) -> None:
    """Records that this account exists and was seen. Idempotent.

    First call is account creation -- there is no separate sign-up step,
    because there is nothing to sign up *with*: the Google `sub` is the whole
    record.
    """
    now = int(time.time())
    with _lock:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO accounts (sub, created_at, last_seen_at) VALUES (?, ?, ?)
            ON CONFLICT(sub) DO UPDATE SET last_seen_at = excluded.last_seen_at
            """,
            (sub, now, now),
        )
        conn.commit()


def check_and_count(sub: str, op: str) -> None:
    """Authorises one metered call, or raises.

    Counted BEFORE the provider call, not after. A request that is going to
    cost money must be paid for out of quota even if the provider then fails --
    otherwise a client that reliably triggers a 502 gets unmetered retries,
    which is the cheapest possible abuse of a metered endpoint.
    """
    now = time.time()
    day = _today()
    window_start = now - config.RATE_LIMIT_WINDOW_SECONDS
    limit = config.DAILY_QUOTA.get(op)

    with _lock:
        conn = _connect()
        row = conn.execute("SELECT banned, ban_reason FROM accounts WHERE sub = ?", (sub,)).fetchone()
        if row is not None and row["banned"]:
            raise AccountBannedError(row["ban_reason"] or "account suspended")

        conn.execute("DELETE FROM rate_events WHERE at < ?", (now - config.RATE_LIMIT_WINDOW_SECONDS,))
        burst = conn.execute(
            "SELECT COUNT(*) AS n FROM rate_events WHERE sub = ? AND op = ? AND at >= ?",
            (sub, op, window_start),
        ).fetchone()["n"]
        if burst >= config.RATE_LIMIT_MAX_REQUESTS:
            raise RateLimitedError(
                f"more than {config.RATE_LIMIT_MAX_REQUESTS} '{op}' requests in "
                f"{config.RATE_LIMIT_WINDOW_SECONDS}s"
            )

        used = conn.execute(
            "SELECT count FROM usage WHERE sub = ? AND day = ? AND op = ?", (sub, day, op)
        ).fetchone()
        if limit is not None and used is not None and used["count"] >= limit:
            raise QuotaExceededError(f"daily '{op}' limit of {limit} reached")

        conn.execute(
            """
            INSERT INTO usage (sub, day, op, count) VALUES (?, ?, ?, 1)
            ON CONFLICT(sub, day, op) DO UPDATE SET count = count + 1
            """,
            (sub, day, op),
        )
        conn.execute("INSERT INTO rate_events (sub, op, at) VALUES (?, ?, ?)", (sub, op, now))
        conn.commit()


def access_record(sub: str) -> dict:
    """The GDPR Art. 15(3) access response, in full.

    `specs/legal-accounts.md` rule 93: this is the entire set of personal data
    the developer holds about a user -- the identifier, usage counters, quota
    state, rate-limit records. There is no second store, no archive and no
    photo bundle, because nothing else is ever written. Art. 20 portability
    does not engage (counters are observed/derived data), so this is an access
    document, not an export format.
    """
    with _lock:
        conn = _connect()
        account = conn.execute(
            "SELECT sub, created_at, last_seen_at, banned FROM accounts WHERE sub = ?", (sub,)
        ).fetchone()
        usage = conn.execute(
            "SELECT day, op, count FROM usage WHERE sub = ? ORDER BY day DESC, op", (sub,)
        ).fetchall()
        pending = conn.execute(
            "SELECT COUNT(*) AS n FROM rate_events WHERE sub = ?", (sub,)
        ).fetchone()["n"]

    return {
        "account": dict(account) if account else None,
        "usage": [dict(r) for r in usage],
        "rate_limit_events_currently_held": pending,
        "quota_per_day": dict(config.DAILY_QUOTA),
        "what_is_not_here": (
            "Your beans, brew sessions, notes and photos are on your phone only. "
            "This server has never received them and has no copy to give you."
        ),
    }


def delete(sub: str) -> None:
    """Erases the account and everything keyed to it. Art. 17.

    Hard DELETE, not a tombstone: a "deleted" flag on a row that still holds
    the identifier is not erasure, and the only reason to keep one -- stopping
    a banned user re-registering -- does not apply when the identifier comes
    from Google and the user could not change it anyway.
    """
    with _lock:
        conn = _connect()
        conn.execute("DELETE FROM rate_events WHERE sub = ?", (sub,))
        conn.execute("DELETE FROM usage WHERE sub = ?", (sub,))
        conn.execute("DELETE FROM accounts WHERE sub = ?", (sub,))
        conn.commit()
