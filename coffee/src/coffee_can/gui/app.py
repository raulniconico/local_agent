"""Entry point for the `coffeecan-gui` console script."""

import sys

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from ..assets import icon_path
from ..db import connect
from .main_window import MainWindow
from .theme import STYLESHEET


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont(app.font().family(), 10)
    app.setFont(font)
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
