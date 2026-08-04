""""Can drink": every coffee the roasters currently list, in one filterable
table -- what the main window's shelf shows three random picks of.

The listings are handed in by the caller rather than fetched here: the main
window already fetched all five roasters to fill the shelf, and whats_new.py's
cache is per-process, so re-fetching would either be a no-op or, once the
cache expired, five more requests for a dialog the user only wanted to browse.
See specs/legal.md §3.4 -- the politeness budget is spent by the window, and
this dialog is free.

Filtering is entirely local, over listings already in memory: picking a
roaster or an origin never issues a request. As in whats_new_dialog, the one
thing that does touch the network is the photo of the selected row, hotlinked
live from the roaster's own CDN into an in-memory QPixmap and never stored --
here that lives inside widgets.RemoteImageLabel.
"""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import whats_new
from .widgets import RemoteImageLabel

_PREVIEW_SIZE = 180
#: Both filter combos, so they line up whether their longest entry is
#: "Belleville Brûlerie" or "Kenya".
_COMBO_WIDTH = 150
_ANY = "All"
#: Filter value for bags whose origin detect_origin() couldn't work out. Kept
#: selectable rather than hidden -- it is a real chunk of the catalogue
#: (blends under invented names, kits, seasonal boxes), not an error.
_UNKNOWN = "Not stated"


class CanSeeDialog(QDialog):
    _COLUMNS = ("Name", "Roaster", "Origin", "Price", "Weight", "In stock")

    def __init__(self, listings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Can drink — every coffee on the shelf")
        self.resize(920, 620)
        # Origin is derived once per listing, not per keystroke: detect_origin
        # runs ~35 regexes over each bag and the filters re-run on every
        # change.
        self._rows = [(listing, whats_new.detect_origin(listing)) for listing in listings]
        self._visible = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(self._build_filter_row())

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #8E8E93; font-size: 11px;")
        layout.addWidget(self.status_label)

        body = QHBoxLayout()
        body.addWidget(self._build_table(), 1)
        body.addWidget(self._build_preview_panel())
        layout.addLayout(body, 1)

        hint = QLabel(
            "Names, prices and stock are the roasters' own, read from the product "
            "listings they publish. Photos are loaded live from their sites and never "
            "stored — double-click a row to open the product page."
        )
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        buttons = QHBoxLayout()
        buttons.addStretch()
        open_btn = QPushButton("Open product page")
        open_btn.setProperty("variant", "primary")
        open_btn.clicked.connect(self._open_selected)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        buttons.addWidget(open_btn)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self._apply_filters()

    # --- filters ----------------------------------------------------------

    def _build_filter_row(self) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.roaster_combo = QComboBox()
        self.roaster_combo.setMinimumWidth(_COMBO_WIDTH)
        self.roaster_combo.addItem(_ANY)
        self.roaster_combo.addItems(sorted({listing.roaster for listing, _ in self._rows}))
        self.roaster_combo.currentIndexChanged.connect(self._apply_filters)

        self.origin_combo = QComboBox()
        self.origin_combo.setMinimumWidth(_COMBO_WIDTH)
        self.origin_combo.addItem(_ANY)
        found = {origin for _, origin in self._rows if origin}
        self.origin_combo.addItems(sorted(found))
        if any(not origin for _, origin in self._rows):
            self.origin_combo.addItem(_UNKNOWN)
        self.origin_combo.currentIndexChanged.connect(self._apply_filters)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search names…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filters)

        self.stock_check = QCheckBox("In stock only")
        self.stock_check.setChecked(True)
        self.stock_check.stateChanged.connect(self._apply_filters)

        layout.addWidget(QLabel("Roaster"))
        layout.addWidget(self.roaster_combo)
        layout.addWidget(QLabel("Origin"))
        layout.addWidget(self.origin_combo)
        layout.addWidget(self.search_edit, 1)
        layout.addWidget(self.stock_check)
        return row

    def _matches(self, listing, origin: str) -> bool:
        roaster = self.roaster_combo.currentText()
        if roaster != _ANY and listing.roaster != roaster:
            return False
        wanted_origin = self.origin_combo.currentText()
        if wanted_origin == _UNKNOWN and origin:
            return False
        if wanted_origin not in (_ANY, _UNKNOWN) and origin != wanted_origin:
            return False
        if self.stock_check.isChecked() and not listing.in_stock:
            return False
        query = self.search_edit.text().strip().lower()
        return not query or query in listing.name.lower()

    def _apply_filters(self):
        self._visible = [(l, origin) for l, origin in self._rows if self._matches(l, origin)]
        self._fill_table()

    # --- table ------------------------------------------------------------

    def _build_table(self) -> QTableWidget:
        self.table = QTableWidget(0, len(self._COLUMNS))
        self.table.setHorizontalHeaderLabels(self._COLUMNS)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        # Name and roaster carry the long strings; the rest are short enough
        # to share whatever is left.
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 280)
        self.table.setColumnWidth(1, 150)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.doubleClicked.connect(self._open_selected)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        return self.table

    def _fill_table(self):
        # Sorting off while filling: with it on, Qt re-sorts after every
        # setItem and the row a cell lands in stops matching the row it was
        # written for. Signals off for the same span: row 0 stays "current"
        # across a refill, so every setItem would fire itemSelectionChanged
        # and kick off a photo request for a row the user never picked.
        self.table.setSortingEnabled(False)
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._visible))
        for row, (listing, origin) in enumerate(self._visible):
            name_item = QTableWidgetItem(listing.name)
            # The row's identity travels with the cell, so a re-sort can't
            # send a click to a different coffee's page.
            name_item.setData(Qt.ItemDataRole.UserRole, (listing.url, listing.image_url))
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(listing.roaster))
            self.table.setItem(row, 2, QTableWidgetItem(origin or "—"))
            self.table.setItem(row, 3, QTableWidgetItem(listing.price_display))
            self.table.setItem(row, 4, QTableWidgetItem(listing.weight_display))
            self.table.setItem(row, 5, QTableWidgetItem("Yes" if listing.in_stock else "No"))
        self.table.setSortingEnabled(True)
        # The old selection pointed at a row of the previous filter; drop it
        # outright rather than leaving a highlighted row whose photo panel
        # says nothing is selected.
        self.table.setCurrentItem(None)
        self.table.blockSignals(False)
        self._clear_preview()

        total = len(self._rows)
        shown = len(self._visible)
        if not total:
            self.status_label.setText(
                "Nothing fetched yet — the roasters' catalogues are still loading."
            )
        elif shown:
            self.status_label.setText(f"{shown} of {total} coffees")
        else:
            self.status_label.setText(f"No coffee matches these filters (of {total})")

    # --- preview and opening ----------------------------------------------

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(_PREVIEW_SIZE + 8)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.preview_image = RemoteImageLabel(_PREVIEW_SIZE, placeholder="Select a coffee\nfor a photo")
        self.preview_name = QLabel("")
        self.preview_name.setWordWrap(True)
        self.preview_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_name.setStyleSheet("font-size: 11px;")

        layout.addWidget(self.preview_image)
        layout.addWidget(self.preview_name)
        layout.addStretch()
        return panel

    def _selected_payload(self):
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _on_row_selected(self):
        payload = self._selected_payload()
        if payload is None:
            self._clear_preview()
            return
        self.preview_name.setText(self.table.item(self.table.currentRow(), 0).text())
        self.preview_image.load(payload[1])

    def _clear_preview(self):
        self.preview_image.clear_image()
        self.preview_name.setText("")

    def _open_selected(self):
        payload = self._selected_payload()
        if payload and payload[0]:
            QDesktopServices.openUrl(QUrl(payload[0]))

    def closeEvent(self, event):
        # Same reasoning as whats_new_dialog: an in-flight photo request can't
        # be cancelled, but its result must not reach a dialog on its way out.
        self.preview_image.clear_image()
        super().closeEvent(event)
