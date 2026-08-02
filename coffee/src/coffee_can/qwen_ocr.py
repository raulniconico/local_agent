"""Bean profile field extraction from a bag-label photo via Qwen-Omni's
vision support -- the Qwen counterpart to claude_ocr.py's Claude-based
scanning, and the image counterpart to qwen_brew.py's audio-based voice
sessions.

gui/bean_dialog.py's _ScanWorker tries this *first*, ahead of claude_ocr.py,
whenever QWEN_API_KEY is set: a coffee-can install typically has both a
DashScope key (already paying for the voice-session feature) and an
Anthropic key (used elsewhere in the app, e.g. Ask AI's recipe review), and
without an explicit order label scanning would silently prefer whichever
`is_configured()` happened to be checked first -- Claude, before this module
existed -- and bill it on every scan even when Qwen was the one meant to be
used day to day. Falls back to Claude if Qwen isn't configured or the
request fails, then to local Tesseract OCR if neither is. The `openai`
package is an optional dependency (DashScope's compatible-mode endpoint is
OpenAI-compatible, same as qwen_brew.py's client), imported lazily here so
the rest of the app works without it installed.
"""

import base64
import json
import mimetypes
import os
from pathlib import Path

from dotenv import load_dotenv

from .paths import data_dir
from .repo import BEAN_FIELDS

# Same two locations claude_ocr.py and qwen_brew.py check -- current/parent
# working directory (source checkout) and the app's own data dir (packaged
# installs).
load_dotenv()
load_dotenv(data_dir() / ".env")

_BASE_URL = os.environ.get("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
# Same env var (and default) as qwen_brew.py's audio flow -- it's genuinely
# the same "omni" model instance handling a different modality here, not a
# separate deployment, so there's nothing to let vary independently the way
# claude_ocr.py's ANTHROPIC_OCR_MODEL is deliberately kept apart from the
# chat model.
_MODEL = os.environ.get("QWEN_OMNI_MODEL", "qwen3.5-omni-flash")
_TIMEOUT_SECONDS = 90.0

FIELDS = tuple(field for field in BEAN_FIELDS if "flavor_" not in field)


class QwenOcrUnavailableError(Exception):
    """Raised whenever this path can't be used -- no API key, the `openai`
    package isn't installed, or the request itself failed. Callers should
    catch this and fall back to Claude or local OCR rather than surface it
    directly."""


def is_configured() -> bool:
    return bool(os.environ.get("QWEN_API_KEY"))


def _extract_json(text: str):
    """Qwen isn't guaranteed to return bare JSON the way claude_ocr.py's
    schema-validated output_config is -- compatible-mode's response_format=
    json_object isn't reliable for omni models, so the shape is spelled out
    in the prompt instead and the reply parsed defensively. Same helper as
    qwen_brew.py's."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if "\n" in text:
            first_line, rest = text.split("\n", 1)
            if first_line.strip().lower() in ("json", ""):
                text = rest
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def guess_bean_fields(image_path: Path) -> dict:
    """Same {field: value} shape as ocr.guess_bean_fields/claude_ocr.guess_bean_fields,
    produced by asking Qwen to read the label directly instead of running
    local OCR text through regex/keyword heuristics."""
    if not is_configured():
        raise QwenOcrUnavailableError(
            "QWEN_API_KEY isn't set. Export it in your shell to enable Qwen-based scanning."
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise QwenOcrUnavailableError(f"The 'openai' package isn't installed: {exc}") from exc

    media_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
    image_b64 = base64.standard_b64encode(Path(image_path).read_bytes()).decode("ascii")

    prompt = (
        "This is a photo of a coffee bag label. Extract these fields, using an "
        "empty string for anything not present on the label. \"name\" is the "
        "specific coffee's name or lot -- not the roaster's brand, which goes "
        "in \"roaster\". \"process\" should be a short, standard process name "
        "(e.g. Washed, Natural, Honey, Anaerobic Natural) matching the label's "
        "own wording rather than an invented one. \"roast_date\" should be ISO "
        "format (YYYY-MM-DD) if a full date is printed, otherwise whatever "
        "partial date is shown. \"note\" is the label's tasting/flavour notes "
        "(e.g. \"blueberry, dark chocolate, jasmine\") plus any other remark "
        "worth keeping that has no field of its own, such as a roast level or "
        "a brew recommendation -- transcribe what's printed, don't invent "
        "tasting notes that aren't on the label. Reply with a single JSON "
        "object only, no other text, no markdown fencing, with exactly these "
        f"keys: {json.dumps(list(FIELDS))}."
    )

    try:
        client = OpenAI(api_key=os.environ["QWEN_API_KEY"], base_url=_BASE_URL, timeout=_TIMEOUT_SECONDS)
        response = client.chat.completions.create(
            model=_MODEL,
            modalities=["text"],
            stream=False,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{media_type};base64,{image_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
    except Exception as exc:  # network errors, auth errors, rate limits, etc.
        raise QwenOcrUnavailableError(f"Qwen API request failed: {exc}") from exc

    text = response.choices[0].message.content
    if not text:
        raise QwenOcrUnavailableError("Qwen's response didn't include any text.")

    data = _extract_json(text)
    if data is None:
        raise QwenOcrUnavailableError("Qwen didn't return valid JSON.")

    return {field: str(data.get(field) or "").strip() for field in FIELDS}