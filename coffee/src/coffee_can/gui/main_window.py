"""Main window: a welcome screen with three stacked blocks -- logo header,
coffee profiles list, and a fused overview block holding the brewing
activity calendar and flavor profile panes."""

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import coffee_news, repo, whats_new
from ..assets import icon_path
from ..formatting import format_or_dash
from . import background
from .bean_dialog import BeanDialog
from .profile_dialog import ProfileSettingsDialog
from .whats_new_dialog import WhatsNewDialog
from .widgets import ContributionCalendar, HeaderBanner, RadarChart, VerticalTicker


class _TickerFetchWorker(QThread):
    """One whats_new.fetch_listings() call off the GUI thread, for the main
    window's rolling feed. Mirrors whats_new_dialog._FetchWorker."""

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


class _NewsFetchWorker(QThread):
    """coffee_news.fetch_news() off the GUI thread -- several RSS round-trips
    plus an optional Qwen ranking call."""

    succeeded = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            items = coffee_news.fetch_news()
        except coffee_news.NewsUnavailableError as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(items)


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
    _LOGO_SIZE = 73  # 70% of the original 104px mark
    # Coffee Profiles gets 150% of the overview card's share of the leftover
    # vertical space. Expressed as stretch rather than a pixel floor so the
    # ratio survives every window size -- an absolute minimum tall enough to
    # look right maximised also became a minimum the window could never go
    # below, which pushed it past the height of a 1080p screen.
    _BEANS_STRETCH, _OVERVIEW_STRETCH = 3, 2
    # Chart radius is min(half-width - 64, half-height - 26), and the card
    # is much wider than it is tall, so height is what actually binds. Width
    # past roughly (radius + label margin) * 2 is dead space the widget
    # centres its polygon inside -- which pushed the chart visibly away from
    # the calendar without ever drawing it any bigger.
    _RADAR_MAX_WIDTH = 360
    _CALENDAR_SCALE = 1.2  # contribution grid, relative to its natural size
    _HEADER_GAP = 10  # extra breathing room under a pane's heading
    # What the window's content margin used to be. Now added inside each
    # card on the sides facing the window, so the cards sit flush while
    # their contents stay exactly where they were.
    _WINDOW_INSET = 20
    # What used to separate one card from the next: 8px of layout spacing
    # plus the 8px QGroupBox margin-top each card carried. Now folded into
    # the card's own top padding, so cards abut while their contents hold
    # position.
    _BLOCK_GAP = 16
    _MARKET_LIMIT = 20  # entries in the Coffee Market rolling feed
    _THEME_CARD_PADDING = 12  # theme.STYLESHEET's QGroupBox left/right/bottom padding
    _THEME_CARD_PADDING_TOP = 14  # ... and its top padding, which differs
    # The app-wide QGroupBox rule reserves margin-top:22px for a native
    # title drawn *above* the card background. These top-level cards render
    # their own heading as a QLabel inside the card instead (see
    # _pane_header), so that reserved strip is dead space -- drop it
    # entirely and let the cards meet.
    #
    # The padding restates theme.STYLESHEET's own values and adds back the
    # space the window margin and the inter-card gap used to provide. It
    # goes here, in the card's QSS box, rather than on the card's layout: a
    # QVBoxLayout built on a QGroupBox leaves its margins unset and resolves
    # them from the style at layout time, so reading them and writing back a
    # larger value froze them at a different number than the one actually in
    # effect (11 vs 9) and shifted the contents 2px.
    # Square corners: the theme's 14px radius is for a card floating on the
    # window background. Now that the cards are full-bleed and abut each
    # other, that radius only showed up as grey wedges of window background
    # notched into the seams where two cards meet.
    _CARD_STYLE = (
        "QGroupBox { margin-top: 0px; border-radius: 0px; padding-top: %(top)dpx;"
        " padding-left: %(side)dpx; padding-right: %(side)dpx; }"
    )

    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.setWindowTitle("Coffee Can")
        self.resize(1320, 960)

        central = QWidget()
        layout = QVBoxLayout(central)
        # Cards run flush to the window edge. The inset each one used to get
        # from this margin is pushed inside the card instead (_WINDOW_INSET,
        # added to the sides that face the window in each _build_* method),
        # so only the card backgrounds reach further out -- nothing they
        # contain moves.
        layout.setContentsMargins(0, 0, 0, 0)
        # Cards abut; the gap that used to sit here lives in their top
        # padding now (_BLOCK_GAP), so contents stay put.
        layout.setSpacing(0)
        layout.addWidget(self._build_header())
        layout.addWidget(self._build_beans_card(), self._BEANS_STRETCH)
        layout.addWidget(self._build_overview_card(), self._OVERVIEW_STRETCH)

        self.setCentralWidget(central)

        self._refresh_beans()
        self._refresh_activity()
        self._start_news_feed()
        self._start_market_feed()

    def _open_whats_new(self):
        """Open the release-notes dialog.

        Nothing in the window calls this right now -- the button that used
        to sit in the overview card was removed. Kept, along with the
        WhatsNewDialog import, so a future entry point (menu item, first-run
        prompt) only has to connect to it."""
        WhatsNewDialog(parent=self).exec()

    # --- header ---------------------------------------------------------

    def _build_header(self):
        header = HeaderBanner()
        header.setMinimumHeight(132)
        # Square off the strip's rounded corners for the same reason the
        # cards below it are squared -- it is full-bleed now and its bottom
        # corners notched into the card underneath.
        header._RADIUS = 0
        # A grid rather than a plain QVBoxLayout: the centred icon/title/
        # subtitle stack and the settings button both occupy cell (0, 0),
        # each aligned differently within it (stack fills it, button pins
        # to its top-right corner), so the button floats over the banner
        # instead of pushing the centred content down.
        grid = QGridLayout(header)
        # Both margins are just the content's inset from the banner edge --
        # no lane is reserved for the walking can. It tracks the strip's own
        # bottom edge and tops its lap out at the top edge, so it passes
        # behind the tagline on the way past and behind the logo at the
        # apex; child widgets paint over the strip, which makes that read as
        # depth rather than as clipping.
        # Left/top/right face the window and carry _WINDOW_INSET; the bottom
        # faces the card below and does not.
        grid.setContentsMargins(
            0 + self._WINDOW_INSET,
            10 + self._WINDOW_INSET,
            12 + self._WINDOW_INSET,
            8,
        )

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = icon_path()
        if icon:
            icon_label.setPixmap(QIcon(icon).pixmap(self._LOGO_SIZE, self._LOGO_SIZE))
            header.set_logo(icon_label, self._LOGO_SIZE)

        title = QLabel("Coffee Can")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #1C1C1E;")

        subtitle = QLabel("Ready to be a brew chem(can)ist")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #8E8E93; font-size: 12px;")

        layout.addWidget(icon_label)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        grid.addWidget(content, 0, 0)

        settings_btn = self._build_settings_button()
        grid.addWidget(settings_btn, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        return header

    def _build_settings_button(self):
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
        return settings_btn

    def _open_profile_settings(self):
        ProfileSettingsDialog(parent=self).exec()

    # --- coffee profiles card --------------------------------------------

    def _build_beans_card(self):
        group = QGroupBox()
        # Only the sides face the window -- a card sits above and below.
        group.setStyleSheet(self._card_style())
        layout = QVBoxLayout(group)
        layout.addWidget(self._pane_header("Coffee Profiles"))

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
        # A floor, not a target -- the 3:2 stretch sizes the table at every
        # normal window height. This only stops the overview card's own
        # minimum from squeezing the list down to a header and no rows on a
        # short window, and is small enough not to raise the window's
        # minimum height beyond a laptop screen.
        self.beans_table.setMinimumHeight(160)
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

    # --- overview card (brewing activity + flavor profile) ----------------

    def _build_overview_card(self):
        """Brewing Activity and Flavor Profile share one bordered block --
        two panes inside a single QGroupBox, rather than separately-bordered
        boxes side by side.

        A plain row, not a QSplitter: a splitter always divides its whole
        width between its panes, so maximised it handed the flavor pane
        ~1600px it had no use for (the radar's radius is capped by the
        shorter of its half-width and half-height, so surplus width just
        becomes blank card). The trailing stretch parks that surplus outside
        both panes instead, keeping the calendar and radar adjacent."""
        group = QGroupBox()
        # Left/right/bottom face the window; the top faces the card above.
        group.setStyleSheet(self._card_style(flush_bottom=True))
        outer = QVBoxLayout(group)
        outer.setContentsMargins(0, 0, 0, 0)

        row = QHBoxLayout()
        # No inter-pane spacing: the radar already carries a wide internal
        # margin for its axis labels, so the layout's default gap on top of
        # that just reads as the chart drifting away from the calendar.
        row.setSpacing(0)
        row.addWidget(self._build_calendar_pane())
        row.addWidget(self._build_flavor_profile_pane())
        # The corner the trailing stretch used to hold, split evenly in two.
        row.addWidget(self._build_whats_new_pane(), 1)
        row.addWidget(self._build_market_pane(), 1)
        outer.addLayout(row)
        return group

    # --- what's new pane ----------------------------------------------------

    def _build_whats_new_pane(self):
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.addWidget(self._pane_header("What's New"))
        layout.addSpacing(self._HEADER_GAP)

        self.news_ticker = VerticalTicker()
        self.news_ticker.set_placeholder("Loading today's coffee news…")
        self.news_ticker.activated.connect(self._open_news_item)
        layout.addWidget(self.news_ticker, 1)
        return pane

    def _start_news_feed(self):
        """Today's coffee headlines, ranked by Qwen. See coffee_news for why
        the headlines come from the outlets' RSS rather than from the model."""
        self._news_worker = _NewsFetchWorker()
        self._news_worker.succeeded.connect(self._on_news_ready)
        self._news_worker.failed.connect(self._on_news_failed)
        background.start(self._news_worker)

    def _on_news_ready(self, items):
        self.news_ticker.set_entries(
            [(item.title, f"{item.source} · {item.age_display()}", item.url) for item in items]
        )
        if not items:
            self.news_ticker.set_placeholder("No coffee news in the last 24 hours")

    def _on_news_failed(self, message):
        self.news_ticker.set_placeholder(message)

    def _open_news_item(self, url):
        QDesktopServices.openUrl(QUrl(url))

    # --- coffee market pane -------------------------------------------------

    def _start_market_feed(self):
        """Populate the market ticker from the roasters' own product endpoints.

        One worker per roaster, off the GUI thread. whats_new.fetch_listings()
        caches for 15 minutes, so re-opening the window inside that window
        costs no requests at all -- the ticker never becomes a reason to hit
        a host more often than the dialog already would."""
        self._market_rows = []
        self._market_workers = []
        for roaster_key in whats_new.ROASTERS:
            worker = _TickerFetchWorker(roaster_key)
            worker.succeeded.connect(self._on_market_batch)
            worker.failed.connect(self._on_market_failed)
            self._market_workers.append(worker)
            # background.start() owns the lifetime -- a QThread torn down while
            # still running aborts the process, and an in-flight HTTP call
            # can't be cancelled.
            background.start(worker)

    def _on_market_batch(self, _roaster_key, listings):
        for listing in listings:
            if not listing.in_stock or not whats_new.looks_like_coffee(listing):
                continue
            subtitle = " · ".join(
                part
                for part in (listing.roaster, listing.price_display, listing.weight_display)
                if part and part != "—"
            )
            self._market_rows.append((listing.published_at, listing.name, subtitle, listing.url))
        # Newest first, on the seller's own published_at. Undated listings
        # (the WooCommerce Store API exposes none) sort last rather than
        # being presented as if they were new.
        self._market_rows.sort(key=lambda row: (row[0] is not None, row[0]), reverse=True)
        self.market_ticker.set_entries(
            [(name, subtitle, url) for _, name, subtitle, url in self._market_rows[: self._MARKET_LIMIT]]
        )

    def _on_market_failed(self, _roaster_key, _message):
        if not self._market_rows:
            self.market_ticker.set_placeholder("Couldn't reach the roasters")

    def closeEvent(self, event):
        # The requests keep running to completion (background.py owns the
        # threads and app shutdown waits on them), but their signals must
        # stop reaching a window on its way out -- same reasoning as
        # whats_new_dialog.closeEvent.
        for worker in self._market_workers:
            worker.succeeded.disconnect(self._on_market_batch)
            worker.failed.disconnect(self._on_market_failed)
        self._market_workers.clear()
        if self._news_worker is not None:
            self._news_worker.succeeded.disconnect(self._on_news_ready)
            self._news_worker.failed.disconnect(self._on_news_failed)
            self._news_worker = None
        super().closeEvent(event)

    def _build_market_pane(self):
        pane = QWidget()
        layout = QVBoxLayout(pane)
        layout.addWidget(self._pane_header("Coffee Market"))
        layout.addSpacing(self._HEADER_GAP)

        self.market_ticker = VerticalTicker()
        self.market_ticker.set_placeholder("Loading new arrivals…")
        self.market_ticker.activated.connect(self._open_news_item)
        layout.addWidget(self.market_ticker, 1)
        return pane

    @staticmethod
    def _pane_header(text):
        label = QLabel(text)
        label.setStyleSheet("font-weight: 700; font-size: 13px; color: #1C1C1E;")
        return label

    @classmethod
    def _card_style(cls, flush_bottom=False):
        """QSS for a top-level card sitting flush against the window edge."""
        style = cls._CARD_STYLE % {
            "side": cls._THEME_CARD_PADDING + cls._WINDOW_INSET,
            "top": cls._THEME_CARD_PADDING_TOP + cls._BLOCK_GAP,
        }
        if flush_bottom:
            style += "QGroupBox { padding-bottom: %dpx; }" % (
                cls._THEME_CARD_PADDING + cls._WINDOW_INSET
            )
        return style

    # --- brewing activity pane ---------------------------------------------

    def _build_calendar_pane(self):
        pane = QWidget()
        # Hug the grid's own width. Left at the default Preferred the pane
        # would soak up the card's surplus width and shove the radar beside
        # it out to the middle of the window, with the calendar stranded far
        # to its left.
        pane.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        # A grid so the heading and the grid can be aligned independently
        # inside one cell: the heading stays pinned to the pane's top-left
        # while the calendar centres on the card's horizontal midline. A
        # QVBoxLayout could only centre it in the space left under the
        # heading, which sits a half-heading's height above the true middle.
        grid = QGridLayout(pane)
        grid.addWidget(
            self._pane_header("Brewing Activity"),
            0, 0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )

        self.calendar = ContributionCalendar()
        # ContributionCalendar defaults to Expanding and fills whatever space
        # its container hands it; pin it to a fixed size instead, scaled off
        # its own natural size so the cell geometry stays proportional --
        # _metrics() recomputes cell and gap from whatever size it is given.
        self.calendar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.calendar.setFixedSize(self.calendar.sizeHint() * self._CALENDAR_SCALE)

        column = QWidget()
        inner = QVBoxLayout(column)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.addWidget(self.calendar, 0, Qt.AlignmentFlag.AlignLeft)

        legend = QHBoxLayout()
        for color in ("#EBEDF0", "#C8F0D4", "#7FDB9E", "#42CE7C", "#34C759"):
            swatch = QLabel()
            swatch.setFixedSize(10, 10)
            swatch.setStyleSheet(f"background-color: {color}; border-radius: 2px;")
            legend.addWidget(swatch)
        legend.addStretch()
        inner.addLayout(legend)

        grid.addWidget(column, 0, 0, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        return pane

    # --- flavor profile pane ------------------------------------------------

    def _build_flavor_profile_pane(self):
        pane = QWidget()
        layout = QVBoxLayout(pane)
        # No left inset -- every pixel here is dead space between the
        # contribution grid and the chart beside it. The radar reserves its
        # own 64px label margin internally, which is already generous.
        layout.setContentsMargins(0, 4, 4, 4)
        # Heading pinned top-left over the chart, matching how "Brewing
        # Activity" sits above the calendar in the pane to the left.
        layout.addWidget(self._pane_header("Flavor Profile"))
        layout.addSpacing(self._HEADER_GAP)

        column = QWidget()
        inner = QVBoxLayout(column)
        inner.setContentsMargins(0, 0, 0, 0)

        self.flavor_radar = RadarChart([label for _, label in repo.FLAVOR_AXES])
        # Free to grow with the card, but the column is capped in width: the
        # radius is min(half-width - label margin, half-height - label
        # margin), so width past roughly twice the height buys nothing and
        # would only push the chart away from the calendar it sits beside.
        self.flavor_radar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # RadarChart pins its own minimum to its 320x250 sizeHint. Relax it
        # for this instance: as a hard floor it set the overview card's
        # minimum height, which on a short window was met by starving the
        # profiles table above rather than by drawing a smaller chart.
        self.flavor_radar.setMinimumSize(250, 180)
        column.setMaximumWidth(self._RADAR_MAX_WIDTH)
        inner.addWidget(self.flavor_radar, 1)

        # Caption stays under the chart it summarises, centred on it.
        self.flavor_caption = QLabel()
        self.flavor_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.flavor_caption.setStyleSheet("color: #8E8E93; font-size: 11px;")
        inner.addWidget(self.flavor_caption)

        layout.addWidget(column)
        return pane

    def _refresh_activity(self):
        self.calendar.set_counts(repo.count_sessions_by_date(self.conn))

        count, averages = repo.get_average_flavor_scores(self.conn)
        if averages is None:
            self.flavor_radar.set_values(None, has_data=False)
            self.flavor_caption.setText("No brewing sessions yet")
        else:
            self.flavor_radar.set_values(averages, has_data=True)
            self.flavor_caption.setText(f"Average across {count} session{'s' if count != 1 else ''}")
