#!/usr/bin/env python3
"""Prove the desktop's SQLite schema still mirrors the app's Room schema.

WHY THIS EXISTS. `coupling-spec.md` §2.3 says a column added to `Entities.kt`
also moves `db.py`, `repo.py` and both halves of the sync bundle -- and the
failure mode when it does not is silence. Nothing crashes. The field simply
stops travelling, and surfaces months later as "my phone did not get my brews".
That is exactly what happened to `waterG`, `waterTempC`, `waterAlkalinity`,
`totalTimeSec`, `session_stages.label` and (from the other direction)
`humidity`, all repaired on 2026-08-23. This script is the check that would
have caught all six the day each was added.

WHAT IT CHECKS. Every column of every Room entity has a home in
`coffee/src/coffee_can/db.py`, under the name the bundle uses -- and, for the
tables sync carries, that `sync_tools`' allowlists actually list it. An
allowlist is the second place a field can go missing without failing, and the
one that bit `humidity`, whose column existed on both sides the whole time.

WHAT IT CHECKS ABOUT TYPES: one thing, and it is the narrowest useful one. A
desktop **TEXT** column read into a Kotlin **numeric** field is a silent
one-way drain: `SyncBundle`'s `num()` returns null for anything that is not a
number, so a value someone actually typed vanishes with no error on either
side. That is not hypothetical -- it is how five `humidity` readings of
`'high'` / `'low'` failed to reach the phone on 2026-08-23, after every count
and every other field matched. Reported as a WARNING rather than a failure,
because the pairing is legitimate when the text is always numeric; what is
never legitimate is *not knowing* which case you are in.

Nothing else about types is compared. SQLite's declared types are advisory and
the two sides differ harmlessly in plenty of places.

Read-only over `../../v1/` and over `../../../coffee/`, per §1.1 rule 2.

    python3 check_schema_parity.py     # exit 0 = in step
"""

import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE.parent.parent / "v1"
ROOT = HERE.parent.parent.parent
ENTITIES = APP / "app/src/main/java/app/coffeecan/data/Entities.kt"
DB_PY = ROOT / "coffee/src/coffee_can/db.py"
SYNC = ROOT / "coffee_agent/sync_tools.py"

#: Room table -> desktop table. The names differ where coffee-can chose first
#: and the port did not rename ("brew_sessions" predates the phone entirely).
TABLES = {
    "beans": "beans",
    "bean_images": "bean_images",
    "sessions": "brew_sessions",
    "session_stages": "brew_stages",
    "journeys": "journeys",
    "journey_images": "journey_images",
    "catalogue_items": "catalogue_items",
    "news_items": "news_items",
}

#: Kotlin property -> desktop column, where snake_case alone does not get you
#: there. Each is a deliberate mapping, not a drift: see SyncBundle's docstring.
RENAMES = {
    ("sessions", "filter"): "filter_paper",
    ("sessions", "brewedAt"): "brew_date",
    ("session_stages", "position"): "stage_number",
    ("session_stages", "note"): "circling",
    # A pour's own temperature. Note `sessions.waterTempC` is a *different*
    # field with a different desktop column (`brew_sessions.water_temp_c`) --
    # the brew's temperature against this pour's. Same Kotlin name, two tables.
    ("session_stages", "waterTempC"): "temperature_c",
    ("session_stages", "atSec"): "time_seconds",
    # ...and when it stopped. Named for its pair rather than snake_cased from
    # the Kotlin, so the desktop reads `time_seconds` / `end_seconds` the way
    # the phone reads `atSec` / `endSec`.
    ("session_stages", "endSec"): "end_seconds",
    # The stage's own span, as against the pour's two above. Same reasoning as
    # `endSec`: named for the pair it belongs to on each side, so the desktop
    # reads `stage_start_seconds` / `stage_end_seconds` where the phone reads
    # `stageStartSec` / `stageEndSec`.
    ("session_stages", "stageStartSec"): "stage_start_seconds",
    ("session_stages", "stageEndSec"): "stage_end_seconds",
}

#: Room columns with no desktop counterpart and no need of one. Keep this list
#: short and argued -- it is the place a real gap would hide.
EXEMPT = {
    # Room's surrogate keys and audit stamps exist on both sides under the
    # obvious names; these entries cover the ones the port spells differently
    # only in case (`createdAt` -> `created_at` is handled by snake_case).
}

#: Tables the sync bundle carries, and the sync_tools allowlist that gates each.
SYNCED = {
    "beans": "_BEAN_FIELDS",
    "sessions": "_SESSION_FIELDS",
    "session_stages": "_STAGE_FIELDS",
    "journeys": "_JOURNEY_FIELDS",
}

#: Columns a synced table holds that are deliberately NOT in its allowlist.
NOT_CARRIED = {
    # Parent keys. The bundle nests sessions inside beans and stages inside
    # sessions, so the relationship is carried by the shape of the JSON and
    # the id is assigned by whichever database is doing the inserting.
    ("sessions", "bean_id"): "implied by nesting; assigned on insert",
    ("session_stages", "session_id"): "implied by nesting; assigned on insert",
    ("beans", "status"): "set to 'saved' on import; a draft is not exported",
    ("beans", "created_at"): "the receiving database stamps its own",
    ("beans", "updated_at"): "the receiving database stamps its own",
    ("sessions", "status"): "set to 'saved' on import",
    ("sessions", "created_at"): "the receiving database stamps its own",
    ("sessions", "updated_at"): "the receiving database stamps its own",
    ("journeys", "created_at"): "the receiving database stamps its own",
    ("journeys", "updated_at"): "the receiving database stamps its own",
    ("session_stages", "stage_number"): "assigned on insert from list order",
}


def snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def room_tables() -> dict:
    """Room table name -> [kotlin property names], parsed out of Entities.kt.

    A parser and not a Room export, because `app/schema/`'s JSON is a build
    artefact and this has to run without Gradle (§1.1: the audit side is
    standalone Python).
    """
    text = ENTITIES.read_text()
    out = {}
    for match in re.finditer(r"data class (\w+)\(", text):
        # The @Entity annotation is whatever precedes this class, and its
        # argument list nests parens (foreignKeys = [ForeignKey(...)]), so it
        # is found by scanning back to the last @Entity rather than by a
        # regex that would have to balance them.
        head = text[: match.start()]
        at = head.rfind("@Entity")
        if at < 0:
            continue
        table_match = re.search(r'tableName\s*=\s*"(\w+)"', head[at:])
        if not table_match:
            continue
        # Balance the constructor parens to find where the class ends.
        depth, i = 0, match.end() - 1
        while i < len(text):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = text[match.end() : i]
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
        body = re.sub(r"//[^\n]*", "", body)
        out[table_match.group(1)] = re.findall(
            r"\b(?:override\s+)?val\s+(\w+)\s*:\s*([\w<>?]+)", body
        )
    return out


def desktop_columns() -> dict:
    """Desktop table -> {column names}, by executing the real schema.

    Against a throwaway in-memory database rather than by parsing db.py, so
    what is checked is what a user's database actually gets -- including
    anything `_migrate` adds that `SCHEMA` does not.
    """
    src = str(ROOT / "coffee" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from coffee_can.db import SCHEMA  # noqa: PLC0415

    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    return {t: {r[1]: (r[2] or "").upper() for r in conn.execute(f"PRAGMA table_info({t})")}
            for t in tables}


def allowlist(name: str) -> set:
    """The contents of one of sync_tools' field lists.

    Parsed rather than imported, because importing `sync_tools` drags in
    LangChain and this script must run on the audit side with nothing but the
    standard library. The `+ FLAVOR_FIELDS` suffix two of these tuples carry is
    expanded from `repo`, which is stdlib-only and already importable here.
    """
    text = SYNC.read_text()
    match = re.search(rf"^{name} = \((.*?)^\)( \+ FLAVOR_FIELDS)?", text, re.S | re.M)
    if not match:
        return set()
    body = re.sub(r"#[^\n]*", "", match.group(1))
    fields = set(re.findall(r'"(\w+)"', body))
    if match.group(2):
        from coffee_can.repo import FLAVOR_FIELDS  # noqa: PLC0415

        fields |= set(FLAVOR_FIELDS)
    return fields


#: Kotlin types that cannot hold arbitrary text. A desktop TEXT column paired
#: with one of these loses any non-numeric value silently.
NUMERIC_KOTLIN = {"Float", "Float?", "Int", "Int?", "Long", "Long?", "Double", "Double?"}

#: Columns whose TEXT-to-number crossing goes through an explicit converter
#: rather than through `num()`, so the drain does not apply. `brew_date` is an
#: ISO day parsed by `brewedAtMillis`, which falls back to "now" rather than to
#: null; the timestamp columns are not carried at all (see NOT_CARRIED) and each
#: side stamps its own.
CONVERTED = {("sessions", "brew_date")}


def main() -> int:
    room, desktop = room_tables(), desktop_columns()
    problems, warnings = [], []

    for table, props in sorted(room.items()):
        target = TABLES.get(table)
        if target is None:
            problems.append(f"{table}: Room table not mapped in TABLES")
            continue
        if target not in desktop:
            problems.append(f"{table}: no desktop table {target!r}")
            continue
        columns = desktop[target]
        carried = allowlist(SYNCED[table]) if table in SYNCED else None

        for prop, ktype in props:
            column = RENAMES.get((table, prop), snake(prop))
            if (table, prop) in EXEMPT:
                continue
            if column not in columns:
                problems.append(
                    f"{table}.{prop} -> {target}.{column} MISSING "
                    f"(add it to db.py's SCHEMA and _migrate)"
                )
                continue
            # Only a column the bundle actually carries through `num()` can
            # drain. One that is not carried, or that has its own converter,
            # never reaches that code path.
            if (
                columns[column] == "TEXT"
                and ktype in NUMERIC_KOTLIN
                and carried is not None
                and column in carried
                and (table, column) not in CONVERTED
            ):
                warnings.append(
                    f"{target}.{column} is TEXT but {table}.{prop} is {ktype} — any "
                    f"non-numeric value stored on the desktop reaches the phone as "
                    f"null, silently"
                )
            if carried is None or column in ("id",) or (table, column) in NOT_CARRIED:
                continue
            if column not in carried:
                problems.append(
                    f"{table}.{prop} has a column ({target}.{column}) but is not in "
                    f"sync_tools.{SYNCED[table]} — it will not travel, and nothing "
                    f"will fail"
                )

    print(f"Room tables:    {len(room)}")
    print(f"Desktop tables: {len(desktop)}")
    print(f"Columns checked: {sum(len(v) for v in room.values())}")
    if warnings:
        print(f"\n{len(warnings)} warning(s) — not drift, but a lossy pairing:")
        for w in warnings:
            print(f"  ! {w}")
    if problems:
        print(f"\n{len(problems)} problem(s):")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\nSchemas are in step, and every synced column is on its allowlist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
