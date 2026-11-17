"""Spots that arrive before the PC clock is calibrated (sh/dx right after login)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta, timezone  # noqa: E402

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from dxclient.core.alarms import AlarmEntry  # noqa: E402
from dxclient.core.clock import judge_spot  # noqa: E402
from dxclient.core.spot import cluster_date  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _window(tmp_path, monkeypatch, alarm_calls):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from dxclient.core.settings import Settings
    from dxclient.ui.main_window import MainWindow

    s = Settings(tmp_path / "s.json")
    s.data.update(callsign="N0CALL", server_enabled=False, check_updates=False, auto_update_cty=False,
                  alarms=[], filter=None)
    w = MainWindow(s)
    w.alarms.entries = [AlarmEntry("*")]  # every station raises an alarm
    w._notify = lambda spot, entry: alarm_calls.append(spot)
    return w


def _shdx(dx: str, when: datetime) -> str:
    """A sh/dx line: it carries the full date, so the spot time itself is exact."""
    return f"   14025.0  {dx:<12} {cluster_date(when)} {when:%H%M}Z  CW 599                  <RA3CO>"


def _live(dx: str, when: datetime) -> str:
    return f"DX de RA3CO-#:    14025.0  {dx:<12} CW 23 dB 25 WPM CQ             {when:%H%M}Z"


def test_history_spot_does_not_alarm_when_pc_clock_is_slow(app, tmp_path, monkeypatch):
    """PC clock 3 h slow: a spot from 3 h ago looks 'just now' to the PC. It must not alarm."""
    calls = []
    w = _window(tmp_path, monkeypatch, calls)
    cluster_now = datetime.now(timezone.utc) + timedelta(hours=3)
    w._on_line(_shdx("JA1ABC", cluster_now - timedelta(hours=3)))
    assert calls == []
    assert w.spot_model.rowCount() == 1  # kept, just not treated as new
    w.close()


def test_history_spot_is_kept_until_calibrated_then_judged_by_cluster_time(app, tmp_path, monkeypatch):
    """PC clock 3 h fast. Before calibration the spot (10 min old in cluster time) must not be
    dropped; after calibration an old spot is dropped and a recent one is kept."""
    calls = []
    w = _window(tmp_path, monkeypatch, calls)
    cluster_now = datetime.now(timezone.utc) - timedelta(hours=3)

    w._on_line(_shdx("JA1ABC", cluster_now - timedelta(minutes=10)))
    assert w.spot_model.rowCount() == 1
    assert not w.clock.calibrated

    for i in range(6):  # live spots calibrate the clock to the cluster time
        w._on_line(_live(f"K{i}AA", cluster_now))
    assert w.clock.calibrated and w.clock.offset_minutes == -180

    w._on_line(_shdx("JA2ABC", cluster_now - timedelta(hours=3)))  # really 3 h old now
    assert all(s.dx != "JA2ABC" for s in w.spot_model.spots)
    w._on_line(_shdx("JA3ABC", cluster_now - timedelta(minutes=5)))  # recent
    assert any(s.dx == "JA3ABC" for s in w.spot_model.spots)
    w.close()


def test_judge_spot_before_calibration():
    # history: kept, never fresh, whatever the PC clock says
    v = judge_spot(live=False, calibrated=False, age_min=0, max_age_min=60, fresh_min=10)
    assert v.drop is False and v.fresh is False
    v = judge_spot(live=False, calibrated=False, age_min=500, max_age_min=60, fresh_min=10)
    assert v.drop is False and v.fresh is False
    # live: kept and fresh
    v = judge_spot(live=True, calibrated=False, age_min=500, max_age_min=60, fresh_min=10)
    assert v.drop is False and v.fresh is True


def test_judge_spot_after_calibration():
    assert judge_spot(live=False, calibrated=True, age_min=90, max_age_min=60, fresh_min=10).drop is True
    v = judge_spot(live=False, calibrated=True, age_min=5, max_age_min=60, fresh_min=10)
    assert v.drop is False and v.fresh is True
    v = judge_spot(live=False, calibrated=True, age_min=30, max_age_min=60, fresh_min=10)
    assert v.drop is False and v.fresh is False
    # zero limits mean "no limit" / "everything is fresh"
    v = judge_spot(live=False, calibrated=True, age_min=9999, max_age_min=0, fresh_min=0)
    assert v.drop is False and v.fresh is True
