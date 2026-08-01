"""Bundled static files: the app icon and the Fredoka UI font.

Fredoka (SIL Open Font License 1.1, see Fredoka-OFL.txt) is shipped with the
package rather than assumed present on the system, so the app looks the same
on any machine it's installed to.

These are static Regular/Bold instances cut from the upstream variable font
(`Fredoka[wdth,wght].ttf`, wght 300-700). The variable original registers
with Qt as a single "Light" style -- its default weight is 300 -- so bold
text came out synthetically emboldened off a too-thin base, and the QSS
`font-weight` rules in theme.py had nothing real to select. Two static faces
give Qt genuine Regular and Bold styles under one family.
"""

from importlib import resources
from typing import List, Optional

FONT_FAMILY = "Fredoka"
_FONT_FILES = ("Fredoka-Regular.ttf", "Fredoka-Bold.ttf")


def icon_path() -> Optional[str]:
    path = resources.files(__package__).joinpath("icon.svg")
    return str(path) if path.is_file() else None


def font_paths() -> List[str]:
    """Every bundled face of the UI font; all must be registered with Qt for
    the family to offer both weights."""
    found = []
    for name in _FONT_FILES:
        path = resources.files(__package__).joinpath(name)
        if path.is_file():
            found.append(str(path))
    return found
