"""Command-line interface for the coffee brewing journal."""

from datetime import date
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import repo
from .db import connect
from .formatting import (
    format_concentration,
    format_extraction,
    format_or_dash,
    format_score,
    format_seconds,
    parse_time_to_seconds,
)
from .paths import ALLOWED_IMAGE_SUFFIXES, MAX_IMAGES_PER_BEAN

console = Console()


def resolve_bean_or_fail(conn, identifier):
    try:
        return repo.resolve_bean(conn, identifier)
    except repo.NotFoundError as exc:
        raise click.ClickException(str(exc))


def get_session_or_fail(conn, session_id):
    row = repo.get_session(conn, session_id)
    if row is None:
        raise click.ClickException(f"no brewing session found with id {session_id}")
    return row


def ask(label, default=None, required=False):
    """Prompt for an optional (or required) text field. Blank keeps `default`."""
    suffix = "" if required else " [optional]"
    while True:
        value = click.prompt(f"{label}{suffix}", default=default or "", show_default=bool(default))
        value = value.strip()
        if value:
            return value
        if required:
            click.echo("  this field is required.")
            continue
        return default or None


def ask_float(label, default=None, minimum=None, maximum=None):
    default_display = "" if default is None else str(default)
    while True:
        raw = click.prompt(f"{label} [optional]", default=default_display, show_default=bool(default_display))
        raw = raw.strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except ValueError:
            click.echo("  please enter a number.")
            continue
        if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
            click.echo(f"  must be between {minimum} and {maximum}.")
            continue
        return value


def ask_time(label, default=None):
    default_display = "" if default is None else format_seconds(default)
    while True:
        raw = click.prompt(
            f"{label} (seconds or mm:ss) [optional]", default=default_display, show_default=bool(default_display)
        )
        raw = raw.strip()
        if not raw:
            return default
        try:
            return parse_time_to_seconds(raw)
        except ValueError:
            click.echo("  use seconds (e.g. 45) or mm:ss (e.g. 1:30).")


@click.group()
def main():
    """Track hand-brew coffee profiles and daily brewing sessions."""


@main.group()
def bean():
    """Manage coffee bean profiles."""


@main.group()
def brew():
    """Manage daily brewing sessions."""


# --- bean commands -----------------------------------------------------------

BEAN_TEXT_FIELDS = (
    ("origin", "Origin"),
    ("variety", "Variety"),
    ("altitude", "Altitude"),
    ("roaster", "Roaster (torrefactor)"),
    ("producer", "Producer"),
    ("process", "Process (e.g. washed, natural/dry, honey)"),
    ("roast_date", "Roast date (YYYY-MM-DD)"),
    ("note", "Note (tasting notes or other remark)"),
)

BEAN_SHOW_LABELS = (
    ("origin", "Origin"),
    ("variety", "Variety"),
    ("altitude", "Altitude"),
    ("roaster", "Roaster"),
    ("producer", "Producer"),
    ("process", "Process"),
    ("roast_date", "Roast date"),
    ("note", "Note"),
)


def _collect_bean_fields(conn, bean_id, row):
    for field, label in BEAN_TEXT_FIELDS:
        value = ask(label, default=row[field] if row else None)
        if value is not None:
            repo.update_bean_field(conn, bean_id, field, value)


def _collect_bean_images(conn, bean_id):
    existing = len(repo.list_bean_images(conn, bean_id))
    if existing >= MAX_IMAGES_PER_BEAN:
        return
    click.echo(f"Add photos/pages of the bag or spec sheet (up to {MAX_IMAGES_PER_BEAN - existing} more, blank to stop).")
    while existing < MAX_IMAGES_PER_BEAN:
        raw = click.prompt("  Image/PDF path", default="", show_default=False)
        raw = raw.strip()
        if not raw:
            break
        path = Path(raw).expanduser()
        if not path.is_file():
            click.echo("  file not found.")
            continue
        if path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
            click.echo(f"  unsupported file type; allowed: {', '.join(sorted(ALLOWED_IMAGE_SUFFIXES))}")
            continue
        try:
            position = repo.add_bean_image(conn, bean_id, path)
        except ValueError as exc:
            click.echo(f"  {exc}")
            break
        click.echo(f"  saved as page {position}.")
        existing += 1


@bean.command("add")
def bean_add():
    """Create a new coffee bean profile."""
    conn = connect()
    name = ask("Coffee name", required=True)
    bean_id = repo.create_bean(conn, name)
    click.echo(f"Created draft profile #{bean_id}. Leave a field blank to skip it.")
    _collect_bean_fields(conn, bean_id, row=None)
    _collect_bean_images(conn, bean_id)
    if click.confirm("Mark this profile as complete now?", default=True):
        repo.set_bean_status(conn, bean_id, "complete")
        click.echo(f"Saved coffee profile #{bean_id}: {name} (complete)")
    else:
        click.echo(f"Saved coffee profile #{bean_id}: {name} (draft -- resume with `coffee bean edit {bean_id}`)")


@bean.command("edit")
@click.argument("identifier")
def bean_edit(identifier):
    """Edit an existing coffee bean profile (by id or exact name)."""
    conn = connect()
    row = resolve_bean_or_fail(conn, identifier)
    click.echo(f"Editing profile #{row['id']}: {row['name']} (blank keeps current value)")
    new_name = ask("Coffee name", default=row["name"], required=True)
    if new_name != row["name"]:
        repo.update_bean_field(conn, row["id"], "name", new_name)
    _collect_bean_fields(conn, row["id"], row=row)
    _collect_bean_images(conn, row["id"])
    if row["status"] != "complete" and click.confirm("Mark this profile as complete now?", default=True):
        repo.set_bean_status(conn, row["id"], "complete")
    click.echo(f"Saved coffee profile #{row['id']}.")


@bean.command("list")
def bean_list():
    """List all coffee bean profiles."""
    conn = connect()
    rows = repo.list_beans(conn)
    if not rows:
        click.echo("No coffee profiles yet. Add one with `coffee bean add`.")
        return
    table = Table(title="Coffee profiles")
    for col in ("ID", "Name", "Origin", "Process", "Roast date", "Status", "Sessions"):
        table.add_column(col)
    for row in rows:
        table.add_row(
            str(row["id"]),
            row["name"],
            format_or_dash(row["origin"]),
            format_or_dash(row["process"]),
            format_or_dash(row["roast_date"]),
            row["status"],
            str(row["session_count"]),
        )
    console.print(table)


@bean.command("show")
@click.argument("identifier")
def bean_show(identifier):
    """Show full detail for a coffee bean profile."""
    conn = connect()
    row = resolve_bean_or_fail(conn, identifier)
    body = "\n".join(f"{label}: {format_or_dash(row[field])}" for field, label in BEAN_SHOW_LABELS)
    images = repo.list_bean_images(conn, row["id"])
    if images:
        body += "\nPages: " + ", ".join(img["file_path"] for img in images)
    console.print(Panel(body, title=f"#{row['id']} {row['name']} ({row['status']})"))

    sessions = repo.list_sessions(conn, bean_id=row["id"])
    if sessions:
        table = Table(title="Brewing sessions")
        for col in ("ID", "Date", "Dripper", "Score", "Status"):
            table.add_column(col)
        for s in sessions:
            table.add_row(
                str(s["id"]),
                format_or_dash(s["brew_date"]),
                format_or_dash(s["dripper"]),
                format_score(s["score"]),
                s["status"],
            )
        console.print(table)


@bean.command("delete")
@click.argument("identifier")
def bean_delete(identifier):
    """Delete a coffee bean profile and its brewing sessions."""
    conn = connect()
    row = resolve_bean_or_fail(conn, identifier)
    if click.confirm(f"Delete profile #{row['id']} '{row['name']}' and all its brewing sessions?"):
        repo.delete_bean(conn, row["id"])
        click.echo("Deleted.")


# --- brew commands -------------------------------------------------------------

SESSION_TEXT_FIELDS = (
    ("dripper", "Dripper"),
    ("filter_paper", "Filter paper"),
    ("grinder", "Grinder"),
    ("grind_size", "Grind size"),
    ("water_ppm", "Water PPM"),
    ("humidity", "Humidity %"),
    ("dose_g", "Dose (g)"),
)


def _collect_stages(conn, session_id):
    existing = len(repo.list_stages(conn, session_id))
    if existing:
        click.echo(f"{existing} stage(s) already recorded.")
    while True:
        if not click.confirm(f"Add {'a' if existing == 0 else 'another'} brewing stage?", default=(existing == 0)):
            break
        temperature = ask_float("  Temperature (°C)")
        water_g = ask_float("  Water (g)")
        time_seconds = ask_time("  Time")
        circling = ask("  Circling/agitation (e.g. swirl, stir, none)")
        stage_number = repo.add_stage(conn, session_id, temperature, water_g, time_seconds, circling)
        click.echo(f"  saved stage {stage_number}.")
        existing += 1


def _collect_evaluation(conn, session_id, row):
    has_score = row is not None and row["score"] is not None
    if not click.confirm("Evaluate this batch now?", default=not has_score):
        return
    score = ask_float("Score (0-5)", default=row["score"] if row else None, minimum=0, maximum=5)
    if score is not None:
        repo.update_session_field(conn, session_id, "score", score)
    extraction = ask_float(
        f"Extraction ({repo.EXTRACTION_MIN:g} under .. 0 well .. {repo.EXTRACTION_MAX:g} over)",
        default=row["extraction"] if row else None,
        minimum=repo.EXTRACTION_MIN,
        maximum=repo.EXTRACTION_MAX,
    )
    if extraction is not None:
        repo.update_session_field(conn, session_id, "extraction", float(extraction))
    concentration = ask_float(
        f"Concentration ({repo.CONCENTRATION_MIN:g} weak .. 0 just right .. {repo.CONCENTRATION_MAX:g} strong)",
        default=row["concentration"] if row else None,
        minimum=repo.CONCENTRATION_MIN,
        maximum=repo.CONCENTRATION_MAX,
    )
    if concentration is not None:
        repo.update_session_field(conn, session_id, "concentration", float(concentration))
    note = ask("Note", default=row["note"] if row else None)
    if note is not None:
        repo.update_session_field(conn, session_id, "note", note)


@brew.command("add")
@click.argument("bean_identifier")
def brew_add(bean_identifier):
    """Start a new brewing session for a coffee profile."""
    conn = connect()
    bean_row = resolve_bean_or_fail(conn, bean_identifier)
    session_id = repo.create_session(conn, bean_row["id"])
    click.echo(f"Brewing session #{session_id} for: {bean_row['name']}")

    brew_date = ask("Date (YYYY-MM-DD)", default=date.today().isoformat(), required=True)
    repo.update_session_field(conn, session_id, "brew_date", brew_date)
    for field, label in SESSION_TEXT_FIELDS:
        value = ask(label)
        if value is not None:
            repo.update_session_field(conn, session_id, field, value)

    _collect_stages(conn, session_id)
    _collect_evaluation(conn, session_id, row=None)

    if click.confirm("Mark this session as complete now?", default=True):
        repo.set_session_status(conn, session_id, "complete")
        click.echo(f"Saved brewing session #{session_id} (complete).")
    else:
        click.echo(f"Saved brewing session #{session_id} (draft -- resume with `coffee brew edit {session_id}`).")


@brew.command("edit")
@click.argument("session_id", type=int)
def brew_edit(session_id):
    """Resume/edit a brewing session (by id)."""
    conn = connect()
    row = get_session_or_fail(conn, session_id)
    bean_row = repo.get_bean(conn, row["bean_id"])
    click.echo(f"Editing session #{session_id} for {bean_row['name']} (blank keeps current value)")

    brew_date = ask("Date (YYYY-MM-DD)", default=row["brew_date"] or date.today().isoformat(), required=True)
    repo.update_session_field(conn, session_id, "brew_date", brew_date)
    for field, label in SESSION_TEXT_FIELDS:
        value = ask(label, default=row[field])
        if value is not None:
            repo.update_session_field(conn, session_id, field, value)

    _collect_stages(conn, session_id)
    _collect_evaluation(conn, session_id, row=row)

    if row["status"] != "complete" and click.confirm("Mark this session as complete now?", default=True):
        repo.set_session_status(conn, session_id, "complete")
    click.echo(f"Saved brewing session #{session_id}.")


@brew.command("list")
@click.option("--bean", "bean_identifier", default=None, help="Filter by coffee profile (id or name).")
def brew_list(bean_identifier):
    """List brewing sessions."""
    conn = connect()
    bean_id = None
    if bean_identifier is not None:
        bean_id = resolve_bean_or_fail(conn, bean_identifier)["id"]
    rows = repo.list_sessions(conn, bean_id=bean_id)
    if not rows:
        click.echo("No brewing sessions yet. Add one with `coffee brew add <bean>`.")
        return
    table = Table(title="Brewing sessions")
    for col in ("ID", "Bean", "Date", "Dripper", "Score", "Status"):
        table.add_column(col)
    for row in rows:
        table.add_row(
            str(row["id"]),
            row["bean_name"],
            format_or_dash(row["brew_date"]),
            format_or_dash(row["dripper"]),
            format_score(row["score"]),
            row["status"],
        )
    console.print(table)


@brew.command("show")
@click.argument("session_id", type=int)
def brew_show(session_id):
    """Show full detail for a brewing session."""
    conn = connect()
    row = get_session_or_fail(conn, session_id)
    bean_row = repo.get_bean(conn, row["bean_id"])

    flavor_bits = [f"{label} {row[field]:g}" for field, label in repo.FLAVOR_AXES if row[field]]

    body_lines = [
        f"Date: {format_or_dash(row['brew_date'])}",
        f"Dripper: {format_or_dash(row['dripper'])}",
        f"Filter paper: {format_or_dash(row['filter_paper'])}",
        f"Grinder: {format_or_dash(row['grinder'])}",
        f"Grind size: {format_or_dash(row['grind_size'])}",
        f"Water PPM: {format_or_dash(row['water_ppm'])}",
        f"Humidity: {format_or_dash(row['humidity'])}",
        f"Dose: {format_or_dash(row['dose_g'])}",
        f"Score: {format_score(row['score'])}",
        f"Extraction: {format_extraction(row['extraction'])}",
        f"Concentration: {format_concentration(row['concentration'])}",
        f"Flavor: {', '.join(flavor_bits) if flavor_bits else '-'}",
        f"Note: {format_or_dash(row['note'])}",
    ]
    console.print(Panel("\n".join(body_lines), title=f"#{row['id']} {bean_row['name']} ({row['status']})"))

    stages = repo.list_stages(conn, session_id)
    if stages:
        table = Table(title="Stages")
        for col in ("Stage", "Temp (°C)", "Water (g)", "Time", "Circling"):
            table.add_column(col)
        for s in stages:
            table.add_row(
                str(s["stage_number"]),
                format_or_dash(s["temperature_c"]),
                format_or_dash(s["water_g"]),
                format_seconds(s["time_seconds"]),
                format_or_dash(s["circling"]),
            )
        console.print(table)


@brew.command("delete")
@click.argument("session_id", type=int)
def brew_delete(session_id):
    """Delete a brewing session."""
    conn = connect()
    get_session_or_fail(conn, session_id)
    if click.confirm(f"Delete brewing session #{session_id}?"):
        repo.delete_session(conn, session_id)
        click.echo("Deleted.")


if __name__ == "__main__":
    main()
