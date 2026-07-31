"""Bundled static files (currently just the app icon)."""

from importlib import resources
from typing import Optional


def icon_path() -> Optional[str]:
    path = resources.files(__package__).joinpath("icon.svg")
    return str(path) if path.is_file() else None
