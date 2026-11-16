"""Table model for spots + filtering proxy."""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

from ..core.filters import SpotFilter
from ..core.spot import Spot
from ..i18n import tr

COLUMNS = ["Time", "Freq", "DX", "Country", "Cont", "Band", "Mode", "Comment", "Spotter", "Sp. cont"]
COL_TIME, COL_FREQ, COL_DX, COL_COUNTRY, COL_CONT, COL_BAND, COL_MODE, COL_COMMENT, COL_SPOTTER, COL_SPCONT = range(10)

BAND_COLORS = {
    "160m": "#8e44ad", "80m": "#2c7fb8", "60m": "#16a085", "40m": "#27ae60",
    "30m": "#7f8c1a", "20m": "#d35400", "17m": "#c0392b", "15m": "#b03a7a",
    "12m": "#6c5ce7", "10m": "#0984e3", "6m": "#e17055",
}
ALARM_BG = QColor(255, 196, 0, 90)

SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class SpotTableModel(QAbstractTableModel):
    def __init__(self, max_rows: int = 2000, parent=None) -> None:
        super().__init__(parent)
        self.spots: list[Spot] = []  # newest first
        self.max_rows = max_rows
        self._bold = QFont()
        self._bold.setBold(True)

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.spots)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return tr(COLUMNS[section])
        return None

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        s = self.spots[index.row()]
        c = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if c == COL_TIME:
                return s.time
            if c == COL_FREQ:
                return f"{s.freq:.1f}"
            if c == COL_DX:
                return s.dx
            if c == COL_COUNTRY:
                return s.country
            if c == COL_CONT:
                return s.continent
            if c == COL_BAND:
                return s.band or ""
            if c == COL_MODE:
                return tr(s.mode)
            if c == COL_COMMENT:
                return s.comment
            if c == COL_SPOTTER:
                return s.spotter
            if c == COL_SPCONT:
                return s.spotter_continent
        elif role == SORT_ROLE:
            if c == COL_TIME:
                return s.received.timestamp()
            if c == COL_FREQ:
                return s.freq
            return self.data(index, Qt.ItemDataRole.DisplayRole)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if c == COL_FREQ:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        elif role == Qt.ItemDataRole.ForegroundRole:
            if c in (COL_BAND, COL_FREQ) and s.band in BAND_COLORS:
                return QColor(BAND_COLORS[s.band])
        elif role == Qt.ItemDataRole.BackgroundRole:
            if s.alarm:
                return ALARM_BG
        elif role == Qt.ItemDataRole.FontRole:
            if c == COL_DX or s.alarm and c == COL_FREQ:
                return self._bold
        elif role == Qt.ItemDataRole.ToolTipRole:
            if c in (COL_DX, COL_COUNTRY) and s.dx_entity:
                e = s.dx_entity
                return f"{e.name} ({e.prefix}) — {e.continent}, CQ {e.cq}, ITU {e.itu}"
            if c == COL_COMMENT:
                return s.comment
        return None

    def add_spot(self, spot: Spot) -> None:
        self.beginInsertRows(QModelIndex(), 0, 0)
        self.spots.insert(0, spot)
        self.endInsertRows()
        if len(self.spots) > self.max_rows:
            first = self.max_rows
            self.beginRemoveRows(QModelIndex(), first, len(self.spots) - 1)
            del self.spots[first:]
            self.endRemoveRows()

    def set_max_rows(self, n: int) -> None:
        self.max_rows = max(100, n)
        if len(self.spots) > self.max_rows:
            self.beginRemoveRows(QModelIndex(), self.max_rows, len(self.spots) - 1)
            del self.spots[self.max_rows:]
            self.endRemoveRows()

    def clear(self) -> None:
        self.beginResetModel()
        self.spots.clear()
        self.endResetModel()

    def spot_at(self, row: int) -> Spot | None:
        return self.spots[row] if 0 <= row < len(self.spots) else None

    def refresh_alarm_flags(self) -> None:
        if self.spots:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.spots) - 1, len(COLUMNS) - 1))

    def retranslate(self) -> None:
        self.headerDataChanged.emit(Qt.Orientation.Horizontal, 0, len(COLUMNS) - 1)
        self.refresh_alarm_flags()


class SpotFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.spot_filter: SpotFilter | None = None
        self.setSortRole(SORT_ROLE)
        self.setDynamicSortFilter(True)

    def set_filter(self, f: SpotFilter | None) -> None:
        if hasattr(self, "beginFilterChange"):  # Qt >= 6.9
            self.beginFilterChange()
            self.spot_filter = f
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        else:
            self.spot_filter = f
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if self.spot_filter is None:
            return True
        spot = self.sourceModel().spot_at(source_row)
        return spot is not None and self.spot_filter.match(spot)

    def spot_at(self, proxy_row: int) -> Spot | None:
        src = self.mapToSource(self.index(proxy_row, 0))
        return self.sourceModel().spot_at(src.row())


# Compact default widths; the Comment column takes the remaining space.
_COL_WIDTHS = {COL_TIME: 46, COL_FREQ: 72, COL_DX: 92, COL_COUNTRY: 135, COL_CONT: 40,
               COL_BAND: 50, COL_MODE: 62, COL_SPOTTER: 85, COL_SPCONT: 58}


def setup_spot_view(view: QTableView) -> None:
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.setAlternatingRowColors(True)
    view.setWordWrap(False)
    view.verticalHeader().hide()
    view.verticalHeader().setDefaultSectionSize(20)
    h = view.horizontalHeader()
    h.setStretchLastSection(False)
    h.setMinimumSectionSize(30)
    h.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    for col, w in _COL_WIDTHS.items():
        view.setColumnWidth(col, w)
    h.setSectionResizeMode(COL_COMMENT, QHeaderView.ResizeMode.Stretch)
