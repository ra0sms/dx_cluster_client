"""Main application window."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication, QIcon
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDockWidget, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMenu, QMessageBox, QPushButton, QSizePolicy, QSystemTrayIcon, QTableView, QTabWidget, QToolBar,
    QVBoxLayout, QWidget,
)

from .. import __version__
from ..core.alarms import KIND_COUNTRY, AlarmEntry, AlarmList
from ..core.bands import mode_label
from ..core.clock import ClockSync, judge_spot
from ..core.cluster_list import parse_address
from ..core.dxcc import DxccDB
from ..core.filters import SpotFilter
from ..core.geo import bearing_distance, locator_to_latlon
from ..core.settings import Settings, atomic_write, config_dir
from ..core.solar import SolarData, SolarFetcher
from ..core.spot import Spot, nearest_datetime, parse_spot
from ..core.telnet_client import STATE_CONNECTED, STATE_DISCONNECTED, ClusterClient
from ..core.telnet_server import SpotServer
from ..core.updates import RELEASES_PAGE, UpdateChecker
from ..i18n import LANGUAGES, tr, translator
from .alarm_tab import AlarmTab
from .clusters_tab import ClustersTab
from .console_tab import ConsoleTab
from .filter_panel import FilterPanel
from .send_spot import SendSpotDialog
from .settings_dialog import SettingsDialog
from .spot_model import COL_TIME, SpotFilterProxy, SpotTableModel, setup_spot_view

try:
    from PySide6.QtMultimedia import QSoundEffect
except ImportError:  # pragma: no cover
    QSoundEffect = None

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CTY_URL = "https://www.country-files.com/cty/cty.dat"
CLUSTER_LIST_MAX_AGE = 3600
CTY_MAX_AGE_DAYS = 30
UPDATE_CHECK_INTERVAL = 24 * 3600
log = logging.getLogger("dxclient.ui")


def load_dxcc() -> DxccDB:
    """Load cty.dat: the user's downloaded copy or the bundled one, whichever is newer."""
    best: DxccDB | None = None
    for p in (config_dir() / "cty.dat", DATA_DIR / "cty.dat"):
        if not p.exists():
            continue
        try:
            db = DxccDB.from_file(p)
        except OSError:
            continue
        if len(db.entities) > 100 and (best is None or (db.version or date.min) > (best.version or date.min)):
            best = db
    return best or DxccDB()


class MainWindow(QMainWindow):
    STATE_VERSION = 2  # bump when the dock layout changes
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.s = settings
        self.db = load_dxcc()
        self.alarms = AlarmList(
            [AlarmEntry.from_dict(d) for d in settings["alarms"]], settings["alarm_repeat_minutes"]
        )
        self.unread_alarms = 0
        self.home = locator_to_latlon(settings["locator"]) if settings["locator"] else None
        self.clock = ClockSync()
        self.setWindowIcon(QIcon(str(DATA_DIR / "icon.svg")))
        self.resize(1200, 750)

        # ---------------- client
        self.client = ClusterClient(self)
        self.client.line_received.connect(self._on_line)
        self.client.state_changed.connect(self._on_state)
        self.client.state_changed.connect(lambda st: self.console.append(f"*** {tr(st)}"))
        self.client.error.connect(lambda m: self.statusBar().showMessage(tr("Connection error: {msg}", msg=m), 8000))

        # ---------------- toolbar
        tb = QToolBar()
        tb.setObjectName("main_toolbar")
        tb.setMovable(False)
        self.addToolBar(tb)
        self.cluster_lbl = QLabel()
        self.cluster_combo = QComboBox()
        self.cluster_combo.setEditable(True)
        self.cluster_combo.setMinimumContentsLength(28)
        self.cluster_combo.addItems(settings["cluster_history"])
        self.cluster_combo.setCurrentText(settings["cluster"])
        self.cluster_combo.lineEdit().returnPressed.connect(self._toggle_connect)
        self.connect_btn = QPushButton()
        self.connect_btn.clicked.connect(self._toggle_connect)
        self.state_lbl = QLabel()
        self.state_lbl.setContentsMargins(10, 0, 0, 0)
        tb.addWidget(self.cluster_lbl)
        tb.addWidget(self.cluster_combo)
        tb.addWidget(self.connect_btn)
        tb.addWidget(self.state_lbl)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        self.solar_lbl = QLabel("SFI —  A —  K —  SN —")
        self.solar_lbl.setContentsMargins(0, 0, 8, 0)
        self.solar_lbl.setTextFormat(Qt.TextFormat.RichText)
        tb.addWidget(self.solar_lbl)
        self.solar = SolarFetcher(self)
        self.solar.updated.connect(self._on_solar)
        self.solar.failed.connect(self._on_solar_failed)
        self._solar_error = ""

        # ---------------- status bar
        self.count_lbl = QLabel()
        self.clock_lbl = QLabel()
        self.clock_lbl.setStyleSheet("color: #c0392b;")
        self.clock_lbl.hide()
        self.statusBar().addPermanentWidget(self.clock_lbl)
        self.server_lbl = QLabel()
        self.statusBar().addPermanentWidget(self.server_lbl)
        self.statusBar().addPermanentWidget(self.count_lbl)

        # ---------------- built-in telnet server for logging programs
        self.server = SpotServer(self._recent_filtered_spots, self)
        self.server.clients_changed.connect(lambda _n: self._update_server_label())
        self.server.error.connect(self._server_error)
        self._server_error_text = ""
        self._server_cfg: tuple[int, bool] | None = None

        # ---------------- tabs
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.spot_model = SpotTableModel(settings["max_spots"], self)
        self.proxy = SpotFilterProxy(self)
        self.proxy.setSourceModel(self.spot_model)
        self.spot_view = QTableView()
        self.spot_view.setModel(self.proxy)
        self.spot_view.setSortingEnabled(True)
        self.spot_view.sortByColumn(COL_TIME, Qt.SortOrder.DescendingOrder)
        setup_spot_view(self.spot_view)
        self.spot_view.doubleClicked.connect(lambda idx: self._lookup(self.proxy.spot_at(idx.row())))
        self.spot_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.spot_view.customContextMenuRequested.connect(self._spot_menu)
        self.proxy.rowsInserted.connect(self._update_counts)
        self.proxy.rowsRemoved.connect(self._update_counts)
        self.proxy.modelReset.connect(self._update_counts)
        self.proxy.layoutChanged.connect(self._update_counts)

        self.spots_page = QWidget()
        sp = QVBoxLayout(self.spots_page)
        sp.setContentsMargins(0, 4, 0, 0)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(240)
        self.search.setMaximumWidth(320)
        self.search.textChanged.connect(self._search_changed)
        self.send_spot_btn = QPushButton()
        self.send_spot_btn.clicked.connect(lambda: self._send_spot_dialog())
        row.addWidget(self.search)
        self.clear_spots_btn = QPushButton()
        self.clear_spots_btn.clicked.connect(self._clear_spots)
        row.addWidget(self.clear_spots_btn)
        row.addStretch(1)
        row.addWidget(self.send_spot_btn)
        sp.addLayout(row)
        sp.addWidget(self.spot_view)

        countries = self.db.country_names
        self.alarm_tab = AlarmTab(countries)
        self.alarm_tab.set_entries(self.alarms.entries)
        self.alarm_tab.set_options(settings["alarm_sound"], settings["alarm_popup"])
        self.alarm_tab.entries_changed.connect(self._alarms_changed)
        self.alarm_tab.options_changed.connect(self._alarm_options)
        self.alarm_tab.spot_activated.connect(self._lookup)
        self.alarm_tab.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.alarm_tab.view.customContextMenuRequested.connect(self._alarm_spot_menu)

        self.console = ConsoleTab()
        self.console.command.connect(self.client.send)

        self.clusters_tab = ClustersTab(config_dir() / "clusters.json", settings["custom_clusters"])
        self.clusters_tab.connect_requested.connect(self._connect_to_node)
        self.clusters_tab.custom_changed.connect(lambda lst: self._set("custom_clusters", lst))

        self.tabs.addTab(self.spots_page, "")
        self.tabs.addTab(self.alarm_tab, "")
        self.tabs.addTab(self.console, "")
        self.tabs.addTab(self.clusters_tab, "")
        self.tabs.currentChanged.connect(self._tab_changed)

        # ---------------- filter dock
        self.filter_panel = FilterPanel(countries)
        self.filter_panel.set_presets(settings["filter_presets"])
        self.filter_panel.filter_changed.connect(self._filter_changed)
        self.filter_panel.presets_changed.connect(lambda p: self._set("filter_presets", p))
        self.filter_dock = QDockWidget()
        self.filter_dock.setObjectName("filter_dock")
        self.filter_dock.setWidget(self.filter_panel)
        self.filter_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable | QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.filter_dock)
        self.filter_panel.set_filter(SpotFilter.from_dict(settings["filter"]))

        # ---------------- notifications
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.windowIcon(), self)
            self.tray.activated.connect(lambda *_: (self.showNormal(), self.activateWindow()))
            self.tray.show()
        self.sound = None
        if QSoundEffect is not None:
            self.sound = QSoundEffect(self)
            self.sound.setSource(QUrl.fromLocalFile(str(DATA_DIR / "alarm.wav")))
            self.sound.setVolume(0.8)

        self._nam = QNetworkAccessManager(self)
        self._build_menu()
        translator.language_changed.connect(self.retranslate)
        self.retranslate()
        self._on_state(STATE_DISCONNECTED)
        self._apply_server_settings()
        self._apply_age_settings()
        QTimer.singleShot(1000, self.solar.start)

        # spot aging: remove / grey out old spots once a minute
        self.age_timer = QTimer(self)
        self.age_timer.setInterval(60_000)
        self.age_timer.timeout.connect(self._age_tick)
        self.age_timer.start()

        # new version check and cty.dat freshness
        self.updates = UpdateChecker(self)
        self.updates.update_available.connect(self._update_available)
        self.updates.up_to_date.connect(self._up_to_date)
        self.updates.failed.connect(self._update_check_failed)
        self._manual_update_check = False
        self.update_lbl = QLabel()
        self.update_lbl.setOpenExternalLinks(True)
        self.update_lbl.hide()
        self.statusBar().addWidget(self.update_lbl)
        self._last_cty_attempt = 0.0
        QTimer.singleShot(3000, self._periodic_checks)
        # the program may stay open for weeks: repeat the daily checks every hour
        self.daily_timer = QTimer(self)
        self.daily_timer.setInterval(3600_000)
        self.daily_timer.timeout.connect(self._periodic_checks)
        self.daily_timer.start()
        if settings.load_error:
            QTimer.singleShot(500, lambda: QMessageBox.warning(
                self, tr("Settings"),
                tr("The settings file was damaged and has been reset. A copy was kept:\n{msg}",
                   msg=settings.load_error)))

        if settings["geometry"]:
            self.restoreGeometry(QByteArray.fromBase64(settings["geometry"].encode()))
        if settings["window_state"]:
            self.restoreState(QByteArray.fromBase64(settings["window_state"].encode()), self.STATE_VERSION)

        age = self.clusters_tab.cache_age_seconds()
        if age is None or age > CLUSTER_LIST_MAX_AGE:
            QTimer.singleShot(500, self.clusters_tab.refresh)
        if settings["auto_connect"] and settings["callsign"]:
            QTimer.singleShot(300, self._toggle_connect)
        elif not settings["callsign"]:
            QTimer.singleShot(300, self._open_settings)

    # ================================================================ UI setup
    def _build_menu(self) -> None:
        mb = self.menuBar()
        self.file_menu = mb.addMenu("")
        self.act_settings = self.file_menu.addAction("", self._open_settings)
        self.act_cty = self.file_menu.addAction("", self._update_cty)
        self.file_menu.addSeparator()
        self.act_quit = self.file_menu.addAction("", self.close)
        self.act_quit.setShortcut("Ctrl+Q")

        self.view_menu = mb.addMenu("")
        self.view_menu.addAction(self.filter_dock.toggleViewAction())
        self.view_menu.addSeparator()
        self.act_clear_all = self.view_menu.addAction("", self._clear_all)
        self.act_clear_all.setShortcut("Ctrl+L")

        self.lang_menu = mb.addMenu("")
        group = QActionGroup(self)
        for code, name in LANGUAGES.items():
            a = QAction(name, self, checkable=True)
            a.setChecked(code == translator.lang)
            a.triggered.connect(lambda _=False, c=code: self._set_language(c))
            group.addAction(a)
            self.lang_menu.addAction(a)
        self.help_menu = mb.addMenu("")
        self.act_check_updates = self.help_menu.addAction("", self._manual_update)
        self.act_open_folder = self.help_menu.addAction(
            "", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(config_dir()))))
        self.help_menu.addSeparator()
        self.act_about = self.help_menu.addAction("", self._about)

    def retranslate(self, *_):
        self.setWindowTitle(f"DX Cluster Client {__version__}")
        self.cluster_lbl.setText(tr("Cluster:") + " ")
        self.tabs.setTabText(0, tr("Spots"))
        self._update_alarm_tab_title()
        self.tabs.setTabText(2, tr("Console"))
        self.tabs.setTabText(3, tr("Clusters"))
        self.filter_dock.setWindowTitle(tr("Filters"))
        self.file_menu.setTitle(tr("File"))
        self.view_menu.setTitle(tr("View"))
        self.act_clear_all.setText(tr("Clear all spots and Alarm matches"))
        self.clear_spots_btn.setText(tr("Clear"))
        self.clear_spots_btn.setToolTip(tr("Remove all spots from the table (Alarm matches are kept)"))
        self.act_settings.setText(tr("Settings..."))
        self.act_cty.setText(tr("Update cty.dat"))
        self.act_quit.setText(tr("Quit"))
        self.lang_menu.setTitle(tr("Language"))
        self.help_menu.setTitle(tr("Help"))
        self.act_about.setText(tr("About"))
        self.act_check_updates.setText(tr("Check for updates"))
        self.act_open_folder.setText(tr("Open settings and log folder"))
        self.search.setPlaceholderText(tr("Search callsign or country..."))
        self.send_spot_btn.setText(tr("Send spot..."))
        self.spot_model.retranslate()
        self.filter_panel.retranslate()
        self.alarm_tab.retranslate()
        self.console.retranslate()
        self.clusters_tab.retranslate()
        self._on_state(self.client.state)
        self._update_counts()
        self._update_server_label()
        self._update_solar_label()

    # ================================================================ settings
    def _set(self, key, value) -> None:
        self.s[key] = value
        self.s.save()

    def _set_language(self, code: str) -> None:
        self._set("language", code)
        translator.set_language(code)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.s, self)
        if dlg.exec():
            dlg.apply()
            self.s.save()
            self.spot_model.set_max_rows(self.s["max_spots"])
            self.alarms.repeat_minutes = self.s["alarm_repeat_minutes"]
            self.client.auto_reconnect = self.s["auto_reconnect"]
            self._apply_server_settings()
            self._apply_age_settings()
            self._set_home(self.s["locator"])
            translator.set_language(self.s["language"])
            for a in self.lang_menu.actions():
                a.setChecked(a.text() == LANGUAGES.get(self.s["language"]))

    def _about(self) -> None:
        QMessageBox.about(
            self, tr("About"),
            f"<b>DX Cluster Client {__version__}</b><br>{tr('DX cluster client for Linux and Windows.')}"
            "<br><br>Cluster list: <a href='https://clusters.ra3co.com/'>clusters.ra3co.com</a>"
            "<br>Country data: <a href='https://www.country-files.com/'>country-files.com</a> (cty.dat)",
        )

    # ================================================================ connection
    def _toggle_connect(self) -> None:
        if self.client.state != STATE_DISCONNECTED:
            self.client.disconnect_from()
            return
        if not self.s["callsign"]:
            QMessageBox.warning(self, tr("Settings"), tr("Set your callsign in Settings first."))
            self._open_settings()
            if not self.s["callsign"]:
                return
        addr = parse_address(self.cluster_combo.currentText())
        if not addr:
            QMessageBox.warning(self, tr("Cluster:"), tr("Invalid cluster address. Use host:port."))
            return
        host, port = addr
        text = f"{host}:{port}"
        hist = [text] + [h for h in self.s["cluster_history"] if h != text]
        self.s["cluster_history"] = hist[:15]
        self.s["cluster"] = text
        self.s.save()
        self.cluster_combo.blockSignals(True)
        self.cluster_combo.clear()
        self.cluster_combo.addItems(self.s["cluster_history"])
        self.cluster_combo.setCurrentText(text)
        self.cluster_combo.blockSignals(False)

        self.client.callsign = self.s["callsign"]
        self.client.password = self.s["password"]
        self.client.login_commands = list(self.s["login_commands"])
        self.client.auto_reconnect = self.s["auto_reconnect"]
        self.console.append(f"*** {text}")
        self.client.connect_to(host, port)

    def _connect_to_node(self, host: str, port: int) -> None:
        if self.client.state != STATE_DISCONNECTED:
            self.client.disconnect_from()
        self.cluster_combo.setCurrentText(f"{host}:{port}")
        self._toggle_connect()
        self.tabs.setCurrentIndex(0)

    def _on_state(self, state: str) -> None:
        self.state_lbl.setText(tr(state))
        color = {"connected": "#27ae60", "disconnected": "#c0392b"}.get(state, "#e67e22")
        self.state_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.connect_btn.setText(tr("Connect") if state == STATE_DISCONNECTED else tr("Disconnect"))
        self.cluster_combo.setEnabled(state == STATE_DISCONNECTED)
        self.send_spot_btn.setEnabled(state == STATE_CONNECTED)
        self.send_spot_btn.setToolTip("" if state == STATE_CONNECTED else tr("Connect to a cluster first."))

    # ================================================================ spots
    def _on_line(self, line: str) -> None:
        self.console.append(line)
        local = datetime.now(timezone.utc)
        spot = parse_spot(line, self.db, now=self.clock.now(local))
        if spot is None:
            return
        live = spot.raw.startswith("DX de ")
        if live:  # live spot: its HHMM is (almost) the current cluster time → calibrates the PC clock
            hhmm = spot.time.replace(":", "")
            self.clock.feed(hhmm, local)
            spot.when = nearest_datetime(hhmm, self.clock.now(local))
            self._update_clock_label()
        now = self.clock.now(local)
        if self.spot_model.has_exact(spot):
            return  # the same spot again (sh/dx repeated after a reconnect)
        age = spot.age_minutes(now)  # never negative: "future" spots count as current
        verdict = judge_spot(live=live, calibrated=self.clock.calibrated, age_min=age,
                             max_age_min=self.s["max_age_minutes"], fresh_min=self.s["fresh_minutes"])
        if verdict.drop:
            return  # e.g. hours-old spots from sh/dx: not worth showing
        fresh = verdict.fresh
        self._apply_geo(spot)
        entry = self.alarms.find(spot)
        spot.alarm = entry is not None
        dupe = self.s["dupe_minutes"]
        replaced = self.spot_model.add_spot(spot, dupe)
        # loggers get each station once per dupe window, and only fresh spots
        if fresh and replaced is None and self.server.listening and self._passes_filter(spot):
            self.server.send_spot(spot)
        if entry:
            self.alarm_tab.model.add_spot(spot, dupe)
            if fresh and self.alarms.should_notify(spot):
                self._notify(spot, entry)

    def _apply_geo(self, spot: Spot) -> None:
        e = spot.dx_entity
        if self.home and e:
            spot.bearing, spot.distance = bearing_distance(self.home[0], self.home[1], e.lat, e.lon)
        else:
            spot.bearing = spot.distance = None

    def _set_home(self, locator: str) -> None:
        home = locator_to_latlon(locator) if locator else None
        if home == self.home:
            return
        self.home = home
        for model in (self.spot_model, self.alarm_tab.model):
            for s in model.spots:
                self._apply_geo(s)
            model.refresh_alarm_flags()

    # ================================================================ aging
    def _apply_age_settings(self) -> None:
        self.spot_model.fade_minutes = self.s["max_age_minutes"] // 2
        self.alarm_tab.model.fade_minutes = self.s["alarm_max_age_hours"] * 60 // 2
        self._age_tick()

    def _age_tick(self) -> None:
        now = self.clock.now()
        # Age-based removal needs a calibrated clock; before that the PC clock may be hours off.
        if self.clock.calibrated and self.s["max_age_minutes"]:
            self.spot_model.remove_older_than(self.s["max_age_minutes"], now)
        if self.clock.calibrated and self.s["alarm_max_age_hours"]:
            self.alarm_tab.model.remove_older_than(self.s["alarm_max_age_hours"] * 60, now)
        self.spot_model.tick(now)
        self.alarm_tab.model.tick(now)
        self._update_counts()

    def _clear_spots(self) -> None:
        self.spot_model.clear()
        self._update_counts()

    def _clear_all(self) -> None:
        self.spot_model.clear()
        self.alarm_tab.model.clear()
        self.unread_alarms = 0
        self._update_alarm_tab_title()
        self._update_counts()

    def _update_clock_label(self) -> None:
        off = self.clock.offset_minutes
        if self.clock.clock_is_off:
            text = tr("PC clock is off by {n} min (corrected automatically)", n=f"{-off:+d}")
            if self.clock_lbl.text() != text:
                log.warning("PC clock differs from the cluster by %+d min", -off)
            self.clock_lbl.setText(text)
            self.clock_lbl.setToolTip(tr("Spot ages are computed with the cluster time. "
                                         "Please synchronise the computer clock and time zone."))
            self.clock_lbl.show()
        else:
            self.clock_lbl.hide()

    def _search_changed(self, text: str) -> None:
        self.proxy.set_search(text)
        self._update_counts()

    # ================================================================ sending spots
    def _send_spot_dialog(self, spot: Spot | None = None) -> None:
        if self.client.state != STATE_CONNECTED:
            return
        dlg = SendSpotDialog(spot.freq if spot else None, spot.dx if spot else "", self)
        if dlg.exec():
            cmd = dlg.command()
            if cmd:
                self.console.append(f">>> {cmd}")
                self.client.send(cmd)
                self.statusBar().showMessage(tr("Spot sent: {cmd} (the cluster reply is in the Console)", cmd=cmd), 10000)

    # ================================================================ telnet server
    def _passes_filter(self, spot: Spot) -> bool:
        f = self.proxy.spot_filter
        return f is None or f.match(spot)

    def _recent_filtered_spots(self, n: int) -> list[Spot]:
        out: list[Spot] = []
        for s in self.spot_model.spots:  # newest first
            if self._passes_filter(s):
                out.append(s)
                if len(out) >= n:
                    break
        return out

    def _apply_server_settings(self) -> None:
        self._server_error_text = ""
        port, lan = self.s["server_port"], self.s["server_allow_lan"]
        if not self.s["server_enabled"]:
            self.server.stop()
        elif not (self.server.listening and self._server_cfg == (port, lan)):
            self.server.start(port, lan)
        self._server_cfg = (port, lan)
        self._update_server_label()

    def _server_error(self, msg: str) -> None:
        self._server_error_text = msg
        self._update_server_label()
        self.statusBar().showMessage(tr("Telnet server error: {msg}", msg=msg), 10000)

    def _update_server_label(self) -> None:
        if self.server.listening:
            self.server_lbl.setText(tr("Telnet {addr}: {n} clients", addr=self.server.address,
                                       n=self.server.client_count))
            self.server_lbl.setStyleSheet("")
        elif self.s["server_enabled"] and self._server_error_text:
            self.server_lbl.setText(tr("Telnet: port {port} unavailable", port=self.s["server_port"]))
            self.server_lbl.setStyleSheet("color: #c0392b;")
        else:
            self.server_lbl.setText("")
        self.server_lbl.setToolTip(self._server_error_text)

    # ================================================================ solar indices
    def _on_solar(self, d: SolarData) -> None:
        self._solar_error = ""
        self._update_solar_label()

    def _on_solar_failed(self, msg: str) -> None:
        self._solar_error = msg
        self._update_solar_label()

    def _update_solar_label(self) -> None:
        d = self.solar.data
        if d is None:
            self.solar_lbl.setToolTip(tr("Solar data unavailable: {msg}", msg=self._solar_error)
                                      if self._solar_error else "")
            return

        def val(v, warn=None, bad=None):
            if v is None:
                return "—"
            text = f"{v:g}"
            color = "#c0392b" if bad is not None and v >= bad else "#e67e22" if warn is not None and v >= warn else ""
            return f"<b style='color:{color}'>{text}</b>" if color else f"<b>{text}</b>"

        self.solar_lbl.setText(
            f"SFI {val(d.sfi)}&nbsp;&nbsp; A {val(d.a, 16, 30)}&nbsp;&nbsp; "
            f"K {val(d.k, 4, 5)}&nbsp;&nbsp; SN {val(d.ssn)}"
        )
        fetched = d.fetched.strftime("%H:%M UTC") if d.fetched else "?"
        tip = tr("SFI — solar flux, A / K — geomagnetic indices, SN — sunspot number.") + "\n" + \
            tr("Source: {src}, data time: {upd}, fetched {at}. Updated hourly.", src=d.source,
               upd=d.updated or "?", at=fetched)
        if self._solar_error:
            tip += "\n" + tr("Last update failed: {msg}", msg=self._solar_error)
        self.solar_lbl.setToolTip(tip)

    def _notify(self, spot: Spot, entry: AlarmEntry) -> None:
        if self.tabs.currentWidget() is not self.alarm_tab:
            self.unread_alarms += 1
            self._update_alarm_tab_title()
        if self.s["alarm_sound"]:
            if self.sound is not None and self.sound.status() != QSoundEffect.Status.Error:
                self.sound.play()
            else:
                QApplication.beep()
        if self.s["alarm_popup"] and self.tray is not None:
            title = tr("ALARM: {dx} {freq} {band} {mode}", dx=spot.dx, freq=f"{spot.freq:.1f}",
                       band=spot.band or "", mode=mode_label(spot.mode))
            body = f"{spot.country}\n{spot.comment}\nde {spot.spotter} {spot.time}Z"
            if entry.note:
                body += f"\n{entry.note}"
            self.tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 10000)
        QApplication.alert(self)

    def _update_alarm_tab_title(self) -> None:
        text = tr("Alarm") + (f" ({self.unread_alarms})" if self.unread_alarms else "")
        self.tabs.setTabText(1, text)
        self.tabs.tabBar().setTabTextColor(
            1, Qt.GlobalColor.red if self.unread_alarms else self.tabs.tabBar().palette().windowText().color()
        )

    def _tab_changed(self, idx: int) -> None:
        if self.tabs.widget(idx) is self.alarm_tab and self.unread_alarms:
            self.unread_alarms = 0
            self._update_alarm_tab_title()

    def _update_counts(self, *_):
        self.count_lbl.setText(tr("Spots: {shown} / {total}", shown=self.proxy.rowCount(),
                                  total=self.spot_model.rowCount()))

    def _filter_changed(self, f: SpotFilter) -> None:
        self.proxy.set_filter(f)
        self._set("filter", f.to_dict())
        self._update_counts()

    def _alarms_changed(self, entries: list[AlarmEntry]) -> None:
        self.alarms.entries = entries
        self._set("alarms", [e.to_dict() for e in entries])
        for s in self.spot_model.spots:
            s.alarm = self.alarms.find(s) is not None
        self.spot_model.refresh_alarm_flags()

    def _alarm_options(self, sound: bool, popup: bool) -> None:
        self.s["alarm_sound"] = sound
        self.s["alarm_popup"] = popup
        self.s.save()

    # ================================================================ spot actions
    def _lookup(self, spot: Spot | None) -> None:
        if spot:
            base = max(spot.dx.split("/"), key=len)
            QDesktopServices.openUrl(QUrl(self.s["lookup_url"].replace("{call}", base)))

    def _spot_context(self, spot: Spot | None, global_pos) -> None:
        if not spot:
            return
        m = QMenu(self)
        m.addAction(tr("Open in QRZ.com"), lambda: self._lookup(spot))
        m.addAction(tr("Copy callsign"), lambda: QGuiApplication.clipboard().setText(spot.dx))
        a = m.addAction(tr("Send spot..."), lambda: self._send_spot_dialog(spot))
        a.setEnabled(self.client.state == STATE_CONNECTED)
        m.addSeparator()
        m.addAction(tr("Add to Alarm"), lambda: self._quick_alarm(AlarmEntry(spot.dx)))
        if spot.country:
            m.addAction(tr("Add country to Alarm"),
                        lambda: self._quick_alarm(AlarmEntry(spot.country, kind=KIND_COUNTRY)))
            m.addAction(tr("Exclude country") + f": {spot.country}",
                        lambda: self.filter_panel.exclude_country(spot.country))
        m.exec(global_pos)

    def _spot_menu(self, pos) -> None:
        idx = self.spot_view.indexAt(pos)
        if idx.isValid():
            self._spot_context(self.proxy.spot_at(idx.row()), self.spot_view.viewport().mapToGlobal(pos))

    def _alarm_spot_menu(self, pos) -> None:
        v = self.alarm_tab.view
        idx = v.indexAt(pos)
        if idx.isValid():
            self._spot_context(self.alarm_tab.model.spot_at(idx.row()), v.viewport().mapToGlobal(pos))

    def _quick_alarm(self, entry: AlarmEntry) -> None:
        self.alarm_tab.add_entry(entry)

    # ================================================================ cty.dat
    def _cty_outdated(self) -> bool:
        v = self.db.version
        return v is None or (datetime.now(timezone.utc).date() - v).days > CTY_MAX_AGE_DAYS

    def _update_cty(self, silent: bool = False) -> None:
        req = QNetworkRequest(QUrl(CTY_URL))
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "DXClusterClient")
        req.setTransferTimeout(30000)
        reply = self._nam.get(req)
        reply.finished.connect(lambda: self._cty_done(reply, silent))

    def _cty_done(self, reply: QNetworkReply, silent: bool = False) -> None:
        reply.deleteLater()

        def fail(msg: str) -> None:
            log.warning("cty.dat update failed: %s", msg)
            text = tr("cty.dat update failed: {msg}", msg=msg)
            if silent:
                self.statusBar().showMessage(text, 10000)
            else:
                QMessageBox.warning(self, "cty.dat", text)

        if reply.error() != QNetworkReply.NetworkError.NoError:
            fail(reply.errorString())
            return
        text = bytes(reply.readAll().data()).decode("latin-1")
        db = DxccDB()
        db.load_text(text)
        if len(db.entities) < 300:
            fail("invalid file")
            return
        try:
            atomic_write(config_dir() / "cty.dat", text, encoding="latin-1")
        except OSError as e:
            fail(str(e))
            return
        self.db = db
        ver = db.version.isoformat() if db.version else "?"
        log.info("cty.dat updated to %s", ver)
        msg = tr("cty.dat updated: {n} entities, version {ver}.", n=len(db.entities), ver=ver)
        if silent:
            self.statusBar().showMessage(msg, 10000)
        else:
            QMessageBox.information(self, "cty.dat", msg)

    # ================================================================ new versions
    def _periodic_checks(self) -> None:
        if self.s["check_updates"] and time.time() - self.s["last_update_check"] > UPDATE_CHECK_INTERVAL:
            self._auto_update_check()
        # one cty.dat attempt per day at most, even if the download keeps failing
        if (self.s["auto_update_cty"] and self._cty_outdated()
                and time.time() - self._last_cty_attempt > UPDATE_CHECK_INTERVAL):
            self._last_cty_attempt = time.time()
            self._update_cty(silent=True)

    def _auto_update_check(self) -> None:
        self._manual_update_check = False
        self._set("last_update_check", time.time())
        self.updates.check()

    def _manual_update(self) -> None:
        self._manual_update_check = True
        self.updates.check()

    def _update_available(self, version: str, url: str) -> None:
        log.info("new version available: %s", version)
        self.update_lbl.setText(f"<a href='{url}'>{tr('Version {v} is available', v=version)}</a>")
        self.update_lbl.show()
        if self._manual_update_check:
            QMessageBox.information(
                self, tr("Check for updates"),
                tr("Version {v} is available", v=version) + f": <a href='{url}'>{url}</a>")

    def _up_to_date(self) -> None:
        if self._manual_update_check:
            QMessageBox.information(self, tr("Check for updates"),
                                    tr("You have the latest version ({v}).", v=__version__))

    def _update_check_failed(self, msg: str) -> None:
        log.warning("update check failed: %s", msg)
        if self._manual_update_check:
            QMessageBox.warning(self, tr("Check for updates"),
                                tr("Could not check for updates: {msg}", msg=msg)
                                + f"<br><a href='{RELEASES_PAGE}'>{RELEASES_PAGE}</a>")

    # ================================================================ shutdown
    def closeEvent(self, e) -> None:
        self.s["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.s["window_state"] = bytes(self.saveState(self.STATE_VERSION).toBase64()).decode()
        self.s.save()
        self.client.disconnect_from()
        self.server.stop()
        if self.tray:
            self.tray.hide()
        super().closeEvent(e)
