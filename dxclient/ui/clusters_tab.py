"""Clusters tab: node list from clusters.ra3co.com + user-defined nodes."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, QUrl, Signal
from PySide6.QtGui import QColor
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox, QTableView, QVBoxLayout, QWidget,
)

from ..core.cluster_list import CLUSTERS_URL, ClusterNode, load_cache, parse_clusters_json
from ..i18n import tr
from .qt_compat import change_filter

COLS = ["Name", "Address", "Region", "Type", "Status", "★", "Spots/min", "Users", "Uptime 7d"]
SORT_ROLE = Qt.ItemDataRole.UserRole + 1
UP_COLOR = QColor("#27ae60")
DOWN_COLOR = QColor("#c0392b")


class ClusterModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.nodes: list[ClusterNode] = []

    def set_nodes(self, nodes: list[ClusterNode]) -> None:
        self.beginResetModel()
        self.nodes = nodes
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.nodes)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return tr(COLS[section])
        return None

    def _status(self, n: ClusterNode) -> str:
        if n.custom:
            return tr("custom")
        return tr("up") if n.up else tr("down")

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        n = self.nodes[index.row()]
        c = index.column()
        if role in (Qt.ItemDataRole.DisplayRole, SORT_ROLE):
            raw = role == SORT_ROLE
            if c == 0:
                return n.name
            if c == 1:
                return n.address
            if c == 2:
                return n.region
            if c == 3:
                return tr(n.kind)
            if c == 4:
                return self._status(n)
            if c == 5:
                return (n.stars or 0.0) if raw else (f"{n.stars:.1f}" if n.stars is not None else "")
            if c == 6:
                return (n.spots_per_min or 0.0) if raw else (f"{n.spots_per_min:.0f}" if n.spots_per_min is not None else "")
            if c == 7:
                return (n.users or 0) if raw else ("" if n.users is None else str(n.users))
            if c == 8:
                return (n.uptime_7d or 0.0) if raw else ("" if n.uptime_7d is None else f"{n.uptime_7d * 100:.0f}%")
        elif role == Qt.ItemDataRole.ForegroundRole and c == 4 and not n.custom:
            return UP_COLOR if n.up else DOWN_COLOR
        elif role == Qt.ItemDataRole.TextAlignmentRole and c >= 5:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def retranslate(self) -> None:
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, len(COLS) - 1)
        if self.nodes:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.nodes) - 1, len(COLS) - 1))


class ClusterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.only_up = True
        self.region = ""
        self.text = ""
        self.setSortRole(SORT_ROLE)

    def update(self, only_up: bool, region: str, text: str) -> None:
        def apply() -> None:
            self.only_up, self.region, self.text = only_up, region, text.lower().strip()

        change_filter(self, apply)

    def filterAcceptsRow(self, row, parent) -> bool:
        n: ClusterNode = self.sourceModel().nodes[row]
        if n.custom:
            return True
        if self.only_up and not n.up:
            return False
        if self.region and n.region != self.region:
            return False
        if self.text and self.text not in n.name.lower() and self.text not in n.address.lower():
            return False
        return True


class AddClusterDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Add cluster"))
        f = QFormLayout(self)
        self.name = QLineEdit()
        self.host = QLineEdit()
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(7300)
        f.addRow(tr("Name:"), self.name)
        f.addRow(tr("Host:"), self.host)
        f.addRow(tr("Port:"), self.port)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(lambda: self.host.text().strip() and self.accept())
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def node(self) -> ClusterNode:
        host = self.host.text().strip()
        return ClusterNode(self.name.text().strip() or host, host, self.port.value(), custom=True)


class ClustersTab(QWidget):
    connect_requested = Signal(str, int)
    custom_changed = Signal(list)  # list[dict]

    def __init__(self, cache_path: Path, custom: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.cache_path = cache_path
        self.custom = [
            ClusterNode(d.get("name", d["host"]), d["host"], int(d["port"]), custom=True)
            for d in custom
            if d.get("host")
        ]
        self.remote: list[ClusterNode] = []
        self._nam = QNetworkAccessManager(self)
        self._reply: QNetworkReply | None = None

        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.only_up = QCheckBox()
        self.only_up.setChecked(True)
        self.region = QComboBox()
        self.refresh_btn = QPushButton()
        self.add_btn = QPushButton()
        self.rm_btn = QPushButton()
        self.connect_btn = QPushButton()
        for w in (self.search, self.only_up, self.region):
            bar.addWidget(w)
        bar.addStretch(1)
        for w in (self.refresh_btn, self.add_btn, self.rm_btn, self.connect_btn):
            bar.addWidget(w)
        lay.addLayout(bar)

        self.model = ClusterModel(self)
        self.proxy = ClusterProxy(self)
        self.proxy.setSourceModel(self.model)
        self.view = QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(5, Qt.SortOrder.DescendingOrder)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.verticalHeader().hide()
        self.view.verticalHeader().setDefaultSectionSize(22)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.view.doubleClicked.connect(self._connect_selected)
        lay.addWidget(self.view)
        self.status = QLabel()
        lay.addWidget(self.status)

        self.search.textChanged.connect(self._refilter)
        self.only_up.toggled.connect(self._refilter)
        self.region.currentIndexChanged.connect(self._refilter)
        self.refresh_btn.clicked.connect(self.refresh)
        self.add_btn.clicked.connect(self._add_custom)
        self.rm_btn.clicked.connect(self._remove_custom)
        self.connect_btn.clicked.connect(self._connect_selected)

        self.remote = load_cache(cache_path)
        self._rebuild()
        self.retranslate()

    # ---------------------------------------------------------------- i18n
    def retranslate(self) -> None:
        self.search.setPlaceholderText(tr("Search..."))
        self.only_up.setText(tr("Only working"))
        self.refresh_btn.setText(tr("Refresh list"))
        self.add_btn.setText(tr("Add custom..."))
        self.rm_btn.setText(tr("Remove custom"))
        self.connect_btn.setText(tr("Connect"))
        if self.region.count():
            self.region.setItemText(0, tr("All regions"))
        self.model.retranslate()
        self._update_status()

    # ---------------------------------------------------------------- data
    def _rebuild(self) -> None:
        self.model.set_nodes(self.custom + self.remote)
        current = self.region.currentData()
        self.region.blockSignals(True)
        self.region.clear()
        self.region.addItem(tr("All regions"), "")
        for r in sorted({n.region for n in self.remote if n.region}):
            self.region.addItem(r, r)
        i = self.region.findData(current) if current else 0
        self.region.setCurrentIndex(max(i, 0))
        self.region.blockSignals(False)
        self._refilter()

    def _refilter(self, *_):
        self.proxy.update(self.only_up.isChecked(), self.region.currentData() or "", self.search.text())

    def _update_status(self, error: str | None = None) -> None:
        if error:
            self.status.setText(tr("Failed to load cluster list: {msg}", msg=error))
        elif self._reply is not None:
            self.status.setText(tr("Loading cluster list..."))
        elif self.remote:
            try:
                when = datetime.fromtimestamp(self.cache_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            except OSError:
                when = "?"
            up = sum(1 for n in self.remote if n.up)
            self.status.setText(tr("Loaded {n} nodes ({up} up), updated {when}.", n=len(self.remote), up=up, when=when))
        else:
            self.status.setText("")

    def cache_age_seconds(self) -> float | None:
        try:
            return datetime.now().timestamp() - self.cache_path.stat().st_mtime
        except OSError:
            return None

    def refresh(self) -> None:
        if self._reply is not None:
            return
        req = QNetworkRequest(QUrl(CLUSTERS_URL))
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "DXClusterClient")
        req.setTransferTimeout(20000)
        self._reply = self._nam.get(req)
        self._reply.finished.connect(self._on_reply)
        self._update_status()

    def _on_reply(self) -> None:
        reply, self._reply = self._reply, None
        if reply is None:
            return
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self._update_status(reply.errorString())
            return
        data = bytes(reply.readAll().data())
        try:
            nodes = parse_clusters_json(data)
        except ValueError as e:
            self._update_status(str(e))
            return
        if not nodes:
            self._update_status("empty list")
            return
        try:
            self.cache_path.write_bytes(data)
        except OSError:
            pass
        self.remote = nodes
        self._rebuild()
        self._update_status()

    # ---------------------------------------------------------------- actions
    def _selected(self) -> ClusterNode | None:
        idx = self.view.currentIndex()
        if not idx.isValid():
            return None
        return self.model.nodes[self.proxy.mapToSource(idx).row()]

    def _connect_selected(self, *_):
        n = self._selected()
        if n:
            self.connect_requested.emit(n.host, n.port)

    def _emit_custom(self) -> None:
        self.custom_changed.emit([{"name": n.name, "host": n.host, "port": n.port} for n in self.custom])

    def _add_custom(self) -> None:
        dlg = AddClusterDialog(self)
        if dlg.exec():
            self.custom.append(dlg.node())
            self._rebuild()
            self._emit_custom()

    def _remove_custom(self) -> None:
        n = self._selected()
        if n and n.custom:
            self.custom.remove(n)
            self._rebuild()
            self._emit_custom()
