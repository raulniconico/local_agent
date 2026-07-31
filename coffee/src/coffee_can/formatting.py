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
