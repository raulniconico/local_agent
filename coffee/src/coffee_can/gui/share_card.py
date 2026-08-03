"""Renders shareable PNG summaries: a portrait, phone-screen-sized card
(1080 wide, 9:16-ish -- matches Instagram/WhatsApp/Snapchat story formats)
with a pure white background and a small app-icon logo tucked into the
bottom-right corner.

Two flavors:
- render_share_card: a bean profile -- first uploaded page photo, basic
  details, and its flavor radar. Used by bean_dialog.py's Share button.
- render_session_share_card: a single brewing session -- the bean's basic
  info and photo (no bean-level radar, since the session has its own),
  followed by the session's brew details, every stage, the evaluation
  note/score, and *that session's* flavor radar. Used by brew_dialog.py's
  Share button. Its height is content-dependent (stage count and note
  length vary), so it's rendered onto an oversized scratch canvas and then
  cropped to the actual content height.

Both dialogs also share save_share_image() (the save-to-disk + tips-dialog
flow) and _ShareTipsDialog, defined here to avoid a circular import between
bean_dialog.py and brew_dialog.py.
"""

from pathlib import Path

from PySide6.QtCore import QRectF, QStandardPaths, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PySide6.QtWidgets import QDialog, QFileDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout

from .. import profile, repo
from ..assets import icon_path
from ..formatting import format_or_dash, format_seconds
from .widgets import RadarChart, circular_pixmap, default_avatar_pixmap

WIDTH = 1080
HEIGHT = 1920
#: The logo's own green (theme.ACCENT), unmodified.
BACKGROUND = "#34C759"
#: The radar panel is the same green as the card, not a white box -- no
#: border either, so it reads as part of the card rather than a box dropped
#: on top of it.
_PANEL_FILL = BACKGROUND
#: RadarChart.set_palette() overrides for a green panel: the default
#: dark-text/grey-grid/green-polygon scheme (right for the app's white cards)
#: would be unreadable here, so grid, spokes, labels and the data polygon are
#: all shades of white instead, at bolder weights than the in-app hairline
#: default -- this chart is rendered much larger, and thin white-on-green
#: reads as faint at that size. data_fill is high-opacity rather than the
#: in-app translucency for the same reason: at low alpha it blends toward
#: the green panel behind it instead of reading as white.
_RADAR_PALETTE = dict(
    grid="#B3FFFFFF", spoke="#CCFFFFFF", label="#FFFFFF",
    data_stroke="#FFFFFF", data_fill="#E6FFFFFF", data_dot="#FFFFFF",
    grid_width=2, spoke_width=2, data_stroke_width=3, bold_label=True,
)
_MARGIN = 64
_TEXT_COLOR = "#FFFFFF"
#: White text throughout, per the redesign -- this is the same white at
#: reduced opacity for the secondary/label role _MUTED_COLOR used to play in
#: a dark grey, so labels still read as secondary next to full-white values.
_MUTED_COLOR = "#B3FFFFFF"
#: The bean-info/session-info divider used to be a pale green line, chosen
#: for a white card -- nearly invisible on the deep green background, so it's
#: a translucent white here instead, same role.
_DIVIDER_COLOR = "#4DFFFFFF"
_AVATAR_SIZE = 72

# Mirrors bean_dialog.FIELD_LABELS -- kept as a separate small copy rather
# than importing from bean_dialog.py, since bean_dialog.py is the one that
# imports this module (to wire up the Share button) and a mutual top-level
# import would be circular.
_DETAIL_FIELDS = (
    ("origin", "Origin"),
    ("variety", "Variety"),
    ("altitude", "Altitude"),
    ("roaster", "Roaster"),
    ("producer", "Producer"),
    ("process", "Process"),
    ("roast_date", "Roast date"),
)


def _fitted_photo(path: str, rotation: int, max_width: int, max_height: int, radius: int) -> QPixmap:
    """Scale an image to fit entirely within max_width x max_height (no
    cropping -- the whole photo is always visible, letterboxed on the
    shorter axis if its aspect ratio doesn't match the box) and mask it to
    rounded corners -- same idea as widgets.circular_pixmap, just
    rectangular. Applies `rotation` first (bean_images.rotation, set via the
    bean page's Rotate button) so the share card matches what's actually
    shown there -- the source file on disk is never itself rotated."""
    source = QPixmap(path)
    if source.isNull():
        return QPixmap()
    if rotation:
        source = source.transformed(QTransform().rotate(rotation), Qt.TransformationMode.SmoothTransformation)
    scaled = source.scaled(
        max_width, max_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )

    result = QPixmap(scaled.size())
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, scaled.width(), scaled.height()), radius, radius)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return result


def _draw_share_header(painter: QPainter, y: float, content_width: int, margin: int) -> float:
    """The "XXX share with you:" line every card opens with: the local
    profile's avatar (or the same generic placeholder profile_dialog.py falls
    back to when there's no photo) beside their name. Returns the y position
    the rest of the card should continue from."""
    data = profile.load_profile()
    path = data.get("image_path")
    avatar = circular_pixmap(path, _AVATAR_SIZE) if path and Path(path).exists() else QPixmap()
    if avatar.isNull():
        avatar = default_avatar_pixmap(_AVATAR_SIZE, background="#FFFFFF", foreground=BACKGROUND)
    painter.drawPixmap(margin, int(y), avatar)

    name = (data.get("name") or "").strip() or "Someone"
    header_font = QFont()
    header_font.setPointSize(28)
    header_font.setBold(True)
    painter.setFont(header_font)
    painter.setPen(QColor(_TEXT_COLOR))
    text_x = margin + _AVATAR_SIZE + 28
    painter.drawText(
        QRectF(text_x, y, margin + content_width - text_x, _AVATAR_SIZE),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        f"{name} share with you:",
    )
    return y + _AVATAR_SIZE + 56


def _draw_centered_field(painter: QPainter, y: float, label: str, value: str, content_width: int, margin: int, row_height: int = 44) -> float:
    """One "Label: value" row, centered as a single unit -- the label in the
    muted (translucent-white) color, the value in full white, sized and
    positioned from the two segments' actual widths so the pair reads as one
    centered phrase rather than two independently-centered pieces."""
    label_text = f"{label}: "
    metrics = painter.fontMetrics()
    label_width = metrics.horizontalAdvance(label_text)
    value_width = metrics.horizontalAdvance(str(value))
    start_x = margin + (content_width - label_width - value_width) / 2

    painter.setPen(QColor(_MUTED_COLOR))
    painter.drawText(
        QRectF(start_x, y, label_width, row_height),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        label_text,
    )
    painter.setPen(QColor(_TEXT_COLOR))
    painter.drawText(
        QRectF(start_x + label_width, y, value_width, row_height),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        str(value),
    )
    return y + row_height


def _flavor_snapshot(conn, bean_id: int):
    """Same manual-vs-averaged decision as bean_dialog.BeanDialog._refresh_flavor,
    returning (values_or_None, has_data, caption)."""
    bean = repo.get_bean(conn, bean_id)
    if bean["flavor_source"] == "manual" and any(bean[f] is not None for f in repo.FLAVOR_FIELDS):
        return [bean[f] or 0 for f in repo.FLAVOR_FIELDS], True, "Manually set flavor profile"
    count, averages = repo.get_bean_average_flavor_scores(conn, bean_id)
    if averages is None:
        return None, False, "No flavor data yet"
    return averages, True, f"Average across {count} session{'s' if count != 1 else ''}"


def render_share_card(conn, bean_id: int) -> QPixmap:
    bean = repo.get_bean(conn, bean_id)
    images = repo.list_bean_images(conn, bean_id)

    card = QPixmap(WIDTH, HEIGHT)
    card.fill(QColor(BACKGROUND))
    painter = QPainter(card)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    y = _MARGIN
    content_width = WIDTH - 2 * _MARGIN

    y = _draw_share_header(painter, y, content_width, _MARGIN)

    # --- first uploaded page photo -- shown in full, never cropped ---
    if images:
        photo_max_height = int(WIDTH * 0.45)
        photo = _fitted_photo(images[0]["file_path"], images[0]["rotation"], content_width, photo_max_height, 28)
        if not photo.isNull():
            photo_x = _MARGIN + (content_width - photo.width()) // 2
            painter.drawPixmap(photo_x, y, photo)
            y += photo.height() + 64

    # --- name ---
    name_font = QFont()
    name_font.setPointSize(52)
    name_font.setBold(True)
    painter.setFont(name_font)
    painter.setPen(QColor(_TEXT_COLOR))
    name_rect = QRectF(_MARGIN, y, content_width, 90)
    painter.drawText(
        name_rect,
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
        bean["name"] or "Untitled",
    )
    y += 124

    # --- flavor radar --- (green panel matching the card, white net/labels/
    # polygon via _RADAR_PALETTE -- the radar itself is grabbed with a
    # transparent background so it overlays the panel cleanly)
    # Ahead of the detail fields below: the chart is the card's visual draw,
    # so it leads: name, then the flavor picture, then the text specifics.
    values, has_data, caption = _flavor_snapshot(conn, bean_id)
    radar_size = 741  # 570 * 1.3
    # 2.6x the in-app label size (8pt -> ~21pt), readable at phone-screen
    # scale. Independent of radar_size on purpose, so the extra size goes to
    # the polygon rather than to label margin -- see RadarChart.set_label_scale.
    radar_label_scale = 2.6
    panel_pad = 24
    panel_rect = QRectF((WIDTH - radar_size) / 2 - panel_pad, y - panel_pad, radar_size + 2 * panel_pad, radar_size + 2 * panel_pad)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(_PANEL_FILL))
    painter.drawRoundedRect(panel_rect, 28, 28)

    radar = RadarChart([label for _, label in repo.FLAVOR_AXES])
    radar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    radar.setStyleSheet("background: transparent;")
    radar.resize(radar_size, radar_size)
    radar.set_label_scale(radar_label_scale)
    radar.set_palette(**_RADAR_PALETTE)
    radar.set_values(values, has_data=has_data)
    radar_pixmap = radar.grab()
    painter.drawPixmap(int((WIDTH - radar_size) / 2), y, radar_pixmap)
    y += radar_size + panel_pad + 40

    caption_font = QFont()
    caption_font.setPointSize(22)
    painter.setFont(caption_font)
    painter.setPen(QColor(_MUTED_COLOR))
    painter.drawText(
        QRectF(_MARGIN, y, content_width, 40), Qt.AlignmentFlag.AlignHCenter, caption
    )
    y += 64

    # --- detail fields -- centered as a block, each row its own centered unit ---
    detail_font = QFont()
    detail_font.setPointSize(26)
    painter.setFont(detail_font)
    for field, label in _DETAIL_FIELDS:
        value = bean[field]
        if not value:
            continue
        y = _draw_centered_field(painter, y, label, str(value), content_width, _MARGIN)

    # --- small logo, bottom-right corner ---
    icon = icon_path()
    if icon:
        logo_size = 84
        logo = QIcon(icon).pixmap(logo_size, logo_size)
        painter.drawPixmap(WIDTH - _MARGIN - logo_size, HEIGHT - _MARGIN - logo_size, logo)

    painter.end()
    return card


_SESSION_DETAIL_FIELDS = (
    ("dripper", "Dripper"),
    ("filter_paper", "Filter Paper"),
    ("grinder", "Grinder"),
    ("grind_size", "Grind size"),
    ("water_ppm", "Water PPM"),
    ("humidity", "Humidity %"),
)

# Generous scratch height a session card is cropped down from -- see the
# module docstring for why this can't just be a fixed HEIGHT like the bean
# card: stage count and note length both vary per session.
_SESSION_SCRATCH_HEIGHT = 4000


def render_session_share_card(conn, session_id: int) -> QPixmap:
    session = repo.get_session(conn, session_id)
    bean = repo.get_bean(conn, session["bean_id"])
    images = repo.list_bean_images(conn, bean["id"])
    stages = repo.list_stages(conn, session_id)

    card = QPixmap(WIDTH, _SESSION_SCRATCH_HEIGHT)
    card.fill(QColor(BACKGROUND))
    painter = QPainter(card)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    y = _MARGIN
    content_width = WIDTH - 2 * _MARGIN
    detail_font = QFont()
    detail_font.setPointSize(24)

    y = _draw_share_header(painter, y, content_width, _MARGIN)

    # --- bean name ---
    name_font = QFont()
    name_font.setPointSize(44)
    name_font.setBold(True)
    painter.setFont(name_font)
    painter.setPen(QColor(_TEXT_COLOR))
    painter.drawText(
        QRectF(_MARGIN, y, content_width, 78),
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
        bean["name"] or "Untitled",
    )
    y += 96

    # --- bean photo, shown in full -- no bean-level radar here, the session has its own ---
    if images:
        photo_max_height = int(WIDTH * 0.42)
        photo = _fitted_photo(images[0]["file_path"], images[0]["rotation"], content_width, photo_max_height, 28)
        if not photo.isNull():
            photo_x = _MARGIN + (content_width - photo.width()) // 2
            painter.drawPixmap(photo_x, y, photo)
            y += photo.height() + 48

    # --- this session's own flavor radar (never averaged/manual bean data) ---
    # Ahead of all the text below: the chart is the card's visual draw, so it
    # leads, with the detail text (bean's, then the session's own) following.
    values = [session[field] or 0 for field in repo.FLAVOR_FIELDS]
    has_data = any(values)
    caption = "This session's flavor profile" if has_data else "No flavor data for this session"
    radar_size = 741  # 570 * 1.3
    radar_label_scale = 2.6
    panel_pad = 24
    panel_rect = QRectF((WIDTH - radar_size) / 2 - panel_pad, y - panel_pad, radar_size + 2 * panel_pad, radar_size + 2 * panel_pad)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(_PANEL_FILL))
    painter.drawRoundedRect(panel_rect, 28, 28)

    radar = RadarChart([label for _, label in repo.FLAVOR_AXES])
    radar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    radar.setStyleSheet("background: transparent;")
    radar.resize(radar_size, radar_size)
    radar.set_label_scale(radar_label_scale)
    radar.set_palette(**_RADAR_PALETTE)
    radar.set_values(values, has_data=has_data)
    radar_pixmap = radar.grab()
    painter.drawPixmap(int((WIDTH - radar_size) / 2), y, radar_pixmap)
    y += radar_size + panel_pad + 40

    caption_font = QFont()
    caption_font.setPointSize(22)
    painter.setFont(caption_font)
    painter.setPen(QColor(_MUTED_COLOR))
    painter.drawText(QRectF(_MARGIN, y, content_width, 40), Qt.AlignmentFlag.AlignHCenter, caption)
    y += 64

    # --- bean basic details -- centered as a block ---
    painter.setFont(detail_font)
    for field, label in _DETAIL_FIELDS:
        value = bean[field]
        if not value:
            continue
        y = _draw_centered_field(painter, y, label, str(value), content_width, _MARGIN, row_height=42)
    y += 40

    # --- divider ---
    painter.setPen(QColor(_DIVIDER_COLOR))
    painter.drawLine(int(_MARGIN), int(y), int(WIDTH - _MARGIN), int(y))
    y += 40

    # --- session header ---
    header_font = QFont()
    header_font.setPointSize(32)
    header_font.setBold(True)
    painter.setFont(header_font)
    painter.setPen(QColor(_TEXT_COLOR))
    title = "Brewing Session"
    if session["brew_date"]:
        title += f" -- {session['brew_date']}"
    painter.drawText(QRectF(_MARGIN, y, content_width, 54), Qt.AlignmentFlag.AlignLeft, title)
    y += 70

    # --- session brew details -- centered as a block ---
    painter.setFont(detail_font)
    for field, label in _SESSION_DETAIL_FIELDS:
        value = session[field]
        if not value:
            continue
        y = _draw_centered_field(painter, y, label, str(value), content_width, _MARGIN, row_height=42)
    if session["dose_g"]:
        y = _draw_centered_field(painter, y, "Dose", f"{session['dose_g']:g} g", content_width, _MARGIN, row_height=42)
    y += 30

    # --- stages ---
    if stages:
        stage_header_font = QFont()
        stage_header_font.setPointSize(26)
        stage_header_font.setBold(True)
        painter.setFont(stage_header_font)
        painter.setPen(QColor(_TEXT_COLOR))
        painter.drawText(QRectF(_MARGIN, y, content_width, 40), Qt.AlignmentFlag.AlignLeft, "Stages")
        y += 46

        painter.setFont(detail_font)
        for stage in stages:
            parts = [
                f"Stage {stage['stage_number']}",
                f"{format_or_dash(stage['temperature_c'])} °C",
                f"{format_or_dash(stage['water_g'])} g",
                format_seconds(stage["time_seconds"]),
            ]
            if stage["circling"]:
                parts.append(stage["circling"])
            painter.setPen(QColor(_TEXT_COLOR))
            painter.drawText(QRectF(_MARGIN, y, content_width, 40), Qt.AlignmentFlag.AlignLeft, "  ·  ".join(parts))
            y += 44
        y += 30

    # --- evaluation: score + note ---
    if session["score"] is not None:
        painter.setFont(detail_font)
        y = _draw_centered_field(painter, y, "Score", f"{session['score']:g}/5", content_width, _MARGIN, row_height=46)
    if session["note"]:
        painter.setPen(QColor(_MUTED_COLOR))
        painter.drawText(QRectF(_MARGIN, y, 220, 38), Qt.AlignmentFlag.AlignLeft, "Note")
        painter.setPen(QColor(_TEXT_COLOR))
        note_rect = painter.boundingRect(
            QRectF(_MARGIN + 230, y, content_width - 230, 600), Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, session["note"]
        )
        painter.drawText(note_rect, Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, session["note"])
        y = note_rect.bottom() + 30
    y += 20

    # --- small logo, bottom-right corner ---
    icon = icon_path()
    if icon:
        logo_size = 84
        painter.drawPixmap(WIDTH - _MARGIN - logo_size, int(y), QIcon(icon).pixmap(logo_size, logo_size))
        y += logo_size

    y += _MARGIN
    painter.end()
    return card.copy(0, 0, WIDTH, min(int(y), _SESSION_SCRATCH_HEIGHT))


class _ShareTipsDialog(QDialog):
    """Shown after a share-card PNG is saved: a preview plus quick pointers
    on how to actually get it in front of someone -- posting it directly
    works for stories/messaging, but a QR code or a hosted link is often the
    better call when the image itself won't fit (packaging, a menu, print)."""

    def __init__(self, pixmap, saved_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Share Image Saved")
        self.resize(420, 660)

        preview_label = QLabel()
        preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_label.setPixmap(pixmap.scaledToHeight(420, Qt.TransformationMode.SmoothTransformation))

        path_label = QLabel(f"Saved to:\n{saved_path}")
        path_label.setWordWrap(True)
        path_label.setStyleSheet("color: #8E8E93; font-size: 11px;")

        tips = QLabel(
            "<b>Sharing ideas</b><br>"
            "&bull; <b>Instagram/Facebook/Snapchat Story or WhatsApp Status:</b> "
            "post this image directly -- it's already sized to fill the screen.<br>"
            "&bull; <b>Messaging apps (iMessage, Telegram, etc.):</b> just attach "
            "the PNG, no resizing needed.<br>"
            "&bull; <b>On packaging, a cafe menu, or anywhere space is tight:</b> "
            "a small QR code linking to a hosted copy of this image (or page) "
            "works better than trying to shrink the image itself.<br>"
            "&bull; <b>Printing:</b> at 1080px wide it's roughly 300 DPI at a "
            "3.6 in width -- fine for a small card or tag, not a full page."
        )
        tips.setWordWrap(True)
        tips.setStyleSheet("font-size: 12px;")

        close_btn = QPushButton("Close")
        close_btn.setProperty("variant", "primary")
        close_btn.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(preview_label)
        layout.addWidget(path_label)
        layout.addWidget(tips)
        layout.addStretch()
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


def save_share_image(parent, pixmap: QPixmap, default_name: str) -> None:
    """Prompt for a save location, write the PNG, then show _ShareTipsDialog.
    Shared by bean_dialog.py's and brew_dialog.py's Share buttons so the
    save-and-explain flow stays identical for both."""
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in default_name).strip() or "coffee"
    pictures_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
    default_path = str(Path(pictures_dir or str(Path.home())) / f"{safe_name}-share.png")

    path, _ = QFileDialog.getSaveFileName(parent, "Save share image", default_path, "PNG Image (*.png)")
    if not path:
        return
    if not pixmap.save(path, "PNG"):
        QMessageBox.warning(parent, "Save failed", f"Couldn't write the image to {path}.")
        return

    _ShareTipsDialog(pixmap, path, parent=parent).exec()
