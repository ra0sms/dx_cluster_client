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


def _spot(line, minutes_ago=0):
    from datetime import datetime, timedelta, timezone

    from dxclient.core.spot import parse_spot

    s = parse_spot(line)
    s.when = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return s


def test_dupes_aging_search(app):
    from datetime import datetime, timezone

    from dxclient.ui.spot_model import SpotFilterProxy, SpotTableModel

    cw = "DX de RA3CO-#:    14025.0  JA1ABC       CW 23 dB 25 WPM CQ             1234Z"
    m = SpotTableModel()
    assert m.add_spot(_spot(cw, 20), dupe_minutes=10) is None
    assert m.add_spot(_spot(cw, 5), dupe_minutes=10) is None  # 15 min apart → not a dupe
    old = m.spots[0]
    assert m.add_spot(_spot(cw, 0), dupe_minutes=10) is old  # 5 min apart → merged
    assert m.rowCount() == 2 and m.spots[0].count == 2
    m.add_spot(_spot("DX de W1AW:      28495.0  VP8LP        SSB 59                          1236Z", 90))
    assert m.rowCount() == 3
    assert m.remove_older_than(60, datetime.now(timezone.utc)) == 1 and m.rowCount() == 2

    p = SpotFilterProxy()
    p.setSourceModel(m)
    m.add_spot(_spot("DX de W1AW:      28495.0  VP8LP        SSB 59                          1236Z"))
    p.set_search("vp8")
    assert p.rowCount() == 1
    p.set_search("ja1")
    assert p.rowCount() == 2  # two JA1ABC spots 15 min apart (not merged)
    p.set_search("")
    assert p.rowCount() == 3


def test_settings_dialog_builds(app, tmp_path):
    from dxclient.core.settings import Settings
    from dxclient.ui.settings_dialog import SettingsDialog

    s = Settings(tmp_path / "s.json")
    d = SettingsDialog(s)
    d.locator.setText("ko85uq")
    d.dupe.setValue(0)
    d.apply()
    assert s["locator"] == "KO85UQ" and s["dupe_minutes"] == 0


def test_alarm_cleanup_and_clear_all(app, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from dxclient.core.settings import Settings
    from dxclient.ui.main_window import MainWindow

    s = Settings(tmp_path / "s.json")
    s["callsign"] = "N0CALL"
    s["server_enabled"] = False
    s["check_updates"] = False
    s["auto_update_cty"] = False
    w = MainWindow(s)
    line = "DX de RA3CO-#:    3510.0  3Y0J         CW 30 dB 28 WPM CQ             1237Z"
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    for _ in range(5):  # age-based cleanup needs a calibrated clock; the PC clock is right here
        w.clock.feed(f"{now:%H%M}", now)
    assert w.clock.calibrated
    w.alarm_tab.model.add_spot(_spot(line, 25 * 60))  # 25 h old
    w.alarm_tab.model.add_spot(_spot(line, 60))  # 1 h old
    w.spot_model.add_spot(_spot(line, 5))
    w._age_tick()
    assert w.alarm_tab.model.rowCount() == 1  # 24 h limit by default
    assert w.spot_model.rowCount() == 1

    w.unread_alarms = 3
    w._clear_all()
    assert w.alarm_tab.model.rowCount() == 0 and w.spot_model.rowCount() == 0 and w.unread_alarms == 0
    w.close()


def _window(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from dxclient.core.settings import Settings
    from dxclient.ui.main_window import MainWindow

    s = Settings(tmp_path / "s.json")
    s.data.update(callsign="N0CALL", server_enabled=False, check_updates=False, auto_update_cty=False,
                  alarms=[], filter=None)
    return MainWindow(s)


def test_wrong_pc_clock_does_not_drop_spots(app, tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    w = _window(tmp_path, monkeypatch)
    cluster_now = datetime.now(timezone.utc) + timedelta(minutes=20)  # PC clock 20 min slow
    for i in range(8):
        w._on_line(f"DX de RA3CO-#:    14025.0  JA{i}ABC       CW 23 dB 25 WPM CQ             {cluster_now:%H%M}Z")
    assert w.spot_model.rowCount() == 8
    assert w.clock.offset_minutes == 20 and not w.clock_lbl.isHidden()
    assert all(s.age_minutes(w.clock.now()) < 2 for s in w.spot_model.spots)
    w.close()


def test_repeated_shdx_is_ignored(app, tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    w = _window(tmp_path, monkeypatch)
    t = datetime.now(timezone.utc) - timedelta(minutes=5)
    from dxclient.core.spot import cluster_date

    line = f"   14025.0  JA1ABC      {cluster_date(t)} {t:%H%M}Z  CW 599                  <RA3CO>"
    w._on_line(line)
    w._on_line(line)  # sh/dx again after a reconnect
    assert w.spot_model.rowCount() == 1 and w.spot_model.spots[0].count == 1
    w.close()


def test_watchdog_reconnects_silent_connection(app):
    from PySide6.QtNetwork import QHostAddress, QTcpServer

    from dxclient.core import telnet_client as tc

    srv = QTcpServer()
    assert srv.listen(QHostAddress(QHostAddress.SpecialAddress.LocalHost), 0)
    accepted = []
    srv.newConnection.connect(lambda: accepted.append(srv.nextPendingConnection()))

    c = tc.ClusterClient()
    c.WATCHDOG_S = 1
    c.RECONNECT_DELAYS = [0]
    c._watchdog.setInterval(300)
    c.connect_to("127.0.0.1", srv.serverPort())
    for _ in range(50):
        QTest.qWait(100)
        if len(accepted) >= 2:
            break
    assert len(accepted) >= 2  # silent server → watchdog dropped the link → reconnected
    c.disconnect_from()
    srv.close()


def _destroy(widget):
    """Delete a dialog while the QApplication is still alive (PySide6 6.12 crashes otherwise)."""
    from PySide6.QtCore import QCoreApplication, QEvent

    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_alarm_pattern_is_uppercase_in_call_mode(app):
    from dxclient.core.alarms import KIND_CALL, KIND_COUNTRY
    from dxclient.ui.alarm_tab import AlarmEntryDialog

    dlg = AlarmEntryDialog(None, ["Japan"])
    dlg.show()
    dlg.pattern.setFocus()
    QTest.keyClicks(dlg.pattern, "ja1abc")
    assert dlg.pattern.text() == "JA1ABC"
    assert dlg.pattern.validator() is not None
    assert dlg.entry().pattern == "JA1ABC"

    # country names keep their normal case (they are matched case-insensitively)
    dlg.kind.setCurrentIndex(dlg.kind.findData(KIND_COUNTRY))
    assert dlg.pattern.validator() is None
    dlg.pattern.clear()
    QTest.keyClicks(dlg.pattern, "Japan")
    assert dlg.pattern.text() == "Japan"

    # switching back to a callsign uppercases whatever is already typed
    dlg.kind.setCurrentIndex(dlg.kind.findData(KIND_CALL))
    assert dlg.pattern.text() == "JAPAN"
    _destroy(dlg)


def test_watch_list_sorts_rules_by_name(app):
    from dxclient.core.alarms import KIND_COUNTRY, AlarmEntry
    from dxclient.ui.alarm_tab import WatchListDialog

    entries = [
        AlarmEntry("VP8*"),
        AlarmEntry("3Y0J"),
        AlarmEntry("Japan", kind=KIND_COUNTRY),
        AlarmEntry("ja1abc"),
    ]
    dlg = WatchListDialog(entries, ["Japan"])

    dlg.sort_btn.click()  # first click: A → Z, case-insensitive
    assert [e.pattern for e in entries] == ["3Y0J", "ja1abc", "Japan", "VP8*"]
    assert [dlg.table.item(r, 1).text() for r in range(4)] == [e.pattern for e in entries]
    assert "↑" in dlg.sort_btn.text()

    dlg.sort_btn.click()  # second click: Z → A
    assert [e.pattern for e in entries] == ["VP8*", "Japan", "ja1abc", "3Y0J"]
    assert "↓" in dlg.sort_btn.text()

    dlg._header_clicked(1)  # the "Pattern" header toggles the direction too
    assert [e.pattern for e in entries] == ["3Y0J", "ja1abc", "Japan", "VP8*"]

    before = list(entries)
    dlg._header_clicked(0)  # other columns are ignored
    assert entries == before
    _destroy(dlg)


def test_alarm_rejects_duplicate_rules(app, monkeypatch):
    from PySide6.QtWidgets import QDialog, QMessageBox

    from dxclient.core.alarms import AlarmEntry
    from dxclient.ui.alarm_tab import AlarmEntryDialog, WatchListDialog

    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning",
                        lambda parent, title, text, *a, **k: warnings.append(text))

    entries = [AlarmEntry("JA1ABC")]

    # a new rule with the same callsign (any case) is rejected and the editor stays open
    dlg = AlarmEntryDialog(None, [], existing=entries)
    dlg.pattern.setText("ja1abc")
    dlg._accept()
    assert warnings and "JA1ABC" in warnings[-1]
    assert dlg.result() != QDialog.DialogCode.Accepted
    _destroy(dlg)

    # the rule being edited is not a duplicate of itself
    warnings.clear()
    dlg = AlarmEntryDialog(entries[0], [], existing=entries)
    dlg._accept()
    assert warnings == []
    assert dlg.result() == QDialog.DialogCode.Accepted
    _destroy(dlg)

    # quick-add from the spot menu: a duplicate preset is rejected before the editor opens
    warnings.clear()
    wl = WatchListDialog(entries, [])
    wl.add(AlarmEntry("ja1abc"))
    assert warnings and "JA1ABC" in warnings[-1]
    assert [e.pattern for e in entries] == ["JA1ABC"]
    _destroy(wl)
