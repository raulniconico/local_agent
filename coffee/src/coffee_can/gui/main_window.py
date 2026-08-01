"""Main window: a welcome screen with three stacked blocks -- logo header,
coffee profiles list, and a GitHub-style brewing activity calendar."""

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import profile, repo
from ..assets import icon_path
from ..formatting import format_or_dash
from .bean_dialog import BeanDialog
from .profile_dialog import ProfileSettingsDialog
from .widgets import ContributionCalendar, HeaderBanner, RadarChart, circular_pixmap, default_avatar_pixmap


class _TextSortItem(QTableWidgetItem):
    """Case-insensitive sort, so lowercase names don't get shoved to the bottom."""

    def __lt__(self, other):
        if isinstance(other, QTableWidgetItem):
            return self.text().casefold() < other.text().casefold()
        return super().__lt__(other)


class _NumericSortItem(QTableWidgetItem):
    """Sorts by the underlying number, not its lexicographic string ('10' < '9')."""

    def __init__(self, value):
        super().__init__(str(value))
        self._value = value

    def __lt__(self, other):
        if isinstance(other, _NumericSortItem):
            return self._value < other._value
        return super().__lt__(other)


class MainWindow(QMainWindow):
    _AVATAR_SIZE = 60

    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.setWindowTitle("Coffee Can")
        self.resize(1320, 960)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        layout.addWidget(self._build_header())
        layout.addWidget(self._build_beans_card(), 1)

        activity_splitter = QSplitter(Qt.Orientation.Horizontal)
        activity_splitter.setChildrenCollapsible(False)
        activity_splitter.addWidget(self._build_profile_card())
        activity_splitter.addWidget(self._build_calendar_card())
        activity_splitter.addWidget(self._build_flavor_profile_card())
        # Flavor Profile gets less width than Profile/Brewing Activity -- its
        # radar chart doesn't need as much horizontal room as the other two
        # cards' text content.
        activity_splitter.setStretchFactor(0, 2)
        activity_splitter.setStretchFactor(1, 2)
        activity_splitter.setStretchFactor(2, 1)
        layout.addWidget(activity_splitter)
        # setSizes() before the window is shown has no real width to split --
        # defer it a tick so it acts on the splitter's actual laid-out size.
        QTimer.singleShot(0, lambda: activity_splitter.setSizes([2, 2, 1]))

        self.setCentralWidget(central)

        self._refresh_beans()
        self._refresh_activity()
        self._refresh_profile()

    # --- header ---------------------------------------------------------

    def _build_header(self):
        header = HeaderBanner()
        header.setMinimumHeight(150)
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 18, 0, 46)  # leave room at the bottom for the walking can
        layout.setSpacing(4)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = icon_path()
        if icon:
            icon_label.setPixmap(QIcon(icon).pixmap(64, 64))

        title = QLabel("Coffee Can")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1C1C1E;")

        subtitle = QLabel("Track your hand-brew coffee, one cup at a time")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #8E8E93; font-size: 12px;")

        layout.addWidget(icon_label)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return header

    # --- coffee profiles card --------------------------------------------

    def _build_beans_card(self):
        group = QGroupBox("Coffee Profiles")
        layout = QVBoxLayout(group)

        self.beans_table = QTableWidget(0, 6)
        self.beans_table.setHorizontalHeaderLabels(
            ["ID", "Name", "Origin", "Process", "Roast date", "Sessions"]
        )
        self.beans_table.setColumnHidden(0, True)
        self.beans_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.beans_table.verticalHeader().setVisible(False)
        self.beans_table.setAlternatingRowColors(True)
        self.beans_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.beans_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.beans_table.setSortingEnabled(True)
        self.beans_table.doubleClicked.connect(self._edit_bean)
        layout.addWidget(self.beans_table)

        buttons = QHBoxLayout()
        new_btn = QPushButton("New Profile")
        new_btn.setProperty("variant", "primary")
        new_btn.clicked.connect(self._new_bean)
        edit_btn = QPushButton("Edit / View")
        edit_btn.clicked.connect(self._edit_bean)
        delete_btn = QPushButton("Delete")
        delete_btn.setProperty("variant", "destructive")
        delete_btn.clicked.connect(self._delete_bean)
        for button in (new_btn, edit_btn, delete_btn):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        return group

    def _selected_bean_id(self):
        row = self.beans_table.currentRow()
        if row < 0:
            return None
        return int(self.beans_table.item(row, 0).text())

    def _refresh_beans(self):
        rows = repo.list_beans(self.conn)
        self.beans_table.setSortingEnabled(False)
        self.beans_table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.beans_table.setItem(i, 0, QTableWidgetItem(str(row["id"])))
            self.beans_table.setItem(i, 1, _TextSortItem(row["name"]))
            self.beans_table.setItem(i, 2, _TextSortItem(format_or_dash(row["origin"])))
            self.beans_table.setItem(i, 3, _TextSortItem(format_or_dash(row["process"])))
            self.beans_table.setItem(i, 4, _TextSortItem(format_or_dash(row["roast_date"])))
            self.beans_table.setItem(i, 5, _NumericSortItem(row["session_count"]))
        self.beans_table.setSortingEnabled(True)

    def _new_bean(self):
        BeanDialog(self.conn, bean_id=None, parent=self).exec()
        self._refresh_beans()
        self._refresh_activity()

    def _edit_bean(self):
        bean_id = self._selected_bean_id()
        if bean_id is None:
            QMessageBox.information(self, "No selection", "Select a coffee profile first.")
            return
        BeanDialog(self.conn, bean_id=bean_id, parent=self).exec()
        self._refresh_beans()
        self._refresh_activity()

    def _delete_bean(self):
        bean_id = self._selected_bean_id()
        if bean_id is None:
            QMessageBox.information(self, "No selection", "Select a coffee profile first.")
            return
        row = repo.get_bean(self.conn, bean_id)
        confirm = QMessageBox.question(
            self, "Delete profile", f"Delete profile '{row['name']}' and all its brewing sessions?"
        )
        if confirm == QMessageBox.Yes:
            repo.delete_bean(self.conn, bean_id)
            self._refresh_beans()
            self._refresh_activity()

    # --- profile card -----------------------------------------------------

    def _build_profile_card(self):
        group = QGroupBox("Profile")
        outer = QVBoxLayout(group)

        top_row = QHBoxLayout()
        top_row.addStretch()
        settings_btn = QPushButton("⚙")  # gear
        settings_btn.setFixedSize(30, 30)
        settings_btn.setToolTip("Profile settings")
        # The global QPushButton rule pads 8px/18px, which leaves no room for
        # the glyph in a small fixed-size button -- same issue as the image
        # carousel's nav buttons; override with a style sized for this one.
        settings_btn.setStyleSheet(
            "QPushButton { padding: 0px; font-size: 15px; border-radius: 15px; "
            "background-color: #E5E5EA; color: #1C1C1E; }"
            "QPushButton:hover { background-color: #DCDCE1; }"
            "QPushButton:pressed { background-color: #CFCFD4; }"
        )
        settings_btn.clicked.connect(self._open_profile_settings)
        top_row.addWidget(settings_btn)
        outer.addLayout(top_row)

        self.profile_avatar_label = QLabel()
        self.profile_avatar_label.setFixedSize(self._AVATAR_SIZE, self._AVATAR_SIZE)
        self.profile_avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.profile_avatar_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.profile_name_label = QLabel()
        self.profile_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_name_label.setStyleSheet("font-weight: 700; font-size: 14px; color: #1C1C1E;")
        outer.addWidget(self.profile_name_label)

        self.profile_email_label = QLabel()
        self.profile_email_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_email_label.setStyleSheet("color: #8E8E93; font-size: 11px;")
        outer.addWidget(self.profile_email_label)

        outer.addStretch()
        return group

    def _open_profile_settings(self):
        ProfileSettingsDialog(parent=self).exec()
        self._refresh_profile()

    def _refresh_profile(self):
        data = profile.load_profile()
        self.profile_name_label.setText(data.get("name") or "Set up your profile")
        email = data.get("email") or ""
        self.profile_email_label.setText(email)
        self.profile_email_label.setVisible(bool(email))

        image_path = data.get("image_path")
        pixmap = circular_pixmap(image_path, self._AVATAR_SIZE) if image_path and Path(image_path).exists() else QPixmap()
        if pixmap.isNull():
            self.profile_avatar_label.setPixmap(default_avatar_pixmap(self._AVATAR_SIZE))
            self.profile_avatar_label.setText("")
            self.profile_avatar_label.setStyleSheet("")
        else:
            self.profile_avatar_label.setPixmap(pixmap)
            self.profile_avatar_label.setText("")
            self.profile_avatar_label.setStyleSheet("")

    # --- brewing activity card --------------------------------------------

    def _build_calendar_card(self):
        group = QGroupBox("Brewing Activity")
        layout = QVBoxLayout(group)

        self.calendar = ContributionCalendar()
        layout.addWidget(self.calendar)

        legend = QHBoxLayout()
        legend.addStretch()
        legend.addWidget(self._legend_label("Less"))
        for color in ("#EBEDF0", "#C8F0D4", "#7FDB9E", "#42CE7C", "#34C759"):
            swatch = QLabel()
            swatch.setFixedSize(10, 10)
            swatch.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
            legend.addWidget(swatch)
        legend.addWidget(self._legend_label("More"))
        layout.addLayout(legend)
        return group

    @staticmethod
    def _legend_label(text):
        label = QLabel(text)
        label.setStyleSheet("color: #8E8E93; font-size: 11px;")
        return label

    # --- flavor profile card ----------------------------------------------

    def _build_flavor_profile_card(self):
        group = QGroupBox("Flavor Profile")
        layout = QVBoxLayout(group)

        self.flavor_caption = QLabel()
        self.flavor_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.flavor_caption.setStyleSheet("color: #8E8E93; font-size: 11px;")

        self.flavor_radar = RadarChart([label for _, label in repo.FLAVOR_AXES])

        layout.addWidget(self.flavor_radar, 1, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.flavor_caption)
        return group

    def _refresh_activity(self):
        self.calendar.set_counts(repo.count_sessions_by_date(self.conn))

        count, averages = repo.get_average_flavor_scores(self.conn)
        if averages is None:
            self.flavor_radar.set_values(None, has_data=False)
            self.flavor_caption.setText("No brewing sessions yet")
        else:
            self.flavor_radar.set_values(averages, has_data=True)
            self.flavor_caption.setText(f"Average across {count} session{'s' if count != 1 else ''}")
