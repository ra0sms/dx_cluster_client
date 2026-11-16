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
- **Spots**: a table with country, continent, band and mode (CW / SSB / DIGI / FT8). The mode comes from
  the spot comment, or from the band plan when the comment has none. Double-click a spot to look the
  callsign up on QRZ.com.
- **Filters**: applied in the client, instantly. Filter by band, mode, DX continent, spotter continent
  and country (only the selected countries, or all except them). Filter sets can be saved as presets.
- **Alarm**: a watch list of callsigns, masks (`3Y0*`, `*/MM`) or whole countries, optionally limited to
  bands and modes. The list opens in its own window. Matching spots go to a dedicated tab and trigger a
  sound and a desktop notification.
- **Console**: the raw cluster output and a command line with history (`sh/dx 20`, `sh/wwv`, …).
- **Clusters**: the list of working nodes from [clusters.ra3co.com](https://clusters.ra3co.com/).
  It is cached and refreshed hourly. You can add your own nodes.
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

- Linux: `~/.config/DXClusterClient/` (`settings.json`, `clusters.json`, updated `cty.dat`)
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
