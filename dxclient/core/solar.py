"""Solar / geomagnetic indices (SFI, A, K, sunspot number) fetched from the internet.

Primary source: N0NBH  https://www.hamqsl.com/solarxml.php  (all four values)
Fallback:       NOAA SWPC  https://services.swpc.noaa.gov/text/wwv.txt  (SFI, A, K; no sunspots)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

HAMQSL_URL = "https://www.hamqsl.com/solarxml.php"
NOAA_WWV_URL = "https://services.swpc.noaa.gov/text/wwv.txt"
REFRESH_MS = 60 * 60 * 1000  # every hour
RETRY_MS = 10 * 60 * 1000  # after a failure


@dataclass
class SolarData:
    sfi: int | None = None
    a: int | None = None
    k: float | None = None
    ssn: int | None = None
    updated: str = ""  # as reported by the source
    source: str = ""
    fetched: datetime | None = None


def _num(text: str | None) -> float | None:
    if text is None:
        return None
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(m.group()) if m else None


def _int(text: str | None) -> int | None:
    v = _num(text)
    return None if v is None else int(round(v))


def parse_hamqsl(xml: str) -> SolarData | None:
    def tag(name: str) -> str | None:
        m = re.search(rf"<{name}>([^<]*)</{name}>", xml)
        return m.group(1).strip() if m else None

    d = SolarData(
        sfi=_int(tag("solarflux")),
        a=_int(tag("aindex")),
        k=_num(tag("kindex")),
        ssn=_int(tag("sunspots")),
        updated=tag("updated") or "",
        source="hamqsl.com (N0NBH)",
    )
    return d if d.sfi is not None or d.k is not None else None


def parse_noaa_wwv(text: str) -> SolarData | None:
    sfi = re.search(r"Solar flux\s+(\d+)", text)
    a = re.search(r"planetary A-index\s+(\d+)", text)
    k = re.search(r"planetary K-index .*? was\s+(\d+(?:\.\d+)?)", text)
    issued = re.search(r":Issued:\s*(.+)", text)
    if not (sfi or a or k):
        return None
    return SolarData(
        sfi=int(sfi.group(1)) if sfi else None,
        a=int(a.group(1)) if a else None,
        k=float(k.group(1)) if k else None,
        updated=issued.group(1).strip() if issued else "",
        source="NOAA SWPC",
    )


class SolarFetcher(QObject):
    updated = Signal(object)  # SolarData
    failed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.data: SolarData | None = None
        self._nam = QNetworkAccessManager(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.refresh)
        self._busy = False

    def start(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._timer.stop()
        self._get(HAMQSL_URL, self._on_hamqsl)

    def _get(self, url: str, handler) -> None:
        req = QNetworkRequest(QUrl(url))
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "DXClusterClient")
        req.setTransferTimeout(20000)
        reply = self._nam.get(req)
        reply.finished.connect(lambda: handler(reply))

    @staticmethod
    def _text(reply: QNetworkReply) -> str | None:
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return None
        return bytes(reply.readAll().data()).decode("utf-8", "replace")

    def _on_hamqsl(self, reply: QNetworkReply) -> None:
        text = self._text(reply)
        d = parse_hamqsl(text) if text else None
        if d is None:
            self._get(NOAA_WWV_URL, self._on_noaa)
        else:
            self._done(d)

    def _on_noaa(self, reply: QNetworkReply) -> None:
        text = self._text(reply)
        d = parse_noaa_wwv(text) if text else None
        if d is None:
            self._busy = False
            self.failed.emit(reply.errorString() if reply.error() != QNetworkReply.NetworkError.NoError else "no data")
            self._timer.start(RETRY_MS)
        else:
            self._done(d)

    def _done(self, d: SolarData) -> None:
        d.fetched = datetime.now(timezone.utc)
        self.data = d
        self._busy = False
        self.updated.emit(d)
        self._timer.start(REFRESH_MS)
