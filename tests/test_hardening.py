"""Robustness tests: damaged input files, the duplicate index of the spot table, Qt compatibility."""
import json
import os
import stat
from datetime import datetime, timedelta, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from dxclient.core.alarms import AlarmEntry
from dxclient.core.bands import BAND_NAMES
from dxclient.core.cluster_list import load_cache, parse_clusters_json
from dxclient.core.filters import SpotFilter
from dxclient.core.settings import DEFAULTS, Settings, atomic_write
from dxclient.core.spot import parse_spot

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def spot_at(dx, freq, hhmm, spotter="W1AW", comment="CW", now=NOW):
    return parse_spot(f"DX de {spotter}:  {freq:.1f}  {dx:<12} {comment:<30} {hhmm}Z", now=now)


# ---------------------------------------------------------------- clusters.json
@pytest.mark.parametrize("data", [b"[]", b"null", b"42", b"not json", b'"text"'])
def test_clusters_non_object_is_a_value_error(data):
    with pytest.raises(ValueError):
        parse_clusters_json(data)


def test_clusters_bad_items_are_skipped_or_defaulted():
    doc = {
        "nodes": "not a list",
        "directory": [
            1,
            None,
            {"addr": "noport"},
            {"addr": "h.example:7300", "call": "X1", "stars": {"value": "bad"}, "state": 5},
        ],
    }
    nodes = parse_clusters_json(json.dumps(doc).encode())
    assert len(nodes) == 1
    n = nodes[0]
    assert (n.host, n.port, n.name) == ("h.example", 7300, "X1")
    assert n.stars is None
    assert n.up is True  # state is not a string → the list default (directory → up)


def test_damaged_cluster_cache_gives_empty_list(tmp_path):
    p = tmp_path / "clusters.json"
    p.write_bytes(b"[]")
    assert load_cache(p) == []
    p.write_bytes(b"\xff\xfe garbage")
    assert load_cache(p) == []


def test_custom_nodes_tolerate_bad_items():
    from dxclient.core.cluster_list import parse_custom_nodes

    nodes = parse_custom_nodes([
        {"host": "a.example", "port": 7300},
        {"host": "b.example", "port": "8000", "name": "B"},
        {"host": "a.example", "port": 7300},  # duplicate
        {"host": "c.example"},  # no port
        {"host": "", "port": 1},
        {"host": "d.example", "port": "abc"},
        {"host": "e.example", "port": 70000},
        "garbage",
        None,
    ])
    assert [(n.name, n.host, n.port, n.custom) for n in nodes] == [
        ("a.example", "a.example", 7300, True),
        ("B", "b.example", 8000, True),
    ]
    assert parse_custom_nodes("not a list") == []


# ---------------------------------------------------------------- settings
def test_settings_with_wrong_types_fall_back_to_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({
        "max_spots": "abc",
        "fresh_minutes": True,
        "callsign": 123,
        "alarms": {"not": "a list"},
        "login_commands": ["sh/dx 30", 3, None],
        "cluster_history": "ra3co.com:7373",
        "filter": {"bands": None},  # None default → kept as is; SpotFilter handles it
        "custom_option": "kept",
    }), encoding="utf-8")
    s = Settings(path)
    assert s["max_spots"] == DEFAULTS["max_spots"]
    assert s["fresh_minutes"] == DEFAULTS["fresh_minutes"]
    assert s["callsign"] == DEFAULTS["callsign"]
    assert s["alarms"] == []
    assert s["login_commands"] == ["sh/dx 30"]
    assert s["cluster_history"] == DEFAULTS["cluster_history"]
    assert s["custom_option"] == "kept"


def test_settings_drops_non_string_geometry(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"geometry": 123, "window_state": ["x"]}), encoding="utf-8")
    s = Settings(path)
    assert s["geometry"] is None and s["window_state"] is None


def test_settings_drops_invalid_spot_sort_order(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"spot_sort_order": "sideways"}), encoding="utf-8")
    s = Settings(path)
    assert s["spot_sort_order"] == DEFAULTS["spot_sort_order"]


def test_settings_list_items_of_the_wrong_kind_are_dropped(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"alarms": [{"pattern": "3Y0*"}, "JA1ABC", 7]}), encoding="utf-8")
    s = Settings(path)
    assert s["alarms"] == [{"pattern": "3Y0*"}]


def test_settings_file_is_private_on_posix(tmp_path):
    if os.name != "posix":
        pytest.skip("POSIX permissions only")
    s = Settings(tmp_path / "settings.json")
    s["password"] = "secret"
    s.save()
    mode = stat.S_IMODE((tmp_path / "settings.json").stat().st_mode)
    assert mode & 0o077 == 0  # no access for group or others
    assert not (tmp_path / "settings.json.tmp").exists()  # temporary file was renamed


def test_atomic_write_replaces_content_without_leftovers(tmp_path):
    target = tmp_path / "cty.dat"
    target.write_text("old", encoding="latin-1")
    atomic_write(target, "новый", encoding="cp1251")
    assert target.read_bytes() == "новый".encode("cp1251")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["cty.dat"]


def test_atomic_write_bytes_replaces_content_without_leftovers(tmp_path):
    from dxclient.core.settings import atomic_write_bytes

    target = tmp_path / "clusters.json"
    target.write_bytes(b"old")
    atomic_write_bytes(target, b'{"nodes": []}')
    assert target.read_bytes() == b'{"nodes": []}'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["clusters.json"]


# ---------------------------------------------------------------- filters and alarms
def test_filter_from_damaged_dict_keeps_defaults():
    assert SpotFilter.from_dict("garbage").bands == set(BAND_NAMES)
    f = SpotFilter.from_dict({"bands": None, "country_mode": "weird", "modes": ["CW", 5, None]})
    assert f.bands == set(BAND_NAMES)  # a damaged value must not hide every spot
    assert f.country_mode == "all"
    assert f.modes == {"CW"}


def test_alarm_entry_from_damaged_dict():
    e = AlarmEntry.from_dict({"pattern": None, "kind": "bogus", "bands": "20m", "modes": ["CW", 1]})
    assert e.pattern == ""
    assert e.kind == "call"
    assert e.bands == set()
    assert e.modes == {"CW"}


# ---------------------------------------------------------------- spot table index
@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _index_consistent(model):
    total = sum(len(v) for v in model._by_call.values())
    assert total == len(model.spots)
    for call, lst in model._by_call.items():
        assert all(s.dx == call for s in lst)
        assert all(any(s is x for x in model.spots) for s in lst)


def test_spot_table_index_survives_trim_and_age_removal(app):
    from dxclient.ui.spot_model import SpotTableModel

    model = SpotTableModel(max_rows=100)
    for i in range(150):  # trimming to max_rows happens inside _insert
        model.add_spot(spot_at(f"K{i % 7}AA", 14025 + i * 0.1, "1200", spotter=f"W{i}", now=NOW))
    assert len(model.spots) == 100
    _index_consistent(model)

    # age out spots of the oldest half of the table
    for s in model.spots[50:]:
        s.when = NOW - timedelta(hours=5)
    removed = model.remove_older_than(60, NOW)
    assert removed == 50
    _index_consistent(model)


def test_exact_and_dupe_lookups_use_the_index(app):
    from dxclient.ui.spot_model import SpotTableModel

    model = SpotTableModel(max_rows=200)
    first = spot_at("JA1ABC", 14025.0, "1200", spotter="W1AW", now=NOW)
    model.add_spot(first, dupe_minutes=10)
    assert model.has_exact(spot_at("JA1ABC", 14025.0, "1200", spotter="W1AW", now=NOW))
    assert not model.has_exact(spot_at("JA1ABC", 14025.0, "1201", spotter="W1AW", now=NOW))

    # same station, same band and mode, 5 minutes later → duplicate; the counter carries over
    later = spot_at("JA1ABC", 14026.0, "1205", spotter="K1XX", now=NOW)
    replaced = model.add_spot(later, dupe_minutes=10)
    assert replaced is first
    assert later.count == 2
    assert len(model.spots) == 1
    _index_consistent(model)

    # outside the window → a new row
    far = spot_at("JA1ABC", 14026.0, "1300", spotter="K1XX", now=NOW)
    assert model.add_spot(far, dupe_minutes=10) is None
    assert len(model.spots) == 2
    _index_consistent(model)


def test_clear_empties_the_index(app):
    from dxclient.ui.spot_model import SpotTableModel

    model = SpotTableModel(max_rows=200)
    model.add_spot(spot_at("JA1ABC", 14025.0, "1200", now=NOW))
    model.clear()
    assert model._by_call == {} and model.spots == []


def test_max_rows_is_clamped(app):
    from dxclient.ui.spot_model import SpotTableModel

    assert SpotTableModel(max_rows=0).max_rows == 100
    m = SpotTableModel(max_rows=500)
    m.set_max_rows(-5)
    assert m.max_rows == 100


# ---------------------------------------------------------------- Qt filter compatibility
def test_change_filter_works_with_and_without_begin_end(app):
    from PySide6.QtCore import QSortFilterProxyModel

    from dxclient.ui.qt_compat import change_filter
    from dxclient.ui.spot_model import SpotFilterProxy, SpotTableModel

    class OldProxy:  # Qt < 6.9 has no beginFilterChange
        def __init__(self):
            self.invalidated = 0

        def invalidateFilter(self):
            self.invalidated += 1

    old = OldProxy()
    seen = []
    change_filter(old, lambda: seen.append(1))
    assert seen == [1] and old.invalidated == 1

    model = SpotTableModel(max_rows=200)
    for dx in ("JA1ABC", "UA9XYZ", "JA2DEF"):
        model.add_spot(spot_at(dx, 14025.0, "1200", spotter=dx, now=NOW))
    proxy = SpotFilterProxy()
    proxy.setSourceModel(model)
    proxy.set_search("JA")
    assert proxy.rowCount() == 2
    proxy.set_search("")
    assert proxy.rowCount() == 3
    assert isinstance(proxy, QSortFilterProxyModel)
