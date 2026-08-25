"""CRUD operations against the SQLite store.

Every write commits immediately so an interrupted interactive session (e.g.
Ctrl-C mid-prompt) never loses fields already answered -- that's what makes
"save as draft" a natural side effect rather than a separate code path.
"""

import shutil
import sqlite3
import uuid
from pathlib import Path
from typing import Optional

from .paths import MAX_IMAGES_PER_BEAN, images_dir, journey_images_dir

FLAVOR_AXES = (
    ("flavor_fruity", "Fruity"),
    ("flavor_floral", "Floral"),
    ("flavor_tea_like", "Tea-like"),
    ("flavor_sweet", "Sweet"),
    ("flavor_nutty_cocoa", "Nutty/Cocoa"),
    ("flavor_spices", "Spices"),
    ("flavor_roasted", "Roasted"),
    ("flavor_cereal", "Cereal"),
    ("flavor_green_vegetative", "Green/Vegetative"),
    ("flavor_sour", "Sour"),
    ("flavor_fermented", "Fermented"),
)
# Everything else -- table columns, migrations, sliders, radar charts, CLI
# output -- is derived from the tuple above, so an axis is added or split by
# editing it and nothing else. The one exception is data already recorded
# against a retired axis; see _migrate_split_sour_fermented in db.py.
_RETIRED_FLAVOR_FIELD = "flavor_sour_fermented"
FLAVOR_FIELDS = tuple(field for field, _ in FLAVOR_AXES)

# How the brew extracted, as a continuous signed offset from 0 ("well
# extracted") rather than discrete steps: under- and over-extraction are
# opposite failure modes either side of a target, so a symmetric scale is
# what the GUI's bar reads as, and 0 stays the natural centre. Keeping it
# falsy at the centre also means an untouched session still counts as empty
# for BrewDialog._is_empty()'s discard-on-close check.
EXTRACTION_MIN = -1.0
EXTRACTION_MAX = 1.0
# The three named zones the continuous value falls into, and where the outer
# two begin -- used to render a stored number back as words (the CLI) and to
# label the GUI bar. A third of the range each.
EXTRACTION_ZONES = ("Under extracted", "Well extracted", "Over extracted")
EXTRACTION_ZONE_EDGE = (EXTRACTION_MAX - EXTRACTION_MIN) / 6.0

# How *strong* the cup was, on the same signed scale and for the same reason:
# the other axis of the brewing control chart. A coffee can be fully extracted
# and still watery (too much water for the dose) or under-extracted and syrupy
# (too little), so one number cannot say both -- which is exactly the pair of
# mistakes a brew log is kept to tell apart. Added 2026-08-22, following the
# phone, which grew the slider first; the two now write the same column and it
# travels in a sync bundle (coffee_agent/sync_tools._SESSION_FIELDS).
#
# Symmetric like extraction, and not a 0..5 magnitude, because both ends are a
# miss: a cup twice as strong as you wanted is as wrong as one half as strong,
# and a scale running from light to strong would make one end look like the
# good one. Its centre is falsy for the same discard-on-close reason.
CONCENTRATION_MIN = -1.0
CONCENTRATION_MAX = 1.0
CONCENTRATION_ZONES = ("Too weak", "Just right", "Too strong")
CONCENTRATION_ZONE_EDGE = (CONCENTRATION_MAX - CONCENTRATION_MIN) / 6.0

BEAN_FIELDS = (
    "name",
    "origin",
    "variety",
    "altitude",
    "roaster",
    "producer",
    "process",
    "roast_date",
    "note",
    "flavor_source",
) + FLAVOR_FIELDS

SESSION_FIELDS = (
    "brew_date",
    "dripper",
    "filter_paper",
    "grinder",
    "grind_size",
    # Who made it -- moved off `journeys` on 2026-08-25. Storage only here; no
    # CLI or GUI surface reads it, and the allowlist is what lets it travel.
    "barista",
    "water_ppm",
    # Carbonate hardness (ppm as CaCO3), beside water_ppm's total dissolved
    # solids rather than instead of it.
    "water_alkalinity",
    "humidity",
    "dose_g",
    # Brew-level water and temperature, and how long the whole thing took.
    # Carried, not interpreted, exactly like flavor_notes below: no desktop
    # screen renders these three, and the columns exist so a
    # phone -> desktop -> phone round trip does not lose what the phone put
    # there. Note water_temp_c is the *brew's* temperature; a single pour's
    # lives on brew_stages.temperature_c and is unaffected.
    "water_g",
    "water_temp_c",
    "total_time_sec",
    # The cafe this was drunk at, or NULL for a brew made at home. Storage
    # only: nothing in the CLI or the GUI sets it, and nothing displays it.
    # It is here so a "cup" logged on the phone survives a round trip through
    # this database still attached to its cafe -- see db.py's schema comment
    # on the journeys table.
    "journey_id",
    "score",
    "extraction",
    "concentration",
    "note",
    # Carried, not interpreted: no desktop screen renders these, and the
    # column exists so a sync round trip through this database does not lose
    # what the phone put there. See db.py's migration note.
    "flavor_notes",
) + FLAVOR_FIELDS


class NotFoundError(Exception):
    pass


def _touch(conn: sqlite3.Connection, table: str, row_id: int) -> None:
    conn.execute(f"UPDATE {table} SET updated_at = datetime('now') WHERE id = ?", (row_id,))


def _update_field(conn: sqlite3.Connection, table: str, allowed: tuple, row_id: int, field: str, value) -> None:
    if field not in allowed:
        raise ValueError(f"unknown field {field!r} for {table}")
    conn.execute(f"UPDATE {table} SET {field} = ? WHERE id = ?", (value, row_id))
    _touch(conn, table, row_id)
    conn.commit()


# --- beans ---------------------------------------------------------------

def create_bean(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.execute("INSERT INTO beans (name) VALUES (?)", (name,))
    conn.commit()
    return cur.lastrowid


def update_bean_field(conn: sqlite3.Connection, bean_id: int, field: str, value) -> None:
    _update_field(conn, "beans", BEAN_FIELDS, bean_id, field, value)


def set_bean_status(conn: sqlite3.Connection, bean_id: int, status: str) -> None:
    conn.execute("UPDATE beans SET status = ? WHERE id = ?", (status, bean_id))
    _touch(conn, "beans", bean_id)
    conn.commit()


def get_bean(conn: sqlite3.Connection, bean_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM beans WHERE id = ?", (bean_id,)).fetchone()


def resolve_bean(conn: sqlite3.Connection, identifier: str) -> sqlite3.Row:
    if identifier.isdigit():
        row = get_bean(conn, int(identifier))
        if row:
            return row
    matches = conn.execute(
        "SELECT * FROM beans WHERE lower(name) = lower(?)", (identifier,)
    ).fetchall()
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise NotFoundError(f"multiple coffee profiles named {identifier!r}; use its numeric id instead")
    raise NotFoundError(f"no coffee profile found matching {identifier!r}")


def list_beans(conn: sqlite3.Connection):
    return conn.execute(
        """
        SELECT beans.*,
               (SELECT COUNT(*) FROM brew_sessions WHERE brew_sessions.bean_id = beans.id) AS session_count
        FROM beans
        ORDER BY beans.created_at DESC
        """
    ).fetchall()


def delete_bean(conn: sqlite3.Connection, bean_id: int) -> None:
    conn.execute("DELETE FROM beans WHERE id = ?", (bean_id,))
    conn.commit()


def add_bean_image(conn: sqlite3.Connection, bean_id: int, source_path: Path) -> int:
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM bean_images WHERE bean_id = ?", (bean_id,)
    ).fetchone()["n"]
    if count >= MAX_IMAGES_PER_BEAN:
        raise ValueError(f"this profile already has the maximum of {MAX_IMAGES_PER_BEAN} pages")

    position = conn.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 AS n FROM bean_images WHERE bean_id = ?", (bean_id,)
    ).fetchone()["n"]
    dest_dir = images_dir(bean_id)
    dest = dest_dir / f"{uuid.uuid4().hex}{source_path.suffix.lower()}"
    shutil.copy2(source_path, dest)

    conn.execute(
        "INSERT INTO bean_images (bean_id, position, file_path) VALUES (?, ?, ?)",
        (bean_id, position, str(dest)),
    )
    _touch(conn, "beans", bean_id)
    conn.commit()
    return position


def list_bean_images(conn: sqlite3.Connection, bean_id: int):
    return conn.execute(
        "SELECT * FROM bean_images WHERE bean_id = ? ORDER BY position", (bean_id,)
    ).fetchall()


def delete_bean_image(conn: sqlite3.Connection, image_id: int) -> None:
    row = conn.execute("SELECT * FROM bean_images WHERE id = ?", (image_id,)).fetchone()
    if row is None:
        return
    conn.execute("DELETE FROM bean_images WHERE id = ?", (image_id,))
    _touch(conn, "beans", row["bean_id"])
    conn.commit()
    Path(row["file_path"]).unlink(missing_ok=True)


def rotate_bean_image(conn: sqlite3.Connection, image_id: int, degrees: int = 90) -> int:
    """Rotate how a page is displayed (does not touch the source file). Returns the new rotation."""
    row = conn.execute("SELECT rotation, bean_id FROM bean_images WHERE id = ?", (image_id,)).fetchone()
    if row is None:
        return 0
    new_rotation = (row["rotation"] + degrees) % 360
    conn.execute("UPDATE bean_images SET rotation = ? WHERE id = ?", (new_rotation, image_id))
    _touch(conn, "beans", row["bean_id"])
    conn.commit()
    return new_rotation


# --- brew sessions ---------------------------------------------------------

def create_session(conn: sqlite3.Connection, bean_id: int) -> int:
    cur = conn.execute("INSERT INTO brew_sessions (bean_id) VALUES (?)", (bean_id,))
    conn.commit()
    return cur.lastrowid


def update_session_field(conn: sqlite3.Connection, session_id: int, field: str, value) -> None:
    _update_field(conn, "brew_sessions", SESSION_FIELDS, session_id, field, value)


def set_session_status(conn: sqlite3.Connection, session_id: int, status: str) -> None:
    conn.execute("UPDATE brew_sessions SET status = ? WHERE id = ?", (status, session_id))
    _touch(conn, "brew_sessions", session_id)
    conn.commit()


def get_session(conn: sqlite3.Connection, session_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM brew_sessions WHERE id = ?", (session_id,)).fetchone()


def resolve_session(conn: sqlite3.Connection, identifier: str) -> sqlite3.Row:
    if identifier.isdigit():
        row = get_session(conn, int(identifier))
        if row:
            return row
    raise NotFoundError(f"no brewing session found with id {identifier!r}")


def list_sessions(conn: sqlite3.Connection, bean_id: Optional[int] = None):
    if bean_id is None:
        return conn.execute(
            """
            SELECT brew_sessions.*, beans.name AS bean_name
            FROM brew_sessions JOIN beans ON beans.id = brew_sessions.bean_id
            ORDER BY brew_sessions.created_at DESC
            """
        ).fetchall()
    return conn.execute(
        """
        SELECT brew_sessions.*, beans.name AS bean_name
        FROM brew_sessions JOIN beans ON beans.id = brew_sessions.bean_id
        WHERE brew_sessions.bean_id = ?
        ORDER BY brew_sessions.created_at DESC
        """,
        (bean_id,),
    ).fetchall()


def delete_session(conn: sqlite3.Connection, session_id: int) -> None:
    conn.execute("DELETE FROM brew_sessions WHERE id = ?", (session_id,))
    conn.commit()


def count_sessions_by_date(conn: sqlite3.Connection) -> dict:
    """{'YYYY-MM-DD': n} for every date that has at least one brewing session."""
    rows = conn.execute(
        """
        SELECT brew_date, COUNT(*) AS n
        FROM brew_sessions
        WHERE brew_date IS NOT NULL AND brew_date != ''
        GROUP BY brew_date
        """
    ).fetchall()
    return {row["brew_date"]: row["n"] for row in rows}


# --- brew stages ------------------------------------------------------------

def add_stage(
    conn: sqlite3.Connection,
    session_id: int,
    temperature_c: Optional[float],
    water_g: Optional[float],
    time_seconds: Optional[int],
    circling: Optional[str],
    label: Optional[str] = None,
) -> int:
    """`label` is trailing and defaults to None so the four existing positional
    callers (the CLI, both GUI dialogs, the agent) keep working untouched. It
    names the pour -- "Bloom", "Second pour" -- and is not a synonym for
    `circling`, which says how the pour was circled; only sync writes it today.
    """
    next_number = conn.execute(
        "SELECT COALESCE(MAX(stage_number), 0) + 1 AS n FROM brew_stages WHERE session_id = ?",
        (session_id,),
    ).fetchone()["n"]
    conn.execute(
        """
        INSERT INTO brew_stages (session_id, stage_number, temperature_c, water_g, time_seconds, circling, label)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (session_id, next_number, temperature_c, water_g, time_seconds, circling, label),
    )
    _touch(conn, "brew_sessions", session_id)
    conn.commit()
    return next_number


def list_stages(conn: sqlite3.Connection, session_id: int):
    return conn.execute(
        "SELECT * FROM brew_stages WHERE session_id = ? ORDER BY stage_number", (session_id,)
    ).fetchall()


def get_stage(conn: sqlite3.Connection, stage_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM brew_stages WHERE id = ?", (stage_id,)).fetchone()


def update_stage(
    conn: sqlite3.Connection,
    stage_id: int,
    temperature_c: Optional[float],
    water_g: Optional[float],
    time_seconds: Optional[int],
    circling: Optional[str],
    label: Optional[str] = None,
) -> None:
    """`label` defaults to None for the same positional-caller reason as
    :func:`add_stage` -- but note the consequence: an existing caller that
    omits it *clears* the label, because this is a full-row update rather than
    a patch. Only the GUI stage editor calls this, and it has no label field to
    lose; give it one and it must pass the value through here too.
    """
    row = conn.execute("SELECT session_id FROM brew_stages WHERE id = ?", (stage_id,)).fetchone()
    if row is None:
        return
    conn.execute(
        "UPDATE brew_stages SET temperature_c = ?, water_g = ?, time_seconds = ?, circling = ?, label = ? WHERE id = ?",
        (temperature_c, water_g, time_seconds, circling, label, stage_id),
    )
    _touch(conn, "brew_sessions", row["session_id"])
    conn.commit()


def delete_stage(conn: sqlite3.Connection, stage_id: int) -> None:
    conn.execute("DELETE FROM brew_stages WHERE id = ?", (stage_id,))
    conn.commit()


# A session whose flavor sliders were never touched still gets every axis
# written as 0 the first time it's saved (BrewDialog._save() writes each
# slider's current value unconditionally) -- so an all-zero row means
# "never rated", not "rated zero on everything", and averaging it in would
# silently drag every bean's flavor profile toward zero.
_FLAVOR_UNRATED_CONDITION = " AND ".join(f"COALESCE({field}, 0) = 0" for field in FLAVOR_FIELDS)


def get_average_flavor_scores(conn: sqlite3.Connection):
    """(session_count, [mean per flavor axis in FLAVOR_AXES order]) across
    sessions that actually have a flavor rating, or (0, None) if none do."""
    columns = ", ".join(f"AVG({field}) AS {field}" for field in FLAVOR_FIELDS)
    row = conn.execute(
        f"SELECT COUNT(*) AS n, {columns} FROM brew_sessions WHERE NOT ({_FLAVOR_UNRATED_CONDITION})"
    ).fetchone()
    if row["n"] == 0:
        return 0, None
    return row["n"], [row[field] or 0 for field in FLAVOR_FIELDS]


def get_bean_average_flavor_scores(conn: sqlite3.Connection, bean_id: int):
    """Same as get_average_flavor_scores, scoped to one bean's own sessions."""
    columns = ", ".join(f"AVG({field}) AS {field}" for field in FLAVOR_FIELDS)
    row = conn.execute(
        f"SELECT COUNT(*) AS n, {columns} FROM brew_sessions "
        f"WHERE bean_id = ? AND NOT ({_FLAVOR_UNRATED_CONDITION})",
        (bean_id,),
    ).fetchone()
    if row["n"] == 0:
        return 0, None
    return row["n"], [row[field] or 0 for field in FLAVOR_FIELDS]


# --- journeys ---------------------------------------------------------------
#
# STORAGE WITHOUT A UI, ON PURPOSE. A journey is a cafe you went to, and this
# app has no screen for one -- `coffee_android` does. These functions exist so
# `coffee_agent/sync_tools.py` has somewhere to put a journey that arrives in a
# bundle, and somewhere to read one back from when a bundle goes the other way.
# Nothing in `cli.py` or `gui/` calls them, which is the intended state: the
# desktop's *schema* matches the phone's, its *interface* does not.
#
# Journeys match across devices BY NAME, the same limitation and the same
# reasoning as beans: the two id sequences are independent and mean nothing to
# each other. Two visits to one cafe are one journey on both sides, so the name
# is the identity; rename it on one device and it arrives as a second cafe.

JOURNEY_FIELDS = (
    "name",
    "location",
    "address",
    "barista",
    # Retired on the phone (2026-08-20) and retained there because migrations
    # are additive only. Kept here for the same reason: a device that still
    # holds coordinates needs somewhere to put them.
    "latitude",
    "longitude",
    # Epoch milliseconds, not a date string -- see db.py's schema comment.
    "visited_at",
    "note",
)


def create_journey(conn: sqlite3.Connection, name: str, visited_at: int) -> int:
    """`visited_at` is required because a visit you cannot date is not a visit
    you took -- JourneyEntity makes it non-null for the same reason, unlike
    `beans.roast_date`, where "not set" is a real and common state."""
    cur = conn.execute(
        "INSERT INTO journeys (name, visited_at) VALUES (?, ?)", (name, visited_at)
    )
    conn.commit()
    return cur.lastrowid


def update_journey_field(conn: sqlite3.Connection, journey_id: int, field: str, value) -> None:
    _update_field(conn, "journeys", JOURNEY_FIELDS, journey_id, field, value)


def list_journeys(conn: sqlite3.Connection):
    return conn.execute(
        "SELECT * FROM journeys ORDER BY visited_at DESC, id DESC"
    ).fetchall()


def get_journey(conn: sqlite3.Connection, journey_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM journeys WHERE id = ?", (journey_id,)).fetchone()


def delete_journey(conn: sqlite3.Connection, journey_id: int) -> None:
    """Deleting a cafe orphans its cups back into ordinary brews rather than
    destroying them: `brew_sessions.journey_id` carries no foreign key, so no
    cascade reaches them. The journey's own photographs *do* cascade, and their
    files are unlinked first for the same reason delete_bean_image exists --
    ON DELETE CASCADE knows nothing about the filesystem.
    """
    for row in list_journey_images(conn, journey_id):
        delete_journey_image(conn, row["id"])
    conn.execute("DELETE FROM journeys WHERE id = ?", (journey_id,))
    conn.commit()


def add_journey_image(conn: sqlite3.Connection, journey_id: int, source_path: Path) -> int:
    """Copies the file in, exactly as add_bean_image does -- a path handed to
    this function is a borrowed handle (an extracted zip member, a picker
    result), not a durable one."""
    position = conn.execute(
        "SELECT COALESCE(MAX(position), 0) + 1 AS n FROM journey_images WHERE journey_id = ?",
        (journey_id,),
    ).fetchone()["n"]
    dest = journey_images_dir(journey_id) / f"{uuid.uuid4().hex}{source_path.suffix.lower()}"
    shutil.copy2(source_path, dest)
    conn.execute(
        "INSERT INTO journey_images (journey_id, position, file_path) VALUES (?, ?, ?)",
        (journey_id, position, str(dest)),
    )
    _touch(conn, "journeys", journey_id)
    conn.commit()
    return position


def list_journey_images(conn: sqlite3.Connection, journey_id: int):
    return conn.execute(
        "SELECT * FROM journey_images WHERE journey_id = ? ORDER BY position", (journey_id,)
    ).fetchall()


def delete_journey_image(conn: sqlite3.Connection, image_id: int) -> None:
    row = conn.execute("SELECT * FROM journey_images WHERE id = ?", (image_id,)).fetchone()
    if row is None:
        return
    conn.execute("DELETE FROM journey_images WHERE id = ?", (image_id,))
    _touch(conn, "journeys", row["journey_id"])
    conn.commit()
    Path(row["file_path"]).unlink(missing_ok=True)


def list_sessions_for_journey(conn: sqlite3.Connection, journey_id: int):
    """The cups drunk at one cafe. Reads *from* the journey, which is what makes
    an unenforced `journey_id` safe: a dangling id is simply never looked up."""
    return conn.execute(
        "SELECT * FROM brew_sessions WHERE journey_id = ? ORDER BY brew_date DESC, id DESC",
        (journey_id,),
    ).fetchall()
