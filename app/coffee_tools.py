"""Tools that let the agent register coffee bean profiles and brew sessions
into coffee-can, the sibling GUI app in ../coffee.

coffee-can's own dependencies (PySide6 for its GUI, click/rich for its CLI)
are not installed into this project's .venv -- only the storage layer we need
(repo.py/db.py) imports stdlib only, so we add coffee/src to sys.path and
import the package directly rather than pip-installing the whole distribution.

Field extraction from a file or image is left to the model: these tools hand
it raw text (via read_document / extract_text_from_image) and structured
create/list primitives, the same division of labor as the rest of app/tools.py.

Image OCR goes through the Claude API directly (not coffee_can.ocr's local
Tesseract), for the same reason coffee_can's own claude_ocr.py prefers it over
ocr.py: far more reliable at reading varied real-world label/handwriting
layouts. This requires ANTHROPIC_API_KEY regardless of LLM_PROVIDER, since
it's an independent API call rather than a turn of the main chat model.
"""

import base64
import mimetypes
import os
import sys
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from .config import ANTHROPIC_OCR_MODEL
from .tools import _resolve

_COFFEE_SRC = Path(__file__).resolve().parent.parent / "coffee" / "src"
if str(_COFFEE_SRC) not in sys.path:
    sys.path.insert(0, str(_COFFEE_SRC))

from coffee_can import repo  # noqa: E402
from coffee_can.db import connect  # noqa: E402
from coffee_can.paths import ALLOWED_IMAGE_SUFFIXES, MAX_IMAGES_PER_BEAN  # noqa: E402

_OCR_MAX_TOKENS = 2048
_OCR_PROMPT = (
    "Transcribe all readable text from this image exactly as it appears, "
    "preserving line breaks. It may be a coffee bag label, a handwritten "
    "brew note, or a receipt. Output only the transcribed text, nothing else."
)

BEAN_TEXT_FIELDS = ("origin", "variety", "altitude", "roaster", "producer", "process", "roast_date")
SESSION_TEXT_FIELDS = ("brew_date", "dripper", "filter_paper", "grinder", "grind_size", "water_ppm", "humidity", "note")


@tool
def list_coffee_beans() -> str:
    """List every coffee bean profile stored in coffee-can (id, name, origin, process, roast date, status)."""
    conn = connect()
    rows = repo.list_beans(conn)
    if not rows:
        return "No coffee bean profiles yet."
    lines = [
        f"#{r['id']} {r['name']} | origin={r['origin'] or '-'} | process={r['process'] or '-'} | "
        f"roast_date={r['roast_date'] or '-'} | status={r['status']} | sessions={r['session_count']}"
        for r in rows
    ]
    return "\n".join(lines)


@tool
def create_coffee_bean(
    name: str,
    origin: str = "",
    variety: str = "",
    altitude: str = "",
    roaster: str = "",
    producer: str = "",
    process: str = "",
    roast_date: str = "",
) -> str:
    """Register a new coffee bean profile in coffee-can and mark it complete.

    Always creates a new profile (does not update an existing one with a
    matching name) -- check list_coffee_beans first if you want to avoid
    duplicates. roast_date should be ISO format (YYYY-MM-DD) when known.
    """
    conn = connect()
    bean_id = repo.create_bean(conn, name)
    values = {
        "origin": origin,
        "variety": variety,
        "altitude": altitude,
        "roaster": roaster,
        "producer": producer,
        "process": process,
        "roast_date": roast_date,
    }
    for field in BEAN_TEXT_FIELDS:
        value = values[field]
        if value:
            repo.update_bean_field(conn, bean_id, field, value)
    repo.set_bean_status(conn, bean_id, "complete")
    return f"Created coffee bean #{bean_id}: {name}"


@tool
def add_coffee_bean_image(bean: str, path: str) -> str:
    """Attach a photo in the workspace (e.g. the bag label the agent just scanned) as a page image on a coffee bean profile.

    `bean` is the bean's numeric id or exact profile name. `path` must be
    .jpg, .jpeg, .png, .webp, or .pdf. A bean can hold only a few pages (see
    MAX_IMAGES_PER_BEAN); the file is copied into coffee-can's own storage,
    so it also shows up there (in the GUI's bean detail view and CLI's
    `bean show`).
    """
    try:
        full_path = _resolve(path)
    except ValueError as exc:
        return str(exc)
    if not full_path.exists():
        return f"File not found: {path}"
    if full_path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
        return f"Unsupported image type '{full_path.suffix}'. Allowed: {', '.join(sorted(ALLOWED_IMAGE_SUFFIXES))}"

    conn = connect()
    try:
        bean_row = repo.resolve_bean(conn, bean)
    except repo.NotFoundError as exc:
        return str(exc)
    try:
        position = repo.add_bean_image(conn, bean_row["id"], full_path)
    except ValueError as exc:
        return str(exc)
    return f"Attached {path} as page {position} on bean #{bean_row['id']} ({bean_row['name']})"


@tool
def list_coffee_brew_sessions(bean: str = "") -> str:
    """List brewing sessions in coffee-can, optionally filtered by bean (its numeric id or exact name)."""
    conn = connect()
    bean_id = None
    if bean:
        try:
            bean_id = repo.resolve_bean(conn, bean)["id"]
        except repo.NotFoundError as exc:
            return str(exc)
    rows = repo.list_sessions(conn, bean_id=bean_id)
    if not rows:
        return "No brewing sessions yet."
    lines = [
        f"#{r['id']} {r['bean_name']} | date={r['brew_date'] or '-'} | dripper={r['dripper'] or '-'} | "
        f"score={r['score'] if r['score'] is not None else '-'} | status={r['status']}"
        for r in rows
    ]
    return "\n".join(lines)


@tool
def create_coffee_brew_session(
    bean: str,
    brew_date: str = "",
    dripper: str = "",
    filter_paper: str = "",
    grinder: str = "",
    grind_size: str = "",
    water_ppm: str = "",
    humidity: str = "",
    dose_g: Optional[float] = None,
    score: Optional[float] = None,
    note: str = "",
) -> str:
    """Register a new brewing session in coffee-can for an existing bean and mark it complete.

    `bean` is the bean's numeric id or its exact profile name (use
    list_coffee_beans or create_coffee_bean first if it doesn't exist yet).
    brew_date should be ISO format (YYYY-MM-DD). score is 0-5.
    """
    conn = connect()
    try:
        bean_row = repo.resolve_bean(conn, bean)
    except repo.NotFoundError as exc:
        return str(exc)

    session_id = repo.create_session(conn, bean_row["id"])
    values = {
        "brew_date": brew_date,
        "dripper": dripper,
        "filter_paper": filter_paper,
        "grinder": grinder,
        "grind_size": grind_size,
        "water_ppm": water_ppm,
        "humidity": humidity,
        "note": note,
    }
    for field in SESSION_TEXT_FIELDS:
        value = values[field]
        if value:
            repo.update_session_field(conn, session_id, field, value)
    if dose_g is not None:
        repo.update_session_field(conn, session_id, "dose_g", dose_g)
    if score is not None:
        repo.update_session_field(conn, session_id, "score", score)
    repo.set_session_status(conn, session_id, "complete")
    return f"Created brewing session #{session_id} for bean #{bean_row['id']} ({bean_row['name']})"


@tool
def add_coffee_brew_stage(
    session_id: int,
    temperature_c: Optional[float] = None,
    water_g: Optional[float] = None,
    time_seconds: Optional[int] = None,
    circling: str = "",
) -> str:
    """Add one pour/stage (e.g. bloom, first pour) to an existing brewing session, in order added."""
    conn = connect()
    if repo.get_session(conn, session_id) is None:
        return f"No brewing session found with id {session_id}"
    stage_number = repo.add_stage(conn, session_id, temperature_c, water_g, time_seconds, circling or None)
    return f"Added stage {stage_number} to brewing session #{session_id}"


def _claude_extract_text(image_path: Path) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY isn't set. Image OCR uses the Claude API "
            "directly, so it needs a key even when LLM_PROVIDER=vllm -- set "
            "it in .env."
        )

    from anthropic import Anthropic  # imported lazily; only this tool needs it

    media_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
    image_b64 = base64.standard_b64encode(image_path.read_bytes()).decode("ascii")

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=ANTHROPIC_OCR_MODEL,
        max_tokens=_OCR_MAX_TOKENS,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                    {"type": "text", "text": _OCR_PROMPT},
                ],
            }
        ],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined to process this image.")
    text = next((block.text for block in response.content if block.type == "text"), None)
    return text or ""


@tool
def extract_text_from_image(path: str) -> str:
    """OCR a photo in the workspace (e.g. a coffee bag label or a handwritten brew note) via the Claude API and return its transcribed text.

    Supports .jpg, .jpeg, .png, .webp. Requires ANTHROPIC_API_KEY to be set
    (independent of LLM_PROVIDER) -- the photo is sent to the Claude API.
    The result is best-effort -- read it yourself to pick out bean or
    brew-session fields, then call create_coffee_bean /
    create_coffee_brew_session with what you find.
    """
    try:
        full_path = _resolve(path)
    except ValueError as exc:
        return str(exc)
    if not full_path.exists():
        return f"File not found: {path}"
    try:
        text = _claude_extract_text(full_path)
    except Exception as exc:  # missing key, bad/missing package, network, refusal, etc.
        return f"Image OCR failed: {exc}"
    return text or "(no text detected in image)"


COFFEE_TOOLS = [
    list_coffee_beans,
    create_coffee_bean,
    add_coffee_bean_image,
    list_coffee_brew_sessions,
    create_coffee_brew_session,
    add_coffee_brew_stage,
    extract_text_from_image,
]