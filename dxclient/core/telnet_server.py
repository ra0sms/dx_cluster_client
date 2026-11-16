"""Built-in telnet server: re-publishes filtered spots to logging programs (N1MM, Log4OM, ...).

Behaves like a minimal DX cluster node: asks for a callsign, then streams 'DX de' lines.
Supported commands: sh/dx [n], bye / quit / exit; anything else just gets a prompt back.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QAbstractSocket, QHostAddress, QTcpServer, QTcpSocket

from .spot import Spot
from .telnet_client import strip_telnet

NODE_NAME = "DXCLIENT"
_SHDX_RE = re.compile(r"^sh(o(w)?)?/dx(\s+(\d+))?", re.I)
_MAX_LINE = 1024


class _Session:
    def __init__(self, sock: QTcpSocket) -> None:
        self.sock = sock
        self.call = ""
        self.buf = ""

    @property
    def ready(self) -> bool:
        return bool(self.call)


class SpotServer(QObject):
    clients_changed = Signal(int)
    error = Signal(str)

    def __init__(self, recent_spots: Callable[[int], list[Spot]] | None = None, parent=None) -> None:
        super().__init__(parent)
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._on_new_connection)
        self._sessions: dict[QTcpSocket, _Session] = {}
        # returns up to n most recent *filtered* spots, newest first
        self.recent_spots = recent_spots or (lambda n: [])

    # ------------------------------------------------------------------ API
    @property
    def listening(self) -> bool:
        return self._server.isListening()

    @property
    def address(self) -> str:
        return f"{self._server.serverAddress().toString()}:{self._server.serverPort()}"

    @property
    def client_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.ready)

    def start(self, port: int, allow_lan: bool = False) -> bool:
        self.stop()
        host = QHostAddress(QHostAddress.SpecialAddress.Any if allow_lan else QHostAddress.SpecialAddress.LocalHost)
        if not self._server.listen(host, port):
            self.error.emit(self._server.errorString())
            return False
        return True

    def stop(self) -> None:
        for sock in list(self._sessions):
            sock.abort()
        self._sessions.clear()
        if self._server.isListening():
            self._server.close()
        self.clients_changed.emit(0)

    def send_spot(self, spot: Spot) -> None:
        line = spot.to_dx_line()
        for s in self._sessions.values():
            if s.ready:
                self._write(s, line)

    # ------------------------------------------------------------------ internals
    @staticmethod
    def _write(s: _Session, text: str) -> None:
        if s.sock.state() == QAbstractSocket.SocketState.ConnectedState:
            s.sock.write((text + "\r\n").encode("utf-8", "replace"))

    def _prompt(self, s: _Session) -> None:
        now = datetime.now(timezone.utc).strftime("%d-%b-%Y %H%MZ")
        s.sock.write(f"{s.call} de {NODE_NAME} {now} >\r\n".encode())

    def _on_new_connection(self) -> None:
        while self._server.hasPendingConnections():
            sock = self._server.nextPendingConnection()
            s = _Session(sock)
            self._sessions[sock] = s
            sock.readyRead.connect(lambda sk=sock: self._on_ready_read(sk))
            sock.disconnected.connect(lambda sk=sock: self._on_disconnected(sk))
            sock.write(f"Welcome to {NODE_NAME} (DX Cluster Client spot server)\r\n\r\nlogin: ".encode())

    def _on_disconnected(self, sock: QTcpSocket) -> None:
        s = self._sessions.pop(sock, None)
        sock.deleteLater()
        if s and s.ready:
            self.clients_changed.emit(self.client_count)

    def _on_ready_read(self, sock: QTcpSocket) -> None:
        s = self._sessions.get(sock)
        if s is None:
            return
        data = strip_telnet(bytes(sock.readAll().data()), sock)
        s.buf += data.decode("utf-8", "replace").replace("\r\n", "\n").replace("\r", "\n")
        if len(s.buf) > _MAX_LINE and "\n" not in s.buf:
            s.buf = ""  # garbage without newlines
        *lines, s.buf = s.buf.split("\n")
        for line in lines:
            self._handle(s, line.strip())

    def _handle(self, s: _Session, line: str) -> None:
        if not s.ready:
            call = re.sub(r"[^A-Za-z0-9/\-]", "", line).upper()
            if not call:
                s.sock.write(b"login: ")
                return
            s.call = call
            self._write(s, f"Hello {call}, this is {NODE_NAME}. Filtered spots follow.")
            self._prompt(s)
            self.clients_changed.emit(self.client_count)
            return
        if not line:
            self._prompt(s)
            return
        low = line.lower()
        if low in ("bye", "quit", "exit", "q"):
            self._write(s, "73!")
            s.sock.disconnectFromHost()
            return
        m = _SHDX_RE.match(low)
        if m:
            n = min(int(m.group(4) or 10), 100)
            for spot in reversed(self.recent_spots(n)):  # oldest first, like a cluster
                self._write(s, spot.to_dx_line())
        # set/..., unset/..., other commands: accepted silently
        self._prompt(s)
