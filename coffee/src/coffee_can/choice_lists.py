"""User-editable choice lists (drippers, grinders, ...).

Each list is seeded once from a bundled default JSON file (assets/<name>.json)
into a writable copy under the app's data dir, so users can add their own
entries without touching the installed package.
"""

import json
from importlib import resources
from pathlib import Path
from typing import List

from .paths import data_dir


def _bundled_defaults(name: str) -> List[str]:
    try:
        text = resources.files("coffee_can.assets").joinpath(f"{name}.json").read_text(encoding="utf-8")
        return json.loads(text)
    except (FileNotFoundError, ModuleNotFoundError, json.JSONDecodeError):
        return []


def _user_path(name: str) -> Path:
    return data_dir() / f"{name}.json"


def save_list(name: str, values: List[str]) -> None:
    _user_path(name).write_text(json.dumps(values, indent=2, ensure_ascii=False), encoding="utf-8")


def load_list(name: str) -> List[str]:
    path = _user_path(name)
    if not path.exists():
        values = _bundled_defaults(name)
        save_list(name, values)
        return values
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _bundled_defaults(name)


def add_value(name: str, value: str) -> List[str]:
    """Append `value` to list `name` if it's new (case-insensitive) and persist it."""
    value = value.strip()
    values = load_list(name)
    if value and not any(existing.lower() == value.lower() for existing in values):
        values.append(value)
        save_list(name, values)
    return values
