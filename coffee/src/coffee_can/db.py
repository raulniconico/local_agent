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
    -- The farm (2026-08-26). Beside `producer`, not instead of it: a producer
    -- is a person or a cooperative, a farm is a place. Storage only here, the
    -- same as the roast block below.
    farm        TEXT,
    process     TEXT,
    roast_date  TEXT,
    -- The day the bag went into the freezer, ISO-8601, or NULL for a bag that
    -- did not (2026-08-26). One nullable date is the whole state -- there is
    -- deliberately no `frozen` flag beside it to disagree with.
    frozen_date TEXT,
    note        TEXT,
    -- The roast (2026-08-24). Mirrors BeanEntity's four; snake_case here,
    -- camelCase there, and sync_tools maps between them. No CLI or GUI reads
    -- these yet -- they exist so a phone -> desktop -> phone round trip does
    -- not drop them, the same reason `journeys` is here.
    roast_level    TEXT,
    color_value    TEXT,
    weight_loss    TEXT,
    expansion_rate TEXT,
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
    -- The cafe this was drunk at, or NULL for a brew made at home. A session
    -- with one is what the Android app calls a "cup".
    --
    -- DELIBERATELY NOT A FOREIGN KEY, matching SessionEntity.journeyId. A
    -- cascade here would delete a brew -- its stages, its score, its tasting
    -- notes -- because someone tidied away a cafe they no longer wanted
    -- listed. Deleting a journey should orphan its cups back into ordinary
    -- brews, which is what a plain nullable column does. Nothing enforces the
    -- reference, so a reader has to tolerate an id whose row is gone; every
    -- query here joins *from* the journey, so a dangling id is never looked up.
    journey_id   INTEGER,
    brew_date    TEXT,
    dripper      TEXT,
    filter_paper TEXT,
    grinder      TEXT,
    grind_size   TEXT,
    -- Who made it, for a coffee somebody else brewed. Storage only on this
    -- side: no CLI command and no GUI dialog reads it, exactly like `journeys`
    -- and the five water columns above -- it exists so a
    -- phone -> desktop -> phone round trip does not drop what the phone put
    -- there. It moved off `journeys` on 2026-08-25 (a cafe has many baristas;
    -- which one made the cup is a fact about the cup), and `journeys.barista`
    -- is deliberately left in place rather than migrated: there is no honest
    -- way to attribute a cafe's one recorded name to a particular cup.
    barista      TEXT,
    water_ppm    TEXT,
    water_alkalinity REAL,
    humidity     TEXT,
    dose_g       REAL,
    water_g      REAL,
    water_temp_c REAL,
    total_time_sec INTEGER,
    score        REAL,
    extraction   REAL,
    concentration REAL,
    note         TEXT,
    -- The roast (2026-08-24). Mirrors BeanEntity's four; snake_case here,
    -- camelCase there, and sync_tools maps between them.
    roast_level    TEXT,
    color_value    TEXT,
    weight_loss    TEXT,
    expansion_rate TEXT,
    flavor_notes TEXT,
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
    circling      TEXT,
    label         TEXT
);

-- THE JOURNEY TABLES EXIST HERE SO THE SCHEMAS MATCH, NOT BECAUSE THIS APP
-- LOGS CAFES. `coffee_android` grew them (a cafe visited, on a date, in a
-- place, with photographs) and nothing on this side reads or writes them: no
-- CLI command, no GUI dialog, no repo call outside the sync bridge. That is
-- the point. Structure parity is what makes a phone -> desktop -> phone round
-- trip lossless, and the alternative -- letting the phone hold a table this
-- database cannot receive -- is how a user's cafes quietly disappear the first
-- time they sync.
--
-- Column-for-column with JourneyEntity / JourneyImageEntity, including the two
-- retired ones. `latitude`/`longitude` are no longer surfaced on the phone and
-- are retained there because migrations are additive only; they are here for
-- the same reason, so a device still holding coordinates has somewhere to put
-- them.
--
-- `visited_at` is an epoch **millisecond**, not a date string like
-- `beans.roast_date` or `brew_sessions.brew_date`. That is the phone's choice
-- and it is kept rather than converted: a visit you cannot date is not a visit
-- you took, so unlike a roast date it is never absent, and rewriting the units
-- at the boundary would be this side inventing a second representation of a
-- column it does not otherwise touch.
CREATE TABLE IF NOT EXISTS journeys (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    location    TEXT,
    address     TEXT,
    barista     TEXT,
    latitude    REAL,
    longitude   REAL,
    visited_at  INTEGER NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A journey's photographs, the same contract as bean_images. The FK *is*
-- declared here, unlike brew_sessions.journey_id above, and for the reason
-- JourneyImageEntity declares one too: a photo of a cafe has no meaning once
-- the cafe row is gone, whereas a brew keeps all of its own meaning.
CREATE TABLE IF NOT EXISTS journey_images (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    journey_id INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    position   INTEGER NOT NULL,
    file_path  TEXT NOT NULL,
    rotation   INTEGER NOT NULL DEFAULT 0
);

-- The last two Android tables, and the least interesting: both are caches of a
-- `coffee_server` endpoint, replaced wholesale on every successful fetch, and
-- neither holds anything the user typed. They are here only so "the two
-- schemas match" is a statement that can be checked mechanically rather than
-- one with a footnote.
--
-- NOTHING ON THIS SIDE WRITES THEM. coffee-can caches the same two feeds as
-- JSON files beside this database (`coffee_news.py`, `whats_new.py`), and that
-- is not changed here -- moving a working cache into SQLite would be a desktop
-- behaviour change, which is out of scope. Sync does not carry them either:
-- re-fetching is free and a stale catalogue row is worse than none.
CREATE TABLE IF NOT EXISTS catalogue_items (
    url           TEXT PRIMARY KEY,
    roaster       TEXT NOT NULL,
    name          TEXT NOT NULL,
    image_url     TEXT,
    origin        TEXT,
    process       TEXT,
    price_eur     REAL,
    weight_g      INTEGER,
    tasting_note  TEXT,
    first_seen_at INTEGER
);

-- The column list is a legal boundary, not a convenience: `specs/legal-accounts.md`
-- rule 74 is a [BLOCKER] limiting a news feed to headline, source, date and
-- link. There is deliberately nowhere here to put a snippet, an excerpt or an
-- AI-written summary. Do not add one; NewsItemEntity says the same.
CREATE TABLE IF NOT EXISTS news_items (
    url          TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    source       TEXT NOT NULL,
    published_at INTEGER,
    -- The publisher's own standfirst, <=200 chars, added 2026-08-24 with the
    -- override of specs/legal-accounts.md rule 74. Mirrors
    -- NewsItemEntity.excerpt; the phone is where it is displayed and this
    -- table exists so a round trip through the desktop loses nothing.
    excerpt      TEXT,
    fetched_at   INTEGER NOT NULL
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
    if "concentration" not in session_columns:
        # How strong the cup was -- the second bar in the evaluation block,
        # beside extraction (repo.CONCENTRATION_ZONES). NULL for every session
        # logged before it existed, which reads as "-" rather than being
        # backfilled as "Just right": nobody assessed those, and a symmetric
        # scale's centre is a real answer, not an absence.
        conn.execute("ALTER TABLE brew_sessions ADD COLUMN concentration REAL")
        conn.commit()
    if "flavor_notes" not in session_columns:
        # The tasting notes picked under each flavour axis on the phone --
        # {"floral": ["jasmine", "rose"]}, axis slug to note keys. Stored as
        # the JSON string the Android side writes and read back out unchanged:
        # no desktop screen renders these yet, and the column exists so that a
        # phone -> desktop -> phone round trip does not quietly lose them.
        # See coffee_agent/sync_tools.BUNDLE_VERSION.
        conn.execute("ALTER TABLE brew_sessions ADD COLUMN flavor_notes TEXT")
        conn.commit()
    # The four columns the phone had first (2026-08-23). Every one of them is
    # a measurement someone actually typed on a device, and until now a
    # sync bundle had nowhere to put it: the Android session has carried
    # `waterG`, `waterTempC`, `waterAlkalinity` and `totalTimeSec` for months
    # while `brew_sessions` had no column for any of them, so a
    # phone -> desktop -> phone round trip silently dropped all four. They are
    # added here so the round trip is lossless, not because a desktop screen
    # renders them -- the same reason `flavor_notes` above exists.
    #
    # NULL for every session logged before the column, which reads as "not
    # recorded". Nothing is backfilled: a brew nobody weighed the water for
    # has no water weight, and inventing one would put a number in a log whose
    # whole purpose is to be trusted.
    if "water_g" not in session_columns:
        conn.execute("ALTER TABLE brew_sessions ADD COLUMN water_g REAL")
        conn.commit()
    if "water_temp_c" not in session_columns:
        # The brew's water temperature, distinct from `brew_stages.temperature_c`,
        # which is one pour's. The phone stopped surfacing this on 2026-08-21
        # and kept the column rather than destroying what users had typed; the
        # column here exists to receive exactly that history.
        conn.execute("ALTER TABLE brew_sessions ADD COLUMN water_temp_c REAL")
        conn.commit()
    if "water_alkalinity" not in session_columns:
        # Carbonate hardness in ppm as CaCO3 -- beside water_ppm (total
        # dissolved solids), not instead of it: two waters at the same TDS can
        # buffer acidity completely differently.
        conn.execute("ALTER TABLE brew_sessions ADD COLUMN water_alkalinity REAL")
        conn.commit()
    if "total_time_sec" not in session_columns:
        conn.execute("ALTER TABLE brew_sessions ADD COLUMN total_time_sec INTEGER")
        conn.commit()
    if "journey_id" not in session_columns:
        # No REFERENCES clause, matching the CREATE above and the phone -- see
        # the schema comment for why a cascade would be wrong here. SQLite
        # could not add an enforced FK by ALTER anyway, so an existing database
        # and a fresh one end up with the same (deliberately unenforced) shape.
        conn.execute("ALTER TABLE brew_sessions ADD COLUMN journey_id INTEGER")
        conn.commit()
    for field in FLAVOR_FIELDS:
        if field not in session_columns:
            conn.execute(f"ALTER TABLE brew_sessions ADD COLUMN {field} REAL")
            conn.commit()

    stage_columns = {row["name"] for row in conn.execute("PRAGMA table_info(brew_stages)")}
    if "water_g" not in stage_columns:
        conn.execute("ALTER TABLE brew_stages ADD COLUMN water_g REAL")
        conn.commit()
    if "label" not in stage_columns:
        # What the pour is called -- "Bloom", "Second pour". The phone has had
        # `SessionStageEntity.label` all along and this table only had
        # `circling`, so a stage crossing a sync bundle arrived unnamed. It is
        # a separate column and not a rename of `circling`: circling says how
        # the pour was poured, the label says which pour it was, and folding
        # one into the other would lose whichever was written second.
        conn.execute("ALTER TABLE brew_stages ADD COLUMN label TEXT")
        conn.commit()

    bean_columns = {row[1] for row in conn.execute("PRAGMA table_info(beans)")}
    for column in ("roast_level", "color_value", "weight_loss", "expansion_rate",
                   # The farm and the freezer date the phone gained on
                   # 2026-08-26. Same treatment as the roast block: no desktop
                   # UI reads either, they exist so a phone -> desktop -> phone
                   # round trip does not drop them.
                   "farm", "frozen_date"):
        if column not in bean_columns:
            # The roast block the phone gained on 2026-08-24. No desktop UI
            # reads these yet -- they exist so a phone -> desktop -> phone round
            # trip does not drop them, the same reason `journeys` and the
            # server-cache tables are here.
            conn.execute(f"ALTER TABLE beans ADD COLUMN {column} TEXT")
            conn.commit()

    session_columns = {row[1] for row in conn.execute("PRAGMA table_info(brew_sessions)")}
    if "barista" not in session_columns:
        # `sessions.barista`, which the phone added on 2026-08-25 when the field
        # moved out of a journey and into the brew form. Additive and nullable;
        # storage only here, like the water columns above it.
        conn.execute("ALTER TABLE brew_sessions ADD COLUMN barista TEXT")
        conn.commit()

    news_columns = {row[1] for row in conn.execute("PRAGMA table_info(news_items)")}
    if "excerpt" not in news_columns:
        # The phone gained NewsItemEntity.excerpt with rule 74's 2026-08-24
        # override. Additive and nullable: an existing cache simply has no
        # excerpts until the next fetch replaces it, which costs nothing
        # because the feed is replaced wholesale every time.
        conn.execute("ALTER TABLE news_items ADD COLUMN excerpt TEXT")
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
