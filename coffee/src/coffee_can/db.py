"""SQLite connection and schema management."""

import os
import sqlite3
from pathlib import Path

from . import paths, repo
from .paths import db_path
from .repo import FLAVOR_FIELDS

SCHEMA = """
CREATE TABLE IF NOT EXISTS beans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    origin      TEXT,
    variety     TEXT,
    altitude    TEXT,
    roaster     TEXT,
    producer    TEXT,
    process     TEXT,
    roast_date  TEXT,
    note        TEXT,
    status      TEXT NOT NULL DEFAULT 'draft',
    flavor_source TEXT NOT NULL DEFAULT 'auto',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
    {flavor_columns}
);

CREATE TABLE IF NOT EXISTS bean_images (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    bean_id   INTEGER NOT NULL REFERENCES beans(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    rotation  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS brew_sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    bean_id      INTEGER NOT NULL REFERENCES beans(id) ON DELETE CASCADE,
    brew_date    TEXT,
    dripper      TEXT,
    filter_paper TEXT,
    grinder      TEXT,
    grind_size   TEXT,
    water_ppm    TEXT,
    humidity     TEXT,
    dose_g       REAL,
    score        REAL,
    extraction   REAL,
    note         TEXT,
    status       TEXT NOT NULL DEFAULT 'draft',
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
    {flavor_columns}
);

CREATE TABLE IF NOT EXISTS brew_stages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    INTEGER NOT NULL REFERENCES brew_sessions(id) ON DELETE CASCADE,
    stage_number  INTEGER NOT NULL,
    temperature_c REAL,
    water_g       REAL,
    time_seconds  INTEGER,
    circling      TEXT
);
""".format(flavor_columns="".join(f",\n    {field} REAL" for field in FLAVOR_FIELDS))


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after a user's database was first created."""
    bean_columns = {row["name"] for row in conn.execute("PRAGMA table_info(beans)")}
    if "flavor_source" not in bean_columns:
        conn.execute("ALTER TABLE beans ADD COLUMN flavor_source TEXT NOT NULL DEFAULT 'auto'")
        conn.commit()
    if "note" not in bean_columns:
        conn.execute("ALTER TABLE beans ADD COLUMN note TEXT")
        conn.commit()
    for field in FLAVOR_FIELDS:
        if field not in bean_columns:
            conn.execute(f"ALTER TABLE beans ADD COLUMN {field} REAL")
            conn.commit()

    image_columns = {row["name"] for row in conn.execute("PRAGMA table_info(bean_images)")}
    if "rotation" not in image_columns:
        conn.execute("ALTER TABLE bean_images ADD COLUMN rotation INTEGER NOT NULL DEFAULT 0")
        conn.commit()

    session_columns = {row["name"] for row in conn.execute("PRAGMA table_info(brew_sessions)")}
    if "filter_paper" not in session_columns:
        conn.execute("ALTER TABLE brew_sessions ADD COLUMN filter_paper TEXT")
        conn.commit()
    if "dose_g" not in session_columns:
        conn.execute("ALTER TABLE brew_sessions ADD COLUMN dose_g REAL")
        conn.commit()
    if "extraction" not in session_columns:
        # Left NULL for sessions logged before the extraction bar existed --
        # those were never assessed, which reads as "-" rather than being
        # silently backfilled as "Well extracted". A database that got this
        # column while it was briefly declared INTEGER keeps that
        # declaration, which is harmless: SQLite only narrows a REAL to an
        # INTEGER when the conversion is lossless, so fractional values
        # still round-trip intact.
        conn.execute("ALTER TABLE brew_sessions ADD COLUMN extraction REAL")
        conn.commit()
    for field in FLAVOR_FIELDS:
        if field not in session_columns:
            conn.execute(f"ALTER TABLE brew_sessions ADD COLUMN {field} REAL")
            conn.commit()

    stage_columns = {row["name"] for row in conn.execute("PRAGMA table_info(brew_stages)")}
    if "water_g" not in stage_columns:
        conn.execute("ALTER TABLE brew_stages ADD COLUMN water_g REAL")
        conn.commit()

    _migrate_split_sour_fermented(conn)
    _migrate_image_paths(conn)


def _migrate_split_sour_fermented(conn: sqlite3.Connection) -> None:
    """Carry ratings recorded against the old combined "Sour/Fermented" axis
    over to "Sour", which replaced it alongside a new "Fermented" axis.

    A combined score doesn't say how much of it was which, so there is no
    honest way to divide it: the whole value moves to Sour and Fermented is
    left unrated, rather than inventing a Fermented score or double-counting
    the same number on both axes (which would skew every average and radar
    that reads them). Re-rate those sessions by hand if the character was
    actually fermented.

    The retired column is left in place -- unreferenced, but dropping it
    would throw away the only record of what the original rating covered.
    Only ever fills a NULL, so it neither repeats on later startups nor
    overwrites a rating entered since.
    """
    old = repo._RETIRED_FLAVOR_FIELD
    for table in ("beans", "brew_sessions"):
        columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        if old not in columns or "flavor_sour" not in columns:
            continue
        conn.execute(
            f"UPDATE {table} SET flavor_sour = {old} "
            f"WHERE flavor_sour IS NULL AND {old} IS NOT NULL"
        )
        conn.commit()


def _migrate_image_paths(conn: sqlite3.Connection) -> None:
    """Rewrite bean_images.file_path entries left pointing at the pre-rename
    data dir. paths.data_dir() moves the folder on disk (coffee-journal ->
    coffee-can), but that move doesn't touch absolute paths already stored
    in the database -- without this, every uploaded page's file_path points
    at a directory that no longer exists.
    """
    base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    old_prefix = str(base / paths._OLD_APP_DIR_NAME)
    new_prefix = str(base / paths.APP_DIR_NAME)
    if old_prefix == new_prefix:
        return
    like_pattern = old_prefix + os.sep + "%"
    rows = conn.execute("SELECT id, file_path FROM bean_images WHERE file_path LIKE ?", (like_pattern,)).fetchall()
    for row in rows:
        new_path = new_prefix + row["file_path"][len(old_prefix):]
        conn.execute("UPDATE bean_images SET file_path = ? WHERE id = ?", (new_path, row["id"]))
    if rows:
        conn.commit()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn
