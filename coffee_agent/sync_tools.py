"""Two-way sync between coffee-can on this machine and the Android app.

WHY THIS IS A FILE BUNDLE AND NOT A SERVER CALL. `specs/legal-accounts.md`
§3.8 is a binding statement that **no user content exists server-side**, and
the Android app tells the user so in three languages ("Your beans, brews,
notes and photos stay on this phone. We have no copy."). Routing a sync
through `coffee_server` would make that sentence false, flip the developer
from "not a controller for the on-device database" (rule 64) to controller,
and re-derive the whole Play Data safety form -- `CoffeeRepository`'s own
docstring says §3.8 has to be re-opened *first* if a sync path is ever added.

None of that applies here, and the reason is worth being precise about: this
moves data between two devices the *same person* owns, through a file they
carry themselves, with no third party in the path. The developer never holds
it. That is a different act from "the app syncs to the cloud", and it is the
only shape of sync that leaves the privacy claim standing.

THE CONFLICT MODEL. Beans are matched **by name**, because that is the only
identifier the two databases share -- coffee-can's `beans.id` and Room's
`beans.id` are independent autoincrement sequences and mean nothing to each
other. A name on both sides with any differing field is a conflict, and it is
never resolved silently: [inspect_coffee_bundle] reports them and
[apply_coffee_bundle] refuses to touch a conflicted bean until it is given an
explicit "phone" or "desktop" for it. Matching on a mutable, non-unique field
is a real limitation -- rename a bean on one side and it imports as a second
bean -- and it is stated in the tool output rather than hidden.

WHAT DOES NOT CROSS. Almost nothing, since 2026-08-23. The list used to run
to five session fields and a stage field: the phone had `waterG`,
`waterTempC`, `waterAlkalinity` and `totalTimeSec` with no column here to
receive them, `humidity` was a desktop column the phone had since grown a
field for without anyone reconnecting the two, and a stage's `label` had
nowhere to land. All six now cross -- `coffee_can.db` grew the four columns
and `brew_stages.label` on 2026-08-23, and `humidity` was simply added to
:data:`_SESSION_FIELDS`, which is all it ever needed.

**Journeys cross too, as of the same day.** A journey is the café a cup was
drunk at -- `coffee_android`'s own table, with no desktop screen behind it --
and until now a cup exported here arrived as an ordinary brew with the place
stripped off. `coffee_can.db` now carries `journeys`, `journey_images` and
`brew_sessions.journey_id` purely so that stops happening; `repo.py` gained the
storage calls and nothing else did. The desktop still cannot *show* you a café.
It can hold one, hand it back unchanged, and that is the whole requirement.

So nothing is dropped any more. What remains are two representational seams,
both of which are mappings rather than losses: a session's `filter_paper` is
the phone's `filter`, and a stage's `circling` is the phone's stage `note`.

HOW A JOURNEY IS ADDRESSED. Sessions reference their café **by name**, in a
`journey` key -- never by id, for exactly the reason beans match by name: the
two `journeys.id` sequences are independent autoincrement counters and mean
nothing to each other. `journeys.json` carries the café rows themselves.

Journeys are imported **additively** -- a name already here is kept, never
replaced, and counted in the result. That is a different rule from the one
beans get two paragraphs up, and the difference is not an oversight: the
per-bean "phone or desktop?" question is worth asking because the user can see
both beans. There is no desktop screen that renders a café, so asking which
version of one to keep would be asking a question the user has no way to
answer here.
"""

import json
import shutil
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple, Optional

from langchain_core.tools import tool

from tools import _resolve

_COFFEE_SRC = Path(__file__).resolve().parent.parent / "coffee" / "src"
if str(_COFFEE_SRC) not in sys.path:
    sys.path.insert(0, str(_COFFEE_SRC))

from coffee_can import repo  # noqa: E402
from coffee_can.db import connect  # noqa: E402
from coffee_can.paths import images_dir  # noqa: E402
from coffee_can.repo import FLAVOR_FIELDS  # noqa: E402

#: Bumped when the on-disk shape changes incompatibly. The Android exporter
#: writes the same number; an importer that meets a higher one refuses rather
#: than guessing, because a partial understanding of someone's coffee log is
#: worse than a clear "this bundle is newer than I am".
#:
#: v1 -> v2 adds ``flavor_notes`` on sessions: the tasting notes picked under
#: each radar axis on the phone, carried as the JSON string the Android column
#: stores (``{"floral": ["jasmine", "rose"]}``, axis slug -> note keys). This
#: side stores and forwards it verbatim and never interprets it -- the desktop
#: app has no UI for these yet, and re-encoding a format you do not render is
#: how a round trip starts losing keys it did not recognise.
#:
#: v2 -> v3 adds ``concentration`` on sessions: how strong the cup was, the
#: second bar beside extraction. Unlike ``flavor_notes`` this one is *rendered*
#: on both sides -- coffee-can grew the column, the CLI prompt and the GUI bar
#: on 2026-08-22, the same day the phone's slider shipped -- so the field is
#: carried the ordinary way rather than forwarded blind. Additive again, and
#: the bump is again about telling a later incompatible change which shapes it
#: must read, not about this one.
#:
#: v3 -> v4 (2026-08-23) closes the schema gap rather than adding a feature.
#: Six fields that both sides had been storing separately now travel:
#: ``humidity``, ``water_g``, ``water_temp_c``, ``water_alkalinity`` and
#: ``total_time_sec`` on the session, and ``label`` on a stage. Five of the six
#: needed a column here first -- see `coffee_can.db._migrate`; ``humidity``
#: needed only to be listed, having been a desktop column the phone quietly
#: grew a field for. Additive like the others: a v3 reader given a v4 bundle
#: ignores keys it does not know, and a v4 reader given a v3 bundle finds them
#: absent, which means "not recorded" and not "zero".
#:
#: v4 also carries **journeys**: a new ``journeys.json`` member, a
#: ``journey_images/`` tree beside ``images/``, and a ``journey`` key on a
#: session naming its café. Additive in the same sense -- a v3 bundle simply
#: has no ``journeys.json``, which reads as "no cafés" -- but this is the part
#: of v4 that needed a schema on this side rather than a list entry: see
#: `coffee_can.db`'s `journeys` / `journey_images` tables, which exist so the
#: two databases match and for no other reason.
#:
#: v4 -> v5 (2026-08-25) carries one new session field, ``barista``. It moved
#: off the journey and onto the session -- a café has many baristas, so which
#: one made the cup is a fact about the cup -- which meant a new column on both
#: sides (`coffee_can.db._migrate`, and Room's MIGRATION_11_12) and an entry in
#: `_SESSION_FIELDS`. **``journeys.barista`` is deliberately not migrated and
#: not removed**: there is no honest way to attribute a café's one recorded
#: name to a particular cup drunk there, and dropping a column means rebuilding
#: a table that holds text a user typed.
#:
#: Additive in exactly the sense v4 was, so the bump is again about telling a
#: later incompatible change which shapes it must read: a v4 reader given a v5
#: bundle ignores the key, and a v5 reader given a v4 bundle finds it absent,
#: which means "not recorded".
#:
#: v5 -> v6 (2026-08-26) carries two new bean fields, ``farm`` and
#: ``frozen_date``: the estate a lot came from, and the day a bag went into the
#: freezer. Both needed a column on both sides (`coffee_can.db._migrate`, and
#: Room's MIGRATION_12_13) as well as an entry in `_BEAN_FIELDS`. Additive in
#: exactly the sense v5 was -- an older reader ignores the keys, and a v6
#: reader given an older bundle finds them absent, which is "no farm recorded"
#: and "not frozen" rather than an empty string and an epoch.
BUNDLE_VERSION = 7

_MANIFEST = "manifest.json"
_BEANS = "beans.json"
_IMAGES = "images"

#: Cafés, and their photographs. Separate members rather than a key nested
#: under a bean, because a journey belongs to no bean: several beans' brews can
#: have been drunk at one café, and a café with no cup logged against it yet is
#: still a place someone went.
_JOURNEYS = "journeys.json"
_JOURNEY_IMAGES = "journey_images"

#: Journey fields carried across, in coffee-can's column names -- which are the
#: phone's, snake_cased. `visited_at` is epoch milliseconds on both sides.
_JOURNEY_FIELDS = (
    "name", "location", "address", "barista", "latitude", "longitude",
    "visited_at", "note",
)

#: Bean fields carried across, in coffee-can's own column names. The Android
#: side uses camelCase for the same values and converts on the way out.
_BEAN_FIELDS = (
    "name", "origin", "variety", "altitude", "roaster", "producer",
    "process", "roast_date", "note", "flavor_source",
    # v6, 2026-08-26: the farm the lot came from, and the day the bag went
    # into the freezer. Both are storage-only on this side, like the roast
    # block below -- listed the moment the columns existed on both sides.
    "farm", "frozen_date",
    # The region inside the origin, bundle v7 (2026-08-29). Listed the moment
    # the column existed on both sides -- an unlisted column is silently not
    # synced, which is what `humidity` did for months.
    "region",
    # The roast block, 2026-08-24. Listed the moment the columns existed --
    # `humidity` had a column on both sides for months and simply was not here,
    # so it silently never travelled and nothing failed.
    "roast_level", "color_value", "weight_loss", "expansion_rate",
) + FLAVOR_FIELDS

#: Session fields that exist on both sides -- which, since 2026-08-23, is all
#: of them bar `journey_id` (see the module docstring: this database has no
#: café to point it at).
#:
#: This is an **allowlist, not a reflection of the table**. A column added to
#: `brew_sessions` and not added here is silently not synced, which is the
#: failure mode that left five fields stranded on the phone for months. When
#: you add a column on either side, this tuple, `SyncBundle`'s two halves,
#: `repo.SESSION_FIELDS` and `db.py`'s migration all move together.
#:
#: The eleven flavour axes are here as well as on the bean, and dropping them
#: would be the quiet kind of data loss this module exists to avoid: both
#: schemas score a *session's* taste separately from the bean's, and a bean
#: whose `flavor_source` is `'auto'` derives its whole radar by averaging its
#: sessions (`repo.get_bean_average_flavor_scores`). Carry the bean columns
#: alone and an imported auto bean shows an empty radar with no way to
#: recompute it.
#:
#: ``flavor_notes`` is the tier under those axes -- which florals, not how
#: floral. See :data:`BUNDLE_VERSION`.
_SESSION_FIELDS = (
    "brew_date", "dripper", "filter_paper", "grinder", "grind_size",
    # Who made it. Moved off the journey on 2026-08-25 -- a cafe has many
    # baristas, so which one made the cup belongs to the cup. Listed here the
    # moment the column existed on both sides, which is the discipline the
    # docstring above demands and `humidity` is the counter-example to.
    "barista",
    # Water, in the four independent senses both schemas record it: how much
    # (`water_g`), how hot (`water_temp_c` -- the *brew's* temperature; a
    # single pour's is on the stage), how mineral (`water_ppm`, total
    # dissolved solids) and how buffering (`water_alkalinity`, carbonate
    # hardness). The last is not a rewording of the third: two waters at equal
    # TDS can read completely differently for acidity.
    "water_ppm", "water_alkalinity", "water_g", "water_temp_c",
    "humidity", "dose_g", "total_time_sec",
    "score", "extraction", "concentration", "note",
    "flavor_notes",
    # Present in this tuple so `_row_to_dict` reads it out on export and
    # `update_session_field` writes it on import -- but it never appears in a
    # bundle under this name. The exporter pops it and writes the café's
    # `journey` name instead, and the importer puts the *local* id back. Two
    # `journeys.id` sequences that mean nothing to each other is the same
    # reason beans match by name.
    "journey_id",
) + FLAVOR_FIELDS

#: Stage fields, in coffee-can's column names. `stage_number` is handled
#: separately (the desktop assigns it on insert, the phone derives it from list
#: order), so it is not in this tuple.
#:
#: `circling` and `label` are two columns and not one: the phone's stage note
#: became `circling` -- how the pour was poured -- long before this table had
#: anywhere to put the pour's *name*, and now that it does, folding them
#: together would lose whichever was written second.
_STAGE_FIELDS = ("temperature_c", "water_g", "time_seconds", "circling", "label")


def _row_to_dict(row, fields) -> dict:
    out = {}
    for f in fields:
        try:
            value = row[f]
        except (IndexError, KeyError):
            value = None
        if value is not None:
            out[f] = value
    return out


# ------------------------------------------------------------------ export --

@tool
def export_coffee_bundle(destination: str) -> str:
    """Write this machine's coffee-can database to a sync bundle the Android
    app can import.

    `destination` is a path inside the agent workspace; a `.zip` suffix is
    added if missing. The bundle contains every bean, its brew sessions and
    its images. Hand the resulting file to the phone (share it, copy it over
    USB, whatever you like) and open it there from Profile -> "Sync with
    desktop" -> "Receive from desktop".

    The phone imports **additively**: it adds beans whose names are new to it
    and leaves any bean it already has untouched, reporting how many it
    skipped. It never overwrites, so tell the user that edits made here will
    not reach a bean the phone already holds.
    """
    target = _resolve(destination)
    if target.suffix != ".zip":
        target = target.with_suffix(".zip")
    written = _export_to(target)
    cafes = f", {written.journeys} cafés" if written.journeys else ""
    return (
        f"Wrote {written.path} — {written.beans} beans, {written.sessions} "
        f"sessions{cafes}, {written.images} images. On the phone, open it from "
        f"Profile > 'Sync with desktop' > 'Receive from desktop'. It adds "
        f"beans the phone doesn't have and leaves ones it already has "
        f"untouched. (send_coffee_data_to_phone does all of this over USB "
        f"without a file to carry.)"
    )


class _Written(NamedTuple):
    path: Path
    beans: int
    sessions: int
    images: int
    journeys: int = 0


def _export_to(target: Path) -> _Written:
    """Write the bundle to an already-decided path, and say what went in it.

    Split out of the tool so `usb_sync` can stage a bundle somewhere the model
    never names. The **caller** owns the sandbox decision: `export_coffee_bundle`
    resolves a model-supplied path through `_resolve` first, while `usb_sync`
    passes a fixed cache location of its own choosing. Never call this with a
    path that came from the model without resolving it first.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        beans = []
        journeys = []
        image_count = 0
        journey_image_count = 0
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
            # Cafés first, because a session refers to one by name and the map
            # from local id to name has to exist before the bean loop reads it.
            journey_names = {}
            for journey_row in repo.list_journeys(conn):
                journey = _row_to_dict(journey_row, _JOURNEY_FIELDS)
                journey_names[journey_row["id"]] = journey.get("name")
                journey["images"] = []
                for image_row in repo.list_journey_images(conn, journey_row["id"]):
                    source = Path(image_row["file_path"])
                    if not source.exists():
                        continue
                    name = f"{_JOURNEY_IMAGES}/{journey_image_count:04d}{source.suffix.lower()}"
                    bundle.write(source, name)
                    journey["images"].append({"file": name, "position": image_row["position"]})
                    journey_image_count += 1
                journeys.append(journey)

            for bean_row in repo.list_beans(conn):
                bean = _row_to_dict(bean_row, _BEAN_FIELDS)
                bean["sessions"] = []
                for session_row in repo.list_sessions(conn, bean_row["id"]):
                    session = _row_to_dict(session_row, _SESSION_FIELDS)
                    # The raw id is meaningless on the far side; the name is
                    # the identity. Popped rather than left alongside, so a
                    # reader cannot pick the wrong one of the two.
                    local_journey_id = session.pop("journey_id", None)
                    journey_name = journey_names.get(local_journey_id)
                    if journey_name:
                        session["journey"] = journey_name
                    # `stage_number` is written explicitly and unconditionally;
                    # everything else goes through _row_to_dict so a NULL is an
                    # absent key rather than a null, the same rule the beans and
                    # sessions follow. A stage with no number has no place in
                    # the pour order, so that one field is never omitted.
                    session["stages"] = [
                        {"stage_number": stage_row["stage_number"],
                         **_row_to_dict(stage_row, _STAGE_FIELDS)}
                        for stage_row in repo.list_stages(conn, session_row["id"])
                    ]
                    bean["sessions"].append(session)

                bean["images"] = []
                for image_row in repo.list_bean_images(conn, bean_row["id"]):
                    source = Path(image_row["file_path"])
                    if not source.exists():
                        continue
                    # Namespaced by index rather than by the original filename:
                    # two beans can hold identically-named files, and a zip with
                    # duplicate entries loses one of them silently.
                    name = f"{_IMAGES}/{image_count:04d}{source.suffix.lower()}"
                    bundle.write(source, name)
                    bean["images"].append({"file": name, "position": image_row["position"]})
                    image_count += 1
                beans.append(bean)

            bundle.writestr(_BEANS, json.dumps(beans, ensure_ascii=False, indent=1))
            bundle.writestr(_JOURNEYS, json.dumps(journeys, ensure_ascii=False, indent=1))
            bundle.writestr(_MANIFEST, json.dumps({
                "version": BUNDLE_VERSION,
                "source": "desktop",
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "beans": len(beans),
                "journeys": len(journeys),
            }, indent=1))
    finally:
        conn.close()

    return _Written(
        target,
        len(beans),
        sum(len(b["sessions"]) for b in beans),
        image_count + journey_image_count,
        len(journeys),
    )


# ----------------------------------------------------------------- inspect --

def _read_bundle(path: Path) -> tuple:
    """Open a bundle and return ``(beans, journeys)``, or raise a ValueError
    saying why not.

    Everything that can go wrong with someone's hand-carried file -- not a zip,
    a zip of something else, truncated JSON -- surfaces here as one sentence,
    because these tools are pointed at whatever the user copied off their phone
    and `explain()` in main.py has nothing useful to say about a `BadZipFile`.
    """
    if not path.exists():
        raise ValueError(f"no such bundle: {path}")
    try:
        with zipfile.ZipFile(path) as bundle:
            names = set(bundle.namelist())
            if _MANIFEST not in names or _BEANS not in names:
                raise ValueError(
                    f"{path.name} is a zip but not a coffee bundle (no "
                    f"{_MANIFEST}/{_BEANS} inside)."
                )
            manifest = json.loads(bundle.read(_MANIFEST))
            version = manifest.get("version", 0)
            if version > BUNDLE_VERSION:
                raise ValueError(
                    f"bundle is version {version}, this agent understands up to "
                    f"{BUNDLE_VERSION}. Update coffee_agent rather than importing "
                    f"it partially."
                )
            beans = json.loads(bundle.read(_BEANS))
            # Optional: a v3 bundle predates cafés entirely, and an absent
            # member reads as "no cafés" rather than as a malformed file.
            journeys = json.loads(bundle.read(_JOURNEYS)) if _JOURNEYS in names else []
    except zipfile.BadZipFile:
        raise ValueError(f"{path.name} is not a zip file.") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} contains damaged JSON: {exc}") from None
    if not isinstance(beans, list):
        raise ValueError(f"{path.name}'s {_BEANS} is not a list of beans.")
    if not isinstance(journeys, list):
        raise ValueError(f"{path.name}'s {_JOURNEYS} is not a list of journeys.")
    return beans, journeys


def _differences(incoming: dict, existing_row) -> list:
    """Which shared fields actually disagree. Equal beans are not conflicts.

    A field the bundle does not carry is **no opinion**, not an empty value.
    That distinction is the whole correctness of this function: the exporter
    omits nulls, so comparing an absent key against a column with a database
    default (`flavor_source` defaults to `'auto'`, `status` to `'draft'`)
    reported every such column as a disagreement. The result was phantom
    conflicts on beans that were in fact identical, and -- worse -- a bundle
    imported twice flagged its own previous import as a conflict, so a user
    re-running a sync was asked to adjudicate beans nothing had touched.
    """
    diffs = []
    for field in _BEAN_FIELDS:
        if field == "name" or field not in incoming:
            continue
        mine = existing_row[field] if field in existing_row.keys() else None
        theirs = incoming.get(field)
        if (mine or None) != (theirs or None):
            diffs.append(field)
    return diffs


@tool
def inspect_coffee_bundle(bundle: str) -> str:
    """Report what a bundle from the Android app would change, without
    changing anything.

    Names every bean that exists on both sides with differing values -- those
    are conflicts, and `apply_coffee_bundle` will refuse to import them until
    you say which side wins for each. Run this first, show the user the
    conflicts, and ask them one at a time.
    """
    path = _resolve(bundle)
    beans, journeys = _read_bundle(path)

    conn = connect()
    try:
        existing = {row["name"]: row for row in repo.list_beans(conn)}
        here = {row["name"] for row in repo.list_journeys(conn)}
        new_cafes = [
            (j.get("name") or "").strip() for j in journeys
            if (j.get("name") or "").strip() and (j.get("name") or "").strip() not in here
        ]
        new, conflicts, identical = [], [], []
        for bean in beans:
            name = bean.get("name") or ""
            if name not in existing:
                new.append(name)
                continue
            diffs = _differences(bean, existing[name])
            (conflicts if diffs else identical).append((name, diffs))
    finally:
        conn.close()

    lines = [
        f"{len(beans)} beans in the bundle.",
        f"  {len(new)} new, {len(identical)} already identical, {len(conflicts)} in conflict.",
    ]
    if new:
        lines.append("New (will be added): " + ", ".join(sorted(new)[:20]))
    if conflicts:
        lines.append("Conflicts — each needs a choice of 'phone' or 'desktop':")
        for name, diffs in conflicts:
            lines.append(f"  - {name}: differs on {', '.join(diffs)}")
    if journeys:
        lines.append(
            f"{len(journeys)} cafés in the bundle, {len(new_cafes)} new. "
            f"Cafés are added, never replaced — this database has no screen "
            f"that could show you two versions to choose between."
        )
        if new_cafes:
            lines.append("New cafés: " + ", ".join(sorted(new_cafes)[:20]))
    lines.append(
        "Beans and cafés are both matched by name; renaming one on either side "
        "makes it import as a separate record."
    )
    return "\n".join(lines)


# ------------------------------------------------------------------- apply --

@tool
def apply_coffee_bundle(bundle: str, resolutions: str = "{}") -> str:
    """Import a bundle into this machine's coffee-can.

    `resolutions` is a JSON object mapping a conflicted bean name to `"phone"`
    (take the bundle's version), `"desktop"` (keep what is here) or `"skip"`.
    New beans are always added and need no entry. A conflicted bean with no
    entry is left untouched and reported, so a half-answered run cannot
    silently overwrite anything -- call `inspect_coffee_bundle` first and ask
    the user per conflict.
    """
    path = _resolve(bundle)
    beans, journeys = _read_bundle(path)
    try:
        choices = json.loads(resolutions or "{}")
    except json.JSONDecodeError as exc:
        return f"resolutions is not valid JSON: {exc}"

    added, replaced, kept, unanswered, skipped, duplicates = [], [], [], [], [], []
    sessions_added = 0
    cafes_added = []
    conn = connect()
    try:
        existing = {row["name"]: row for row in repo.list_beans(conn)}
        seen = set()
        with zipfile.ZipFile(path) as archive:
            # Cafés before beans: a session names its café, and the name has to
            # resolve to a local id before any session row is written. Beans
            # whose cups refer to a café are therefore never left pointing at
            # nothing, even on a run that adjudicates nothing else.
            journey_ids = _write_journeys(conn, archive, journeys, path, cafes_added)
            for bean in beans:
                name = (bean.get("name") or "").strip()
                if not name:
                    continue
                if name in seen:
                    # Two beans under one name inside a single bundle. Writing
                    # both would leave the database with a name that
                    # repo.resolve_bean can no longer resolve ("multiple coffee
                    # profiles named ..."), so the second is reported instead.
                    duplicates.append(name)
                    continue
                seen.add(name)
                if name in existing:
                    local_id = existing[name]["id"]
                    if not _differences(bean, existing[name]):
                        kept.append(name)
                        # KEEPING THE BEAN'S FIELDS IS NOT KEEPING ITS BREWS
                        # (2026-08-25). This branch used to `continue` past the
                        # whole bean object, so a session logged on the phone
                        # against a bean whose *fields* had not changed never
                        # arrived -- and since nothing about the bean differed,
                        # nothing was reported either. The phone had the same
                        # hole at `SyncBundle.importCopying`; it was found on a
                        # two-phone round trip and fixed on both sides at once,
                        # because this is one rule implemented twice
                        # (`coupling-spec.md` §4).
                        sessions_added += _merge_sessions(
                            conn, bean, local_id, journey_ids
                        )
                        continue
                    choice = choices.get(name)
                    if choice == "desktop":
                        kept.append(name)
                        # Same as above, and for the same reason: "keep mine"
                        # is an answer about the bean's *fields*, which is what
                        # the conflict was about. The phone's brews were never
                        # in dispute -- `_differences` does not look at them --
                        # so declining to overwrite a roast date must not also
                        # throw away a brew this database has never seen.
                        sessions_added += _merge_sessions(
                            conn, bean, local_id, journey_ids
                        )
                        continue
                    if choice == "skip":
                        # The one branch that really does mean "nothing from
                        # this bean": the user was asked and said skip it.
                        skipped.append(name)
                        continue
                    if choice != "phone":
                        # Unanswered: not a decision, so nothing is written at
                        # all -- not even a session. Merging brews under a bean
                        # whose conflict is still open would half-apply a
                        # bundle the caller has not finished adjudicating.
                        unanswered.append(name)
                        continue
                    # "phone" wins: the local row goes, and the bundle's is
                    # written fresh. Deleting cascades its sessions, stages
                    # and images, which is the point -- a half-replaced bean
                    # carrying the other side's sessions is the one outcome
                    # nobody asked for.
                    #
                    # The image *rows* cascade; the JPEGs under images_dir()
                    # do not, since ON DELETE CASCADE knows nothing about the
                    # filesystem. delete_bean_image is what pairs the two, so
                    # the pages go through it first and a replaced bean does
                    # not leave its old scans behind forever.
                    for image_row in repo.list_bean_images(conn, existing[name]["id"]):
                        repo.delete_bean_image(conn, image_row["id"])
                    repo.delete_bean(conn, existing[name]["id"])
                    replaced.append(name)
                else:
                    added.append(name)
                _write_bean(conn, archive, bean, path, journey_ids)
        conn.commit()
    finally:
        conn.close()

    lines = [
        f"Added {len(added)}, replaced {len(replaced)}, kept local {len(kept)}, "
        f"skipped {len(skipped)}."
    ]
    if sessions_added:
        # Reported separately from the bean counts because it is the one number
        # that moves without any bean moving: these are brews merged into beans
        # counted under "kept local", which is exactly the case that used to
        # report success while importing nothing.
        lines.append(
            f"Merged {sessions_added} brews into beans that were already here."
        )
    if cafes_added:
        lines.append(
            f"Added {len(cafes_added)} cafés: " + ", ".join(sorted(cafes_added)[:20])
        )
    if unanswered:
        lines.append(
            "NOT imported — still need a choice of 'phone' or 'desktop': "
            + ", ".join(sorted(unanswered))
        )
    if duplicates:
        lines.append(
            "NOT imported — the bundle holds more than one bean under each of "
            "these names, and only the first was taken: "
            + ", ".join(sorted(set(duplicates)))
        )
    return "\n".join(lines)


def _write_journeys(
    conn, archive: zipfile.ZipFile, journeys: list, bundle_path: Path, added: list
) -> dict:
    """Insert cafés the bundle has and this database does not, and return
    ``{name: local id}`` for **every** café here afterwards -- imported or
    pre-existing -- so a session can be attached either way.

    ADDITIVE, NEVER REPLACING, unlike the bean path in [apply_coffee_bundle].
    A café already here keeps every field it has. The bean rule earns its
    per-record question because the user can look at both beans; there is no
    desktop screen that renders a café, so the same question here would have no
    answerable form. Declining is the only resolution available to a side that
    cannot put the choice to anyone -- the same reasoning `SyncBundle.importFrom`
    applies to beans, from the side that cannot ask about those either.
    """
    known = {row["name"]: row["id"] for row in repo.list_journeys(conn)}
    for journey in journeys:
        name = (journey.get("name") or "").strip()
        if not name or name in known:
            continue
        # visited_at is NOT NULL on both sides. A bundle without one is
        # malformed rather than merely sparse, and the café is skipped: a
        # fabricated visit date would be this tool inventing a memory.
        visited_at = journey.get("visited_at")
        if visited_at is None:
            continue
        journey_id = repo.create_journey(conn, name, visited_at)
        known[name] = journey_id
        added.append(name)
        for field in _JOURNEY_FIELDS:
            if field in ("name", "visited_at"):
                continue
            value = journey.get(field)
            if value is not None:
                try:
                    repo.update_journey_field(conn, journey_id, field, value)
                except Exception:  # noqa: BLE001
                    pass
        _extract_images(
            conn, archive, journey.get("images", []), bundle_path,
            lambda extracted, jid=journey_id: repo.add_journey_image(conn, jid, extracted),
        )
    return known


def _extract_images(conn, archive, images, bundle_path: Path, attach) -> None:
    """Extract each member to a scratch path and hand it to `attach`.

    Images go through coffee-can's own add_*_image rather than being written
    into place here, so they land exactly where a photo added through the GUI
    would -- rather than this module keeping a second, drifting copy of that
    placement rule.
    """
    staging = bundle_path.parent / ".bundle-staging"
    for image in images:
        member = image.get("file")
        if not member:
            continue
        try:
            staging.mkdir(parents=True, exist_ok=True)
            attach(Path(archive.extract(member, staging)))
        except Exception:  # noqa: BLE001
            pass
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)


def _session_key(row: dict) -> tuple:
    """The stand-in identity for a brew, since the format carries no real one.

    A session has no id in a bundle and no `created_at` column on either side,
    and `brew_date` is a calendar day rather than an instant. So "is this brew
    already here?" cannot be answered directly, and both of the obvious ways to
    cope lose data: writing every incoming session duplicates the log on the
    second sync, and skipping the bean drops brews that are genuinely new --
    which is the bug this exists to close.

    Content stands in for identity instead. **Every field the bundle can carry
    is in the key**, read through `_SESSION_FIELDS` so a column added there is
    automatically part of the identity rather than silently excluded from it --
    the same reason that tuple is an allowlist and not a reflection of the
    table.

    Values are normalised to strings because the two sides they are compared
    from disagree about type in ways SQLite does not care about: `water_ppm`
    and `humidity` are TEXT columns holding what someone typed, while the phone
    sends numbers; a REAL column reads back as 15.0 where the bundle said 15.
    `str(float(v))` where a value parses as a number and `str(v)` where it does
    not is what makes those two the same key.

    `journey_id` is deliberately *not* here even though the phone's key has
    `journeyId`: this database has cafés only as storage (see the module
    docstring), the bundle names them rather than numbering them, and the
    resolved id is local. Two otherwise-identical cups drunk at two cafés
    therefore collapse here and do not on the phone -- a real asymmetry, and
    the honest one until a session has an id of its own.
    """
    key = []
    for field in _SESSION_FIELDS:
        if field == "journey_id":
            continue
        value = row.get(field)
        if value is None or value == "":
            key.append("")
            continue
        try:
            key.append(str(float(value)))
        except (TypeError, ValueError):
            key.append(str(value).strip())
    return tuple(key)


def _merge_sessions(conn, bean: dict, bean_id: int, journey_ids: Optional[dict]) -> int:
    """Write the bundle's brews that this bean does not already have.

    A MULTISET RECONCILIATION, NOT A SET ONE. Dialling in a recipe produces
    genuinely identical rows -- same day, same dose, same dripper, nothing
    typed -- and those are two brews, not one recorded twice. Each distinct key
    is counted on both sides and only the shortfall is written, so two incoming
    against one local adds one. `set()` semantics would merge them, and keep
    merging them on every sync afterwards.

    Idempotent by construction: re-applying the same bundle finds every count
    already satisfied and writes nothing.

    What it still cannot do, and the phone's `mergeSessions` cannot either: an
    *edited* session arrives as a second row rather than updating the first,
    because the edit changes the content standing in for the identity. That
    needs a real per-session id in both schemas and a `BUNDLE_VERSION` bump to
    carry it.
    """
    incoming = bean.get("sessions", [])
    if not incoming:
        return 0

    have: dict = {}
    for row in repo.list_sessions(conn, bean_id):
        key = _session_key(dict(row))
        have[key] = have.get(key, 0) + 1

    added = 0
    for session in incoming:
        if have.get(_session_key(session), 0) > 0:
            # Already here. Spend one local copy so a *second* identical
            # incoming row still lands.
            have[_session_key(session)] -= 1
            continue
        _write_session(conn, session, bean_id, journey_ids)
        added += 1
    return added


def _write_session(conn, session: dict, bean_id: int, journey_ids: Optional[dict]) -> None:
    """One incoming session plus its stages, written under `bean_id`."""
    session_id = repo.create_session(conn, bean_id)
    # `journey` is a name; `journey_id` is this database's own id for it.
    # A name with no café here (a v3 bundle, or one whose journeys.json
    # lost the row) leaves the column null, which is exactly "brewed at
    # home" -- the honest reading, and the same thing the phone does with a
    # dangling reference.
    cafe_name = session.get("journey")
    if cafe_name and journey_ids:
        local_id = journey_ids.get(str(cafe_name).strip())
        if local_id is not None:
            session = {**session, "journey_id": local_id}
    for field in _SESSION_FIELDS:
        value = session.get(field)
        if value is not None:
            try:
                repo.update_session_field(conn, session_id, field, value)
            except Exception:  # noqa: BLE001
                pass
    repo.set_session_status(conn, session_id, "saved")
    for stage in session.get("stages", []):
        repo.add_stage(
            conn,
            session_id,
            temperature_c=stage.get("temperature_c"),
            water_g=stage.get("water_g"),
            time_seconds=stage.get("time_seconds"),
            circling=stage.get("circling"),
            label=stage.get("label"),
        )


def _write_bean(
    conn, archive: zipfile.ZipFile, bean: dict, bundle_path: Path,
    journey_ids: Optional[dict] = None,
) -> None:
    bean_id = repo.create_bean(conn, (bean.get("name") or "").strip() or "Untitled")
    for field in _BEAN_FIELDS:
        if field == "name":
            continue
        value = bean.get(field)
        if value is not None:
            try:
                repo.update_bean_field(conn, bean_id, field, value)
            except Exception:  # noqa: BLE001
                # A field this coffee-can build does not have (an older
                # install, or one the Android side added first). Skipped
                # rather than aborting the whole import for one column.
                pass
    repo.set_bean_status(conn, bean_id, "saved")

    # One writer for a session, shared with `_merge_sessions`: a bean written
    # fresh and a brew merged into an existing one must produce the same row,
    # and two copies of this loop is how they would stop.
    for session in bean.get("sessions", []):
        _write_session(conn, session, bean_id, journey_ids)

    _extract_images(
        conn, archive, bean.get("images", []), bundle_path,
        lambda extracted: repo.add_bean_image(conn, bean_id, extracted),
    )


SYNC_TOOLS = [export_coffee_bundle, inspect_coffee_bundle, apply_coffee_bundle]
