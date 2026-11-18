# Changelog

**English** | [Русский](CHANGELOG.ru.md)

All notable changes to DX Cluster Client are documented in this file. The format is inspired by
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Changelog in English and Russian.
- Screenshots in the English and Russian READMEs.

### Changed

- READMEs refreshed for 0.3.2: Alarm behavior, duplicate counter, cluster list refresh, project layout.

## [0.3.2] — 2026-11-17

### Added

- Alarm: callsigns and masks are uppercased while typing; country names keep their normal case.
- Alarm: the watch list can be sorted by rule name with the *Sort by name* button or by clicking the
  *Pattern* header; the order is saved.
- Alarm: duplicate rules are rejected with a warning (same kind and pattern, case-insensitive);
  editing a rule is not a duplicate of itself.

### Fixed

- History spots from `sh/dx` are kept but never treated as fresh until the PC clock is calibrated:
  they no longer raise Alarm, are not forwarded to loggers, and are not removed by age.
- Damaged `clusters.json` and `settings.json` no longer prevent the application from starting;
  wrong-typed settings fall back to defaults and bad list items are dropped.
- `settings.json` is written atomically with owner-only permissions (`0600`); `cty.dat` updates are
  atomic too.
- Filtering and searching work on PySide6 6.6–6.8 (compatibility with Qt versions without
  `beginFilterChange`).
- The spot table uses a callsign index for exact and duplicate lookups, removes rows in contiguous
  ranges, and clamps the maximum number of rows.
- Fixed the test-suite teardown crash on PySide6 6.12.

## [0.3.1] — 2026-11-17

### Added

- Clock correction: spot ages are computed with the cluster time (median offset of live spots);
  the status bar warns when the PC clock differs by more than 5 minutes.
- Connection watchdog: the client reconnects after 15 minutes without data.
- Alarm matches older than 24 hours are removed automatically (configurable); a Clear button on the
  Spots tab and *View → Clear all spots and Alarm matches* (Ctrl+L).

### Changed

- The daily update check and the `cty.dat` freshness check are re-evaluated hourly during long
  sessions.
- Line decoding works at the byte level: UTF-8 characters and telnet commands split across TCP
  packets are handled, with a cp1251 fallback.
- The telnet server prompt uses a locale-independent date.

### Fixed

- Identical spots (for example, `sh/dx` repeated after a reconnect) are ignored.
- A damaged `settings.json` is kept as a backup and reported instead of being silently overwritten.
- The Alarm notification history is pruned so it does not grow without bound.

## [0.3.0] — 2026-11-16

### Added

- Solar indices (SFI, A, K and sunspot number) in the toolbar, refreshed hourly from hamqsl.com with
  NOAA SWPC as a fallback.
- Azimuth and distance columns based on the QTH locator from Settings.
- Search by callsign or country above the spot table.
- *Send spot…* dialog, also available from a spot's context menu.
- Error log `dxclient.log` and a dialog for uncaught exceptions.
- Daily GitHub update check and automatic `cty.dat` update when it is older than 30 days.
- Tabbed Settings dialog.

### Changed

- The mode column, filter buttons and Alarm list show **PH** instead of SSB/AM/FM.
- Old spots (for example, from `sh/dx` after login) are shown but do not trigger Alarm and are not
  forwarded to loggers; spots older than the configured age are removed and greyed out from half
  that age.
- Repeated spots of a station on the same band and mode are merged into one row with a counter.
- Tests for the new logic.

## [0.2.0] — 2026-11-16

### Added

- Built-in telnet server for logging programs (N1MM, Log4OM, …) on `127.0.0.1:7300`; the port and LAN
  access are configurable.
- The server re-publishes only the spots that pass the current filters.
- Minimal cluster dialogue: callsign prompt at `login:`, `sh/dx [n]` for filtered history, `bye` to
  disconnect.
- Status bar shows the server address and client count, or a busy-port error.

### Changed

- Original `DX de` lines are forwarded unchanged; `sh/dx` lines are reformatted.
- Tests for line formatting and the server; English and Russian READMEs updated.

## [0.1.0] — 2026-11-16

### Added

- First public release.
- Telnet DX cluster client with the default cluster RA3CO-2 (`ra3co.com:7373`), automatic login and
  reconnect.
- Filters by band, mode, DX and spotter continent, and country; saved filter presets.
- Alarm watch list of callsigns, masks or countries, with sound and desktop notifications.
- Cluster list from clusters.ra3co.com plus custom nodes.
- English and Russian interface.
- Linux AppImage and Windows single-file builds; MIT license.
