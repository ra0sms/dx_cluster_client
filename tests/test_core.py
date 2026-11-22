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


def test_alarm_history_can_be_cleared(db):
    s = parse_spot("DX de RA3CO-#:    14025.0  3Y0J/P       CW 23 dB 25 WPM CQ             1234Z", db)
    al = AlarmList([AlarmEntry("3Y0J")])
    assert al.should_notify(s, now=0)
    assert not al.should_notify(s, now=60)
    al.clear_history()
    assert al.should_notify(s, now=60)


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
    assert parse_address("host:0") is None
    assert parse_address("host:70000") is None
    assert parse_address("[::1]:7300") == ("::1", 7300)
    assert parse_address("[::1]") == ("::1", 7300)
    assert parse_address("::1") is None


def test_strip_telnet():
    from dxclient.core.telnet_client import strip_telnet

    assert strip_telnet(b"\xff\xfb\x01Hello\xff\xff\r\nlogin: ") == b"Hello\xff\r\nlogin: "
    assert strip_telnet(b"a\xff\xfa\x18\x01\xff\xf0b") == b"ab"


def test_dx_line_format():
    from dxclient.core.spot import format_dx_line

    line = format_dx_line("RA3CO", 14025.0, "JA1ABC", "CW 599", "12:34")
    assert line == "DX de RA3CO:     14025.0  JA1ABC       CW 599                         1234Z"
    s = parse_spot(line)
    assert (s.spotter, s.freq, s.dx, s.comment, s.time) == ("RA3CO", 14025.0, "JA1ABC", "CW 599", "12:34")
    # original DX de lines are passed through unchanged; sh/dx lines are reformatted
    raw = "DX de RA3CO-#:    14025.0  JA1ABC       CW 23 dB 25 WPM CQ             1234Z"
    assert parse_spot(raw).to_dx_line() == raw
    shdx = parse_spot("   7074.0  UA0SMS      16-Nov-2026 0101Z  FT8 -12dB               <DL1ABC>")
    assert shdx.to_dx_line().startswith("DX de DL1ABC:     7074.0  UA0SMS       FT8 -12dB")


def test_mode_label():
    from dxclient.core.bands import mode_label

    assert mode_label("PHONE") == "PH"
    assert mode_label("CW") == "CW" and mode_label("FT8") == "FT8"


def test_solar_parsers():
    from dxclient.core.solar import parse_hamqsl, parse_noaa_wwv

    xml = """<solar><solardata><updated> 16 Nov 2026 1400 GMT</updated>
        <solarflux>122</solarflux><aindex> 4</aindex><kindex> 0</kindex>
        <kindexnt>No Report</kindexnt><sunspots>87</sunspots></solardata></solar>"""
    d = parse_hamqsl(xml)
    assert (d.sfi, d.a, d.k, d.ssn, d.updated) == (122, 4, 0.0, 87, "16 Nov 2026 1400 GMT")
    assert parse_hamqsl("<html>error</html>") is None

    wwv = """:Product: Geophysical Alert Message wwv.txt
:Issued: 2026 Nov 16 1205 UTC
Solar-terrestrial indices for 15 November follow.
Solar flux 122 and estimated planetary A-index 4.
The estimated planetary K-index at 1200 UTC on 16 November was 0.67."""
    d = parse_noaa_wwv(wwv)
    assert (d.sfi, d.a, d.k, d.ssn, d.updated) == (122, 4, 0.67, None, "2026 Nov 16 1205 UTC")
    assert parse_noaa_wwv("nothing here") is None


def test_geo():
    from dxclient.core.geo import bearing_distance, is_locator, locator_to_latlon

    assert is_locator("KO85") and is_locator("ko85uq") and not is_locator("KO8") and not is_locator("ZZ99")
    lat, lon = locator_to_latlon("KO85uq")
    assert abs(lat - 55.69) < 0.05 and abs(lon - 37.71) < 0.05  # Moscow
    # Moscow → Tokyo ≈ 7480 km, initial great-circle bearing ≈ 59°
    b, d = bearing_distance(55.75, 37.62, 35.68, 139.69)
    assert 7400 < d < 7600 and 57 <= b <= 61
    # London → New York ≈ 5570 km, ≈ 288°
    b, d = bearing_distance(51.5074, -0.1278, 40.7128, -74.0060)
    assert 5540 < d < 5600 and 286 <= b <= 290
    b, d = bearing_distance(0, 0, 0, 90)
    assert b == 90 and abs(d - 10008) < 5


def test_entity_coords_and_cty_version(db):
    jp = db.lookup("JA1ABC")
    assert abs(jp.lat - 36.4) < 0.01 and abs(jp.lon - 138.38) < 0.01  # east positive
    assert db.version is not None and db.version.year >= 2024


def test_spot_time_and_age():
    from datetime import datetime, timezone

    from dxclient.core.spot import spot_datetime

    now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
    assert spot_datetime("1155", None, now) == datetime(2026, 11, 16, 11, 55, tzinfo=timezone.utc)
    # just before midnight seen just after midnight → yesterday
    after_midnight = datetime(2026, 11, 17, 0, 3, tzinfo=timezone.utc)
    assert spot_datetime("2358", None, after_midnight).day == 16
    assert spot_datetime("0101", "15-Nov-2026", now) == datetime(2026, 11, 15, 1, 1, tzinfo=timezone.utc)
    s = parse_spot("DX de W1AW:     28495.0  VP8LP        SSB                             1130Z", now=now)
    assert s.age_minutes(now) == 30
    s = parse_spot("   14025.0  JA1ABC      15-Nov-2026 1200Z  CW                  <RA3CO>", now=now)
    assert s.age_minutes(now) == 24 * 60


def test_versions_and_dx_command():
    from dxclient.core.updates import is_newer, parse_version
    from dxclient.ui.send_spot import build_dx_command

    assert parse_version("v0.10.2") == (0, 10, 2)
    assert is_newer("v0.3.0", "0.2.0") and is_newer("v1.0", "0.9.9")
    assert not is_newer("v0.2.0", "0.2.0") and not is_newer("garbage", "0.2.0")
    assert build_dx_command(14025.0, "JA1ABC", "  CW   599 ") == "DX 14025.0 JA1ABC CW 599"
    assert build_dx_command(7074, "UA0SMS", "") == "DX 7074.0 UA0SMS"


def test_clock_sync():
    from datetime import datetime, timezone

    from dxclient.core.clock import ClockSync

    pc = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)
    c = ClockSync(min_samples=3)
    c.feed("1215", pc)
    c.feed("1214", pc)
    assert not c.calibrated and c.offset_minutes == 0 and c.now(pc) == pc
    c.feed("1215", pc)
    assert c.calibrated and c.offset_minutes == 15 and c.clock_is_off  # PC 15 min slow
    # wrap around midnight: PC 23:58, cluster already 00:03 → +5
    c2 = ClockSync(min_samples=1)
    c2.feed("0003", datetime(2026, 11, 17, 23, 58, tzinfo=timezone.utc))
    assert c2.offset_minutes == 5 and not c2.clock_is_off


def test_telnet_stream_helpers():
    from dxclient.core.telnet_client import split_lines, strip_telnet_stream

    # IAC WILL split between two TCP packets
    out, rest = strip_telnet_stream(b"hello\xff\xfb")
    assert out == b"hello" and rest == b"\xff\xfb"
    out, rest = strip_telnet_stream(rest + b"\x01world")
    assert out == b"world" and rest == b""
    # a Cyrillic letter split between packets is decoded correctly once the line is complete
    data = "DX de UA3AB: 14025.0 R1ABC привет 1234Z\n".encode()
    cut = data.index("и".encode()) + 1
    lines, buf = split_lines(data[:cut])
    assert lines == [] and buf
    lines, buf = split_lines(buf + data[cut:])
    assert lines == ["DX de UA3AB: 14025.0 R1ABC привет 1234Z"] and buf == b""
    # cp1251 fallback
    lines, _ = split_lines("тест\r\n".encode("cp1251"))
    assert lines == ["тест"]


def test_damaged_settings_are_kept(tmp_path):
    from dxclient.core.settings import Settings

    p = tmp_path / "settings.json"
    p.write_text("{ broken json", encoding="utf-8")
    s = Settings(p)
    assert s.load_error and not p.exists()
    backups = list(tmp_path.glob("settings.json.bad-*"))
    assert len(backups) == 1 and backups[0].read_text() == "{ broken json"
    assert s["max_spots"] == 2000  # defaults


def test_alarm_history_is_pruned():
    al = AlarmList([AlarmEntry("*")], repeat_minutes=10)
    for i in range(600):
        s = parse_spot(f"DX de W1AW:     14025.0  K{i}AA        CW                              1234Z")
        al.should_notify(s, now=float(i * 2))  # one new station every 2 s
    assert len(al._last) <= 501
