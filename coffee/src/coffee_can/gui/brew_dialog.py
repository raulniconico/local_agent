"""Dialog for creating/editing a brewing session, plus its stage sub-dialog."""

from PySide6.QtCore import QDate, QSize, Qt, QTime
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from .. import repo
from ..formatting import format_or_dash, format_seconds
from .theme import style_calendar_popup
from .widgets import (
    DripperCombo,
    ExtractionBar,
    FilterCombo,
    GrinderCombo,
    RadarChart,
    SaveButton,
    share_icon_pixmap,
)

_TIME_FORMAT = "hh:mm:ss"

SESSION_TEXT_FIELDS = (
    ("dripper", "Dripper"),
    ("filter_paper", "Filter Paper"),
    ("grinder", "Grinder"),
    ("grind_size", "Grind size"),
    ("water_ppm", "Water PPM"),
    ("humidity", "Humidity %"),
)

_ISO_FORMAT = "yyyy-MM-dd"


class StageDialog(QDialog):
    """Collects one brewing stage's fields; caller reads the attributes after
    exec(). Pass an existing stage row (from repo.list_stages/get_stage) to
    edit it -- fields are pre-filled and the dialog is titled accordingly."""

    def __init__(self, parent=None, stage=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Brewing Stage" if stage is not None else "New Brewing Stage")
        self.setStyleSheet("QDialog { background-color: white; }")
        self.temperature = None
        self.water_g = None
        self.time_seconds = None
        self.circling = None

        default_temp = int(stage["temperature_c"]) if stage is not None and stage["temperature_c"] is not None else 90
        self.temp_slider = QSlider(Qt.Orientation.Horizontal)
        self.temp_slider.setRange(-10, 110)
        self.temp_slider.setValue(default_temp)
        self.temp_slider.setMinimumWidth(300)
        self.temp_spin = QSpinBox()
        self.temp_spin.setRange(-10, 110)
        self.temp_spin.setSuffix(" °C")
        self.temp_spin.setValue(default_temp)
        self.temp_slider.valueChanged.connect(self.temp_spin.setValue)
        self.temp_spin.valueChanged.connect(self.temp_slider.setValue)
        temp_row = QHBoxLayout()
        temp_row.addWidget(self.temp_slider, 1)
        temp_row.addWidget(self.temp_spin)

        self.water_spin = QDoubleSpinBox()
        self.water_spin.setRange(0, 1000)
        self.water_spin.setSuffix(" g")
        self.water_spin.setDecimals(1)
        self.water_spin.setValue(stage["water_g"] or 0 if stage is not None else 0)

        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat(_TIME_FORMAT)
        default_seconds = (stage["time_seconds"] or 0) if stage is not None else 0
        self.time_edit.setTime(QTime(0, 0, 0).addSecs(default_seconds))

        self.circling_edit = QLineEdit()
        self.circling_edit.setPlaceholderText("e.g. swirl, stir, none")
        if stage is not None and stage["circling"]:
            self.circling_edit.setText(stage["circling"])

        form = QFormLayout()
        form.addRow("Temperature (°C)", temp_row)
        form.addRow("Water", self.water_spin)
        form.addRow("Time (hh:mm:ss)", self.time_edit)
        form.addRow("Circling/agitation", self.circling_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setProperty("variant", "primary")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        self.temperature = float(self.temp_slider.value())
        self.water_g = float(self.water_spin.value())
        t = self.time_edit.time()
        self.time_seconds = t.hour() * 3600 + t.minute() * 60 + t.second()
        self.circling = self.circling_edit.text().strip() or None
        self.accept()


class BrewDialog(QDialog):
    """Edits an existing session, or -- if session_id is None -- creates one for
    bean_row first, so Stages work right away with no "save first" step.

    If a freshly-created session is closed (Close button or the window's own
    close control) with nothing ever actually saved to it -- no brew details,
    no stages, no evaluation -- the empty draft row is deleted instead of
    being left behind in the bean's session list."""

    _SCORE_HINT = "0 to 5"

    def __init__(self, conn, bean_row, session_id=None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.bean_row = bean_row
        self._reuse_from = None
        self._is_new = session_id is None
        # The bar always shows *some* position, so "never assessed" can't be
        # read off it the way an unset score can -- track it separately so an
        # untouched bar persists as NULL rather than as "Well extracted".
        self._extraction_set = False
        if session_id is None:
            previous_sessions = repo.list_sessions(conn, bean_id=bean_row["id"])
            if previous_sessions:
                self._reuse_from = previous_sessions[0]
            session_id = repo.create_session(conn, bean_row["id"])
        self.session_id = session_id
        self._stage_ids = []

        self.resize(800, 760)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        style_calendar_popup(self.date_edit)
        self.date_edit.setDisplayFormat(_ISO_FORMAT)
        self.date_edit.setMaximumDate(QDate.currentDate())
        self.date_edit.setDate(QDate.currentDate())
        _combo_by_field = {"dripper": DripperCombo, "filter_paper": FilterCombo, "grinder": GrinderCombo}
        self.field_edits = {
            field: (_combo_by_field[field]() if field in _combo_by_field else QLineEdit())
            for field, _ in SESSION_TEXT_FIELDS
        }
        self.dose_spin = QDoubleSpinBox()
        self.dose_spin.setRange(0, 100)
        self.dose_spin.setSuffix(" g")
        self.dose_spin.setSingleStep(0.5)
        self.dose_spin.setValue(0)

        form = QFormLayout()
        form.addRow("Date*", self.date_edit)
        for field, label in SESSION_TEXT_FIELDS:
            form.addRow(label, self.field_edits[field])
        form.addRow("Dose", self.dose_spin)
        details_group = QGroupBox("Brew Details")
        details_group.setLayout(form)

        self.stages_table = QTableWidget(0, 5)
        self.stages_table.setHorizontalHeaderLabels(["Stage", "Temp (°C)", "Water (g)", "Time", "Circling"])
        stages_header = self.stages_table.horizontalHeader()
        stages_header.setSectionResizeMode(QHeaderView.ResizeToContents)
        stages_header.setSectionResizeMode(4, QHeaderView.Stretch)  # Circling: give it the room
        self.stages_table.setMinimumHeight(160)
        self.stages_table.verticalHeader().setVisible(False)
        self.stages_table.setAlternatingRowColors(True)
        self.stages_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.stages_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stages_table.doubleClicked.connect(self._edit_stage)

        add_stage_btn = QPushButton("Add Stage")
        add_stage_btn.clicked.connect(self._add_stage)
        edit_stage_btn = QPushButton("Edit Selected Stage")
        edit_stage_btn.clicked.connect(self._edit_stage)
        remove_stage_btn = QPushButton("Remove Selected Stage")
        remove_stage_btn.setProperty("variant", "destructive")
        remove_stage_btn.clicked.connect(self._remove_stage)
        stage_buttons = QHBoxLayout()
        stage_buttons.addWidget(add_stage_btn)
        stage_buttons.addWidget(edit_stage_btn)
        stage_buttons.addWidget(remove_stage_btn)
        stages_layout = QVBoxLayout()
        stages_layout.addWidget(self.stages_table)
        stages_layout.addLayout(stage_buttons)
        stages_group = QGroupBox("Brewing Stages")
        stages_group.setLayout(stages_layout)

        # "Not set" is the value one step below 0, surfaced through Qt's
        # setSpecialValueText -- its idiom for an unset spinbox, and what
        # replaced the old Scored toggle. A score nobody touches persists as
        # NULL rather than as a real 0, so an unrated session still reads as
        # "-" everywhere instead of claiming a bottom-of-the-range rating.
        self.score_spin = QDoubleSpinBox()
        self.score_spin.setDecimals(1)
        self.score_spin.setSingleStep(0.5)
        self.score_spin.setRange(-0.5, 5)
        self.score_spin.setSpecialValueText(self._SCORE_HINT)
        self.score_spin.setValue(self.score_spin.minimum())
        self.score_spin.valueChanged.connect(self._update_score_style)

        self.extraction_bar = ExtractionBar(
            repo.EXTRACTION_ZONES, repo.EXTRACTION_MIN, repo.EXTRACTION_MAX
        )
        self.extraction_bar.valueChanged.connect(self._on_extraction_changed)

        self.note_edit = QPlainTextEdit()
        self.note_edit.setPlaceholderText("Tasting notes...")
        self.note_edit.setFixedHeight(70)

        eval_form = QFormLayout()
        eval_form.addRow("Score", self.score_spin)
        eval_form.addRow("Extraction", self.extraction_bar)
        eval_form.addRow("Note", self.note_edit)

        self.radar_chart = RadarChart([label for _, label in repo.FLAVOR_AXES])

        self.flavor_sliders = {}
        flavor_form = QFormLayout()
        for field, label in repo.FLAVOR_AXES:
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 5)
            slider.setValue(0)
            slider.setMinimumWidth(140)
            value_label = QLabel("0")
            value_label.setMinimumWidth(16)
            slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(str(v)))
            slider.valueChanged.connect(self._update_radar)
            self.flavor_sliders[field] = slider
            slider_row = QHBoxLayout()
            slider_row.addWidget(slider, 1)
            slider_row.addWidget(value_label)
            flavor_form.addRow(label, slider_row)

        flavor_label = QLabel("Flavor")
        flavor_label.setStyleSheet("font-weight: 700; font-size: 13px; color: #1C1C1E; margin-top: 6px;")

        flavor_row = QHBoxLayout()
        flavor_row.addLayout(flavor_form, 1)
        flavor_row.addWidget(self.radar_chart)

        eval_layout = QVBoxLayout()
        eval_layout.addLayout(eval_form)
        eval_layout.addWidget(flavor_label)
        eval_layout.addLayout(flavor_row)
        eval_group = QGroupBox("Evaluation")
        eval_group.setLayout(eval_layout)

        share_btn = QPushButton()
        share_btn.setIcon(QIcon(share_icon_pixmap(20)))
        share_btn.setIconSize(QSize(20, 20))
        share_btn.setToolTip("Share this session as an image")
        share_btn.setFixedSize(40, 40)
        share_btn.setStyleSheet(
            "QPushButton { padding: 0px; border-radius: 20px; background-color: #E5E5EA; }"
            "QPushButton:hover { background-color: #DCDCE1; }"
            "QPushButton:pressed { background-color: #CFCFD4; }"
        )
        share_btn.clicked.connect(self._share_session)
        top_bar = QWidget()
        top_bar.setObjectName("topBar")
        top_bar.setStyleSheet("#topBar { background-color: white; }")
        top = QHBoxLayout(top_bar)
        top.setContentsMargins(20, 12, 20, 12)
        top.addStretch()
        top.addWidget(share_btn)

        self.save_btn = save_btn = SaveButton()
        save_btn.setProperty("variant", "primary")
        save_btn.clicked.connect(self._save_clicked)
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
        content_layout.addWidget(details_group)
        content_layout.addWidget(stages_group)
        content_layout.addWidget(eval_group)
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

        self._load()

    def _load(self):
        row = repo.get_session(self.conn, self.session_id)
        title = f"Brewing session -- {self.bean_row['name']}"
        if row["brew_date"]:
            title += f" ({row['brew_date']})"
        self.setWindowTitle(title)
        if row["brew_date"]:
            parsed = QDate.fromString(row["brew_date"], _ISO_FORMAT)
            self.date_edit.setDate(parsed if parsed.isValid() else QDate.currentDate())
        else:
            self.date_edit.setDate(QDate.currentDate())
        # A brand-new session starts blank except Brew Details, which carry over
        # from the bean's most recent session -- same dripper/grinder/recipe is
        # the common case, so re-entering it every time would be pure friction.
        details_source = self._reuse_from if self._reuse_from is not None else row
        for field, _ in SESSION_TEXT_FIELDS:
            self.field_edits[field].setText(details_source[field] or "")
        self.dose_spin.setValue(details_source["dose_g"] or 0)
        self._reuse_from = None  # only seed the very first load of a new session
        score = row["score"]
        self.score_spin.setValue(self.score_spin.minimum() if score is None else score)
        self._update_score_style()

        extraction = row["extraction"]
        self._extraction_set = extraction is not None
        # Seeding the bar must not count as the user having assessed it.
        self.extraction_bar.blockSignals(True)
        self.extraction_bar.setValue(extraction or 0.0)
        self.extraction_bar.blockSignals(False)
        self.note_edit.setPlainText(row["note"] or "")
        for field, _ in repo.FLAVOR_AXES:
            self.flavor_sliders[field].setValue(int(row[field] or 0))
        self._update_radar()
        self._refresh_stages()

    def _score_is_set(self) -> bool:
        return self.score_spin.value() > self.score_spin.minimum()

    def _update_score_style(self, *_args):
        # Grey while the hint is showing, normal once it holds a real score --
        # the placeholder look QLineEdit gives for free, which a spinbox's
        # special value text doesn't.
        self.score_spin.setStyleSheet(
            "" if self._score_is_set() else "QDoubleSpinBox { color: #C7C7CC; }"
        )

    def _on_extraction_changed(self, *_args):
        self._extraction_set = True

    def _update_radar(self, *_args):
        values = [self.flavor_sliders[field].value() for field, _ in repo.FLAVOR_AXES]
        self.radar_chart.set_values(values)

    def _refresh_stages(self):
        stages = repo.list_stages(self.conn, self.session_id)
        self._stage_ids = [s["id"] for s in stages]
        self.stages_table.setRowCount(len(stages))
        for i, stage in enumerate(stages):
            self.stages_table.setItem(i, 0, QTableWidgetItem(str(stage["stage_number"])))
            self.stages_table.setItem(i, 1, QTableWidgetItem(format_or_dash(stage["temperature_c"])))
            self.stages_table.setItem(i, 2, QTableWidgetItem(format_or_dash(stage["water_g"])))
            self.stages_table.setItem(i, 3, QTableWidgetItem(format_seconds(stage["time_seconds"])))
            self.stages_table.setItem(i, 4, QTableWidgetItem(format_or_dash(stage["circling"])))

    def _add_stage(self):
        dialog = StageDialog(self)
        if dialog.exec():
            repo.add_stage(
                self.conn, self.session_id, dialog.temperature, dialog.water_g, dialog.time_seconds, dialog.circling
            )
            self._refresh_stages()

    def _edit_stage(self):
        row = self.stages_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "No selection", "Select a stage first.")
            return
        stage_id = self._stage_ids[row]
        stage = repo.get_stage(self.conn, stage_id)
        dialog = StageDialog(self, stage=stage)
        if dialog.exec():
            repo.update_stage(
                self.conn, stage_id, dialog.temperature, dialog.water_g, dialog.time_seconds, dialog.circling
            )
            self._refresh_stages()

    def _remove_stage(self):
        row = self.stages_table.currentRow()
        if row < 0:
            return
        repo.delete_stage(self.conn, self._stage_ids[row])
        self._refresh_stages()

    def _save_clicked(self):
        # Wraps _persist rather than flashing inside it: _share_session also
        # persists the on-screen state before rendering, and that shouldn't
        # read as the user having saved.
        self._persist()
        self.save_btn.flash_saved()

    def _persist(self):
        brew_date = self.date_edit.date().toString(_ISO_FORMAT)
        repo.update_session_field(self.conn, self.session_id, "brew_date", brew_date)
        for field, _ in SESSION_TEXT_FIELDS:
            value = self.field_edits[field].text().strip() or None
            repo.update_session_field(self.conn, self.session_id, field, value)
        repo.update_session_field(self.conn, self.session_id, "dose_g", self.dose_spin.value())

        score = self.score_spin.value() if self._score_is_set() else None
        repo.update_session_field(self.conn, self.session_id, "score", score)
        extraction = self.extraction_bar.value() if self._extraction_set else None
        repo.update_session_field(self.conn, self.session_id, "extraction", extraction)
        note = self.note_edit.toPlainText().strip() or None
        repo.update_session_field(self.conn, self.session_id, "note", note)
        for field, _ in repo.FLAVOR_AXES:
            repo.update_session_field(self.conn, self.session_id, field, self.flavor_sliders[field].value())

        self._load()

    def _share_session(self):
        from .share_card import render_session_share_card, save_share_image

        # Share the on-screen state, not whatever was last saved -- score,
        # note, and flavor sliders in particular are easy to fill in and
        # then reach for Share without an explicit Save first.
        self._persist()

        try:
            pixmap = render_session_share_card(self.conn, self.session_id)
        except Exception as exc:  # noqa: BLE001 -- rendering touches fonts, images, DB rows
            QMessageBox.warning(self, "Couldn't generate image", f"Something went wrong: {exc}")
            return

        bean_name = self.bean_row["name"] or "coffee"
        brew_date = self.date_edit.date().toString(_ISO_FORMAT)
        save_share_image(self, pixmap, f"{bean_name}-{brew_date}")

    def _is_empty(self) -> bool:
        row = repo.get_session(self.conn, self.session_id)
        if any(row[field] for field in repo.SESSION_FIELDS):
            return False
        if repo.list_stages(self.conn, self.session_id):
            return False
        return True

    def closeEvent(self, event):
        if self._is_new and self._is_empty():
            repo.delete_session(self.conn, self.session_id)
        super().closeEvent(event)
