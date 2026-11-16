"""Filter side panel: bands, modes, continents, countries, presets."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QScrollArea,
    QSizePolicy, QToolButton, QVBoxLayout, QWidget,
)

from ..core.bands import BAND_NAMES, MAIN_BANDS, MODES
from ..core.dxcc import CONTINENTS
from ..core.filters import COUNTRY_ALL, COUNTRY_EXCLUDE, COUNTRY_ONLY, SpotFilter
from ..i18n import tr

OTHER_BANDS = [b for b in BAND_NAMES if b not in MAIN_BANDS]


class CountryDialog(QDialog):
    def __init__(self, countries: list[str], selected: set[str], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Select countries"))
        self.resize(380, 520)
        lay = QVBoxLayout(self)
        self.search = QLineEdit(placeholderText=tr("Search..."))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._apply_search)
        lay.addWidget(self.search)
        self.list = QListWidget()
        for name in countries:
            it = QListWidgetItem(name)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if name in selected else Qt.CheckState.Unchecked)
            self.list.addItem(it)
        lay.addWidget(self.list)
        row = QHBoxLayout()
        b1 = QPushButton(tr("Check visible"))
        b1.clicked.connect(lambda: self._set_visible(Qt.CheckState.Checked))
        b2 = QPushButton(tr("Uncheck visible"))
        b2.clicked.connect(lambda: self._set_visible(Qt.CheckState.Unchecked))
        row.addWidget(b1)
        row.addWidget(b2)
        lay.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _apply_search(self, text: str) -> None:
        t = text.strip().lower()
        for i in range(self.list.count()):
            it = self.list.item(i)
            it.setHidden(bool(t) and t not in it.text().lower())

    def _set_visible(self, state) -> None:
        for i in range(self.list.count()):
            it = self.list.item(i)
            if not it.isHidden():
                it.setCheckState(state)

    def selected(self) -> set[str]:
        return {
            self.list.item(i).text()
            for i in range(self.list.count())
            if self.list.item(i).checkState() == Qt.CheckState.Checked
        }


VHF_KEY = "VHF+"
SECTION_STYLE = "font-weight: bold; color: palette(window-text);"


class _ToggleGroup(QWidget):
    """Compact group: bold title with All / None links, then a grid of toggle buttons."""

    changed = Signal()

    def __init__(self, title_key: str, items: list[str], columns: int, label=lambda x: x,
                 tooltip=lambda x: "") -> None:
        super().__init__()
        self.title_key = title_key
        self._label = label
        self._tooltip = tooltip
        self.buttons: dict[str, QToolButton] = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(4)
        self.title = QLabel()
        self.title.setStyleSheet(SECTION_STYLE)
        head.addWidget(self.title, 1)
        self.all_btn = _link_button()
        self.all_btn.clicked.connect(lambda: self.set_checked(set(self.buttons)))
        self.none_btn = _link_button()
        self.none_btn.clicked.connect(lambda: self.set_checked(set()))
        head.addWidget(self.all_btn)
        head.addWidget(self.none_btn)
        lay.addLayout(head)
        grid = QGridLayout()
        grid.setSpacing(2)
        for i, it in enumerate(items):
            b = QToolButton()
            b.setProperty("toggle", True)
            b.setCheckable(True)
            b.setChecked(True)
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            b.setMinimumWidth(10)
            b.toggled.connect(lambda _checked: self.changed.emit())
            self.buttons[it] = b
            grid.addWidget(b, i // columns, i % columns)
        lay.addLayout(grid)
        self.retranslate()

    def retranslate(self) -> None:
        self.title.setText(tr(self.title_key))
        self.all_btn.setText(tr("all"))
        self.none_btn.setText(tr("none"))
        for k, b in self.buttons.items():
            b.setText(self._label(k))
            b.setToolTip(self._tooltip(k))

    def checked(self) -> set[str]:
        return {k for k, b in self.buttons.items() if b.isChecked()}

    def set_checked(self, items: set[str]) -> None:
        for k, b in self.buttons.items():
            b.blockSignals(True)
            b.setChecked(k in items)
            b.blockSignals(False)
        self.changed.emit()


def _link_button() -> QToolButton:
    b = QToolButton()
    b.setAutoRaise(True)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setProperty("link", True)
    return b


_MODE_SHORT = {"PHONE": "SSB"}


class FilterPanel(QWidget):
    filter_changed = Signal(object)  # SpotFilter
    presets_changed = Signal(dict)

    def __init__(self, countries: list[str], parent=None) -> None:
        super().__init__(parent)
        self.countries = countries
        self.selected_countries: set[str] = set()
        self.presets: dict[str, dict] = {}
        self._loading = False

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumWidth(200)
        self.setStyleSheet(
            "QToolButton[toggle=\"true\"] { padding: 1px 2px; border: 1px solid palette(mid);"
            " border-radius: 3px; background: palette(base); }"
            "QToolButton[toggle=\"true\"]:checked { background: palette(highlight);"
            " color: palette(highlighted-text); border-color: palette(highlight); }"
            "QToolButton[link=\"true\"] { border: none; padding: 0 2px; color: palette(link); }"
            "QToolButton[link=\"true\"]:hover { text-decoration: underline; }"
        )
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(8)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        scroll.setWidget(inner)

        # presets: one row
        pl = QHBoxLayout()
        pl.setSpacing(2)
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumContentsLength(6)
        self.preset_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.preset_combo.activated.connect(self._load_preset)
        self.save_btn = QToolButton()
        self.save_btn.setText("+")
        self.save_btn.clicked.connect(self._save_preset)
        self.del_btn = QToolButton()
        self.del_btn.setText("−")
        self.del_btn.clicked.connect(self._delete_preset)
        pl.addWidget(self.preset_combo, 1)
        pl.addWidget(self.save_btn)
        pl.addWidget(self.del_btn)
        lay.addLayout(pl)

        self.bands = _ToggleGroup(
            "Bands", MAIN_BANDS + [VHF_KEY], 6,
            lambda b: b if b == VHF_KEY else b.removesuffix("m"),
            lambda b: tr("Other bands (VHF+, unknown)") if b == VHF_KEY else b,
        )
        self.modes = _ToggleGroup("Modes", MODES, 4, lambda m: _MODE_SHORT.get(m, m), tr)
        self.dx_cont = _ToggleGroup("DX continent", CONTINENTS, 7)
        self.sp_cont = _ToggleGroup("Spotter continent", CONTINENTS, 7)
        for g in (self.bands, self.modes, self.dx_cont, self.sp_cont):
            g.changed.connect(self._emit)
            lay.addWidget(g)

        # countries: title + one row
        self.country_title = QLabel()
        self.country_title.setStyleSheet(SECTION_STYLE)
        lay.addWidget(self.country_title)
        cl = QHBoxLayout()
        cl.setSpacing(2)
        self.country_mode = QComboBox()
        self.country_mode.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.country_mode.setMinimumContentsLength(6)
        self.country_mode.currentIndexChanged.connect(self._emit)
        self.country_btn = QToolButton()
        self.country_btn.setText("…")
        self.country_btn.clicked.connect(self._choose_countries)
        cl.addWidget(self.country_mode, 1)
        cl.addWidget(self.country_btn)
        lay.addLayout(cl)
        self.country_lbl = QLabel()
        self.country_lbl.setStyleSheet("color: palette(placeholder-text);")
        lay.addWidget(self.country_lbl)
        lay.addStretch(1)
        self.retranslate()

    # ---------------------------------------------------------------- i18n
    def retranslate(self) -> None:
        self.preset_combo.setPlaceholderText(tr("Preset"))
        self.save_btn.setToolTip(tr("Save filter preset"))
        self.del_btn.setToolTip(tr("Delete"))
        for g in (self.bands, self.modes, self.dx_cont, self.sp_cont):
            g.retranslate()
        self.country_title.setText(tr("Countries"))
        self.country_btn.setToolTip(tr("Select countries"))
        idx = self.country_mode.currentIndex()
        self.country_mode.blockSignals(True)
        self.country_mode.clear()
        self.country_mode.addItem(tr("All countries"), COUNTRY_ALL)
        self.country_mode.addItem(tr("Only selected"), COUNTRY_ONLY)
        self.country_mode.addItem(tr("Exclude selected"), COUNTRY_EXCLUDE)
        self.country_mode.setCurrentIndex(max(idx, 0))
        self.country_mode.blockSignals(False)
        self._update_country_label()

    # ---------------------------------------------------------------- state
    def current_filter(self) -> SpotFilter:
        bands = self.bands.checked()
        vhf = VHF_KEY in bands
        bands.discard(VHF_KEY)
        if vhf:
            bands |= set(OTHER_BANDS)
        return SpotFilter(
            bands=bands,
            modes=self.modes.checked(),
            dx_continents=self.dx_cont.checked(),
            spotter_continents=self.sp_cont.checked(),
            country_mode=self.country_mode.currentData() or COUNTRY_ALL,
            countries=set(self.selected_countries),
            show_unknown_band=vhf,
        )

    def set_filter(self, f: SpotFilter) -> None:
        self._loading = True
        try:
            vhf = f.show_unknown_band or bool(f.bands & set(OTHER_BANDS))
            self.bands.set_checked((f.bands & set(MAIN_BANDS)) | ({VHF_KEY} if vhf else set()))
            self.modes.set_checked(f.modes)
            self.dx_cont.set_checked(f.dx_continents)
            self.sp_cont.set_checked(f.spotter_continents)
            i = self.country_mode.findData(f.country_mode)
            self.country_mode.setCurrentIndex(max(i, 0))
            self.selected_countries = set(f.countries)
            self._update_country_label()
        finally:
            self._loading = False
        self._emit()

    def set_presets(self, presets: dict[str, dict]) -> None:
        self.presets = dict(presets)
        self.preset_combo.clear()
        self.preset_combo.addItems(sorted(self.presets))
        self.preset_combo.setCurrentIndex(-1)

    def exclude_country(self, name: str) -> None:
        f = self.current_filter()
        if f.country_mode == COUNTRY_ONLY:
            f.countries.discard(name)
        else:
            if f.country_mode == COUNTRY_ALL:
                f.countries = set()
            f.country_mode = COUNTRY_EXCLUDE
            f.countries.add(name)
        self.set_filter(f)

    # ---------------------------------------------------------------- slots
    def _emit(self, *_):
        if not self._loading:
            self.filter_changed.emit(self.current_filter())

    def _update_country_label(self) -> None:
        self.country_lbl.setText(tr("Selected: {n}", n=len(self.selected_countries)))
        self.country_lbl.setToolTip("\n".join(sorted(self.selected_countries)))

    def _choose_countries(self) -> None:
        dlg = CountryDialog(self.countries, self.selected_countries, self)
        if dlg.exec():
            self.selected_countries = dlg.selected()
            self._update_country_label()
            if self.country_mode.currentData() == COUNTRY_ALL and self.selected_countries:
                self.country_mode.setCurrentIndex(self.country_mode.findData(COUNTRY_ONLY))
            else:
                self._emit()

    def _save_preset(self) -> None:
        name, ok = QInputDialog.getText(
            self, tr("Save filter preset"), tr("Preset name:"), text=self.preset_combo.currentText()
        )
        name = name.strip()
        if ok and name:
            self.presets[name] = self.current_filter().to_dict()
            self.set_presets(self.presets)
            self.preset_combo.setCurrentText(name)
            self.presets_changed.emit(self.presets)

    def _delete_preset(self) -> None:
        name = self.preset_combo.currentText()
        if name in self.presets:
            del self.presets[name]
            self.set_presets(self.presets)
            self.presets_changed.emit(self.presets)

    def _load_preset(self, idx: int) -> None:
        name = self.preset_combo.itemText(idx)
        if name in self.presets:
            self.set_filter(SpotFilter.from_dict(self.presets[name]))
