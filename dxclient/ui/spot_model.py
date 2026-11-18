"""Table model for spots + filtering proxy."""
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableView

from ..core.bands import mode_label
from ..core.filters import SpotFilter
from ..core.spot import Spot
from ..i18n import tr
from .qt_compat import change_filter

COLUMNS = ["Time", "Freq", "DX", "Country", "Cont", "Az", "km", "Band", "Mode", "Comment", "Spotter", "Sp. cont"]
(COL_TIME, COL_FREQ, COL_DX, COL_COUNTRY, COL_CONT, COL_AZ, COL_DIST, COL_BAND, COL_MODE, COL_COMMENT,
 COL_SPOTTER, COL_SPCONT) = range(len(COLUMNS))

BAND_COLORS = {
    "160m": "#8e44ad", "80m": "#2c7fb8", "60m": "#16a085", "40m": "#27ae60",
    "30m": "#7f8c1a", "20m": "#d35400", "17m": "#c0392b", "15m": "#b03a7a",
    "12m": "#6c5ce7", "10m": "#0984e3", "6m": "#e17055",
}
ALARM_BG = QColor(255, 196, 0, 90)
OLD_FG = QColor(128, 128, 128)

SORT_ROLE = Qt.ItemDataRole.UserRole + 1
MIN_ROWS = 100


class SpotTableModel(QAbstractTableModel):
    def __init__(self, max_rows: int = 2000, parent=None) -> None:
        super().__init__(parent)
        self.spots: list[Spot] = []  # newest first; read-only for other modules
        self.max_rows = max(MIN_ROWS, int(max_rows))
        self.fade_minutes = 0  # spots older than this are shown greyed out (0 = never)
        self._now = datetime.now(timezone.utc)
        self._bold = QFont()
        self._bold.setBold(True)
        # Index callsign -> its spots, newest first. Keeps duplicate and exact-match lookups
        # proportional to the number of spots of one station, not to the whole table.
        self._by_call: dict[str, list[Spot]] = {}

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
            if c == COL_AZ:
                return "" if s.bearing is None else f"{s.bearing}°"
            if c == COL_DIST:
                return "" if s.distance is None else str(s.distance)
            if c == COL_BAND:
                return s.band or ""
            if c == COL_MODE:
                return mode_label(s.mode)
            if c == COL_COMMENT:
                return s.comment
            if c == COL_SPOTTER:
                return s.spotter
            if c == COL_SPCONT:
                return s.spotter_continent
        elif role == SORT_ROLE:
            if c == COL_TIME:
                return (s.when or s.received).timestamp()
            if c == COL_FREQ:
                return s.freq
            if c == COL_AZ:
                return -1 if s.bearing is None else s.bearing
            if c == COL_DIST:
                return -1 if s.distance is None else s.distance
            return self.data(index, Qt.ItemDataRole.DisplayRole)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if c in (COL_FREQ, COL_AZ, COL_DIST):
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        elif role == Qt.ItemDataRole.ForegroundRole:
            if self.fade_minutes and s.age_minutes(self._now) > self.fade_minutes:
                return OLD_FG
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
                tip = f"{e.name} ({e.prefix}) — {e.continent}, CQ {e.cq}, ITU {e.itu}"
                if s.count > 1:
                    tip += "\n" + tr("Spotted {n} times", n=s.count)
                return tip
            if c == COL_COMMENT:
                return s.comment
        return None

    def add_spot(self, spot: Spot, dupe_minutes: int = 0) -> Spot | None:
        """Insert a spot on top. With dupe_minutes > 0 a previous spot of the same station on the
        same band and mode within that window is replaced (its counter carried over); the replaced
        spot is returned, None otherwise."""
        old = self.find_dupe(spot, dupe_minutes) if dupe_minutes > 0 else None
        if old is not None:
            spot.count = old.count + 1
            row = next(i for i, x in enumerate(self.spots) if x is old)
            self._remove_rows([row])
        self._insert(spot)
        return old

    def has_exact(self, spot: Spot) -> bool:
        """The very same spot (call, frequency, time, spotter) is already in the table —
        e.g. sh/dx output repeated after a reconnect."""
        return any(
            s.when == spot.when and s.spotter == spot.spotter and abs(s.freq - spot.freq) < 0.05
            for s in self._by_call.get(spot.dx, ())
        )

    def find_dupe(self, spot: Spot, minutes: int) -> Spot | None:
        t = spot.when or spot.received
        for s in self._by_call.get(spot.dx, ()):
            if s.band == spot.band and s.mode == spot.mode:
                if abs((t - (s.when or s.received)).total_seconds()) <= minutes * 60:
                    return s
        return None

    def remove_older_than(self, minutes: int, now: datetime) -> int:
        """Drop spots older than `minutes`; returns how many were removed."""
        rows = [i for i, s in enumerate(self.spots) if s.age_minutes(now) > minutes]
        self._remove_rows(rows)
        return len(rows)

    def remove_where(self, keep) -> int:
        """Drop the spots for which `keep(spot)` is False; returns how many were removed."""
        rows = [i for i, s in enumerate(self.spots) if not keep(s)]
        self._remove_rows(rows)
        return len(rows)

    def tick(self, now: datetime | None = None) -> None:
        """Refresh age-dependent colours."""
        self._now = now or datetime.now(timezone.utc)
        if self.fade_minutes and self.spots:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self.spots) - 1, len(COLUMNS) - 1),
                                  [Qt.ItemDataRole.ForegroundRole])

    def _insert(self, spot: Spot) -> None:
        self.beginInsertRows(QModelIndex(), 0, 0)
        self.spots.insert(0, spot)
        self._by_call.setdefault(spot.dx, []).insert(0, spot)
        self.endInsertRows()
        if len(self.spots) > self.max_rows:
            self._remove_rows(list(range(self.max_rows, len(self.spots))))

    def _remove_rows(self, rows: list[int]) -> None:
        """Remove the given row numbers, emitting one signal per contiguous run of rows."""
        runs: list[tuple[int, int]] = []
        for r in sorted(set(rows)):
            if runs and r == runs[-1][1] + 1:
                runs[-1] = (runs[-1][0], r)
            else:
                runs.append((r, r))
        for lo, hi in reversed(runs):  # from the bottom, so earlier row numbers stay valid
            self.beginRemoveRows(QModelIndex(), lo, hi)
            for s in self.spots[lo:hi + 1]:
                self._unindex(s)
            del self.spots[lo:hi + 1]
            self.endRemoveRows()

    def _unindex(self, spot: Spot) -> None:
        lst = self._by_call.get(spot.dx)
        if lst is None:
            return
        lst[:] = [x for x in lst if x is not spot]
        if not lst:
            del self._by_call[spot.dx]

    def set_max_rows(self, n: int) -> None:
        self.max_rows = max(MIN_ROWS, int(n))
        if len(self.spots) > self.max_rows:
            self._remove_rows(list(range(self.max_rows, len(self.spots))))

    def clear(self) -> None:
        self.beginResetModel()
        self.spots.clear()
        self._by_call.clear()
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
        self.search = ""  # substring of callsign or country
        self.setSortRole(SORT_ROLE)
        self.setDynamicSortFilter(True)

    def set_filter(self, f: SpotFilter | None) -> None:
        def apply() -> None:
            self.spot_filter = f

        change_filter(self, apply)

    def set_search(self, text: str) -> None:
        def apply() -> None:
            self.search = text.strip().upper()

        change_filter(self, apply)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        spot = self.sourceModel().spot_at(source_row)
        if spot is None:
            return False
        if self.search and self.search not in spot.dx and self.search not in spot.country.upper():
            return False
        return self.spot_filter is None or self.spot_filter.match(spot)

    def spot_at(self, proxy_row: int) -> Spot | None:
        src = self.mapToSource(self.index(proxy_row, 0))
        return self.sourceModel().spot_at(src.row())


# Compact default widths; the Comment column takes the remaining space.
_COL_WIDTHS = {COL_TIME: 58, COL_FREQ: 72, COL_DX: 92, COL_COUNTRY: 135, COL_CONT: 40, COL_AZ: 44,
               COL_DIST: 52, COL_BAND: 50, COL_MODE: 46, COL_SPOTTER: 85, COL_SPCONT: 52}


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
