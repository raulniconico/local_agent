"""User-editable list of coffee grinders. See choice_lists.py."""

from typing import List

from . import choice_lists

_NAME = "grinders"


def load_grinders() -> List[str]:
    return choice_lists.load_list(_NAME)


def add_grinder(name: str) -> List[str]:
    return choice_lists.add_value(_NAME, name)
