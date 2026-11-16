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
