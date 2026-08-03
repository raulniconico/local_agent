""""What's New" dialog: pick a roaster, see what's currently listed on their
own site. Two stacked pages -- a roaster list, then a product table for
whichever one was picked -- rather than nested dialogs, so "back" just flips
pages instead of opening another modal on top.

All listing data goes through whats_new.py, which is the actual crawler and
the thing specs/legal.md governs; this file is purely presentation -- with
one exception: the photo preview panel fetches the *image* bytes itself,
directly from the roaster's own CDN/media URL, only for whichever single row
is currently selected, and only ever holds the result as an in-memory
QPixmap. Nothing image-related is ever written to disk or cached between
selections -- see _load_preview()/_on_image_loaded() below, and
specs/legal.md rule 31 for why that line is drawn where it is.
"""

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import whats_new
from . import background
from .widgets import WalkingCanLoader

_PREVIEW_SIZE = 180


class _FetchWorker(QThread):
    """Runs one whats_new.fetch_listings() call off the GUI thread -- a
    blocking HTTPS round-trip. See background.py for why the thread isn't
    owned by the dialog."""

    succeeded = Signal(str, list)  # (roaster_key, listings)
    failed = Signal(str, str)  # (roaster_key, message)

    def __init__(self, roaster_key: str):
        super().__init__()
        self._roaster_key = roaster_key

    def run(self):
        try:
            listings = whats_new.fetch_listings(self._roaster_key)
        except whats_new.RoasterUnavailableError as exc:
            self.failed.emit(self._roaster_key, str(exc))
        else:
            self.succeeded.emit(self._roaster_key, listings)


class WhatsNewDialog(QDialog):
    _COLUMNS = ("Name", "Price", "Weight", "In stock", "Description")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("What's New")
        self.resize(760, 560)
        self._worker = None
        self._current_listings = []
        self._network = QNetworkAccessManager(self)
        self._image_reply = None

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_roaster_page())
        self.stack.addWidget(self._build_products_page())

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(close_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(self.stack, 1)
        layout.addLayout(bottom)

    # --- page 0: roaster list --------------------------------------------

    def _build_roaster_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Roasters whose public catalogues coffee-can can read:"))

        self.roaster_list = QListWidget()
        for key, (label, domain, _platform) in whats_new.ROASTERS.items():
            item = QListWidgetItem(f"{label}  —  {domain}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.roaster_list.addItem(item)
        self.roaster_list.itemDoubleClicked.connect(self._open_roaster)
        layout.addWidget(self.roaster_list, 1)

        view_btn = QPushButton("View beans on sale")
        view_btn.setProperty("variant", "primary")
        view_btn.clicked.connect(self._open_selected_roaster)
        layout.addWidget(view_btn)
        return page

    def _open_selected_roaster(self):
        item = self.roaster_list.currentItem()
        if item is None:
            QMessageBox.information(self, "No selection", "Pick a roaster first.")
            return
        self._open_roaster(item)

    def _open_roaster(self, item: QListWidgetItem):
        key = item.data(Qt.ItemDataRole.UserRole)
        self._fetch(key)

    # --- page 1: product table -------------------------------------------

    def _build_products_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        back_btn = QPushButton("‹ Back")
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        top_row.addWidget(back_btn)
        self.roaster_title_label = QLabel("")
        self.roaster_title_label.setStyleSheet("font-weight: 700; font-size: 14px;")
        top_row.addWidget(self.roaster_title_label)
        top_row.addStretch()
        layout.addLayout(top_row)

        self.loader = WalkingCanLoader()
        self.loader.hide()
        layout.addWidget(self.loader)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #8E8E93; font-size: 11px;")
        layout.addWidget(self.status_label)

        self.products_table = QTableWidget(0, len(self._COLUMNS))
        self.products_table.setHorizontalHeaderLabels(self._COLUMNS)
        self.products_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.products_table.verticalHeader().setVisible(False)
        self.products_table.setAlternatingRowColors(True)
        self.products_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.products_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.products_table.doubleClicked.connect(self._open_product_page)
        self.products_table.itemSelectionChanged.connect(self._on_row_selected)

        table_row = QHBoxLayout()
        table_row.addWidget(self.products_table, 1)
        table_row.addWidget(self._build_preview_panel())
        layout.addLayout(table_row, 1)

        hint = QLabel(
            "Select a row for a photo (fetched live from the roaster's own site, "
            "never stored) — double-click to open the product page."
        )
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        return page

    def _build_preview_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(_PREVIEW_SIZE + 20)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(8)

        self.preview_image_label = QLabel("Select a product\nfor a photo")
        self.preview_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image_label.setWordWrap(True)
        self.preview_image_label.setFixedSize(_PREVIEW_SIZE, _PREVIEW_SIZE)
        self.preview_image_label.setStyleSheet(
            "background-color: #FFFFFF; border-radius: 10px; color: #8E8E93;"
        )
        self.preview_name_label = QLabel("")
        self.preview_name_label.setWordWrap(True)
        self.preview_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_name_label.setStyleSheet("font-size: 11px;")

        panel_layout.addWidget(self.preview_image_label)
        panel_layout.addWidget(self.preview_name_label)
        panel_layout.addStretch()
        return panel

    def _fetch(self, roaster_key: str):
        label = whats_new.ROASTERS[roaster_key][0]
        self.roaster_title_label.setText(label)
        self.products_table.setRowCount(0)
        self.status_label.setText(f"Fetching {label}'s current listing…")
        self.loader.show()
        self.stack.setCurrentIndex(1)

        worker = _FetchWorker(roaster_key)
        self._worker = worker
        worker.succeeded.connect(self._on_succeeded)
        worker.failed.connect(self._on_failed)
        background.start(worker)

    def _on_succeeded(self, roaster_key: str, listings: list):
        self._worker = None
        self.loader.hide()
        self._current_listings = listings
        self._clear_preview()

        if not listings:
            self.status_label.setText("No products found.")
            return

        fetched_at = listings[0].fetched_at.strftime("%Y-%m-%d %H:%M UTC")
        self.status_label.setText(
            f"{len(listings)} product(s) — prices as listed by {listings[0].roaster} on {fetched_at}"
        )

        self.products_table.setRowCount(len(listings))
        for row, listing in enumerate(listings):
            name_item = QTableWidgetItem(listing.name)
            name_item.setData(Qt.ItemDataRole.UserRole, listing.url)
            self.products_table.setItem(row, 0, name_item)
            self.products_table.setItem(row, 1, QTableWidgetItem(listing.price_display))
            self.products_table.setItem(row, 2, QTableWidgetItem(listing.weight_display))
            self.products_table.setItem(row, 3, QTableWidgetItem("Yes" if listing.in_stock else "No"))
            self.products_table.setItem(row, 4, QTableWidgetItem(listing.note_excerpt))

    # --- photo preview: fetched live, held only as an in-memory QPixmap ----

    def _on_row_selected(self):
        row = self.products_table.currentRow()
        if row < 0 or row >= len(self._current_listings):
            self._clear_preview()
            return
        listing = self._current_listings[row]
        self.preview_name_label.setText(listing.name)
        self._load_preview(listing.image_url)

    def _clear_preview(self):
        if self._image_reply is not None:
            self._image_reply.abort()
            self._image_reply = None
        self.preview_image_label.setPixmap(QPixmap())
        self.preview_image_label.setText("Select a product\nfor a photo")
        self.preview_name_label.setText("")

    def _load_preview(self, image_url: str):
        if self._image_reply is not None:
            self._image_reply.abort()
            self._image_reply = None

        self.preview_image_label.setPixmap(QPixmap())
        if not image_url:
            self.preview_image_label.setText("No photo listed")
            return
        self.preview_image_label.setText("Loading…")

        request = QNetworkRequest(QUrl(image_url))
        request.setRawHeader(b"User-Agent", whats_new.USER_AGENT.encode())
        reply = self._network.get(request)
        self._image_reply = reply
        reply.finished.connect(lambda: self._on_image_loaded(reply))

    def _on_image_loaded(self, reply: QNetworkReply):
        # A superseded request (selection moved on before this one finished)
        # is aborted in _load_preview/_clear_preview -- its result, if it
        # still arrives, belongs to a row that's no longer selected.
        is_current = reply is self._image_reply
        if is_current:
            self._image_reply = None

        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            reply.deleteLater()
            if is_current:
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                if pixmap.isNull():
                    self.preview_image_label.setText("Preview unavailable")
                else:
                    scaled = pixmap.scaled(
                        _PREVIEW_SIZE,
                        _PREVIEW_SIZE,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.preview_image_label.setText("")
                    self.preview_image_label.setPixmap(scaled)
        else:
            reply.deleteLater()
            if is_current:
                self.preview_image_label.setText("Preview unavailable")

    def _on_failed(self, roaster_key: str, message: str):
        self._worker = None
        self.loader.hide()
        self.status_label.setText("")
        QMessageBox.warning(self, "Couldn't fetch listing", message)

    def _open_product_page(self):
        row = self.products_table.currentRow()
        if row < 0:
            return
        url = self.products_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def closeEvent(self, event):
        # The request keeps running to completion in the background (there's
        # no way to cancel an in-flight HTTP call), but its signals must stop
        # reaching a dialog that's on its way out -- same reasoning as
        # ai_brew_dialog.AiBrewSuggestionDialog.closeEvent.
        if self._worker is not None:
            self._worker.succeeded.disconnect(self._on_succeeded)
            self._worker.failed.disconnect(self._on_failed)
            self._worker = None
        if self._image_reply is not None:
            self._image_reply.abort()
            self._image_reply = None
        super().closeEvent(event)
