"""Dialog for creating/editing a coffee bean profile."""

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import claude_ocr, ocr, repo
from ..formatting import format_or_dash, format_score
from ..paths import ALLOWED_IMAGE_SUFFIXES, MAX_IMAGES_PER_BEAN
from .ai_brew_dialog import AiBrewSuggestionDialog
from .brew_dialog import BrewDialog
from .widgets import ImageCarousel, ImageViewerDialog, OptionalDateEdit, ProcessCombo, RadarChart, share_icon_pixmap

FIELD_LABELS = (
    ("origin", "Origin"),
    ("variety", "Variety"),
    ("altitude", "Altitude"),
    ("roaster", "Roaster (torrefactor)"),
    ("producer", "Producer"),
    ("process", "Process"),
    ("roast_date", "Roast date"),
)


class _ManualFlavorDialog(QDialog):
    """A slider-per-axis picker (0-5, live radar preview) for manually setting
    a bean's flavor profile, for when the auto-average from its brew sessions
    isn't the one you want shown."""

    def __init__(self, initial_values, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Flavor Profile")
        self.setStyleSheet("QDialog { background-color: white; }")
        self.values = None

        self.radar_chart = RadarChart([label for _, label in repo.FLAVOR_AXES])
        self._sliders = {}
        flavor_form = QFormLayout()
        for (field, label), value in zip(repo.FLAVOR_AXES, initial_values):
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 5)
            slider.setValue(int(value or 0))
            slider.setMinimumWidth(140)
            value_label = QLabel(str(int(value or 0)))
            value_label.setMinimumWidth(16)
            slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(str(v)))
            slider.valueChanged.connect(self._update_radar)
            self._sliders[field] = slider
            slider_row = QHBoxLayout()
            slider_row.addWidget(slider, 1)
            slider_row.addWidget(value_label)
            flavor_form.addRow(label, slider_row)

        content_row = QHBoxLayout()
        content_row.addLayout(flavor_form, 1)
        content_row.addWidget(self.radar_chart)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setProperty("variant", "primary")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addLayout(content_row)
        layout.addWidget(buttons)

        self._update_radar()

    def _update_radar(self, *_args):
        self.radar_chart.set_values([slider.value() for slider in self._sliders.values()])

    def _validate_and_accept(self):
        self.values = [self._sliders[field].value() for field, _ in repo.FLAVOR_AXES]
        self.accept()


class _ScanReviewDialog(QDialog):
    """Shows OCR-extracted field guesses as editable text before anything
    touches the profile -- fix a mistake, or clear a field entirely to leave
    that part of the profile untouched when Apply is clicked."""

    _FIELD_LABELS = (("name", "Name"),) + FIELD_LABELS

    def __init__(self, guessed_fields: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review Scanned Details")
        self.setStyleSheet("QDialog { background-color: white; }")
        self.values = None

        note = QLabel(
            "Best-effort guesses from the photo -- fix anything wrong, or clear "
            "a field to leave that part of the profile untouched."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #8E8E93; font-size: 11px;")

        self._edits = {}
        form = QFormLayout()
        for field, label in self._FIELD_LABELS:
            edit = QLineEdit(guessed_fields.get(field, ""))
            self._edits[field] = edit
            form.addRow(label, edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        ok_button.setProperty("variant", "primary")
        ok_button.setText("Apply")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(note)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        self.values = {field: edit.text().strip() for field, edit in self._edits.items()}
        self.accept()


class BeanDialog(QDialog):
    """Edits a bean profile. A bean row is always persisted immediately --
    if bean_id isn't given, one is created on the spot with a blank name --
    so Pages and Brewing sessions work right away, with no "save first" step.
    The Name field stays blank until the user types in it; _DEFAULT_NAME only
    gets used as a fallback if Save is clicked while it's still empty.

    If a freshly-created profile is closed (Close button or the window's own
    close control) with nothing ever actually saved to it -- no name, no
    detail fields, no pages, no sessions -- the empty draft row is deleted
    instead of being left behind in the profile list."""

    _DEFAULT_NAME = "Untitled"

    def __init__(self, conn, bean_id=None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self._is_new = bean_id is None
        self.bean_id = bean_id if bean_id is not None else repo.create_bean(conn, "")
        self.resize(620, 700)

        self.name_edit = QLineEdit()
        _field_widget = {"roast_date": OptionalDateEdit, "process": ProcessCombo}
        self.field_edits = {
            field: _field_widget.get(field, QLineEdit)() for field, _ in FIELD_LABELS
        }

        self.scan_btn = QPushButton("Scan Label...")
        self.scan_btn.clicked.connect(self._show_scan_menu)
        scan_row = QHBoxLayout()
        scan_row.addStretch()
        scan_row.addWidget(self.scan_btn)

        form = QFormLayout()
        form.addRow("Name", self.name_edit)
        for field, label in FIELD_LABELS:
            form.addRow(label, self.field_edits[field])

        details_layout = QVBoxLayout()
        details_layout.addLayout(scan_row)
        details_layout.addLayout(form)
        details_group = QGroupBox("Coffee Details")
        details_group.setLayout(details_layout)

        self.image_carousel = ImageCarousel()
        self.image_carousel.doubleClicked.connect(self._open_image_viewer)
        self.add_image_btn = QPushButton("Add Photo/PDF...")
        self.add_image_btn.clicked.connect(self._add_image)
        self.rotate_image_btn = QPushButton("Rotate")
        self.rotate_image_btn.clicked.connect(self._rotate_image)
        self.remove_image_btn = QPushButton("Remove This Page")
        self.remove_image_btn.setProperty("variant", "destructive")
        self.remove_image_btn.clicked.connect(self._remove_image)
        images_buttons = QHBoxLayout()
        images_buttons.addWidget(self.add_image_btn)
        images_buttons.addWidget(self.rotate_image_btn)
        images_buttons.addWidget(self.remove_image_btn)
        images_layout = QVBoxLayout()
        images_layout.addWidget(self.image_carousel)
        images_layout.addLayout(images_buttons)
        self.images_group = QGroupBox(f"Pages (0/{MAX_IMAGES_PER_BEAN})")
        self.images_group.setLayout(images_layout)

        self.sessions_table = QTableWidget(0, 4)
        self.sessions_table.setHorizontalHeaderLabels(["ID", "Date", "Dripper", "Score"])
        self.sessions_table.setColumnHidden(0, True)
        sessions_header = self.sessions_table.horizontalHeader()
        sessions_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        sessions_header.setSectionResizeMode(2, QHeaderView.Stretch)  # Dripper: give it the room
        self.sessions_table.setMinimumHeight(190)
        self.sessions_table.verticalHeader().setVisible(False)
        self.sessions_table.setAlternatingRowColors(True)
        self.sessions_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sessions_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sessions_table.doubleClicked.connect(self._edit_session)
        new_session_btn = QPushButton("New Session")
        new_session_btn.setProperty("variant", "primary")
        new_session_btn.clicked.connect(self._new_session)
        ask_ai_btn = QPushButton("Ask AI")
        ask_ai_btn.clicked.connect(self._ask_ai_brew)
        edit_session_btn = QPushButton("Edit / View")
        edit_session_btn.clicked.connect(self._edit_session)
        delete_session_btn = QPushButton("Delete")
        delete_session_btn.setProperty("variant", "destructive")
        delete_session_btn.clicked.connect(self._delete_session)
        sessions_buttons = QHBoxLayout()
        for button in (new_session_btn, ask_ai_btn, edit_session_btn, delete_session_btn):
            sessions_buttons.addWidget(button)
        sessions_layout = QVBoxLayout()
        sessions_layout.addWidget(self.sessions_table)
        sessions_layout.addLayout(sessions_buttons)
        self.sessions_group = QGroupBox("Brewing sessions")
        self.sessions_group.setLayout(sessions_layout)

        self.flavor_radar = RadarChart([label for _, label in repo.FLAVOR_AXES])
        self.flavor_caption = QLabel()
        self.flavor_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.flavor_caption.setStyleSheet("color: #8E8E93; font-size: 11px;")
        generate_flavor_btn = QPushButton("Generate from Sessions")
        generate_flavor_btn.clicked.connect(self._generate_flavor)
        manual_flavor_btn = QPushButton("Set Manually...")
        manual_flavor_btn.clicked.connect(self._set_flavor_manually)
        flavor_buttons = QHBoxLayout()
        flavor_buttons.addWidget(generate_flavor_btn)
        flavor_buttons.addWidget(manual_flavor_btn)
        flavor_layout = QVBoxLayout()
        flavor_layout.addWidget(self.flavor_radar, 1, Qt.AlignmentFlag.AlignCenter)
        flavor_layout.addWidget(self.flavor_caption)
        flavor_layout.addLayout(flavor_buttons)
        self.flavor_group = QGroupBox("Flavor Profile")
        self.flavor_group.setLayout(flavor_layout)

        share_btn = QPushButton()
        share_btn.setIcon(QIcon(share_icon_pixmap(20)))
        share_btn.setIconSize(QSize(20, 20))
        share_btn.setToolTip("Share this profile as an image")
        share_btn.setFixedSize(40, 40)
        share_btn.setStyleSheet(
            "QPushButton { padding: 0px; border-radius: 20px; background-color: #E5E5EA; }"
            "QPushButton:hover { background-color: #DCDCE1; }"
            "QPushButton:pressed { background-color: #CFCFD4; }"
        )
        share_btn.clicked.connect(self._share_bean)
        top_bar = QWidget()
        top_bar.setObjectName("topBar")
        top_bar.setStyleSheet("#topBar { background-color: white; }")
        top = QHBoxLayout(top_bar)
        top.setContentsMargins(20, 12, 20, 12)
        top.addStretch()
        top.addWidget(share_btn)

        save_btn = QPushButton("Save")
        save_btn.setProperty("variant", "primary")
        save_btn.clicked.connect(self._save)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        bottom_bar = QWidget()
        bottom_bar.setObjectName("bottomBar")
        bottom_bar.setStyleSheet("#bottomBar { background-color: white; }")
        bottom = QHBoxLayout(bottom_bar)
        bottom.setContentsMargins(20, 12, 20, 12)
        bottom.addStretch()
        bottom.addWidget(save_btn)
        bottom.addWidget(close_btn)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(14)
        content_layout.addWidget(self.images_group)
        content_layout.addWidget(details_group)
        content_layout.addWidget(self.sessions_group)
        content_layout.addWidget(self.flavor_group)
        content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(top_bar)
        layout.addWidget(scroll, 1)
        layout.addWidget(bottom_bar)

        self._load(self.bean_id)

    def _load(self, bean_id):
        row = repo.get_bean(self.conn, bean_id)
        self.setWindowTitle(row["name"] or "New Coffee Profile")
        self.name_edit.setText(row["name"])
        for field, _ in FIELD_LABELS:
            self.field_edits[field].setText(row[field] or "")
        self._refresh_images()
        self._refresh_sessions()
        self._refresh_flavor()

    def _show_scan_menu(self):
        menu = QMenu(self)
        menu.addAction("Take Photo...", self._scan_from_camera)
        menu.addAction("Choose Photo File...", self._scan_from_file)
        menu.exec(self.scan_btn.mapToGlobal(self.scan_btn.rect().bottomLeft()))

    def _scan_from_camera(self):
        try:
            from .camera_dialog import CameraCaptureDialog
        except ImportError as exc:
            QMessageBox.warning(
                self, "Camera unavailable", f"Camera capture isn't available on this system: {exc}"
            )
            return

        dialog = CameraCaptureDialog(parent=self)
        if not dialog.exec() or not dialog.captured_path:
            return
        captured_path = Path(dialog.captured_path)
        try:
            self._run_scan(captured_path)
        finally:
            captured_path.unlink(missing_ok=True)

    def _scan_from_file(self):
        suffixes = " ".join(f"*{s}" for s in sorted(ocr.PHOTO_SUFFIXES))
        path, _ = QFileDialog.getOpenFileName(self, "Select a photo of the bag label", "", f"Images ({suffixes})")
        if not path:
            return
        self._run_scan(Path(path))

    def _run_scan(self, image_path: Path):
        fields = None
        if claude_ocr.is_configured():
            try:
                fields = claude_ocr.guess_bean_fields(image_path)
            except claude_ocr.ClaudeOcrUnavailableError:
                fields = None  # fall back to local OCR below

        if fields is None:
            try:
                fields = ocr.guess_bean_fields(image_path)
            except ocr.OcrUnavailableError as exc:
                QMessageBox.warning(self, "Scan unavailable", str(exc))
                return
            except Exception as exc:  # noqa: BLE001 -- OCR/image decoding can fail in many ways
                QMessageBox.warning(self, "Scan failed", f"Couldn't read that image: {exc}")
                return

        dialog = _ScanReviewDialog(fields, parent=self)
        if not dialog.exec():
            return
        for field, value in dialog.values.items():
            if not value:
                continue
            if field == "name":
                self.name_edit.setText(value)
            else:
                self.field_edits[field].setText(value)

    def _refresh_images(self):
        images = repo.list_bean_images(self.conn, self.bean_id)
        self.image_carousel.set_items(images)
        self.images_group.setTitle(f"Pages ({len(images)}/{MAX_IMAGES_PER_BEAN})")
        self.add_image_btn.setEnabled(len(images) < MAX_IMAGES_PER_BEAN)
        self.rotate_image_btn.setEnabled(len(images) > 0)
        self.remove_image_btn.setEnabled(len(images) > 0)

    def _add_image(self):
        suffixes = " ".join(f"*{s}" for s in sorted(ALLOWED_IMAGE_SUFFIXES))
        path, _ = QFileDialog.getOpenFileName(self, "Select a photo or PDF", "", f"Supported files ({suffixes})")
        if not path:
            return
        try:
            repo.add_bean_image(self.conn, self.bean_id, Path(path))
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot add page", str(exc))
            return
        self._refresh_images()

    def _remove_image(self):
        item = self.image_carousel.current_item()
        if item is None:
            return
        repo.delete_bean_image(self.conn, item["id"])
        self._refresh_images()

    def _rotate_image(self):
        item = self.image_carousel.current_item()
        if item is None:
            return
        repo.rotate_bean_image(self.conn, item["id"], 90)
        self._refresh_images()

    def _open_image_viewer(self):
        item = self.image_carousel.current_item()
        if item is None:
            return
        ImageViewerDialog(Path(item["file_path"]), item["rotation"], parent=self).exec()

    def _share_bean(self):
        from .share_card import render_share_card, save_share_image

        try:
            pixmap = render_share_card(self.conn, self.bean_id)
        except Exception as exc:  # noqa: BLE001 -- rendering touches fonts, images, DB rows
            QMessageBox.warning(self, "Couldn't generate image", f"Something went wrong: {exc}")
            return

        name = self.name_edit.text().strip() or "coffee"
        save_share_image(self, pixmap, name)

    def _refresh_sessions(self):
        sessions = repo.list_sessions(self.conn, bean_id=self.bean_id)
        self.sessions_table.setRowCount(len(sessions))
        for i, s in enumerate(sessions):
            values = (
                str(s["id"]),
                format_or_dash(s["brew_date"]),
                format_or_dash(s["dripper"]),
                format_score(s["score"]),
            )
            for j, value in enumerate(values):
                self.sessions_table.setItem(i, j, QTableWidgetItem(value))
        self.sessions_group.setTitle(f"Brewing sessions ({len(sessions)})")

    def _selected_session_id(self):
        row = self.sessions_table.currentRow()
        if row < 0:
            return None
        return int(self.sessions_table.item(row, 0).text())

    def _new_session(self):
        bean_row = repo.get_bean(self.conn, self.bean_id)
        BrewDialog(self.conn, bean_row, session_id=None, parent=self).exec()
        self._refresh_sessions()
        self._refresh_flavor()

    def _ask_ai_brew(self):
        bean_row = repo.get_bean(self.conn, self.bean_id)
        dialog = AiBrewSuggestionDialog(bean_row, parent=self)
        if not dialog.exec():
            return

        session_id = repo.create_session(self.conn, self.bean_id)
        repo.update_session_field(self.conn, session_id, "dripper", dialog.dripper)
        repo.update_session_field(self.conn, session_id, "note", dialog.suggestion)
        if dialog.grind_size:
            repo.update_session_field(self.conn, session_id, "grind_size", dialog.grind_size)
        if dialog.dose_g is not None:
            repo.update_session_field(self.conn, session_id, "dose_g", dialog.dose_g)
        for stage in dialog.stages:
            repo.add_stage(
                self.conn,
                session_id,
                stage["temperature_c"],
                stage["water_g"],
                stage["time_seconds"],
                stage["circling"],
            )

        bean_row = repo.get_bean(self.conn, self.bean_id)
        BrewDialog(self.conn, bean_row, session_id=session_id, parent=self).exec()
        self._refresh_sessions()
        self._refresh_flavor()

    def _edit_session(self):
        session_id = self._selected_session_id()
        if session_id is None:
            QMessageBox.information(self, "No selection", "Select a brewing session first.")
            return
        bean_row = repo.get_bean(self.conn, self.bean_id)
        BrewDialog(self.conn, bean_row, session_id=session_id, parent=self).exec()
        self._refresh_sessions()
        self._refresh_flavor()

    def _delete_session(self):
        session_id = self._selected_session_id()
        if session_id is None:
            QMessageBox.information(self, "No selection", "Select a brewing session first.")
            return
        confirm = QMessageBox.question(self, "Delete session", f"Delete brewing session #{session_id}?")
        if confirm == QMessageBox.Yes:
            repo.delete_session(self.conn, session_id)
            self._refresh_sessions()
            self._refresh_flavor()

    def _refresh_flavor(self):
        bean = repo.get_bean(self.conn, self.bean_id)
        if bean["flavor_source"] == "manual" and any(bean[f] is not None for f in repo.FLAVOR_FIELDS):
            values = [bean[f] or 0 for f in repo.FLAVOR_FIELDS]
            self.flavor_radar.set_values(values, has_data=True)
            self.flavor_caption.setText("Manually set")
            return
        count, averages = repo.get_bean_average_flavor_scores(self.conn, self.bean_id)
        if averages is None:
            self.flavor_radar.set_values(None, has_data=False)
            self.flavor_caption.setText("No flavor data yet")
        else:
            self.flavor_radar.set_values(averages, has_data=True)
            self.flavor_caption.setText(f"Average across {count} session{'s' if count != 1 else ''}")

    def _generate_flavor(self):
        repo.update_bean_field(self.conn, self.bean_id, "flavor_source", "auto")
        self._refresh_flavor()

    def _set_flavor_manually(self):
        bean = repo.get_bean(self.conn, self.bean_id)
        if bean["flavor_source"] == "manual" and any(bean[f] is not None for f in repo.FLAVOR_FIELDS):
            current = [bean[f] or 0 for f in repo.FLAVOR_FIELDS]
        else:
            _, current = repo.get_bean_average_flavor_scores(self.conn, self.bean_id)
            current = current or [0] * len(repo.FLAVOR_FIELDS)

        dialog = _ManualFlavorDialog(current, parent=self)
        if dialog.exec():
            for field, value in zip(repo.FLAVOR_FIELDS, dialog.values):
                repo.update_bean_field(self.conn, self.bean_id, field, value)
            repo.update_bean_field(self.conn, self.bean_id, "flavor_source", "manual")
            self._refresh_flavor()

    def _save(self):
        name = self.name_edit.text().strip() or self._DEFAULT_NAME
        repo.update_bean_field(self.conn, self.bean_id, "name", name)

        for field, _ in FIELD_LABELS:
            value = self.field_edits[field].text().strip() or None
            repo.update_bean_field(self.conn, self.bean_id, field, value)

        self._load(self.bean_id)

    def _is_empty(self) -> bool:
        row = repo.get_bean(self.conn, self.bean_id)
        if row["name"] or any(row[field] for field, _ in FIELD_LABELS):
            return False
        if row["flavor_source"] == "manual" and any(row[f] is not None for f in repo.FLAVOR_FIELDS):
            return False
        if repo.list_bean_images(self.conn, self.bean_id) or repo.list_sessions(self.conn, bean_id=self.bean_id):
            return False
        return True

    def closeEvent(self, event):
        if self._is_new and self._is_empty():
            repo.delete_bean(self.conn, self.bean_id)
        super().closeEvent(event)
