"""Check GitHub for a newer release."""
from __future__ import annotations

import json
import re

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from .. import __version__

REPO = "ra0sms/dx_cluster_client"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"


def parse_version(text: str) -> tuple[int, ...]:
    """'v0.10.2' → (0, 10, 2); anything unparsable → ()."""
    m = re.match(r"^\s*v?(\d+(?:\.\d+)*)", text or "")
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def is_newer(remote: str, local: str = __version__) -> bool:
    r, l = parse_version(remote), parse_version(local)
    return bool(r) and r > l


class UpdateChecker(QObject):
    # (version, url) when a newer release exists
    update_available = Signal(str, str)
    # manual check finished without finding anything: (message-key, detail)
    up_to_date = Signal()
    failed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)

    def check(self) -> None:
        req = QNetworkRequest(QUrl(LATEST_URL))
        req.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "DXClusterClient")
        req.setRawHeader(b"Accept", b"application/vnd.github+json")
        req.setTransferTimeout(20000)
        reply = self._nam.get(req)
        reply.finished.connect(lambda: self._done(reply))

    def _done(self, reply: QNetworkReply) -> None:
        reply.deleteLater()
        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.failed.emit(reply.errorString())
            return
        try:
            d = json.loads(bytes(reply.readAll().data()))
            tag = d.get("tag_name", "")
            url = d.get("html_url") or RELEASES_PAGE
        except (ValueError, AttributeError) as e:
            self.failed.emit(str(e))
            return
        if is_newer(tag):
            self.update_available.emit(tag.lstrip("v"), url)
        else:
            self.up_to_date.emit()
