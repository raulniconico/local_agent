"""Filesystem locations for the app's persisted data (XDG data dir)."""

import os
import shutil
from pathlib import Path

APP_DIR_NAME = "coffee-can"
_OLD_APP_DIR_NAME = "coffee-journal"  # pre-rename data dir; migrated in place on first run

MAX_IMAGES_PER_BEAN = 5
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


def data_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    path = base / APP_DIR_NAME
    old_path = base / _OLD_APP_DIR_NAME
    if not path.exists() and old_path.exists():
        shutil.move(str(old_path), str(path))
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "coffee.db"


def images_dir(bean_id: int) -> Path:
    path = data_dir() / "images" / f"bean_{bean_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def journey_images_dir(journey_id: int) -> Path:
    """Where a cafe's photographs live -- a sibling of images_dir(), not a
    subdirectory of it.

    Its own tree for the reason the Android app keeps `journey_images/` apart
    from `bean_images/`: the two id sequences are independent, so
    `images/bean_3` and a journey 3 sharing that folder would interleave two
    unrelated sets of photographs and make "delete this bean's pages" delete
    someone's cafe.
    """
    path = data_dir() / "journey_images" / f"journey_{journey_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path
