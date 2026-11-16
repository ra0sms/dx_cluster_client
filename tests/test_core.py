from pathlib import Path

import pytest

from dxclient.core.alarms import KIND_COUNTRY, AlarmEntry, AlarmList
from dxclient.core.bands import band_of, mode_of
from dxclient.core.dxcc import DxccDB
from dxclient.core.filters import COUNTRY_EXCLUDE, COUNTRY_ONLY, SpotFilter
from dxclient.core.spot import parse_spot

CTY = Path(__file__).resolve().parent.parent / "dxclient" / "data" / "cty.dat"


@pytest.fixture(scope="module")
def db():
    return DxccDB.from_file(CTY)


@pytest.mark.parametrize(
    "call,name,cont",
    [
        ("RA3CO", "European Russia", "EU"),
        ("RA0SMS", "Asiatic Russia", "AS"),
        ("UA9AA", "Asiatic Russia", "AS"),
        ("JA1ABC", "Japan", "AS"),
        ("K1ABC", "United States", "NA"),
        ("DL1ABC/P", "Fed. Rep. of Germany", "EU"),
        ("UA0/DL1ABC", "Asiatic Russia", "AS"),
        ("DL1ABC/UA0", "Asiatic Russia", "AS"),
        ("VK9XY", "Christmas Island", "OC"),
        ("R0SMS/3", "European Russia", "EU"),
    ],
)
def test_dxcc(db, call, name, cont):
    e = db.lookup(call)
    assert e is not None, call
    assert e.name == name
    assert e.continent == cont


def test_bands_modes():
    assert band_of(14025.0) == "20m"
    assert band_of(1830) == "160m"
    assert band_of(9000) is None
    assert mode_of(14025.0) == "CW"
    assert mode_of(14074.5) == "FT8"
    assert mode_of(14200.0) == "PHONE"
    assert mode_of(14200.0, "RTTY up 2") == "DIGI"
    assert mode_of(7150.0, "CW 23 dB 25 WPM CQ") == "CW"


def test_parse_dx_line(db):
    s = parse_spot("DX de RA3CO-#:    14025.0  JA1ABC       CW 23 dB 25 WPM CQ             1234Z", db)
    assert s is not None
    assert (s.freq, s.dx, s.spotter, s.time) == (14025.0, "JA1ABC", "RA3CO", "12:34")
    assert s.comment == "CW 23 dB 25 WPM CQ"
    assert s.band == "20m" and s.mode == "CW"
    assert s.country == "Japan" and s.continent == "AS"
    assert s.spotter_continent == "EU"


def test_parse_variants(db):
    s = parse_spot("DX de SV1ABCDEF-2:7074.0  UA0SMS  FT8 -12dB  0101Z KN18", db)
    assert s and s.spotter == "SV1ABCDEF" and s.mode == "FT8" and s.time == "01:01"
    s = parse_spot("DX de W1AW:     28495.0  VP8LP                                       2359Z")
    assert s and s.comment == "" and s.band == "10m"
    s = parse_spot("   14025.0  JA1ABC      16-Nov-2026 1234Z  CW 599                  <RA3CO>", db)
    assert s and s.dx == "JA1ABC" and s.spotter == "RA3CO" and s.comment == "CW 599"
    assert parse_spot("WWV de W0MU <18Z> :   SFI=120, A=5, K=1") is None
    assert parse_spot("RA3CO-2 de RA0SMS 16-Nov-2026 1234Z dxspider >") is None


def test_filter(db):
    s = parse_spot("DX de RA3CO-#:    14025.0  JA1ABC       CW 23 dB 25 WPM CQ             1234Z", db)
    f = SpotFilter()
    assert f.match(s)
    f.bands.discard("20m")
    assert not f.match(s)
    f = SpotFilter(modes={"PHONE"})
    assert not f.match(s)
    f = SpotFilter(dx_continents={"EU"})
    assert not f.match(s)
    f = SpotFilter(spotter_continents={"AS"})
    assert not f.match(s)
    f = SpotFilter(country_mode=COUNTRY_ONLY, countries={"Japan"})
    assert f.match(s)
    f = SpotFilter(country_mode=COUNTRY_EXCLUDE, countries={"Japan"})
    assert not f.match(s)
    assert SpotFilter.from_dict(f.to_dict()) == f


def test_alarms(db):
    s = parse_spot("DX de RA3CO-#:    14025.0  3Y0J/P       CW 23 dB 25 WPM CQ             1234Z", db)
    assert AlarmEntry("3Y0*").match(s)
    assert AlarmEntry("3Y0J").match(s)
    assert not AlarmEntry("3Y0").match(s)
    assert not AlarmEntry("3Y0J", bands={"40m"}).match(s)
    assert AlarmEntry("3Y0J", bands={"20m"}, modes={"CW"}).match(s)
    assert AlarmEntry(s.country, kind=KIND_COUNTRY).match(s)
    al = AlarmList([AlarmEntry("3Y0J")])
    assert al.find(s)
    assert al.should_notify(s, now=0)
    assert not al.should_notify(s, now=60)
    assert al.should_notify(s, now=700)


def test_cluster_list():
    import json

    from dxclient.core.cluster_list import parse_address, parse_clusters_json

    data = json.dumps({
        "nodes": [{"name": "RA3CO-2", "host": "ra3co.com", "port": 7373, "region": "Eastern Europe",
                   "kind": "cluster", "status": {"up": True}, "stars": {"value": 5.0},
                   "users": {"local": 3, "total": 999}}],
        "directory": [{"call": "6L0NJ", "addr": "dxc.dx.or.kr:23", "region": "Asia", "state": "up",
                       "stars": {"value": 3.5}},
                      {"call": "DUP", "addr": "RA3CO.com:7373", "state": "up"}],
        "directory_down": [{"call": "9A0DXC", "addr": "9a0dxc.hamradio.hr:8000", "state": "down"}],
    })
    nodes = parse_clusters_json(data)
    assert [n.name for n in nodes] == ["RA3CO-2", "6L0NJ", "9A0DXC"]
    assert nodes[0].users == 3 and nodes[1].port == 23 and nodes[2].up is False
    assert parse_address("ra3co.com:7373") == ("ra3co.com", 7373)
    assert parse_address("dxc.example.org 8000") == ("dxc.example.org", 8000)
    assert parse_address("host:abc") is None


def test_strip_telnet():
    from dxclient.core.telnet_client import strip_telnet

    assert strip_telnet(b"\xff\xfb\x01Hello\xff\xff\r\nlogin: ") == b"Hello\xff\r\nlogin: "
    assert strip_telnet(b"a\xff\xfa\x18\x01\xff\xf0b") == b"ab"
