# DX Cluster Client

**English** | [Русский](README.ru.md)

A DX cluster telnet client for Linux and Windows, in the spirit of VE7CC CC User.
Written in Python with PySide6 (Qt 6).

## Download

Ready-to-run builds are on the [Releases](https://github.com/ra0sms/dx_cluster_client/releases) page:

- **Linux**: `DXClusterClient-<version>-x86_64.AppImage`. Make it executable (`chmod +x`) and run it.
- **Windows**: `DXClusterClient-<version>-win64.exe`. A single file, no installation needed.

## Features

- **Connection**: connects to a telnet DX cluster, by default **RA3CO-2 (`ra3co.com:7373`)**. Logs in
  with your callsign, sends your commands after login, keeps the connection alive and reconnects
  automatically.
- **Spots**: a table with country, continent, band and mode (CW / PH / DIGI / FT8, where PH means phone:
  SSB, AM or FM). The mode comes from
  the spot comment, or from the band plan when the comment has none. Double-click a spot to look the
  callsign up on QRZ.com.
- **Spot handling**: repeated spots of a station on the same band and mode are merged into one row
  with a counter. Spots older than a set age (60 min by default) are removed, and from half that age
  they are greyed out. Old spots, such as those from `sh/dx` right after login, are shown but do not
  trigger Alarm and are not forwarded to loggers.
- **Azimuth and distance**: set your QTH locator in *Settings* to get the beam heading and distance to
  each DX country.
- **Search** by callsign or country above the spot table, and **Send spot…** to post your own spot
  (also from a spot's right-click menu).
- **Filters**: applied in the client, instantly. Filter by band, mode, DX continent, spotter continent
  and country (only the selected countries, or all except them). Filter sets can be saved as presets.
- **Alarm**: a watch list of callsigns, masks (`3Y0*`, `*/MM`) or whole countries, optionally limited to
  bands and modes. The list opens in its own window. Matching spots go to a dedicated tab and trigger a
  sound and a desktop notification.
- **Built-in telnet server** for logging programs (N1MM, Log4OM, …): connect to `127.0.0.1:7300`
  and receive only the spots that pass the program's current filters. It accepts any callsign at
  `login:` and supports `sh/dx [n]` and `bye`. The port, and whether connections from the local network
  are allowed, are set in *Settings*.
- **Solar indices**: SFI, A, K and the sunspot number in the toolbar, refreshed hourly from
  [hamqsl.com](https://www.hamqsl.com/solar.html) (N0NBH), with NOAA SWPC as a fallback. Elevated A and K
  values are highlighted.
- **Console**: the raw cluster output and a command line with history (`sh/dx 20`, `sh/wwv`, …).
- **Clusters**: the list of working nodes from [clusters.ra3co.com](https://clusters.ra3co.com/).
  It is cached and refreshed hourly. You can add your own nodes.
- **Updates**: the app checks GitHub for a new version once a day and refreshes `cty.dat` automatically
  when it is older than 30 days. Both can be turned off in *Settings*.
- **Error log**: `dxclient.log` in the settings folder (*Help → Open settings and log folder*).
  Unexpected errors are also shown in a dialog.
- **Language**: English and Russian, switchable at runtime from the *Language* menu.
- **Countries**: resolved with `cty.dat` from [country-files.com](https://www.country-files.com/).
  Update it with *File → Update cty.dat*.

## Running from source

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m dxclient          # or: dxclusterclient
pytest                      # tests
```

## Building

Build output goes to `dist/release/`.

**Linux AppImage.** Build it on an older distribution: an AppImage runs only on systems whose glibc is
the same version or newer than the one it was built on.

```bash
bash packaging/build_appimage.sh   # PYTHON=... picks the interpreter, SKIP_PIP=1 skips installing deps
```

**Windows exe**, on Windows:

```bat
pip install pyside6 pyinstaller
pyinstaller dxclusterclient.spec
```

Or on Linux under Wine in a container: `bash packaging/build_windows.sh`.

**GitHub Actions** (`.github/workflows/build.yml`): pushing a `v*` tag builds the AppImage
(on ubuntu-22.04) and the exe (on windows-latest) and attaches both to a GitHub release.

## Settings location

- Linux: `~/.config/DXClusterClient/` (`settings.json`, `clusters.json`, updated `cty.dat`, `dxclient.log`)
- Windows: `%APPDATA%\DXClusterClient\`

## Project layout

```
dxclient/
  core/      telnet client, spot parser, DXCC (cty.dat), bands/modes, filters, alarms, cluster list
  ui/        main window and tabs (PySide6)
  i18n.py    ru/en translations
  data/      cty.dat, icon, alarm sound
packaging/   AppImage / Windows build scripts, icons, .desktop file
tests/       pytest tests
```

## License

[MIT](LICENSE). The bundled `cty.dat` is provided by [country-files.com](https://www.country-files.com/).
