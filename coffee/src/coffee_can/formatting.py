"""Small display/parsing helpers shared by the CLI commands."""

from typing import Optional


def parse_time_to_seconds(text: str) -> Optional[int]:
    """Accept plain seconds ("45") or mm:ss ("1:30")."""
    text = text.strip()
    if not text:
        return None
    if ":" in text:
        minutes, _, seconds = text.partition(":")
        return int(minutes) * 60 + int(seconds)
    return int(float(text))


def format_seconds(seconds) -> str:
    if seconds is None:
        return "-"
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def format_or_dash(value) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def format_score(score) -> str:
    if score is None:
        return "-"
    return f"{score:g}/5"


def format_extraction(value) -> str:
    """Render a continuous extraction value as its zone name plus the raw
    number -- the words alone would hide the difference between a hair off
    centre and the far end of the bar."""
    from .repo import EXTRACTION_ZONE_EDGE, EXTRACTION_ZONES  # keeps this module import-light

    if value is None:
        return "-"
    value = float(value)
    if value < -EXTRACTION_ZONE_EDGE:
        zone = EXTRACTION_ZONES[0]
    elif value <= EXTRACTION_ZONE_EDGE:
        zone = EXTRACTION_ZONES[1]
    else:
        zone = EXTRACTION_ZONES[2]
    return f"{zone} ({value:+.2f})"
