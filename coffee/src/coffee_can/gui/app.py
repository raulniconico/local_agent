"""Entry point for the `coffeecan-gui` console script."""

import sys

from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from ..assets import FONT_FAMILY, font_paths, icon_path
from ..db import connect
from .main_window import MainWindow
from .theme import STYLESHEET


def load_app_font() -> str:
    """Register every bundled UI-font face and return the family name to use.
    Falls back to the platform default if the files are missing or Qt refuses
    them, so a font problem can never stop the app from starting."""
    families = []
    for path in font_paths():
        font_id = QFontDatabase.addApplicationFont(path)
        if font_id >= 0:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    if not families:
        return QApplication.font().family()
    return FONT_FAMILY if FONT_FAMILY in families else families[0]


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont(load_app_font(), 10))
    app.setStyleSheet(STYLESHEET)
    # Ties this running process to coffee-can.desktop so the taskbar/dock
    # (GNOME Shell in particular) picks up its icon instead of a generic one --
    # they match by desktop file, not by reading the live window icon pixmap.
    app.setDesktopFileName("coffee-can")
    icon = icon_path()
    if icon:
        app.setWindowIcon(QIcon(icon))
    window = MainWindow(connect())
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
