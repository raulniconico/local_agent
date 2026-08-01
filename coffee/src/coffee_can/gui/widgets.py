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
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QPolygonF, QTransform
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

from .. import drippers, filters, grinders, processes
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._direction = -1  # -1: walking left, 1: walking right
        self._x = None  # seeded on first tick, once we know our width
        self._tick = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start(self._TICK_MS)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def _advance(self) -> None:
        if self._x is None:
            self._x = float(self.width())  # start just off the right edge
        self._x += self._direction * self._SPEED
        self._tick += 1
        if self._direction == -1 and self._x < -self._CAN_WIDTH:
            self._direction = 1
            self._x = -self._CAN_WIDTH
        elif self._direction == 1 and self._x > self.width():
            self._direction = -1
            self._x = float(self.width())
        self.update()

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
        y = self.height() - self._CAN_HEIGHT - 12 + bob

        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(QRectF(self._x, y + 5, self._CAN_WIDTH, self._CAN_HEIGHT - 5), 4, 4)
        painter.drawRoundedRect(QRectF(self._x - 1, y, self._CAN_WIDTH + 2, 8), 3, 3)

        # a little foot-splay that flips with the bob, to read as a walking gait
        lean = 2 if bob else -2
        painter.drawEllipse(QPointF(self._x + 5 + lean, y + self._CAN_HEIGHT + 1), 3, 2)
        painter.drawEllipse(QPointF(self._x + self._CAN_WIDTH - 5 - lean, y + self._CAN_HEIGHT + 1), 3, 2)


class HeaderBanner(WalkingCanStrip):
    """The welcome-screen header. Its logo/title are added as ordinary child
    widgets via a QVBoxLayout -- Qt paints those over whatever the strip's
    paintEvent draws, so no overlay/transparency tricks are needed."""


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
