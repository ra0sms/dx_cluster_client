"""Dialog for sending a spot to the cluster: DX <freq> <call> <comment>."""
from __future__ import annotations

import re

from PySide6.QtGui import QDoubleValidator, QValidator
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit

from ..core.bands import band_of
from ..i18n import tr

_CALL_RE = re.compile(r"^[A-Z0-9]+(/[A-Z0-9]+)*$")


class _Upper(QValidator):
    def validate(self, text, pos):
        return QValidator.State.Acceptable, text.upper().replace(" ", ""), pos


def build_dx_command(freq: float, call: str, comment: str) -> str:
    comment = " ".join(comment.split())[:30]
    return f"DX {freq:.1f} {call} {comment}".rstrip()


class SendSpotDialog(QDialog):
    def __init__(self, freq: float | None = None, call: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Send spot"))
        f = QFormLayout(self)
        self.freq = QLineEdit("" if freq is None else f"{freq:.1f}")
        v = QDoubleValidator(100.0, 11_000_000.0, 1, self)
        v.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.freq.setValidator(v)
        self.freq.setPlaceholderText("14025.0")
        f.addRow(tr("Frequency, kHz:"), self.freq)
        self.call = QLineEdit(call)
        self.call.setValidator(_Upper(self))
        f.addRow(tr("Callsign:"), self.call)
        self.comment = QLineEdit()
        self.comment.setMaxLength(30)
        self.comment.setPlaceholderText("CW 599 / UP 2 / FT8 -12")
        f.addRow(tr("Comment:"), self.comment)
        self.preview = QLabel()
        self.preview.setStyleSheet("color: palette(placeholder-text);")
        f.addRow(self.preview)
        self.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.bb.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Send"))
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        f.addRow(self.bb)
        for w in (self.freq, self.call, self.comment):
            w.textChanged.connect(self._update)
        self._update()
        (self.comment if freq is not None and call else self.freq).setFocus()
        self.resize(420, self.sizeHint().height())

    def command(self) -> str | None:
        try:
            freq = float(self.freq.text().replace(",", "."))
        except ValueError:
            return None
        call = self.call.text().strip().upper()
        if band_of(freq) is None or not _CALL_RE.match(call) or len(call) < 3:
            return None
        return build_dx_command(freq, call, self.comment.text())

    def _update(self) -> None:
        cmd = self.command()
        self.preview.setText(cmd or tr("Enter a frequency inside an amateur band and a callsign."))
        self.bb.button(QDialogButtonBox.StandardButton.Ok).setEnabled(cmd is not None)
