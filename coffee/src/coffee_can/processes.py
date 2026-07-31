"""User-editable list of coffee processing methods. See choice_lists.py."""

from typing import List

from . import choice_lists

_NAME = "processes"


def load_processes() -> List[str]:
    return choice_lists.load_list(_NAME)


def add_process(name: str) -> List[str]:
    return choice_lists.add_value(_NAME, name)
