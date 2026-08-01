"""iOS-inspired app-wide theme (QSS), applied once via QApplication.setStyleSheet.

Flat cards instead of boxed borders, borderless list rows, pill buttons with
primary/destructive variants (set via the `variant` dynamic property), and
the iOS systemGreen accent throughout.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat

#: The logo green. Inlined throughout STYLESHEET (QSS has no variables); named
#: here for the bits of theming that have to happen in Python instead.
ACCENT = "#34C759"

STYLESHEET = """
QMainWindow, QDialog, QMessageBox {
    background-color: #F2F2F7;
}

QLabel {
    color: #1C1C1E;
    background: transparent;
}

QGroupBox {
    background-color: #FFFFFF;
    border: none;
    border-radius: 14px;
    margin-top: 22px;
    padding: 14px 12px 12px 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 4px;
    top: 4px;
    padding: 0 4px;
    color: #8E8E93;
    font-size: 12px;
    font-weight: 600;
}

QLineEdit, QPlainTextEdit, QDoubleSpinBox, QDateEdit, QTimeEdit, QComboBox {
    background-color: #F2F2F7;
    border: 1.5px solid transparent;
    border-radius: 9px;
    padding: 7px 10px;
    color: #1C1C1E;
    selection-background-color: #BEEAC5;
}
QLineEdit:focus, QPlainTextEdit:focus, QDoubleSpinBox:focus, QDateEdit:focus, QTimeEdit:focus, QComboBox:focus {
    border: 1.5px solid #34C759;
    background-color: #FFFFFF;
}
QDateEdit::drop-down, QComboBox::drop-down {
    border: none;
    width: 22px;
}
QDateEdit::down-arrow, QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8E8E93;
    width: 0;
    height: 0;
    margin-right: 8px;
}
QCalendarWidget QWidget#qt_calendar_navigationbar {
    background-color: #34C759;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
}
QCalendarWidget QToolButton {
    color: #FFFFFF;
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px 10px;
    font-weight: 600;
}
QCalendarWidget QToolButton:hover, QCalendarWidget QToolButton:pressed {
    background-color: #30B953;
}
QCalendarWidget QToolButton::menu-indicator {
    image: none;
}
QCalendarWidget QSpinBox {
    background-color: #FFFFFF;
    border: none;
    border-radius: 6px;
    color: #1C1C1E;
    selection-background-color: #BEEAC5;
    selection-color: #1C1C1E;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #E5E5EA;
    border-radius: 3px;
}
QSlider::sub-page:horizontal {
    background: #34C759;
    border-radius: 3px;
}
QSlider::add-page:horizontal {
    background: #E5E5EA;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    background: #FFFFFF;
    border: 2px solid #34C759;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: #F2F2F7;
}
QCalendarWidget QAbstractItemView:enabled {
    selection-background-color: #34C759;
    selection-color: #FFFFFF;
}
QLineEdit:disabled, QPlainTextEdit:disabled, QDoubleSpinBox:disabled, QDateEdit:disabled {
    color: #C7C7CC;
}

QPushButton {
    background-color: #E5E5EA;
    color: #1C1C1E;
    border: none;
    border-radius: 10px;
    padding: 8px 18px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #DCDCE1;
}
QPushButton:pressed {
    background-color: #CFCFD4;
}
QPushButton:disabled {
    background-color: #F2F2F7;
    color: #C7C7CC;
}

QPushButton[variant="primary"] {
    background-color: #34C759;
    color: white;
}
QPushButton[variant="primary"]:hover {
    background-color: #30B953;
}
QPushButton[variant="primary"]:pressed {
    background-color: #248A3D;
}

QPushButton[variant="destructive"] {
    background-color: #FFEAEA;
    color: #FF3B30;
}
QPushButton[variant="destructive"]:hover {
    background-color: #FFDADA;
}
QPushButton[variant="destructive"]:pressed {
    background-color: #FFC7C7;
}

QTableWidget, QListWidget {
    background-color: #FFFFFF;
    alternate-background-color: #FAFAFC;
    gridline-color: transparent;
    border: none;
    border-radius: 12px;
    selection-background-color: #E3F8E8;
    selection-color: #1C1C1E;
    outline: none;
}
QTableWidget::item, QListWidget::item {
    padding: 6px 4px;
    border-bottom: 1px solid #EDEDF2;
}
QHeaderView::section {
    background-color: #FFFFFF;
    color: #8E8E93;
    padding: 8px 6px;
    border: none;
    border-bottom: 1px solid #EDEDF2;
    font-weight: 600;
    font-size: 11px;
}
QTableCornerButton::section {
    background-color: #FFFFFF;
    border: none;
}

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #D1D1D6;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QMessageBox QPushButton {
    min-width: 76px;
}
"""


def style_calendar_popup(date_edit) -> None:
    """Green the weekend columns of a QDateEdit's calendar popup.

    Everything else about the popup is covered by STYLESHEET, but Qt colors
    Saturday/Sunday -- both the weekday header and every date in those two
    columns -- with a hard-coded red QTextCharFormat that no QSS rule can
    reach. Left alone it's the loudest color in the popup, which makes the
    date picker look like it's flagging an error.

    Call this on every QDateEdit with setCalendarPopup(True). The popup's
    QCalendarWidget is created lazily, so this has to run after
    setCalendarPopup() -- calling it before builds the widget too early and
    the format is discarded.
    """
    weekend_format = QTextCharFormat()
    weekend_format.setForeground(QColor(ACCENT))
    calendar = date_edit.calendarWidget()
    for day in (Qt.DayOfWeek.Saturday, Qt.DayOfWeek.Sunday):
        calendar.setWeekdayTextFormat(day, weekend_format)
