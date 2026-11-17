"""Alarm tab (matching spots) and the separate watch-list window."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QCompleter, QDialog, QDialogButtonBox, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLineEdit, QMessageBox, QPushButton,
    QTableView, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..core.alarms import KIND_CALL, KIND_COUNTRY, AlarmEntry
from ..core.bands import BAND_NAMES, MODES, mode_label
from ..i18n import tr
from .spot_model import SpotTableModel, setup_spot_view


class _UpperValidator(QValidator):
    """Callsigns and masks are always uppercase: lowercase letters are not needed."""

    def validate(self, text: str, pos: int):
        return QValidator.State.Acceptable, text.upper(), pos


def _duplicate_entry(entries: list[AlarmEntry], pattern: str, kind: str,
                     exclude: AlarmEntry | None = None) -> AlarmEntry | None:
    """The first rule with the same kind and pattern (case-insensitive), if any."""
    key = pattern.strip().casefold()
    if not key:
        return None
    for e in entries:
        if e is exclude:
            continue
        if e.kind == kind and e.pattern.strip().casefold() == key:
            return e
    return None


def _warn_duplicate(parent, pattern: str) -> None:
    QMessageBox.warning(
        parent, tr("Alarm entry"),
        tr("This rule already exists in the watch list: {pattern}", pattern=pattern),
    )


class AlarmEntryDialog(QDialog):
    def __init__(self, entry: AlarmEntry | None, countries: list[str], parent=None,
                 existing: list[AlarmEntry] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Alarm entry"))
        self._original = entry  # the rule being edited: not a duplicate of itself
        self._existing = existing or []
        entry = entry or AlarmEntry("")
        form = QFormLayout(self)

        self.kind = QComboBox()
        self.kind.addItem(tr("Callsign"), KIND_CALL)
        self.kind.addItem(tr("Country"), KIND_COUNTRY)
        self.kind.setCurrentIndex(self.kind.findData(entry.kind))
        form.addRow(tr("Type"), self.kind)

        self._upper = _UpperValidator(self)
        initial = entry.pattern.upper() if entry.kind == KIND_CALL else entry.pattern
        self.pattern = QLineEdit(initial)
        self.pattern.setPlaceholderText(tr("Callsign or mask (* and ? allowed), e.g. 3Y0J, VP8*, */MM"))
        self._completer = QCompleter(countries, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        form.addRow(tr("Pattern"), self.pattern)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self._kind_changed()

        bands_box = QGroupBox(tr("Bands") + " — " + tr("Any band") + " = ∅")
        g = QGridLayout(bands_box)
        self.band_cb: dict[str, QCheckBox] = {}
        for i, b in enumerate(BAND_NAMES):
            cb = QCheckBox(b)
            cb.setChecked(b in entry.bands)
            self.band_cb[b] = cb
            g.addWidget(cb, i // 6, i % 6)
        form.addRow(bands_box)

        modes_box = QGroupBox(tr("Modes") + " — " + tr("Any mode") + " = ∅")
        h = QHBoxLayout(modes_box)
        self.mode_cb: dict[str, QCheckBox] = {}
        for m in MODES:
            cb = QCheckBox(mode_label(m))
            cb.setToolTip(tr(m))
            cb.setChecked(m in entry.modes)
            self.mode_cb[m] = cb
            h.addWidget(cb)
        form.addRow(modes_box)

        self.note = QLineEdit(entry.note)
        form.addRow(tr("Note"), self.note)
        self.enabled = QCheckBox(tr("Enabled"))
        self.enabled.setChecked(entry.enabled)
        form.addRow(self.enabled)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)
        self.resize(520, self.sizeHint().height())

    def _kind_changed(self) -> None:
        is_country = self.kind.currentData() == KIND_COUNTRY
        if is_country:
            self.pattern.setValidator(None)
            self.pattern.setCompleter(self._completer)
        else:
            self.pattern.setValidator(self._upper)
            self.pattern.setCompleter(None)
            text = self.pattern.text()
            if text != text.upper():
                self.pattern.setText(text.upper())

    def _accept(self) -> None:
        pattern = self.pattern.text().strip()
        if not pattern:
            return
        duplicate = _duplicate_entry(self._existing, pattern, self.kind.currentData(),
                                     exclude=self._original)
        if duplicate is not None:
            _warn_duplicate(self, duplicate.pattern)
            self.pattern.setFocus()
            self.pattern.selectAll()
            return
        self.accept()

    def entry(self) -> AlarmEntry:
        kind = self.kind.currentData()
        pat = self.pattern.text().strip()
        if kind == KIND_CALL:
            pat = pat.upper()
        return AlarmEntry(
            pattern=pat,
            kind=kind,
            bands={b for b, cb in self.band_cb.items() if cb.isChecked()},
            modes={m for m, cb in self.mode_cb.items() if cb.isChecked()},
            note=self.note.text().strip(),
            enabled=self.enabled.isChecked(),
        )


class WatchListDialog(QDialog):
    """Separate (non-modal) window for editing the alarm watch list."""

    entries_changed = Signal()

    COLS = ["On", "Pattern", "Type", "Bands", "Modes", "Note"]

    def __init__(self, entries: list[AlarmEntry], countries: list[str], parent=None) -> None:
        super().__init__(parent)
        self.entries = entries  # shared list, edited in place
        self.countries = countries
        self.resize(640, 380)
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(20)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionsClickable(True)
        header.setSortIndicatorShown(False)
        header.sectionClicked.connect(self._header_clicked)
        self.table.doubleClicked.connect(self._edit)
        self.table.itemChanged.connect(self._item_changed)
        lay.addWidget(self.table)
        row = QHBoxLayout()
        self.add_btn = QPushButton()
        self.add_btn.clicked.connect(lambda: self.add())
        self.edit_btn = QPushButton()
        self.edit_btn.clicked.connect(self._edit)
        self.rm_btn = QPushButton()
        self.rm_btn.clicked.connect(self._remove)
        self.sort_btn = QPushButton()
        self.sort_btn.clicked.connect(self._sort_by_name)
        self.close_btn = QPushButton()
        self.close_btn.clicked.connect(self.close)
        for w in (self.add_btn, self.edit_btn, self.rm_btn, self.sort_btn):
            row.addWidget(w)
        row.addStretch(1)
        row.addWidget(self.close_btn)
        lay.addLayout(row)
        self._sort_asc: bool | None = None
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("Watch list"))
        self.table.setHorizontalHeaderLabels([tr(c) for c in self.COLS])
        self.add_btn.setText(tr("Add..."))
        self.edit_btn.setText(tr("Edit..."))
        self.rm_btn.setText(tr("Remove"))
        self.close_btn.setText(tr("Close"))
        self._update_sort_btn()
        self.rebuild()

    def rebuild(self) -> None:
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.entries))
        for r, e in enumerate(self.entries):
            on = QTableWidgetItem()
            on.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            on.setCheckState(Qt.CheckState.Checked if e.enabled else Qt.CheckState.Unchecked)
            self.table.setItem(r, 0, on)
            vals = [
                e.pattern,
                tr("Callsign") if e.kind == KIND_CALL else tr("Country"),
                ", ".join(b for b in BAND_NAMES if b in e.bands) or tr("any"),
                ", ".join(mode_label(m) for m in MODES if m in e.modes) or tr("any"),
                e.note,
            ]
            for c, v in enumerate(vals, start=1):
                self.table.setItem(r, c, QTableWidgetItem(v))
        self.table.blockSignals(False)

    def _update_sort_btn(self) -> None:
        arrow = "" if self._sort_asc is None else (" ↑" if self._sort_asc else " ↓")
        self.sort_btn.setText(tr("Sort by name") + arrow)
        self.sort_btn.setToolTip(tr("Sort rules by name; click again to reverse the order"))

    def _sort_by_name(self) -> None:
        """Sort the rules by pattern (case-insensitively); repeated calls toggle the direction."""
        asc = not self._sort_asc if self._sort_asc is not None else True
        self._sort_asc = asc
        self.entries.sort(key=lambda e: (e.pattern.casefold(), e.kind), reverse=not asc)
        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(1, Qt.SortOrder.AscendingOrder if asc else Qt.SortOrder.DescendingOrder)
        self._update_sort_btn()
        self._changed()

    def _header_clicked(self, column: int) -> None:
        if column == 1:  # "Pattern"
            self._sort_by_name()

    def _changed(self) -> None:
        self.rebuild()
        self.entries_changed.emit()

    def _item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0 and 0 <= item.row() < len(self.entries):
            self.entries[item.row()].enabled = item.checkState() == Qt.CheckState.Checked
            self.entries_changed.emit()

    def add(self, preset: AlarmEntry | None = None) -> None:
        if preset is not None:  # quick-add from the spot menu: don't even open a duplicate
            duplicate = _duplicate_entry(self.entries, preset.pattern, preset.kind)
            if duplicate is not None:
                _warn_duplicate(self, duplicate.pattern)
                return
        dlg = AlarmEntryDialog(preset, self.countries, self, existing=self.entries)
        if dlg.exec():
            self.entries.append(dlg.entry())
            self._changed()

    def _edit(self, *_):
        r = self.table.currentRow()
        if 0 <= r < len(self.entries):
            dlg = AlarmEntryDialog(self.entries[r], self.countries, self, existing=self.entries)
            if dlg.exec():
                self.entries[r] = dlg.entry()
                self._changed()

    def _remove(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            del self.entries[r]
        if rows:
            self._changed()


class AlarmTab(QWidget):
    """Whole tab is the table of matching spots; the watch list opens in its own window."""

    entries_changed = Signal(list)  # list[AlarmEntry]
    options_changed = Signal(bool, bool)  # sound, popup
    spot_activated = Signal(object)

    def __init__(self, countries: list[str], parent=None) -> None:
        super().__init__(parent)
        self.countries = countries
        self.entries: list[AlarmEntry] = []
        self._dialog: WatchListDialog | None = None

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.watch_btn = QPushButton()
        self.watch_btn.clicked.connect(self.show_watch_list)
        self.add_btn = QPushButton()
        self.add_btn.clicked.connect(lambda: self.add_entry(None))
        self.sound_cb = QCheckBox()
        self.popup_cb = QCheckBox()
        for cb in (self.sound_cb, self.popup_cb):
            cb.toggled.connect(lambda _=None: self.options_changed.emit(self.sound_cb.isChecked(), self.popup_cb.isChecked()))
        self.clear_btn = QPushButton()
        row.addWidget(self.watch_btn)
        row.addWidget(self.add_btn)
        row.addStretch(1)
        row.addWidget(self.sound_cb)
        row.addWidget(self.popup_cb)
        row.addWidget(self.clear_btn)
        lay.addLayout(row)

        self.model = SpotTableModel(1000, self)
        self.view = QTableView()
        self.view.setModel(self.model)
        setup_spot_view(self.view)
        self.view.doubleClicked.connect(lambda idx: self.spot_activated.emit(self.model.spot_at(idx.row())))
        self.clear_btn.clicked.connect(self.model.clear)
        lay.addWidget(self.view)
        self.retranslate()

    def retranslate(self) -> None:
        self._update_watch_btn()
        self.add_btn.setText(tr("Add..."))
        self.sound_cb.setText(tr("Sound"))
        self.popup_cb.setText(tr("Popup"))
        self.clear_btn.setText(tr("Clear"))
        self.model.retranslate()
        if self._dialog is not None:
            self._dialog.retranslate()

    def _update_watch_btn(self) -> None:
        active = sum(1 for e in self.entries if e.enabled)
        self.watch_btn.setText(tr("Watch list ({n})...", n=active))
        self.watch_btn.setToolTip("\n".join(e.pattern for e in self.entries if e.enabled))

    # ---------------------------------------------------------------- data
    def set_entries(self, entries: list[AlarmEntry]) -> None:
        self.entries = entries
        if self._dialog is not None:
            self._dialog.entries = entries
            self._dialog.rebuild()
        self._update_watch_btn()

    def set_options(self, sound: bool, popup: bool) -> None:
        self.sound_cb.setChecked(sound)
        self.popup_cb.setChecked(popup)

    def _dlg(self) -> WatchListDialog:
        if self._dialog is None:
            self._dialog = WatchListDialog(self.entries, self.countries, self.window())
            self._dialog.entries_changed.connect(self._on_dialog_changed)
        return self._dialog

    def show_watch_list(self) -> None:
        d = self._dlg()
        d.rebuild()
        d.show()
        d.raise_()
        d.activateWindow()

    def add_entry(self, entry: AlarmEntry | None) -> None:
        """Open the entry editor directly (from the spot context menu or the Add button)."""
        self._dlg().add(entry)

    def _on_dialog_changed(self) -> None:
        self._update_watch_btn()
        self.entries_changed.emit(self.entries)
