"""User-editable list of filter papers. See choice_lists.py."""

from typing import List

from . import choice_lists

_NAME = "filters"


def load_filters() -> List[str]:
    return choice_lists.load_list(_NAME)


def add_filter(name: str) -> List[str]:
    return choice_lists.add_value(_NAME, name)
