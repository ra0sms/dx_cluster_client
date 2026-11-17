"""Settings dialog (tabbed)."""
from __future__ import annotations

from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QPlainTextEdit, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)

from ..core.geo import is_locator
from ..core.settings import Settings
from ..i18n import LANGUAGES, tr


class _UpperValidator(QValidator):
    def validate(self, text, pos):
        return QValidator.State.Acceptable, text.upper(), pos


def _minutes(value: int, maximum: int, special: str | None = None) -> QSpinBox:
    sb = QSpinBox()
    sb.setRange(0, maximum)
    sb.setValue(value)
    sb.setSuffix(" " + tr("min"))
    if special:
        sb.setSpecialValueText(special)
    return sb


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.s = settings
        self.setWindowTitle(tr("Settings"))
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        lay.addWidget(tabs)

        # ---------------- connection
        page = QWidget()
        f = QFormLayout(page)
        self.callsign = QLineEdit(settings["callsign"])
        self.callsign.setValidator(_UpperValidator(self))
        f.addRow(tr("Your callsign:"), self.callsign)
        self.locator = QLineEdit(settings["locator"])
        self.locator.setValidator(_UpperValidator(self))
        self.locator.setPlaceholderText("PO02, KO85uq")
        self.locator.setMaxLength(6)
        f.addRow(tr("Your QTH locator:"), self.locator)
        self.password = QLineEdit(settings["password"])
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        f.addRow(tr("Password (if required):"), self.password)
        self.commands = QPlainTextEdit("\n".join(settings["login_commands"]))
        self.commands.setFixedHeight(80)
        f.addRow(tr("Commands after login (one per line):"), self.commands)
        self.auto_connect = QCheckBox(tr("Connect on startup"))
        self.auto_connect.setChecked(settings["auto_connect"])
        f.addRow(self.auto_connect)
        self.auto_reconnect = QCheckBox(tr("Reconnect automatically"))
        self.auto_reconnect.setChecked(settings["auto_reconnect"])
        f.addRow(self.auto_reconnect)
        tabs.addTab(page, tr("Connection"))

        # ---------------- spots
        page = QWidget()
        f = QFormLayout(page)
        self.max_spots = QSpinBox()
        self.max_spots.setRange(100, 50000)
        self.max_spots.setSingleStep(500)
        self.max_spots.setValue(settings["max_spots"])
        f.addRow(tr("Max spots in table:"), self.max_spots)
        self.max_age = _minutes(settings["max_age_minutes"], 1440, tr("keep"))
        self.max_age.setToolTip(tr("Older spots are removed; from half of this age they are greyed out."))
        f.addRow(tr("Remove spots older than:"), self.max_age)
        self.alarm_age = QSpinBox()
        self.alarm_age.setRange(0, 720)
        self.alarm_age.setValue(settings["alarm_max_age_hours"])
        self.alarm_age.setSuffix(" " + tr("h"))
        self.alarm_age.setSpecialValueText(tr("keep"))
        f.addRow(tr("Remove Alarm matches older than:"), self.alarm_age)
        self.dupe = _minutes(settings["dupe_minutes"], 240, tr("off"))
        self.dupe.setToolTip(tr("Repeated spots of a station on the same band and mode are merged into one row."))
        f.addRow(tr("Merge duplicate spots within:"), self.dupe)
        self.fresh = _minutes(settings["fresh_minutes"], 240, tr("no limit"))
        self.fresh.setToolTip(tr("Older spots (e.g. from sh/dx after login) are shown, but do not trigger "
                                 "Alarm and are not forwarded by the telnet server."))
        f.addRow(tr("Alarm and forward only spots newer than:"), self.fresh)
        self.repeat = _minutes(settings["alarm_repeat_minutes"], 240)
        f.addRow(tr("Repeat alarm after:"), self.repeat)
        self.lookup = QLineEdit(settings["lookup_url"])
        f.addRow(tr("Callsign lookup URL ({call}):"), self.lookup)
        tabs.addTab(page, tr("Spots"))

        # ---------------- telnet server
        page = QWidget()
        f = QFormLayout(page)
        self.server_enabled = QCheckBox(tr("Built-in telnet server (filtered spots for logging programs)"))
        self.server_enabled.setChecked(settings["server_enabled"])
        f.addRow(self.server_enabled)
        self.server_port = QSpinBox()
        self.server_port.setRange(1024, 65535)
        self.server_port.setValue(settings["server_port"])
        f.addRow(tr("Server port:"), self.server_port)
        self.server_lan = QCheckBox(tr("Allow connections from the local network (not only 127.0.0.1)"))
        self.server_lan.setChecked(settings["server_allow_lan"])
        f.addRow(self.server_lan)
        self.server_enabled.toggled.connect(self.server_port.setEnabled)
        self.server_enabled.toggled.connect(self.server_lan.setEnabled)
        self.server_port.setEnabled(self.server_enabled.isChecked())
        self.server_lan.setEnabled(self.server_enabled.isChecked())
        tabs.addTab(page, tr("Telnet server"))

        # ---------------- general
        page = QWidget()
        f = QFormLayout(page)
        self.language = QComboBox()
        for code, name in LANGUAGES.items():
            self.language.addItem(name, code)
        self.language.setCurrentIndex(max(self.language.findData(settings["language"]), 0))
        f.addRow(tr("Language:"), self.language)
        self.check_updates = QCheckBox(tr("Check for new versions on GitHub once a day"))
        self.check_updates.setChecked(settings["check_updates"])
        f.addRow(self.check_updates)
        self.auto_cty = QCheckBox(tr("Update cty.dat automatically when it is older than 30 days"))
        self.auto_cty.setChecked(settings["auto_update_cty"])
        f.addRow(self.auto_cty)
        tabs.addTab(page, tr("General"))

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.resize(560, self.sizeHint().height())

    def _accept(self) -> None:
        loc = self.locator.text().strip()
        if loc and not is_locator(loc):
            self.locator.setFocus()
            self.locator.selectAll()
            self.locator.setStyleSheet("border: 1px solid #c0392b;")
            return
        self.accept()

    def apply(self) -> None:
        s = self.s
        s["callsign"] = self.callsign.text().strip().upper()
        s["locator"] = self.locator.text().strip().upper()
        s["password"] = self.password.text()
        s["login_commands"] = [l.strip() for l in self.commands.toPlainText().splitlines() if l.strip()]
        s["auto_connect"] = self.auto_connect.isChecked()
        s["auto_reconnect"] = self.auto_reconnect.isChecked()
        s["max_spots"] = self.max_spots.value()
        s["max_age_minutes"] = self.max_age.value()
        s["alarm_max_age_hours"] = self.alarm_age.value()
        s["dupe_minutes"] = self.dupe.value()
        s["fresh_minutes"] = self.fresh.value()
        s["alarm_repeat_minutes"] = self.repeat.value()
        s["lookup_url"] = self.lookup.text().strip() or "https://www.qrz.com/db/{call}"
        s["server_enabled"] = self.server_enabled.isChecked()
        s["server_port"] = self.server_port.value()
        s["server_allow_lan"] = self.server_lan.isChecked()
        s["language"] = self.language.currentData()
        s["check_updates"] = self.check_updates.isChecked()
        s["auto_update_cty"] = self.auto_cty.isChecked()
