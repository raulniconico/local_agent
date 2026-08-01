"""Brewing recipe suggestions via the DeepSeek chat API -- text-only (see
claude_ocr.py's module docstring for why DeepSeek can't be used for the
image-based label scanning feature). Given a bean's basic info and a chosen
dripper, asks DeepSeek for a structured brew recipe: a short explanation plus
dose/grind/pour-stage numbers that gui/ai_brew_dialog.py turns into an actual
session + brew_stages rows, not just freeform text in a note field.

Used by gui/ai_brew_dialog.py's "Ask AI" flow. The `openai` package is an
optional dependency (DeepSeek's API is OpenAI-compatible), imported lazily
here so the rest of the app works without it installed.
"""

import json
import os

from dotenv import load_dotenv

from .paths import data_dir

# Same two locations claude_ocr.py checks -- current/parent working
# directory (source checkout) and the app's own data dir (packaged
# installs), so DEEPSEEK_API_KEY works the same way ANTHROPIC_API_KEY does.
load_dotenv()
load_dotenv(data_dir() / ".env")

_BASE_URL = "https://api.deepseek.com"
_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
# Without this the SDK will wait indefinitely on a stalled connection, and
# the caller (a background thread behind gui/ai_brew_dialog.py's busy
# indicator) has no way to cancel an in-flight request -- so a dead network
# would leave the dialog spinning until the app is killed.
_TIMEOUT_SECONDS = 90.0

# DeepSeek's JSON mode (unlike Claude's schema-validated structured outputs)
# only guarantees syntactically valid JSON, not that it matches any
# particular shape -- so the prompt has to spell out the shape via an
# example, and the response still needs defensive parsing on our side.
_EXAMPLE = {
    "summary": "A short (2-4 sentence) explanation of the recipe: ratio, why this grind/temperature, anything else worth noting. Plain text, no markdown.",
    "dose_g": 15,
    "grind_size": "medium-fine",
    "stages": [
        {"temperature_c": 92, "water_g": 30, "time_seconds": 30, "circling": "swirl gently"},
        {"temperature_c": 92, "water_g": 120, "time_seconds": 45, "circling": "none"},
        {"temperature_c": 92, "water_g": 100, "time_seconds": 45, "circling": "swirl gently"},
    ],
}


class DeepSeekUnavailableError(Exception):
    """Raised when DEEPSEEK_API_KEY isn't set, or the request itself failed."""


def is_configured() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY"))


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _normalize(data: dict) -> dict:
    stages = []
    for raw in data.get("stages") or []:
        if not isinstance(raw, dict):
            continue
        stages.append(
            {
                "temperature_c": _to_float(raw.get("temperature_c")),
                "water_g": _to_float(raw.get("water_g")),
                "time_seconds": _to_int(raw.get("time_seconds")),
                "circling": (str(raw.get("circling")).strip() or None) if raw.get("circling") else None,
            }
        )
    return {
        "summary": str(data.get("summary") or "").strip(),
        "dose_g": _to_float(data.get("dose_g")),
        "grind_size": str(data.get("grind_size") or "").strip(),
        "stages": stages,
    }


def suggest_brew(bean_info: dict, dripper: str) -> dict:
    """bean_info is a {label: value} dict of the bean's basic details (blank
    values are skipped). Returns {"summary": str, "dose_g": float|None,
    "grind_size": str, "stages": [{"temperature_c", "water_g",
    "time_seconds", "circling"}, ...]} -- any field DeepSeek didn't provide
    or that didn't parse as a number comes back as None/"" rather than
    raising, since JSON mode doesn't guarantee the shape."""
    if not is_configured():
        raise DeepSeekUnavailableError(
            "DEEPSEEK_API_KEY isn't set. Add it to your shell environment or a .env file."
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise DeepSeekUnavailableError(f"The 'openai' package isn't installed: {exc}") from exc

    lines = [f"{label}: {value}" for label, value in bean_info.items() if value]
    bean_summary = "\n".join(lines) if lines else "(no details recorded for this bean)"
    prompt = (
        "You are a specialty coffee hand-brew expert. Given this coffee bean:\n\n"
        f"{bean_summary}\n\nand this dripper: {dripper}\n\n"
        "Suggest a brewing recipe and reply with a single JSON object only, "
        "no other text, in exactly this shape (temperature_c/water_g/"
        "time_seconds are numbers, not strings):\n\n"
        f"{json.dumps(_EXAMPLE, indent=2)}\n\n"
        "\"stages\" should list every pour in order, bloom first, typically "
        "2-5 stages depending on the dripper and recipe."
    )

    try:
        client = OpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"], base_url=_BASE_URL, timeout=_TIMEOUT_SECONDS
        )
        response = client.chat.completions.create(
            model=_MODEL,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # network errors, auth errors, rate limits, etc.
        raise DeepSeekUnavailableError(f"DeepSeek API request failed: {exc}") from exc

    text = response.choices[0].message.content
    if not text:
        raise DeepSeekUnavailableError("DeepSeek's response was empty -- try again.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DeepSeekUnavailableError(f"DeepSeek didn't return valid JSON: {exc}") from exc

    return _normalize(data)
