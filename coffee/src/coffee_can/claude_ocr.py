"""Bean profile field extraction from a bag-label photo via the Claude API's
vision support -- far more reliable at mapping varied real-world label
layouts to the right field than ocr.py's local Tesseract heuristics, at the
cost of needing an API key, network access, and sending the photo off-device.

bean_dialog.py tries this first when ANTHROPIC_API_KEY is set, and falls back
to ocr.py automatically otherwise, or if this raises for any reason (missing
`anthropic` package, network error, refusal, bad response) -- see
BeanDialog._run_scan(). The `anthropic` package is an optional dependency,
imported lazily here so the rest of the app works without it installed.
"""

import base64
import json
import mimetypes
import os
from pathlib import Path

from dotenv import load_dotenv

from .paths import data_dir
from .repo import BEAN_FIELDS

# ANTHROPIC_API_KEY can live in a .env file instead of the real shell
# environment -- checked in the current/parent working directory (running
# from inside a source checkout) and in the app's own data dir (so it's
# found the same way regardless of how coffeecan-gui was launched, e.g. from
# a pipx install via a desktop icon with no inherited shell environment).
# Neither call overrides a variable the real environment already set.
load_dotenv()
load_dotenv(data_dir() / ".env")

_MODEL = os.environ.get("ANTHROPIC_OCR_MODEL", "claude-opus-5")
_MAX_TOKENS = 1024

FIELDS = tuple(field for field in BEAN_FIELDS if "flavor_" not in field)


class ClaudeOcrUnavailableError(Exception):
    """Raised whenever this path can't be used -- no API key, the `anthropic`
    package isn't installed, or the request itself failed. Callers should
    catch this and fall back to ocr.py rather than surface it directly."""


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def guess_bean_fields(image_path: Path) -> dict:
    """Same {field: value} shape as ocr.guess_bean_fields, produced by asking
    Claude to read the label directly instead of running local OCR text
    through regex/keyword heuristics."""
    if not is_configured():
        raise ClaudeOcrUnavailableError(
            "ANTHROPIC_API_KEY isn't set. Export it in your shell to enable Claude-based scanning."
        )

    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise ClaudeOcrUnavailableError(f"The 'anthropic' package isn't installed: {exc}") from exc

    media_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
    image_b64 = base64.standard_b64encode(Path(image_path).read_bytes()).decode("ascii")

    schema = {
        "type": "object",
        "properties": {field: {"type": "string"} for field in FIELDS},
        "required": list(FIELDS),
        "additionalProperties": False,
    }
    prompt = (
        "This is a photo of a coffee bag label. Extract these fields, using an "
        "empty string for anything not present on the label. \"name\" is the "
        "specific coffee's name or lot -- not the roaster's brand, which goes "
        "in \"roaster\". \"process\" should be a short, standard process name "
        "(e.g. Washed, Natural, Honey, Anaerobic Natural) matching the label's "
        "own wording rather than an invented one. \"roast_date\" should be ISO "
        "format (YYYY-MM-DD) if a full date is printed, otherwise whatever "
        "partial date is shown."
    )

    try:
        client = Anthropic()
        response = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": image_b64},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
    except Exception as exc:  # network errors, auth errors, rate limits, etc.
        raise ClaudeOcrUnavailableError(f"Claude API request failed: {exc}") from exc

    if response.stop_reason == "refusal":
        raise ClaudeOcrUnavailableError("Claude declined to process this image.")

    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        raise ClaudeOcrUnavailableError("Claude's response didn't include any text.")

    data = json.loads(text)
    return {field: str(data.get(field) or "").strip() for field in FIELDS}
