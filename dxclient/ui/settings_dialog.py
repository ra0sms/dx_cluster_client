"""Settings dialog."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QPlainTextEdit, QSpinBox,
)

from ..core.settings import Settings
from ..i18n import LANGUAGES, tr


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self.s = settings
        self.setWindowTitle(tr("Settings"))
        f = QFormLayout(self)

        self.callsign = QLineEdit(settings["callsign"])
        self.callsign.textChanged.connect(lambda t: self.callsign.setText(t.upper()) if t != t.upper() else None)
        f.addRow(tr("Your callsign:"), self.callsign)

        self.password = QLineEdit(settings["password"])
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        f.addRow(tr("Password (if required):"), self.password)

        self.commands = QPlainTextEdit("\n".join(settings["login_commands"]))
        self.commands.setFixedHeight(90)
        f.addRow(tr("Commands after login (one per line):"), self.commands)

        self.auto_connect = QCheckBox(tr("Connect on startup"))
        self.auto_connect.setChecked(settings["auto_connect"])
        f.addRow(self.auto_connect)
        self.auto_reconnect = QCheckBox(tr("Reconnect automatically"))
        self.auto_reconnect.setChecked(settings["auto_reconnect"])
        f.addRow(self.auto_reconnect)

        self.max_spots = QSpinBox()
        self.max_spots.setRange(100, 50000)
        self.max_spots.setSingleStep(500)
        self.max_spots.setValue(settings["max_spots"])
        f.addRow(tr("Max spots in table:"), self.max_spots)

        self.repeat = QSpinBox()
        self.repeat.setRange(0, 240)
        self.repeat.setValue(settings["alarm_repeat_minutes"])
        f.addRow(tr("Repeat alarm after (min):"), self.repeat)

        self.lookup = QLineEdit(settings["lookup_url"])
        f.addRow(tr("Callsign lookup URL ({call}):"), self.lookup)

        self.language = QComboBox()
        for code, name in LANGUAGES.items():
            self.language.addItem(name, code)
        self.language.setCurrentIndex(max(self.language.findData(settings["language"]), 0))
        f.addRow(tr("Language:"), self.language)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)
        self.resize(520, self.sizeHint().height())

    def apply(self) -> None:
        s = self.s
        s["callsign"] = self.callsign.text().strip().upper()
        s["password"] = self.password.text()
        s["login_commands"] = [l.strip() for l in self.commands.toPlainText().splitlines() if l.strip()]
        s["auto_connect"] = self.auto_connect.isChecked()
        s["auto_reconnect"] = self.auto_reconnect.isChecked()
        s["max_spots"] = self.max_spots.value()
        s["alarm_repeat_minutes"] = self.repeat.value()
        s["lookup_url"] = self.lookup.text().strip() or "https://www.qrz.com/db/{call}"
        s["language"] = self.language.currentData()
