"""The local user's profile: name, email, and an avatar photo.

Unlike beans/sessions there's exactly one of these per install, so it's a
single JSON blob (plus the avatar file itself) in the app's data dir rather
than a database table -- same idea as choice_lists.py's dripper/grinder
lists, just holding one record instead of a list.
"""

import json
import shutil
from pathlib import Path
from typing import Optional

from .paths import data_dir

_DEFAULTS = {"name": "", "email": "", "image_path": None}


def _profile_path() -> Path:
    return data_dir() / "profile.json"


def _avatar_dir() -> Path:
    return data_dir() / "profile"


def load_profile() -> dict:
    path = _profile_path()
    if not path.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)
    return {**_DEFAULTS, **data}


def save_profile(name: str, email: str, image_path: Optional[str]) -> None:
    data = {"name": name, "email": email, "image_path": image_path}
    _profile_path().write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def set_avatar(source_path: Path) -> str:
    """Copy source_path in as the new avatar (replacing any previous one,
    even under a different extension) and return its stored path."""
    clear_avatar()
    dest_dir = _avatar_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"avatar{source_path.suffix.lower()}"
    shutil.copy2(source_path, dest)
    return str(dest)


def clear_avatar() -> None:
    dest_dir = _avatar_dir()
    if dest_dir.exists():
        for existing in dest_dir.glob("avatar.*"):
            existing.unlink(missing_ok=True)
