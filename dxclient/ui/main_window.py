"""Main application window."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QGuiApplication, QIcon
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDockWidget, QLabel, QMainWindow, QMenu, QMessageBox,
    QPushButton, QSystemTrayIcon, QTableView, QTabWidget, QToolBar,
)

from .. import __version__
from ..core.alarms import KIND_COUNTRY, AlarmEntry, AlarmList
from ..core.cluster_list import parse_address
from ..core.dxcc import DxccDB
from ..core.filters import SpotFilter
from ..core.settings import Settings, config_dir
from ..core.spot import Spot, parse_spot
from ..core.telnet_client import STATE_CONNECTED, STATE_DISCONNECTED, ClusterClient
from ..i18n import LANGUAGES, tr, translator
from .alarm_tab import AlarmTab
from .clusters_tab import ClustersTab
from .console_tab import ConsoleTab
from .filter_panel import FilterPanel
from .settings_dialog import SettingsDialog
from .spot_model import COL_TIME, SpotFilterProxy, SpotTableModel, setup_spot_view

try:
    from PySide6.QtMultimedia import QSoundEffect
except ImportError:  # pragma: no cover
    QSoundEffect = None

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CTY_URL = "https://www.country-files.com/cty/cty.dat"
CLUSTER_LIST_MAX_AGE = 3600


def load_dxcc() -> DxccDB:
    user = config_dir() / "cty.dat"
    for p in (user, DATA_DIR / "cty.dat"):
        if p.exists():
            try:
                db = DxccDB.from_file(p)
                if len(db.entities) > 100:
                    return db
            except OSError:
                pass
    return DxccDB()


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

        # ---------------- status bar
        self.count_lbl = QLabel()
        self.statusBar().addPermanentWidget(self.count_lbl)

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

        self.tabs.addTab(self.spot_view, "")
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

        self.lang_menu = mb.addMenu("")
        group = QActionGroup(self)
        for code, name in LANGUAGES.items():
            a = QAction(name, self, checkable=True)
            a.setChecked(code == translator.lang)
            a.triggered.connect(lambda _=False, c=code: self._set_language(c))
            group.addAction(a)
            self.lang_menu.addAction(a)
        self.help_menu = mb.addMenu("")
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
        self.view_menu.setTitle(tr("Filters"))
        self.act_settings.setText(tr("Settings..."))
        self.act_cty.setText(tr("Update cty.dat"))
        self.act_quit.setText(tr("Quit"))
        self.lang_menu.setTitle(tr("Language"))
        self.help_menu.setTitle(tr("Help"))
        self.act_about.setText(tr("About"))
        self.spot_model.retranslate()
        self.filter_panel.retranslate()
        self.alarm_tab.retranslate()
        self.console.retranslate()
        self.clusters_tab.retranslate()
        self._on_state(self.client.state)
        self._update_counts()

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

    # ================================================================ spots
    def _on_line(self, line: str) -> None:
        self.console.append(line)
        spot = parse_spot(line, self.db)
        if spot is None:
            return
        entry = self.alarms.find(spot)
        if entry:
            spot.alarm = True
        self.spot_model.add_spot(spot)
        if entry:
            self.alarm_tab.model.add_spot(spot)
            if self.alarms.should_notify(spot):
                self._notify(spot, entry)

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
                       band=spot.band or "", mode=tr(spot.mode))
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
    def _update_cty(self) -> None:
        req = QNetworkRequest(QUrl(CTY_URL))
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "DXClusterClient")
        req.setTransferTimeout(30000)
        reply = self._nam.get(req)
        reply.finished.connect(lambda: self._cty_done(reply))

    def _cty_done(self, reply: QNetworkReply) -> None:
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            QMessageBox.warning(self, "cty.dat", tr("cty.dat update failed: {msg}", msg=reply.errorString()))
            return
        text = bytes(reply.readAll().data()).decode("latin-1")
        db = DxccDB()
        db.load_text(text)
        if len(db.entities) < 300:
            QMessageBox.warning(self, "cty.dat", tr("cty.dat update failed: {msg}", msg="invalid file"))
            return
        (config_dir() / "cty.dat").write_text(text, encoding="latin-1")
        self.db = db
        QMessageBox.information(self, "cty.dat", tr("cty.dat updated: {n} entities.", n=len(db.entities)))

    # ================================================================ shutdown
    def closeEvent(self, e) -> None:
        self.s["geometry"] = bytes(self.saveGeometry().toBase64()).decode()
        self.s["window_state"] = bytes(self.saveState(self.STATE_VERSION).toBase64()).decode()
        self.s.save()
        self.client.disconnect_from()
        if self.tray:
            self.tray.hide()
        super().closeEvent(e)
