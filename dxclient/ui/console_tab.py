"""Raw telnet console with a command line."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from ..i18n import tr


class CommandLine(QLineEdit):
    def __init__(self) -> None:
        super().__init__()
        self.history: list[str] = []
        self._pos = 0

    def push(self, text: str) -> None:
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
        self._pos = len(self.history)

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_Up and self.history:
            self._pos = max(0, self._pos - 1)
            self.setText(self.history[self._pos])
        elif e.key() == Qt.Key.Key_Down and self.history:
            self._pos = min(len(self.history), self._pos + 1)
            self.setText(self.history[self._pos] if self._pos < len(self.history) else "")
        else:
            super().keyPressEvent(e)


class ConsoleTab(QWidget):
    command = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(5000)
        self.text.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        lay.addWidget(self.text)
        row = QHBoxLayout()
        self.input = CommandLine()
        self.input.returnPressed.connect(self._send)
        self.send_btn = QPushButton()
        self.send_btn.clicked.connect(self._send)
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(self.text.clear)
        row.addWidget(self.input, 1)
        row.addWidget(self.send_btn)
        row.addWidget(self.clear_btn)
        lay.addLayout(row)
        self.retranslate()

    def retranslate(self) -> None:
        self.input.setPlaceholderText(tr("Command (e.g. sh/dx 20, sh/wwv)"))
        self.send_btn.setText(tr("Send"))
        self.clear_btn.setText(tr("Clear"))

    def append(self, line: str) -> None:
        sb = self.text.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        self.text.appendPlainText(line)
        if at_bottom:
            self.text.moveCursor(QTextCursor.MoveOperation.End)
            sb.setValue(sb.maximum())

    def _send(self) -> None:
        t = self.input.text().strip()
        if not t:
            return
        self.input.push(t)
        self.input.clear()
        self.append(f">>> {t}")
        self.command.emit(t)
