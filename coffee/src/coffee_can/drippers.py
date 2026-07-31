"""User-editable list of hand-brew drippers. See choice_lists.py."""

from typing import List

from . import choice_lists

_NAME = "drippers"


def load_drippers() -> List[str]:
    return choice_lists.load_list(_NAME)


def add_dripper(name: str) -> List[str]:
    return choice_lists.add_value(_NAME, name)
