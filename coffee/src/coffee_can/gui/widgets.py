"""Small custom widgets not provided by Qt."""

import math
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import (
    QDate,
    QPointF,
    Property,
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QTransform
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from .. import drippers, filters, grinders, processes, whats_new
from .theme import style_calendar_popup

_ISO_FORMAT = "yyyy-MM-dd"


def circular_pixmap(path: str, size: int) -> QPixmap:
    """Load an image, center-crop it to a square, and mask it to a circle --
    for avatar-style previews. Returns a null QPixmap if path doesn't load."""
    source = QPixmap(path)
    if source.isNull():
        return QPixmap()
    scaled = source.scaled(
        size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation
    )
    x = max(0, (scaled.width() - size) // 2)
    y = max(0, (scaled.height() - size) // 2)
    cropped = scaled.copy(x, y, size, size)

    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addEllipse(0, 0, size, size)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return result


def default_avatar_pixmap(size: int, background: str = "#D7F5DE", foreground: str = "#FFFFFF") -> QPixmap:
    """A simple coffee-can placeholder avatar -- the same little can shape
    as the header banner's walking animation, just standing still and
    centered -- drawn in solid colors we control exactly, unlike a text/
    emoji glyph, whose color a color-emoji font renders regardless of the
    widget's styled text color."""
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    painter.setBrush(QColor(background))
    painter.drawEllipse(0, 0, size, size)

    # Same proportions as HeaderBanner._draw_can (body 22x19, lid 24x8,
    # overlapping the body by 3), scaled to this avatar's size.
    body_w = size * 0.34
    body_h = body_w * (19 / 22)
    lid_w = body_w * (24 / 22)
    lid_h = body_w * (8 / 22)
    overlap = body_w * (3 / 22)
    radius_body = body_w * (4 / 22)
    radius_lid = body_w * (3 / 22)

    total_h = lid_h + body_h - overlap
    top_y = (size - total_h) / 2

    painter.setBrush(QColor(foreground))
    painter.drawRoundedRect(QRectF((size - body_w) / 2, top_y + lid_h - overlap, body_w, body_h), radius_body, radius_body)
    painter.drawRoundedRect(QRectF((size - lid_w) / 2, top_y, lid_w, lid_h), radius_lid, radius_lid)

    painter.end()
    return result


def share_icon_pixmap(size: int, color: str = "#1C1C1E") -> QPixmap:
    """A share glyph (arrow out of an open tray, the common iOS/Android
    "share" shape) drawn in a solid color we control exactly -- for an
    icon-only button, since a text/emoji glyph's color isn't reliably
    controllable (see default_avatar_pixmap's docstring)."""
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    pen = QPen(QColor(color))
    pen.setWidthF(max(1.4, size * 0.09))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    cx = size / 2
    shaft_top = size * 0.08
    shaft_bottom = size * 0.56
    painter.drawLine(QPointF(cx, shaft_bottom), QPointF(cx, shaft_top))
    head = size * 0.2
    painter.drawLine(QPointF(cx, shaft_top), QPointF(cx - head, shaft_top + head))
    painter.drawLine(QPointF(cx, shaft_top), QPointF(cx + head, shaft_top + head))

    tray_top = size * 0.68
    tray_left = size * 0.14
    tray_right = size * 0.86
    tray_bottom = size * 0.9
    painter.drawLine(QPointF(tray_left, tray_top), QPointF(tray_left, tray_bottom))
    painter.drawLine(QPointF(tray_left, tray_bottom), QPointF(tray_right, tray_bottom))
    painter.drawLine(QPointF(tray_right, tray_bottom), QPointF(tray_right, tray_top))

    painter.end()
    return result


def thumbs_up_can_pixmap(size: int, color: str = "#FFFFFF") -> QPixmap:
    """The walking can (WalkingCanStrip's little character) throwing a thumbs
    up -- the "saved it" confirmation on SaveButton.

    Drawn as a filled silhouette in one colour, so it reads on the green
    primary button it sits on. Three things carry the read at ~24px:

    * The thumb reaches above the can's lid. Once the details stop
      resolving, that break in the top line is what still says "thumbs up".
    * The hand is a separate shape with a gap rather than an arm joined to
      the body -- a connected arm merges into the can and the whole thing
      turns into one blob.
    * The face is punched out with CompositionMode_Clear rather than painted
      in the button's green, so the eyes and smile stay true holes against
      the hover and pressed shades too.
    """
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))

    def box(left, top, right, bottom, radius):
        painter.drawRoundedRect(
            QRectF(size * left, size * top, size * (right - left), size * (bottom - top)),
            size * radius,
            size * radius,
        )

    def capsule(x1, y1, x2, y2, width):
        pen = QPen(QColor(color))
        pen.setWidthF(size * width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(size * x1, size * y1), QPointF(size * x2, size * y2))
        painter.setPen(Qt.PenStyle.NoPen)

    # The can, drawn stubby and heavily rounded -- squarer corners are what
    # made this read as a waste bin rather than as the character.
    box(0.03, 0.30, 0.50, 0.41, 0.05)  # lid
    box(0.06, 0.37, 0.47, 0.85, 0.15)  # body
    painter.drawEllipse(QPointF(size * 0.15, size * 0.88), size * 0.075, size * 0.05)
    painter.drawEllipse(QPointF(size * 0.37, size * 0.88), size * 0.075, size * 0.05)

    # The thumbs up. The thumb rises from the fist's *left* edge, not its
    # middle -- centred, the two shapes read as a lollipop rather than a
    # hand. Drawn as a round-capped stroke so it tapers to a soft tip
    # instead of a cut-off bar.
    box(0.56, 0.55, 0.97, 0.88, 0.12)
    capsule(0.645, 0.60, 0.665, 0.21, 0.20)

    # Everything below is punched out of the silhouette rather than painted
    # in the button's green, so it stays a true hole against the hover and
    # pressed shades too.
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)

    # Two curled fingers -- what finally sells the fist as a hand.
    knuckle = QPen(QColor(color))
    knuckle.setWidthF(size * 0.035)
    knuckle.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(knuckle)
    for y in (0.68, 0.78):
        painter.drawLine(QPointF(size * 0.66, size * y), QPointF(size * 0.94, size * y))
    painter.setPen(Qt.PenStyle.NoPen)

    # A face, so it's the little can and not just a shape.
    eye = size * 0.052
    painter.setBrush(QColor(color))
    painter.drawEllipse(QPointF(size * 0.18, size * 0.53), eye, eye)
    painter.drawEllipse(QPointF(size * 0.35, size * 0.53), eye, eye)
    smile = QPen(QColor(color))
    smile.setWidthF(size * 0.05)
    smile.setCapStyle(Qt.PenCapStyle.RoundCap)
    painter.setPen(smile)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawArc(
        QRectF(size * 0.17, size * 0.56, size * 0.18, size * 0.14), 200 * 16, 140 * 16
    )
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

    painter.end()
    return result


class SaveButton(QPushButton):
    """A Save button that answers a successful save by swapping its label for
    the can giving a thumbs up, then settling back.

    Feedback is pushed by the caller (flash_saved) rather than wired to
    `clicked` here, so it only fires on a save that actually happened -- the
    same handler is reused elsewhere in at least one dialog to persist
    on-screen state before sharing, which shouldn't look like a save.
    """

    _FEEDBACK_MS = 1500
    _ICON_SIZE = 24

    def __init__(self, text: str = "Save", parent=None):
        super().__init__(text, parent)
        self._label = text
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._restore)

    def flash_saved(self) -> None:
        if not self._timer.isActive():
            # Pin the width the label needs before swapping it out, or the
            # button shrinks to the icon and shoves its neighbours sideways
            # for the duration.
            self.setMinimumWidth(self.sizeHint().width())
        self.setIcon(QIcon(thumbs_up_can_pixmap(self._ICON_SIZE)))
        self.setIconSize(QSize(self._ICON_SIZE, self._ICON_SIZE))
        self.setText("")
        self._timer.start(self._FEEDBACK_MS)

    def _restore(self) -> None:
        self.setIcon(QIcon())
        self.setText(self._label)


class OptionalDateEdit(QWidget):
    """A calendar-popup date picker plus a Clear button, for optional date
    fields (e.g. roast date) where "not set" must be a selectable state.
    API-compatible with QLineEdit's text()/setText() for drop-in reuse.

    The picker's own value always stays a real, sensible date (today by
    default) -- Qt's calendar popup and the field's current value are the
    same underlying property, so a "not set" sentinel date would make the
    popup open on that sentinel (e.g. year 1901) instead of today. "Set"
    vs. "not set" is tracked separately in _is_set.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_set = False

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        style_calendar_popup(self.date_edit)
        self.date_edit.setDisplayFormat(_ISO_FORMAT)
        self.date_edit.setMaximumDate(QDate.currentDate())
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.dateChanged.connect(self._on_date_changed)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.date_edit, 1)
        layout.addWidget(clear_btn)
        self._update_style()

    def _on_date_changed(self, _new_date) -> None:
        self._is_set = True
        self._update_style()

    def _update_style(self) -> None:
        # Scoped to QDateEdit rather than a bare `color:` -- a widget's
        # stylesheet applies to its children too, and the calendar popup is
        # one of them, so the unscoped version greyed out the popup's month
        # and year labels against their green navigation bar.
        self.date_edit.setStyleSheet("" if self._is_set else "QDateEdit { color: #8E8E93; }")

    def text(self) -> str:
        return self.date_edit.date().toString(_ISO_FORMAT) if self._is_set else ""

    def setText(self, value) -> None:
        parsed = QDate.fromString(value, _ISO_FORMAT) if value else None
        valid = bool(parsed and parsed.isValid())
        self.date_edit.blockSignals(True)
        self.date_edit.setDate(parsed if valid else QDate.currentDate())
        self.date_edit.blockSignals(False)
        self._is_set = valid
        self._update_style()

    def clear(self) -> None:
        self.date_edit.blockSignals(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.blockSignals(False)
        self._is_set = False
        self._update_style()


class NoteEdit(QPlainTextEdit):
    """A short multi-line free-text box for a bean's tasting notes/remarks.
    API-compatible with QLineEdit's text()/setText(), the same drop-in trick
    OptionalDateEdit uses, so it slots into bean_dialog's FIELD_LABELS loop
    alongside the plain QLineEdit fields."""

    _VISIBLE_ROWS = 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Tasting notes, or any other remark about this coffee")
        # Tall enough for a few lines but not so tall it pushes the rest of
        # the Coffee Details form off-screen; it scrolls past that.
        self.setFixedHeight(int(self.fontMetrics().lineSpacing() * self._VISIBLE_ROWS) + 16)

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, value) -> None:
        self.setPlainText(value or "")


_OFF_COLOR = QColor("#D1D1D6")
_ON_COLOR = QColor("#34C759")


class ToggleSwitch(QWidget):
    """An iOS-style animated pill switch. Drop-in for the QCheckBox calls we
    use elsewhere (isChecked/setChecked/toggled), minus the built-in label."""

    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checked = False
        self._knob_pos = 0.0  # 0.0 = off, 1.0 = on
        self._anim = QPropertyAnimation(self, b"knob_pos", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 26)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool, animate: bool = True) -> None:
        checked = bool(checked)
        changed = checked != self._checked
        self._checked = checked
        self._anim.stop()
        if animate:
            self._anim.setStartValue(self._knob_pos)
            self._anim.setEndValue(1.0 if checked else 0.0)
            self._anim.start()
        else:
            self.knob_pos = 1.0 if checked else 0.0
        if changed:
            self.toggled.emit(checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
        super().mousePressEvent(event)

    def _get_knob_pos(self) -> float:
        return self._knob_pos

    def _set_knob_pos(self, value: float) -> None:
        self._knob_pos = value
        self.update()

    knob_pos = Property(float, _get_knob_pos, _set_knob_pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = QRectF(self.rect().adjusted(1, 1, -1, -1))
        radius = rect.height() / 2
        t = self._knob_pos
        bg_color = QColor(
            int(_OFF_COLOR.red() + (_ON_COLOR.red() - _OFF_COLOR.red()) * t),
            int(_OFF_COLOR.green() + (_ON_COLOR.green() - _OFF_COLOR.green()) * t),
            int(_OFF_COLOR.blue() + (_ON_COLOR.blue() - _OFF_COLOR.blue()) * t),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(rect, radius, radius)

        knob_diameter = rect.height() - 4
        knob_x = rect.left() + 2 + t * (rect.width() - knob_diameter - 4)
        knob_rect = QRectF(knob_x, rect.top() + 2, knob_diameter, knob_diameter)
        painter.setBrush(QColor("white"))
        painter.drawEllipse(knob_rect)


def _blend(start: QColor, end: QColor, t: float) -> QColor:
    """Straight-line RGB mix, `t` clamped to 0..1."""
    t = max(0.0, min(1.0, t))
    return QColor(
        round(start.red() + (end.red() - start.red()) * t),
        round(start.green() + (end.green() - start.green()) * t),
        round(start.blue() + (end.blue() - start.blue()) * t),
    )


class ExtractionBar(QWidget):
    """A continuous under/well/over-extracted scale: one wide bar with its
    three zone names written inside it, tinting as it moves.

    Deliberately not a QSlider. The value is continuous rather than stepped,
    the zone names sit inside the groove, and the whole bar re-tints with
    the value -- light green at the under end, the logo's green at centre,
    dark green at the over end -- none of which QSlider's groove/handle
    subcontrols can express. It still reports through a `valueChanged`
    signal and takes its labels as a constructor argument (like RadarChart),
    so callers wire it up the same way they would a stock widget.

    The colour ramp runs light -> logo -> dark rather than, say, red to
    green: both ends are failures, so neither should look like the "good"
    end, and centring the logo colour makes well-extracted the one the eye
    settles on.
    """

    valueChanged = Signal(float)

    _HEIGHT = 66
    _LABEL_SIZE = 15
    _RADIUS = 16
    _INSET = 16  # keeps the handle clear of the rounded ends
    _HANDLE_WIDTH = 8
    _HANDLE_HEIGHT = 13
    _KEY_STEP = 0.05

    _UNDER = QColor("#BFEDCD")  # light green
    _WELL = QColor("#34C759")  # the logo's green
    _OVER = QColor("#176B2C")  # dark green

    def __init__(self, labels, minimum=-1.0, maximum=1.0, parent=None):
        super().__init__(parent)
        self._labels = tuple(labels)
        self._min = float(minimum)
        self._max = float(maximum)
        self._value = 0.0
        self.setFixedHeight(self._HEIGHT)
        # Wide enough that the three zone names still get a third each
        # without colliding at the label size above.
        self.setMinimumWidth(430)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # --- value ----------------------------------------------------------

    def value(self) -> float:
        return self._value

    def setValue(self, value) -> None:
        value = max(self._min, min(self._max, float(value)))
        if value == self._value:
            return
        self._value = value
        self.update()
        self.valueChanged.emit(value)

    def _fraction(self) -> float:
        return (self._value - self._min) / (self._max - self._min)

    def _active_zone(self) -> int:
        edge = (self._max - self._min) / 6.0
        if self._value < -edge:
            return 0
        return 1 if self._value <= edge else 2

    # --- painting -------------------------------------------------------

    def _fill_color(self) -> QColor:
        centre = (0.0 - self._min) / (self._max - self._min)
        fraction = self._fraction()
        if fraction <= centre:
            return _blend(self._UNDER, self._WELL, fraction / centre if centre else 1.0)
        return _blend(self._WELL, self._OVER, (fraction - centre) / (1.0 - centre) if centre < 1 else 1.0)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())

        fill = self._fill_color()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        painter.drawRoundedRect(rect, self._RADIUS, self._RADIUS)

        self._draw_labels(painter, rect, fill)
        self._draw_handle(painter, rect)

    def _draw_labels(self, painter: QPainter, rect: QRectF, fill: QColor) -> None:
        # Contrast has to follow the tint, which spans most of the way from
        # near-white to near-black as the bar moves end to end.
        luminance = (0.299 * fill.red() + 0.587 * fill.green() + 0.114 * fill.blue()) / 255
        painter.setPen(QColor("#1C1C1E") if luminance > 0.62 else QColor("#FFFFFF"))

        font = painter.font()
        font.setPixelSize(self._LABEL_SIZE)
        active = self._active_zone()
        third = rect.width() / 3
        for index, label in enumerate(self._labels):
            font.setBold(index == active)
            painter.setFont(font)
            cell = QRectF(rect.left() + index * third, rect.top(), third, rect.height())
            painter.drawText(cell, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_handle(self, painter: QPainter, rect: QRectF) -> None:
        # Two marks hugging the top and bottom edges rather than one
        # full-height bar: the zone names run across the middle of the
        # widget, and a solid handle crossing them blanked out whichever
        # letter it happened to land on.
        x = rect.left() + self._INSET + self._fraction() * (rect.width() - 2 * self._INSET)
        radius = self._HANDLE_WIDTH / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 240))
        for top in (rect.top() + 5, rect.bottom() - 5 - self._HANDLE_HEIGHT):
            painter.drawRoundedRect(
                QRectF(x - radius, top, self._HANDLE_WIDTH, self._HANDLE_HEIGHT), radius, radius
            )

    # --- interaction ----------------------------------------------------

    def _value_for_x(self, x: float) -> float:
        usable = max(1.0, self.width() - 2 * self._INSET)
        return self._min + ((x - self._INSET) / usable) * (self._max - self._min)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setValue(self._value_for_x(event.position().x()))
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.setValue(self._value_for_x(event.position().x()))
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Down):
            self.setValue(self._value - self._KEY_STEP)
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_Up):
            self.setValue(self._value + self._KEY_STEP)
        elif key == Qt.Key.Key_Home:
            self.setValue(self._min)
        elif key == Qt.Key.Key_End:
            self.setValue(self._max)
        else:
            super().keyPressEvent(event)
            return
        event.accept()


_BANNER_GREEN = QColor("#D7F5DE")  # lighter tint of the logo's #34C759


class WalkingCanStrip(QWidget):
    """A light-green rounded strip with a little white can strolling along the
    bottom. It exits one edge and re-enters from the other rather than
    bouncing back at the wall, so each lap flips direction: right-to-left,
    gone, then left-to-right, gone, on repeat.

    The animation only runs while the widget is visible, so an instance
    parked on a hidden page costs nothing.

    Subclassed for the two places it's used: HeaderBanner (decorative, behind
    the welcome header's logo/title) and WalkingCanLoader (a "working on it"
    indicator while a slow request runs)."""

    _CAN_WIDTH = 22
    _CAN_HEIGHT = 24
    _SPEED = 1.6
    _TICK_MS = 30
    _BOB_TICKS = 12
    _RADIUS = 20

    # The lap around a detour target (see _detour_rect). Walked faster than
    # the straight stretches -- at plain walking pace a loop this size takes
    # the better part of ten seconds, which reads as stalled rather than as
    # a flourish.
    _LOOP_SPEED = 3.0
    # Floor for the loop's horizontal radius. The logo alone would give a
    # narrow oval that clips through the title and tagline sitting under it;
    # this keeps the can's path outside that text.
    _MIN_LOOP_RADIUS = 130
    _LOOP_CLEARANCE = 10

    def __init__(self, parent=None):
        super().__init__(parent)
        self._direction = -1  # -1: walking left, 1: walking right
        self._x = None  # seeded on first tick, once we know our width
        self._tick = 0
        self._phase = "walk"  # or "loop", while circling a detour target
        self._loop_angle = 0.0
        self._loop_travelled = 0.0
        self._loop = None  # the ellipse being walked, while _phase == "loop"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    def _detour_rect(self):
        """The widget-relative rect the can should walk a lap around, or None
        to stroll straight past. Subclass hook -- the plain strip has nothing
        to walk around."""
        return None

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start(self._TICK_MS)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def _baseline_y(self) -> float:
        """Where the can's top edge sits while walking normally."""
        return self.height() - self._CAN_HEIGHT - 12

    def _advance(self) -> None:
        if self._x is None:
            self._x = float(self.width())  # start just off the right edge
        self._tick += 1
        if self._phase == "loop":
            self._advance_loop()
        else:
            self._advance_walk()
        self.update()

    def _advance_walk(self) -> None:
        previous_centre = self._x + self._CAN_WIDTH / 2
        self._x += self._direction * self._SPEED

        loop = self._loop_at(previous_centre, self._x + self._CAN_WIDTH / 2)
        if loop is not None:
            self._loop = loop
            self._phase = "loop"
            self._loop_angle = 90.0  # bottom of the ellipse, on the walking line
            self._loop_travelled = 0.0
            return

        if self._direction == -1 and self._x < -self._CAN_WIDTH:
            self._direction = 1
            self._x = -self._CAN_WIDTH
        elif self._direction == 1 and self._x > self.width():
            self._direction = -1
            self._x = float(self.width())

    def _loop_at(self, previous_centre: float, centre: float):
        """The ellipse to walk, if this step just carried the can across the
        detour target's centre line -- otherwise None.

        The ellipse is tangent to the walking line at that centre, so the can
        peels off and rejoins mid-stride instead of jumping to the path.
        """
        rect = self._detour_rect()
        if rect is None:
            return None
        target_x = rect.center().x()
        crossed = (
            previous_centre > target_x >= centre
            if self._direction == -1
            else previous_centre < target_x <= centre
        )
        if not crossed:
            return None

        bottom = self._baseline_y() + self._CAN_HEIGHT / 2
        top = max(
            self._CAN_HEIGHT / 2 + 2,  # keep the can inside the strip at the apex
            rect.top() - self._LOOP_CLEARANCE - self._CAN_HEIGHT / 2,
        )
        if bottom - top < 40:
            return None  # too little headroom for the detour to read as one

        radius_x = max(rect.width() / 2 + self._CAN_WIDTH / 2 + 10, self._MIN_LOOP_RADIUS)
        radius_x = min(radius_x, self.width() / 2 - self._CAN_WIDTH)
        if radius_x <= 0:
            return None
        return {
            "x": target_x,
            "y": (bottom + top) / 2,
            "radius_x": radius_x,
            "radius_y": (bottom - top) / 2,
        }

    def _advance_loop(self) -> None:
        radius_x, radius_y = self._loop["radius_x"], self._loop["radius_y"]
        # Ramanujan's ellipse-perimeter approximation, so a bigger loop takes
        # proportionally longer and the can holds one pace throughout.
        perimeter = math.pi * (
            3 * (radius_x + radius_y)
            - math.sqrt((3 * radius_x + radius_y) * (radius_x + 3 * radius_y))
        )
        step = 360.0 * self._SPEED * self._LOOP_SPEED / max(perimeter, 1.0)
        # Away from the walking direction first, so the can carries on the way
        # it was heading rather than doubling back into its own path.
        self._loop_angle += -self._direction * step
        self._loop_travelled += step
        if self._loop_travelled >= 360.0:
            self._phase = "walk"
            self._x = self._loop["x"] - self._CAN_WIDTH / 2
            self._loop = None

    def _can_position(self, bob: float):
        """Top-left of the can this frame, walking or mid-loop."""
        if self._phase == "loop" and self._loop is not None:
            angle = math.radians(self._loop_angle)
            return (
                self._loop["x"] + self._loop["radius_x"] * math.cos(angle) - self._CAN_WIDTH / 2,
                self._loop["y"] + self._loop["radius_y"] * math.sin(angle) - self._CAN_HEIGHT / 2 + bob,
            )
        return self._x, self._baseline_y() + bob

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_BANNER_GREEN)
        painter.drawRoundedRect(self.rect(), self._RADIUS, self._RADIUS)

        if self._x is not None:
            self._draw_can(painter)

    def _draw_can(self, painter: QPainter) -> None:
        bob = -2 if (self._tick // self._BOB_TICKS) % 2 == 0 else 0
        x, y = self._can_position(bob)

        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(QRectF(x, y + 5, self._CAN_WIDTH, self._CAN_HEIGHT - 5), 4, 4)
        painter.drawRoundedRect(QRectF(x - 1, y, self._CAN_WIDTH + 2, 8), 3, 3)

        # a little foot-splay that flips with the bob, to read as a walking gait
        lean = 2 if bob else -2
        painter.drawEllipse(QPointF(x + 5 + lean, y + self._CAN_HEIGHT + 1), 3, 2)
        painter.drawEllipse(QPointF(x + self._CAN_WIDTH - 5 - lean, y + self._CAN_HEIGHT + 1), 3, 2)


class HeaderBanner(WalkingCanStrip):
    """The welcome-screen header. Its logo/title are added as ordinary child
    widgets via a QVBoxLayout -- Qt paints those over whatever the strip's
    paintEvent draws, so no overlay/transparency tricks are needed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._logo_label = None
        self._logo_size = 0

    def set_logo(self, label, size: int) -> None:
        """Register the logo so the can walks a lap around it on its way past.

        Takes the pixmap's size rather than reading the label's geometry: the
        label stretches the full banner width in the layout, so its rect is
        far wider than the icon actually drawn centred inside it.
        """
        self._logo_label = label
        self._logo_size = size

    def _detour_rect(self):
        if self._logo_label is None or self._logo_size <= 0:
            return None
        centre = self._logo_label.geometry().center()
        half = self._logo_size / 2
        return QRectF(centre.x() - half, centre.y() - half, self._logo_size, self._logo_size)


class WalkingCanLoader(WalkingCanStrip):
    """The walking can as a busy indicator: same strip, sized down to a band
    that fits inline in a dialog, with a caption underneath. Shown while a
    slow request is in flight so the window reads as working rather than
    hung -- which means whatever it's waiting on must be off the GUI thread,
    or the can freezes along with everything else."""

    _RADIUS = 12
    _HEIGHT = 56

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self._HEIGHT)


def _render_pdf_first_page(path: Path, size: QSize) -> QPixmap:
    try:
        from PySide6.QtPdf import QPdfDocument

        doc = QPdfDocument()
        if doc.load(str(path)) != QPdfDocument.Error.None_ or doc.pageCount() < 1:
            return QPixmap()
        return QPixmap.fromImage(doc.render(0, size))
    except Exception:
        return QPixmap()


class _ClickableImageLabel(QLabel):
    """A QLabel that reports double-clicks, so the carousel can open a
    larger zoomable view of whatever page is currently on screen."""

    doubleClicked = Signal()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)


class ImageCarousel(QWidget):
    """A one-at-a-time, swipeable viewer for a bean profile's uploaded pages
    (photos or PDFs) -- prev/next arrows plus dot indicators, like a mobile
    photo carousel. Feed it rows with "id"/"file_path"/"position" keys via
    set_items(); current_item() returns the row currently on screen.
    Double-click the image to view it larger (doubleClicked signal)."""

    doubleClicked = Signal()

    _PREVIEW_SIZE = QSize(420, 280)
    _NAV_BTN_STYLE = """
        QPushButton {
            padding: 0px;
            font-size: 20px;
            font-weight: 700;
            border-radius: 20px;
            background-color: #E5E5EA;
            color: #1C1C1E;
        }
        QPushButton:hover { background-color: #DCDCE1; }
        QPushButton:pressed { background-color: #CFCFD4; }
        QPushButton:disabled { background-color: #F2F2F7; color: #C7C7CC; }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items = []
        self._index = 0

        self.image_label = _ClickableImageLabel("No pages yet")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(self._PREVIEW_SIZE)
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_label.doubleClicked.connect(self.doubleClicked)
        self.image_label.setStyleSheet(
            "background-color: #FFFFFF; border-radius: 10px; color: #8E8E93;"
        )

        self.prev_btn = QPushButton("‹")
        self.next_btn = QPushButton("›")
        for button in (self.prev_btn, self.next_btn):
            # The global QPushButton rule pads 8px/18px, which leaves no room
            # for the glyph in a small fixed-size button -- it just doesn't
            # render. Override with a style sized for a compact round button.
            button.setFixedSize(40, 40)
            button.setStyleSheet(self._NAV_BTN_STYLE)
        self.prev_btn.clicked.connect(self._go_prev)
        self.next_btn.clicked.connect(self._go_next)

        self.caption_label = QLabel("")
        self.caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption_label.setStyleSheet("color: #8E8E93; font-size: 11px;")

        self.dots_layout = QHBoxLayout()
        self.dots_layout.setSpacing(6)

        row = QHBoxLayout()
        row.addWidget(self.prev_btn)
        row.addWidget(self.image_label, 1)
        row.addWidget(self.next_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(row)
        layout.addWidget(self.caption_label)
        layout.addLayout(self.dots_layout)

        self._update_view()

    def set_items(self, items) -> None:
        self._items = list(items)
        self._index = min(self._index, len(self._items) - 1) if self._items else 0
        self._update_view()

    def current_item(self):
        return self._items[self._index] if self._items else None

    def _go_prev(self) -> None:
        if self._items:
            self._index = (self._index - 1) % len(self._items)
            self._update_view()

    def _go_next(self) -> None:
        if self._items:
            self._index = (self._index + 1) % len(self._items)
            self._update_view()

    def _rebuild_dots(self, count: int) -> None:
        while self.dots_layout.count():
            child = self.dots_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.dots_layout.addStretch()
        for i in range(count):
            dot = QLabel()
            dot.setFixedSize(7, 7)
            color = "#34C759" if i == self._index else "#D1D1D6"
            dot.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
            self.dots_layout.addWidget(dot)
        self.dots_layout.addStretch()

    def _update_view(self) -> None:
        count = len(self._items)
        self.prev_btn.setEnabled(count > 1)
        self.next_btn.setEnabled(count > 1)
        self._rebuild_dots(count)

        if not count:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("No pages yet")
            self.caption_label.setText("")
            return

        item = self._items[self._index]
        path = Path(item["file_path"])
        if path.suffix.lower() == ".pdf":
            pixmap = _render_pdf_first_page(path, self._PREVIEW_SIZE)
        else:
            pixmap = QPixmap(str(path))

        rotation = item["rotation"]
        if not pixmap.isNull() and rotation:
            pixmap = pixmap.transformed(QTransform().rotate(rotation), Qt.TransformationMode.SmoothTransformation)

        if pixmap.isNull():
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("Preview unavailable")
        else:
            scaled = pixmap.scaled(
                self._PREVIEW_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setText("")
            self.image_label.setPixmap(scaled)

        self.caption_label.setText(f"Page {item['position']} of {count} — {path.name}")


class ImageViewerDialog(QDialog):
    """A larger, zoomable view of a single bean page (photo, or a PDF's
    first page rasterized) -- opened by double-clicking an ImageCarousel."""

    _FIT_VIEWPORT = QSize(760, 600)
    _MIN_ZOOM = 0.1
    _MAX_ZOOM = 6.0
    _ZOOM_STEP = 1.25

    def __init__(self, path: Path, rotation: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle(path.name)
        self.resize(840, 700)

        self._base_pixmap = self._load_pixmap(path, rotation)
        self._fit_zoom = self._compute_fit_zoom()
        self._zoom = self._fit_zoom

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(False)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setStyleSheet("background-color: #F2F2F7; border-radius: 10px;")
        self.scroll.setWidget(self.image_label)

        zoom_out_btn = QPushButton("−")
        zoom_out_btn.setFixedWidth(40)
        zoom_out_btn.clicked.connect(lambda: self._apply_zoom(1 / self._ZOOM_STEP))
        zoom_in_btn = QPushButton("+")
        zoom_in_btn.setFixedWidth(40)
        zoom_in_btn.clicked.connect(lambda: self._apply_zoom(self._ZOOM_STEP))
        fit_btn = QPushButton("Fit to Window")
        fit_btn.clicked.connect(self._reset_zoom)
        self.zoom_label = QLabel()
        self.zoom_label.setStyleSheet("color: #8E8E93;")

        controls = QHBoxLayout()
        controls.addWidget(zoom_out_btn)
        controls.addWidget(self.zoom_label)
        controls.addWidget(zoom_in_btn)
        controls.addWidget(fit_btn)
        controls.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setProperty("variant", "primary")
        close_btn.clicked.connect(self.accept)
        controls.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(self.scroll, 1)
        layout.addLayout(controls)

        self._render()

    @staticmethod
    def _load_pixmap(path: Path, rotation: int) -> QPixmap:
        if path.suffix.lower() == ".pdf":
            pixmap = _render_pdf_first_page(path, QSize(1600, 1600))
        else:
            pixmap = QPixmap(str(path))
        if not pixmap.isNull() and rotation:
            pixmap = pixmap.transformed(QTransform().rotate(rotation), Qt.TransformationMode.SmoothTransformation)
        return pixmap

    def _compute_fit_zoom(self) -> float:
        if self._base_pixmap.isNull() or self._base_pixmap.width() == 0:
            return 1.0
        fitted = self._base_pixmap.size().scaled(self._FIT_VIEWPORT, Qt.AspectRatioMode.KeepAspectRatio)
        return min(1.0, fitted.width() / self._base_pixmap.width())

    def _render(self) -> None:
        if self._base_pixmap.isNull():
            self.image_label.setText("Preview unavailable")
            self.zoom_label.setText("")
            return
        width = max(1, round(self._base_pixmap.width() * self._zoom))
        height = max(1, round(self._base_pixmap.height() * self._zoom))
        scaled = self._base_pixmap.scaled(
            width, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())
        self.zoom_label.setText(f"{round(self._zoom * 100)}%")

    def _apply_zoom(self, factor: float) -> None:
        self._zoom = max(self._MIN_ZOOM, min(self._MAX_ZOOM, self._zoom * factor))
        self._render()

    def _reset_zoom(self) -> None:
        self._zoom = self._fit_zoom
        self._render()

    def wheelEvent(self, event) -> None:
        factor = self._ZOOM_STEP if event.angleDelta().y() > 0 else (1 / self._ZOOM_STEP)
        self._apply_zoom(factor)


_CALENDAR_TIERS = ("#EBEDF0", "#C8F0D4", "#7FDB9E", "#42CE7C", "#34C759")


class ContributionCalendar(QWidget):
    """A GitHub-style heatmap of daily brewing session counts, most recent
    ~3 months on the right. Feed it via set_counts({"YYYY-MM-DD": n, ...}).

    Cell size is recomputed on every paint from the widget's current size
    (down to _MIN_STEP), so the grid actually fills whatever space its
    container -- e.g. a QSplitter pane -- gives it, instead of staying
    pinned to one fixed pixel size regardless of the window."""

    CELL = 9
    GAP = 2
    WEEKS = 13
    LEFT_PAD = 26
    TOP_PAD = 18
    _MIN_STEP = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._counts = {}
        self._cells = []  # [(QRect, date, count), ...]
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(
            self.LEFT_PAD + self.WEEKS * self._MIN_STEP, self.TOP_PAD + 7 * self._MIN_STEP
        )

    def set_counts(self, counts: dict) -> None:
        self._counts = counts
        self.update()

    def sizeHint(self) -> QSize:
        width = self.LEFT_PAD + self.WEEKS * (self.CELL + self.GAP)
        height = self.TOP_PAD + 7 * (self.CELL + self.GAP)
        return QSize(width, height)

    def _metrics(self) -> tuple:
        """(cell, gap, step) sized to fill the widget's current width/height."""
        width_budget = max(self.width() - self.LEFT_PAD, self.WEEKS * self._MIN_STEP)
        height_budget = max(self.height() - self.TOP_PAD, 7 * self._MIN_STEP)
        step = max(self._MIN_STEP, min(width_budget // self.WEEKS, height_budget // 7))
        gap = max(1, round(step * self.GAP / (self.CELL + self.GAP)))
        cell = max(2, step - gap)
        return cell, gap, step

    def _color_for(self, count: int) -> QColor:
        if count <= 0:
            index = 0
        elif count == 1:
            index = 1
        elif count == 2:
            index = 2
        elif count == 3:
            index = 3
        else:
            index = 4
        return QColor(_CALENDAR_TIERS[index])

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cell, _gap, step = self._metrics()

        today = date.today()
        start = today - timedelta(weeks=self.WEEKS - 1)
        start -= timedelta(days=start.isoweekday() % 7)  # snap back to the preceding Sunday

        painter.setPen(QColor("#8E8E93"))
        for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
            y = self.TOP_PAD + row * step + cell
            painter.drawText(0, y, label)

        self._cells = []
        seen_months = set()
        current = start
        while current <= today:
            col = (current - start).days // 7
            row = current.isoweekday() % 7  # Sunday=0 .. Saturday=6
            x = self.LEFT_PAD + col * step
            y = self.TOP_PAD + row * step

            month_key = (current.year, current.month)
            if month_key not in seen_months:
                seen_months.add(month_key)
                painter.setPen(QColor("#8E8E93"))
                painter.drawText(x, self.TOP_PAD - 6, current.strftime("%b"))

            count = self._counts.get(current.isoformat(), 0)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._color_for(count))
            painter.drawRoundedRect(x, y, cell, cell, 2, 2)
            self._cells.append((QRect(x, y, cell, cell), current, count))

            current += timedelta(days=1)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        for rect, day, count in self._cells:
            if rect.contains(pos):
                label = "1 brew" if count == 1 else f"{count} brews"
                QToolTip.showText(event.globalPosition().toPoint(), f"{label} on {day.isoformat()}", self)
                return
        QToolTip.hideText()


_OTHER_LABEL = "Other (type manually)..."


class ChoiceCombo(QComboBox):
    """Dropdown of known values for a free-form field (e.g. dripper, grinder),
    backed by a JSON list (load_fn/add_fn). Picking "Other (type manually)..."
    prompts for a new value and remembers it for next time. API-compatible
    with QLineEdit's text()/setText()."""

    def __init__(self, load_fn, add_fn, label: str, parent=None):
        super().__init__(parent)
        self._load_fn = load_fn
        self._add_fn = add_fn
        self._label = label
        self._reload_items()
        self.activated.connect(self._on_activated)

    def _reload_items(self, select: str = "") -> None:
        self.blockSignals(True)
        self.clear()
        self.addItems(self._load_fn())
        self.addItem(_OTHER_LABEL)
        index = self.findText(select) if select else -1
        if select and index < 0:
            self.insertItem(0, select)
            index = 0
        self.setCurrentIndex(index)
        self.blockSignals(False)

    def _on_activated(self, index: int) -> None:
        if self.itemText(index) != _OTHER_LABEL:
            return
        name, ok = QInputDialog.getText(self, f"New {self._label}", f"{self._label} name:")
        name = name.strip()
        if ok and name:
            self._add_fn(name)
            self._reload_items(select=name)
        else:
            self.setCurrentIndex(-1)

    def text(self) -> str:
        current = self.currentText()
        return "" if current == _OTHER_LABEL else current

    def setText(self, value) -> None:
        self._reload_items(select=value or "")


class DripperCombo(ChoiceCombo):
    def __init__(self, parent=None):
        super().__init__(drippers.load_drippers, drippers.add_dripper, "Dripper", parent)


class GrinderCombo(ChoiceCombo):
    def __init__(self, parent=None):
        super().__init__(grinders.load_grinders, grinders.add_grinder, "Grinder", parent)


class FilterCombo(ChoiceCombo):
    def __init__(self, parent=None):
        super().__init__(filters.load_filters, filters.add_filter, "Filter Paper", parent)


class ProcessCombo(ChoiceCombo):
    def __init__(self, parent=None):
        super().__init__(processes.load_processes, processes.add_process, "Process", parent)


class RadarChart(QWidget):
    """A live radar/spider chart -- one axis per flavor, 0-5 scale. Call
    set_values() (in the same order as the `axes` passed to __init__)
    whenever a slider moves to redraw the filled polygon. Pass
    has_data=False (e.g. when averaging zero sessions) to render the whole
    chart in neutral grey with no data polygon, instead of a misleading
    all-zero green shape."""

    MAX_VALUE = 5
    # Room reserved for the axis labels, kept separate per direction: a label
    # on a left/right axis ("Green/Vegetative") needs half its 88-wide box
    # plus the 16 standoff, while a top/bottom one is a single line of text
    # and needs far less. Using one symmetric margin for both would spend the
    # horizontal allowance on the vertical axis too and shrink the polygon
    # for no reason. Under-shooting these clips labels at the widget edge --
    # grab() crops to the widget's own bounds -- at any size, not just when
    # rendered large for the share card.
    _LABEL_MARGIN_X = 64
    _LABEL_MARGIN_Y = 26

    def __init__(self, axes, parent=None):
        super().__init__(parent)
        self._axes = list(axes)
        self._values = [0] * len(self._axes)
        self._has_data = True
        self._label_scale = 1.0
        self.setMinimumSize(self.sizeHint())

    def set_values(self, values, has_data: bool = True) -> None:
        self._values = list(values) if values is not None else [0] * len(self._axes)
        self._has_data = has_data
        self.update()

    def set_label_scale(self, scale) -> None:
        """Multiplier for the label font and the margin/standoff reserved for
        labels (1.0 = the in-app size). Deliberately independent of the
        widget's size: if labels grew with the widget, a bigger chart would
        spend the extra space on label margin instead of on the polygon.
        Callers rendering large (the share card) scale this up explicitly."""
        self._label_scale = scale
        self.update()

    def sizeHint(self) -> QSize:
        # Wider than tall on purpose: the left/right labels need the extra
        # width, so a square hint would just cap the polygon at the
        # horizontal constraint while wasting vertical space.
        return QSize(320, 250)

    def _point_for(self, cx, cy, radius, index, value) -> QPointF:
        n = len(self._axes)
        angle = -math.pi / 2 + index * (2 * math.pi / n)
        r = (value / self.MAX_VALUE) * radius
        return QPointF(cx + r * math.cos(angle), cy + r * math.sin(angle))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        n = len(self._axes)
        if n < 3:
            return
        cx, cy = self.width() / 2, self.height() / 2
        # Every label-related pixel value below (margins, standoff, box, font)
        # scales off this one factor. It is set by set_label_scale(), NOT
        # derived from the widget size -- see that method for why.
        scale = self._label_scale
        radius = min(
            self.width() / 2 - self._LABEL_MARGIN_X * scale,
            self.height() / 2 - self._LABEL_MARGIN_Y * scale,
        )

        grid_color = QColor("#E5E5EA" if self._has_data else "#EFEFEF")
        spoke_color = QColor("#D1D1D6" if self._has_data else "#E3E3E3")
        label_color = QColor("#1C1C1E" if self._has_data else "#B0B0B0")

        # gridlines (one nested polygon per scale level)
        painter.setPen(grid_color)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for level in range(1, self.MAX_VALUE + 1):
            painter.drawPolygon(QPolygonF([self._point_for(cx, cy, radius, i, level) for i in range(n)]))

        # spokes + labels
        painter.setPen(spoke_color)
        for i in range(n):
            painter.drawLine(QPointF(cx, cy), self._point_for(cx, cy, radius, i, self.MAX_VALUE))

        # 8pt at scale 1.0 -- the size these labels have always been in-app.
        font = painter.font()
        font.setPointSize(max(8, round(8 * scale)))
        painter.setFont(font)
        painter.setPen(label_color)
        label_box_w, label_box_h = 88 * scale, 24 * scale
        for i, label in enumerate(self._axes):
            point = self._point_for(cx, cy, radius + 16 * scale, i, self.MAX_VALUE)
            rect = QRectF(point.x() - label_box_w / 2, point.y() - label_box_h / 2, label_box_w, label_box_h)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        if not self._has_data:
            return

        # data polygon
        values = self._values + [0] * (n - len(self._values))
        data_points = [self._point_for(cx, cy, radius, i, v) for i, v in enumerate(values)]
        painter.setPen(QPen(QColor("#34C759"), 2))
        painter.setBrush(QColor(52, 199, 89, 90))
        painter.drawPolygon(QPolygonF(data_points))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#248A3D"))
        for point in data_points:
            painter.drawEllipse(point, 3, 3)


class ElidedLabel(QLabel):
    """A QLabel that shortens its own text with an ellipsis.

    QLabel has no elide mode: given a long line it either forces its container
    wider or wraps onto extra rows, both of which break a fixed-height card
    layout. This paints the elided form itself and keeps the full string in
    the tooltip."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        # Ignored horizontally: the label must never be the reason its parent
        # asks for more width -- eliding is exactly the alternative to that.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:
        self._full_text = text or ""
        self.setToolTip(self._full_text)
        super().setText(self._full_text)

    def text(self) -> str:
        return self._full_text

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setFont(self.font())
        elided = self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, self.width()
        )
        painter.drawText(self.rect(), self.alignment(), elided)


class RemoteImageLabel(QLabel):
    """A fixed-size thumbnail for a photo that lives on someone else's server.

    `load()` fetches the bytes at the moment they are displayed and keeps the
    result only as an in-memory QPixmap -- never a file, and with HTTP caching
    switched off so Qt cannot spool it either. That is the line specs/legal.md
    rule 31 draws for roaster photos (see whats_new.py's module docstring:
    images are hotlinked, never downloaded), and requests carry the same
    truthful User-Agent as the listing fetch itself.

    Only one request is ever in flight: a second `load()` aborts the first, so
    a fast-changing selection can't paint a stale photo over the current one."""

    def __init__(self, size: int, placeholder: str = "No photo", radius: int = 10, parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._size = size
        self._radius = radius
        self._reply = None
        self._network = QNetworkAccessManager(self)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setStyleSheet(
            f"background-color: #F2F2F7; border-radius: {radius}px;"
            " color: #8E8E93; font-size: 10px;"
        )
        self.setText(placeholder)

    def load(self, image_url: str) -> None:
        """Show the image at `image_url`, or the placeholder if there isn't one."""
        self.clear_image()
        if not image_url:
            return
        self.setText("…")

        request = QNetworkRequest(QUrl(image_url))
        request.setRawHeader(b"User-Agent", whats_new.USER_AGENT.encode())
        request.setAttribute(QNetworkRequest.Attribute.CacheSaveControlAttribute, False)
        reply = self._network.get(request)
        self._reply = reply
        reply.finished.connect(lambda: self._on_finished(reply))

    def clear_image(self) -> None:
        """Drop the photo and any request still in flight."""
        if self._reply is not None:
            self._reply.abort()
            self._reply = None
        self.setPixmap(QPixmap())
        self.setText(self._placeholder)

    def _on_finished(self, reply) -> None:
        # A superseded reply belongs to a photo nobody is looking at any more;
        # read it only if it is still the current one.
        is_current = reply is self._reply
        if is_current:
            self._reply = None
        error_free = reply.error() == QNetworkReply.NetworkError.NoError
        data = reply.readAll() if error_free else None
        reply.deleteLater()
        if not is_current:
            return
        pixmap = QPixmap()
        if data is not None:
            pixmap.loadFromData(data)
        if pixmap.isNull():
            self.setText("No photo")
            return
        self.setText("")
        self.setPixmap(self._rounded(pixmap))

    def _rounded(self, pixmap: QPixmap) -> QPixmap:
        """Scale to fit and clip to the same radius as the label's own
        background -- an unclipped photo squares off corners the QSS just
        rounded, which on a rounded card reads as a rendering glitch."""
        scaled = pixmap.scaled(
            self._size,
            self._size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if not self._radius:
            return scaled
        masked = QPixmap(scaled.size())
        masked.fill(QColor(0, 0, 0, 0))
        painter = QPainter(masked)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(scaled.rect()), self._radius, self._radius)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, scaled)
        painter.end()
        return masked


class VerticalTicker(QWidget):
    """A looping vertical scroller for short one-line-plus-subtitle entries.

    Shows a feed longer than the space available by rolling it upward
    continuously and wrapping around, so a small corner of a card can carry
    20 items without a scrollbar the user has to touch.

    The timer only runs while the widget is visible -- an animation painting
    to an unmapped widget is pure battery drain, and this one sits on the
    main window where it would otherwise run for the whole session."""

    #: Emitted with an entry's payload when it is clicked. Entries added
    #: without a payload are inert.
    activated = Signal(object)

    _INTERVAL_MS = 33  # ~30fps; smooth enough for a 0.4px step, cheap enough to leave on
    _STEP_PX = 0.4
    _ROW_HEIGHT = 42
    _PAUSE_ON_HOVER = True

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []  # [(title, subtitle, payload), ...]
        self._offset = 0.0
        self._placeholder = "Loading…"
        self._hovered = False
        self.setMouseTracking(True)
        self.setMinimumHeight(self._ROW_HEIGHT * 2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._timer = QTimer(self)
        self._timer.setInterval(self._INTERVAL_MS)
        self._timer.timeout.connect(self._advance)

    def set_entries(self, entries) -> None:
        """Feed the ticker. Each entry is (title, subtitle) or
        (title, subtitle, payload); a payload makes the row clickable and is
        handed back verbatim through `activated`."""
        self._entries = [
            (entry[0], entry[1], entry[2] if len(entry) > 2 else None) for entry in entries
        ]
        self._offset = 0.0
        self.update()
        self._sync_timer()

    # --- clicking ---------------------------------------------------------

    def _entry_at(self, y):
        """Index of the row under `y`, accounting for the scroll offset, or
        None. Modulo rather than a hit-rect list: rows are drawn wrapped, so
        the same entry can be on screen twice."""
        if not self._entries:
            return None
        span = len(self._entries) * self._ROW_HEIGHT
        index = int(((y + self._offset) % span) // self._ROW_HEIGHT)
        return index if 0 <= index < len(self._entries) else None

    def mouseMoveEvent(self, event):
        index = self._entry_at(event.position().y())
        clickable = index is not None and self._entries[index][2] is not None
        self.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            index = self._entry_at(event.position().y())
            if index is not None and self._entries[index][2] is not None:
                self.activated.emit(self._entries[index][2])
        super().mouseReleaseEvent(event)

    def set_placeholder(self, text: str) -> None:
        """Message shown while there is nothing to roll (loading, empty, error)."""
        self._placeholder = text
        self.update()

    # --- run only while visible and not hovered ---------------------------

    def _sync_timer(self):
        should_run = (
            self.isVisible()
            and len(self._entries) > 1
            and not (self._PAUSE_ON_HOVER and self._hovered)
        )
        if should_run and not self._timer.isActive():
            self._timer.start()
        elif not should_run and self._timer.isActive():
            self._timer.stop()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_timer()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._sync_timer()

    def enterEvent(self, event):
        self._hovered = True
        self._sync_timer()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._sync_timer()
        super().leaveEvent(event)

    def _advance(self):
        span = len(self._entries) * self._ROW_HEIGHT
        if span <= 0:
            return
        self._offset = (self._offset + self._STEP_PX) % span
        self.update()

    # --- painting ---------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._entries:
            painter.setPen(QColor("#8E8E93"))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._placeholder)
            return

        span = len(self._entries) * self._ROW_HEIGHT
        # Draw one extra wrap-around pass so the entry rolling off the top is
        # already re-entering from the bottom -- otherwise the loop visibly
        # blinks once per cycle.
        passes = self.height() // span + 2
        painter.setClipRect(self.rect())
        for extra in range(passes):
            for index, (title, subtitle, _payload) in enumerate(self._entries):
                y = index * self._ROW_HEIGHT - self._offset + extra * span
                if y > self.height() or y + self._ROW_HEIGHT < 0:
                    continue
                self._paint_entry(painter, y, title, subtitle)

    def _paint_entry(self, painter, y, title, subtitle):
        font = painter.font()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#1C1C1E"))
        title_rect = QRectF(0, y + 3, self.width(), 16)
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._elide(painter, title, self.width()),
        )

        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(QColor("#8E8E93"))
        subtitle_rect = QRectF(0, y + 19, self.width(), 14)
        painter.drawText(
            subtitle_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._elide(painter, subtitle, self.width()),
        )

    @staticmethod
    def _elide(painter, text, width):
        metrics = painter.fontMetrics()
        return metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(0, int(width)))
