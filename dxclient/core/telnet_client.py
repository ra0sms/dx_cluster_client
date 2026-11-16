"""Asynchronous telnet client for DX clusters based on QTcpSocket."""
from __future__ import annotations

import re

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket

IAC = 255
_LOGIN_RE = re.compile(r"(login|call(sign)?|please enter your call.*?)\s*:?\s*>?\s*$", re.I)
_PASSWORD_RE = re.compile(r"password\s*:?\s*$", re.I)

STATE_DISCONNECTED = "disconnected"
STATE_CONNECTING = "connecting"
STATE_CONNECTED = "connected"
STATE_RECONNECT_WAIT = "reconnect_wait"


def strip_telnet(data: bytes, sock: QTcpSocket | None = None) -> bytes:
    """Remove telnet IAC negotiation, refusing every option (WONT/DONT)."""
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        if b != IAC:
            out.append(b)
            i += 1
            continue
        if i + 1 >= n:
            break
        cmd = data[i + 1]
        if cmd == IAC:
            out.append(IAC)
            i += 2
        elif cmd in (251, 252, 253, 254):  # WILL WONT DO DONT
            if i + 2 < n and sock is not None:
                opt = data[i + 2]
                reply = 254 if cmd in (251, 252) else 252  # DONT / WONT
                sock.write(bytes([IAC, reply, opt]))
            i += 3
        elif cmd == 250:  # SB ... IAC SE
            end = data.find(bytes([IAC, 240]), i + 2)
            i = n if end < 0 else end + 2
        else:
            i += 2
    return bytes(out)


class ClusterClient(QObject):
    line_received = Signal(str)
    state_changed = Signal(str)
    logged_in = Signal()
    error = Signal(str)

    KEEPALIVE_MS = 5 * 60 * 1000
    RECONNECT_DELAYS = [5, 10, 30, 60, 120]

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.host = ""
        self.port = 0
        self.callsign = ""
        self.password = ""
        self.login_commands: list[str] = []
        self.auto_reconnect = True

        self._sock = QTcpSocket(self)
        self._sock.connected.connect(self._on_connected)
        self._sock.disconnected.connect(self._on_disconnected)
        self._sock.readyRead.connect(self._on_ready_read)
        self._sock.errorOccurred.connect(self._on_error)

        self._buf = ""
        self._logged_in = False
        self._user_disconnect = False
        self._attempt = 0
        self._state = STATE_DISCONNECTED

        self._keepalive = QTimer(self)
        self._keepalive.setInterval(self.KEEPALIVE_MS)
        self._keepalive.timeout.connect(lambda: self.send(""))
        self._reconnect = QTimer(self)
        self._reconnect.setSingleShot(True)
        self._reconnect.timeout.connect(self._do_connect)
        self._login_fallback = QTimer(self)
        self._login_fallback.setSingleShot(True)
        self._login_fallback.timeout.connect(self._send_login)

    # ------------------------------------------------------------------ API
    @property
    def state(self) -> str:
        return self._state

    def connect_to(self, host: str, port: int) -> None:
        self.disconnect_from()
        self.host, self.port = host, port
        self._attempt = 0
        self._user_disconnect = False
        self._do_connect()

    def disconnect_from(self) -> None:
        self._user_disconnect = True
        self._reconnect.stop()
        self._keepalive.stop()
        self._login_fallback.stop()
        if self._sock.state() != QAbstractSocket.SocketState.UnconnectedState:
            if self._sock.state() == QAbstractSocket.SocketState.ConnectedState:
                self.send("bye")
                self._sock.flush()
            self._sock.abort()
        self._set_state(STATE_DISCONNECTED)

    def send(self, text: str) -> None:
        if self._sock.state() == QAbstractSocket.SocketState.ConnectedState:
            self._sock.write((text + "\r\n").encode("utf-8", "replace"))

    # ------------------------------------------------------------------ internals
    def _set_state(self, st: str) -> None:
        if st != self._state:
            self._state = st
            self.state_changed.emit(st)

    def _do_connect(self) -> None:
        self._buf = ""
        self._logged_in = False
        self._set_state(STATE_CONNECTING)
        self._sock.abort()
        self._sock.connectToHost(self.host, self.port)

    def _on_connected(self) -> None:
        self._attempt = 0
        self._set_state(STATE_CONNECTED)
        self._keepalive.start()
        # Some nodes never print a recognisable prompt — log in anyway after a pause.
        self._login_fallback.start(8000)

    def _on_disconnected(self) -> None:
        self._keepalive.stop()
        self._login_fallback.stop()
        if self._buf:
            self.line_received.emit(self._buf)
            self._buf = ""
        self._schedule_reconnect()

    def _on_error(self, _err) -> None:
        self.error.emit(self._sock.errorString())
        # The socket state is updated after the signal; check on the next loop tick.
        QTimer.singleShot(0, self._after_error)

    def _after_error(self) -> None:
        if self._sock.state() == QAbstractSocket.SocketState.UnconnectedState:
            self._schedule_reconnect()

    def _schedule_reconnect(self) -> None:
        if self._user_disconnect or not self.auto_reconnect or not self.host:
            self._set_state(STATE_DISCONNECTED)
            return
        if self._reconnect.isActive():
            return
        delay = self.RECONNECT_DELAYS[min(self._attempt, len(self.RECONNECT_DELAYS) - 1)]
        self._attempt += 1
        self._set_state(STATE_RECONNECT_WAIT)
        self._reconnect.start(delay * 1000)

    def _send_login(self) -> None:
        if self._logged_in or not self.callsign:
            return
        self._logged_in = True
        self._login_fallback.stop()
        self.send(self.callsign)
        QTimer.singleShot(1500, self._after_login)

    def _after_login(self) -> None:
        for cmd in self.login_commands:
            cmd = cmd.strip()
            if cmd:
                self.send(cmd)
        self.logged_in.emit()

    def _on_ready_read(self) -> None:
        raw = bytes(self._sock.readAll().data())
        data = strip_telnet(raw, self._sock)
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x07", "")
        self._buf += text
        *lines, self._buf = self._buf.split("\n")
        for line in lines:
            self.line_received.emit(line)
        # Prompts come without a trailing newline
        tail = self._buf.strip()
        if tail:
            if not self._logged_in and _LOGIN_RE.search(tail):
                self.line_received.emit(self._buf)
                self._buf = ""
                self._send_login()
            elif self._logged_in and self.password and _PASSWORD_RE.search(tail):
                self.line_received.emit(self._buf)
                self._buf = ""
                self.send(self.password)
