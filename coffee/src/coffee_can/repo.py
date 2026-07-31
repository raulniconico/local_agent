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

from .paths import MAX_IMAGES_PER_BEAN, images_dir

FLAVOR_AXES = (
    ("flavor_fruity", "Fruity"),
    ("flavor_floral", "Floral"),
    ("flavor_sweet", "Sweet"),
    ("flavor_nutty_cocoa", "Nutty/Cocoa"),
    ("flavor_spices", "Spices"),
    ("flavor_roasted", "Roasted"),
    ("flavor_cereal", "Cereal"),
    ("flavor_green_vegetative", "Green/Vegetative"),
    ("flavor_sour_fermented", "Sour/Fermented"),
)
FLAVOR_FIELDS = tuple(field for field, _ in FLAVOR_AXES)

BEAN_FIELDS = (
    "name",
    "origin",
    "variety",
    "altitude",
    "roaster",
    "producer",
    "process",
    "roast_date",
    "flavor_source",
) + FLAVOR_FIELDS

SESSION_FIELDS = (
    "brew_date",
    "dripper",
    "filter_paper",
    "grinder",
    "grind_size",
    "water_ppm",
    "humidity",
    "dose_g",
    "score",
    "note",
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
) -> int:
    next_number = conn.execute(
        "SELECT COALESCE(MAX(stage_number), 0) + 1 AS n FROM brew_stages WHERE session_id = ?",
        (session_id,),
    ).fetchone()["n"]
    conn.execute(
        """
        INSERT INTO brew_stages (session_id, stage_number, temperature_c, water_g, time_seconds, circling)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (session_id, next_number, temperature_c, water_g, time_seconds, circling),
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
) -> None:
    row = conn.execute("SELECT session_id FROM brew_stages WHERE id = ?", (stage_id,)).fetchone()
    if row is None:
        return
    conn.execute(
        "UPDATE brew_stages SET temperature_c = ?, water_g = ?, time_seconds = ?, circling = ? WHERE id = ?",
        (temperature_c, water_g, time_seconds, circling, stage_id),
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
