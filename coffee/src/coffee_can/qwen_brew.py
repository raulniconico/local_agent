"""Brewing session extraction from a spoken description via Qwen-Omni's audio
understanding -- the microphone counterpart to deepseek_brew.py's text-based
"Ask AI" suggestions. Given a short recording of the user describing a brew
out loud and a bean's basic info, asks Qwen to parse it into the same
structured shape (plus a "dripper" field, since voice has to supply that too)
that gui/voice_brew_dialog.py turns into an actual session + brew_stages
rows.

Used by gui/voice_brew_dialog.py's microphone flow. The `openai` package is
an optional dependency (DashScope's compatible-mode endpoint is
OpenAI-compatible, same as deepseek_brew.py's DeepSeek client), imported
lazily here so the rest of the app works without it installed.
"""

import base64
import json
import os

from dotenv import load_dotenv

from .paths import data_dir

# Same two locations deepseek_brew.py and claude_ocr.py check -- current/
# parent working directory (source checkout) and the app's own data dir
# (packaged installs), so QWEN_API_KEY works the same way as the other
# provider keys.
load_dotenv()
load_dotenv(data_dir() / ".env")

_BASE_URL = os.environ.get("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
# Deliberately a separate env var from any chat-model QWEN_MODEL a sibling
# project might set (coffee_agent's LLM_PROVIDER=anthropic branch uses one
# for text chat) -- same reasoning as claude_ocr.py's ANTHROPIC_OCR_MODEL
# being distinct from the chat model, since this needs an audio-capable
# ("omni") model specifically and the two should be free to change
# independently.
_MODEL = os.environ.get("QWEN_OMNI_MODEL", "qwen3.5-omni-flash")
# Without this the SDK will wait indefinitely on a stalled connection, and
# the caller (a background thread behind gui/voice_brew_dialog.py's busy
# indicator) has no way to cancel an in-flight request.
_TIMEOUT_SECONDS = 90.0

# Qwen-Omni's compatible-mode endpoint doesn't support response_format=
# json_object (that's text-only-model territory), so the shape has to be
# spelled out in the prompt and the reply parsed defensively -- same
# reasoning as deepseek_brew.py's _EXAMPLE, plus "dripper" since there's no
# separate combo box to supply it here.
_EXAMPLE = {
    "dripper": "V60",
    "summary": "A short (2-4 sentence) restatement of anything said that doesn't fit another field -- tasting notes, technique remarks, etc. Plain text, no markdown.",
    "dose_g": 15,
    "grind_size": "medium-fine",
    "stages": [
        {"temperature_c": 92, "water_g": 30, "time_seconds": 30, "circling": "swirl gently"},
        {"temperature_c": 92, "water_g": 120, "time_seconds": 45, "circling": "none"},
        {"temperature_c": 92, "water_g": 100, "time_seconds": 45, "circling": "swirl gently"},
    ],
}


class QwenUnavailableError(Exception):
    """Raised when QWEN_API_KEY isn't set, or the request itself failed."""


def is_configured() -> bool:
    return bool(os.environ.get("QWEN_API_KEY"))


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


def _extract_json(text: str):
    """Qwen isn't guaranteed to return bare JSON the way DeepSeek's json_object
    mode is -- it regularly wraps it in a markdown code fence or a sentence of
    preamble. Strip a fence if present, then take the outermost {...} span."""
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
        "dripper": str(data.get("dripper") or "").strip(),
        "summary": str(data.get("summary") or "").strip(),
        "dose_g": _to_float(data.get("dose_g")),
        "grind_size": str(data.get("grind_size") or "").strip(),
        "stages": stages,
    }


def transcribe_brew_session(audio_bytes: bytes, audio_format: str, bean_info: dict) -> dict:
    """audio_bytes/audio_format describe a short recording of the user
    describing a brewing session out loud (e.g. a WAV file's raw bytes and
    "wav"). bean_info is the same {label: value} shape as
    deepseek_brew.suggest_brew's. Returns {"dripper": str, "summary": str,
    "dose_g": float|None, "grind_size": str, "stages": [{"temperature_c",
    "water_g", "time_seconds", "circling"}, ...]} -- any field Qwen didn't
    mention, or that didn't parse as a number, comes back as None/"" rather
    than raising."""
    if not is_configured():
        raise QwenUnavailableError(
            "QWEN_API_KEY isn't set. Add it to your shell environment or a .env file."
        )

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise QwenUnavailableError(f"The 'openai' package isn't installed: {exc}") from exc

    lines = [f"{label}: {value}" for label, value in bean_info.items() if value]
    bean_summary = "\n".join(lines) if lines else "(no details recorded for this bean)"
    audio_b64 = base64.standard_b64encode(audio_bytes).decode("ascii")

    prompt = (
        "This audio is a coffee brewer describing a hand-brew session out loud: "
        "the dripper, dose, grind size, and each pour (temperature, water "
        "amount, time, whether they swirled/stirred). Listen to it and reply "
        "with a single JSON object only, no other text, no markdown fencing, "
        "in exactly this shape (dose_g/temperature_c/water_g/time_seconds are "
        "numbers, not strings; leave a field empty/null if it wasn't "
        "mentioned):\n\n"
        f"{json.dumps(_EXAMPLE, indent=2)}\n\n"
        f"For context, this session is for this coffee bean:\n{bean_summary}\n\n"
        "\"stages\" should list every pour mentioned, in order, bloom first."
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
                        {"type": "text", "text": prompt},
                        {
                            "type": "input_audio",
                            "input_audio": {"data": audio_b64, "format": audio_format},
                        },
                    ],
                }
            ],
        )
    except Exception as exc:  # network errors, auth errors, rate limits, etc.
        raise QwenUnavailableError(f"Qwen API request failed: {exc}") from exc

    text = response.choices[0].message.content
    if not text:
        raise QwenUnavailableError("Qwen's response was empty -- try again.")

    data = _extract_json(text)
    if data is None:
        raise QwenUnavailableError("Qwen didn't return valid JSON -- try again.")

    return _normalize(data)