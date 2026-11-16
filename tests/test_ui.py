import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from dxclient.ui.filter_panel import VHF_KEY, FilterPanel  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_single_filter_buttons(app):
    p = FilterPanel(["Japan"])
    got = []
    p.filter_changed.connect(got.append)

    QTest.mouseClick(p.bands.buttons["20m"], Qt.MouseButton.LeftButton)
    assert got and "20m" not in got[-1].bands and "40m" in got[-1].bands

    QTest.mouseClick(p.modes.buttons["FT8"], Qt.MouseButton.LeftButton)
    assert "FT8" not in got[-1].modes and "CW" in got[-1].modes

    QTest.mouseClick(p.dx_cont.buttons["EU"], Qt.MouseButton.LeftButton)
    assert "EU" not in got[-1].dx_continents

    QTest.mouseClick(p.sp_cont.buttons["AS"], Qt.MouseButton.LeftButton)
    assert "AS" not in got[-1].spotter_continents

    QTest.mouseClick(p.bands.buttons[VHF_KEY], Qt.MouseButton.LeftButton)
    assert "2m" not in got[-1].bands and not got[-1].show_unknown_band

    QTest.mouseClick(p.bands.buttons["20m"], Qt.MouseButton.LeftButton)
    assert "20m" in got[-1].bands


def test_spot_server(app):
    from PySide6.QtNetwork import QHostAddress, QTcpSocket

    from dxclient.core.filters import SpotFilter
    from dxclient.core.spot import parse_spot
    from dxclient.core.telnet_server import SpotServer

    cw = parse_spot("DX de RA3CO-#:    14025.0  JA1ABC       CW 23 dB 25 WPM CQ             1234Z")
    ft8 = parse_spot("DX de DL1ABC:     7074.0  UA0SMS       FT8 -12dB                      1235Z")
    flt = SpotFilter(modes={"CW"})
    history = [cw, ft8]
    srv = SpotServer(lambda n: [s for s in history if flt.match(s)][:n])
    assert srv.start(0)  # any free port on 127.0.0.1
    port = int(srv.address.rsplit(":", 1)[1])

    sock = QTcpSocket()
    sock.connectToHost(QHostAddress(QHostAddress.SpecialAddress.LocalHost), port)
    assert sock.waitForConnected(2000)
    received = bytearray()

    def pump(ms=300):
        QTest.qWait(ms)
        received.extend(bytes(sock.readAll().data()))

    pump()
    assert received.endswith(b"login: ")
    sock.write(b"n0call\r\n")
    pump()
    assert srv.client_count == 1 and b"N0CALL de DXCLIENT" in received

    # main window forwards only filter-passing spots — emulate that here
    for s in (cw, ft8):
        if flt.match(s):
            srv.send_spot(s)
    pump()
    assert cw.raw.encode() + b"\r\n" in received and b"UA0SMS" not in received

    received.clear()
    sock.write(b"sh/dx 5\r\n")
    pump()
    assert received.count(b"DX de ") == 1 and b"JA1ABC" in received

    sock.write(b"bye\r\n")
    pump()
    assert srv.client_count == 0
    srv.stop()
    assert not srv.listening
