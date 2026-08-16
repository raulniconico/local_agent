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

WHAT DOES NOT CROSS, AND WHY THAT IS REPORTED RATHER THAN DROPPED. The two
schemas diverged: the Android session has `waterG` and `waterTempC`, which
coffee-can's `brew_sessions` has no column for, and coffee-can has `humidity`,
which Room has no field for. Stage shapes differ too (Room carries a `label`
and a free `note`; coffee-can carries `circling`). Anything unmappable is
counted and named in the result rather than quietly discarded, so a user who
syncs is told what the round trip cost them.
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
BUNDLE_VERSION = 1

_MANIFEST = "manifest.json"
_BEANS = "beans.json"
_IMAGES = "images"

#: Bean fields carried across, in coffee-can's own column names. The Android
#: side uses camelCase for the same values and converts on the way out.
_BEAN_FIELDS = (
    "name", "origin", "variety", "altitude", "roaster", "producer",
    "process", "roast_date", "note", "flavor_source",
) + FLAVOR_FIELDS

#: Session fields that exist on both sides. `water_g` / `water_temp_c` are
#: deliberately absent: coffee-can has no such columns (see module docstring).
#:
#: The eleven flavour axes are here as well as on the bean, and dropping them
#: would be the quiet kind of data loss this module exists to avoid: both
#: schemas score a *session's* taste separately from the bean's, and a bean
#: whose `flavor_source` is `'auto'` derives its whole radar by averaging its
#: sessions (`repo.get_bean_average_flavor_scores`). Carry the bean columns
#: alone and an imported auto bean shows an empty radar with no way to
#: recompute it.
_SESSION_FIELDS = (
    "brew_date", "dripper", "filter_paper", "grinder", "grind_size",
    "water_ppm", "dose_g", "score", "extraction", "note",
) + FLAVOR_FIELDS


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
    return (
        f"Wrote {written.path} — {written.beans} beans, {written.sessions} "
        f"sessions, {written.images} images. On the phone, open it from "
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
        image_count = 0
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as bundle:
            for bean_row in repo.list_beans(conn):
                bean = _row_to_dict(bean_row, _BEAN_FIELDS)
                bean["sessions"] = []
                for session_row in repo.list_sessions(conn, bean_row["id"]):
                    session = _row_to_dict(session_row, _SESSION_FIELDS)
                    session["stages"] = [
                        {
                            "stage_number": s["stage_number"],
                            "temperature_c": s["temperature_c"],
                            "water_g": s["water_g"],
                            "time_seconds": s["time_seconds"],
                            "circling": s["circling"],
                        }
                        for s in repo.list_stages(conn, session_row["id"])
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
            bundle.writestr(_MANIFEST, json.dumps({
                "version": BUNDLE_VERSION,
                "source": "desktop",
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "beans": len(beans),
            }, indent=1))
    finally:
        conn.close()

    return _Written(target, len(beans), sum(len(b["sessions"]) for b in beans), image_count)


# ----------------------------------------------------------------- inspect --

def _read_bundle(path: Path) -> list:
    """Open a bundle and return its bean list, or raise a ValueError saying why not.

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
    except zipfile.BadZipFile:
        raise ValueError(f"{path.name} is not a zip file.") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path.name} contains damaged JSON: {exc}") from None
    if not isinstance(beans, list):
        raise ValueError(f"{path.name}'s {_BEANS} is not a list of beans.")
    return beans


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
    beans = _read_bundle(path)

    conn = connect()
    try:
        existing = {row["name"]: row for row in repo.list_beans(conn)}
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
    lines.append(
        "Beans are matched by name; renaming one on either side makes it import "
        "as a separate bean."
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
    beans = _read_bundle(path)
    try:
        choices = json.loads(resolutions or "{}")
    except json.JSONDecodeError as exc:
        return f"resolutions is not valid JSON: {exc}"

    added, replaced, kept, unanswered, skipped, duplicates = [], [], [], [], [], []
    conn = connect()
    try:
        existing = {row["name"]: row for row in repo.list_beans(conn)}
        seen = set()
        with zipfile.ZipFile(path) as archive:
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
                    if not _differences(bean, existing[name]):
                        kept.append(name)
                        continue
                    choice = choices.get(name)
                    if choice == "desktop":
                        kept.append(name)
                        continue
                    if choice == "skip":
                        skipped.append(name)
                        continue
                    if choice != "phone":
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
                _write_bean(conn, archive, bean, path)
        conn.commit()
    finally:
        conn.close()

    lines = [
        f"Added {len(added)}, replaced {len(replaced)}, kept local {len(kept)}, "
        f"skipped {len(skipped)}."
    ]
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


def _write_bean(conn, archive: zipfile.ZipFile, bean: dict, bundle_path: Path) -> None:
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

    for session in bean.get("sessions", []):
        session_id = repo.create_session(conn, bean_id)
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
            )

    # Images are extracted to a temporary path and handed to coffee-can's own
    # add_bean_image, so they land in images_dir(bean_id) exactly as they
    # would if added through the GUI -- rather than this module inventing a
    # second, drifting copy of that placement rule.
    staging = bundle_path.parent / ".bundle-staging"
    for image in bean.get("images", []):
        member = image.get("file")
        if not member:
            continue
        try:
            staging.mkdir(parents=True, exist_ok=True)
            extracted = Path(archive.extract(member, staging))
            repo.add_bean_image(conn, bean_id, extracted)
        except Exception:  # noqa: BLE001
            pass
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)


SYNC_TOOLS = [export_coffee_bundle, inspect_coffee_bundle, apply_coffee_bundle]
