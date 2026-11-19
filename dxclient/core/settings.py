"""Persistent settings stored as JSON in the user's config directory."""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .. import APP_NAME
from .cluster_list import DEFAULT_CLUSTER

log = logging.getLogger("dxclient")


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


DEFAULTS: dict[str, Any] = {
    "language": "ru",
    "callsign": "",
    "password": "",
    "cluster": f"{DEFAULT_CLUSTER[1]}:{DEFAULT_CLUSTER[2]}",
    "cluster_history": [f"{DEFAULT_CLUSTER[1]}:{DEFAULT_CLUSTER[2]}"],
    "custom_clusters": [],  # [{"name":..., "host":..., "port":...}]
    "login_commands": ["sh/dx 30"],
    "auto_connect": False,
    "auto_reconnect": True,
    "max_spots": 2000,
    "filter": None,
    "filter_presets": {},  # name -> filter dict
    "alarms": [],
    "alarm_sound": True,
    "alarm_popup": True,
    "alarm_repeat_minutes": 10,
    "lookup_url": "https://www.qrz.com/db/{call}",
    "server_enabled": True,  # built-in telnet server for logging programs
    "server_port": 7300,
    "server_allow_lan": False,
    "locator": "",  # own QTH locator for azimuth / distance
    "fresh_minutes": 10,  # older spots (e.g. from sh/dx at login) don't alarm and aren't forwarded
    "dupe_minutes": 10,  # merge repeated spots of a station on the same band/mode (0 = off)
    "max_age_minutes": 60,  # remove spots older than this (0 = keep)
    "alarm_max_age_hours": 24,  # remove Alarm matches older than this (0 = keep)
    "check_updates": True,
    "last_update_check": 0.0,
    "auto_update_cty": True,
    "geometry": None,
    "window_state": None,
    "spot_header_state": None,  # base64-encoded QHeaderView state
    "spot_sort_column": 0,  # COL_TIME
    "spot_sort_order": "desc",
}


def atomic_write_bytes(path: Path, data: bytes, *, mode: int = 0o644) -> None:
    """Atomically write binary data: a temporary file, fsync, rename and directory fsync."""
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())  # flush the data before the rename when supported
            except OSError:
                pass  # some filesystems do not support fsync; the rename is still atomic
        tmp.replace(path)
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    # Make the rename durable too. Windows does not allow opening a directory this way,
    # and some filesystems do not support fsync on a directory.
    try:
        dir_fd = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:
        pass
    finally:
        os.close(dir_fd)


def atomic_write(path: Path, text: str, *, encoding: str = "utf-8", mode: int = 0o644) -> None:
    """Write text via `atomic_write_bytes`, so a crash never leaves a half-written file.
    `mode` applies on POSIX systems from the moment the file is created."""
    atomic_write_bytes(path, text.encode(encoding), mode=mode)


def _is_type(value: Any, default: Any) -> bool:
    if isinstance(default, bool):
        return isinstance(value, bool)
    if isinstance(default, int):
        return isinstance(value, int) and not isinstance(value, bool)
    if isinstance(default, float):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if isinstance(default, str):
        return isinstance(value, str)
    if isinstance(default, list):
        return isinstance(value, list)
    if isinstance(default, dict):
        return isinstance(value, dict)
    return True  # None default: any JSON value


# list settings whose items must be of one kind; other items are dropped
_LIST_ITEM_TYPE = {"alarms": dict, "custom_clusters": dict, "cluster_history": str, "login_commands": str}
# settings that may be None or a string (base64 geometry / dock / header state)
_STR_OR_NONE = {"geometry", "window_state", "spot_header_state"}


def _sanitize(stored: dict[str, Any]) -> dict[str, Any]:
    """Keep only values of the expected type. A hand-edited or damaged settings file must not
    stop the application from starting: a wrong value falls back to its default."""
    out: dict[str, Any] = {}
    for key, value in stored.items():
        default = DEFAULTS.get(key)
        if key not in DEFAULTS:
            out[key] = value  # unknown keys are kept, so a newer version's settings survive
            continue
        if key in _STR_OR_NONE and value is not None and not isinstance(value, str):
            log.warning("setting %r has an unexpected value %r, using the default", key, value)
            continue
        if key == "spot_sort_order" and value not in ("asc", "desc"):
            log.warning("setting %r has an unexpected value %r, using the default", key, value)
            continue
        if not _is_type(value, default):
            log.warning("setting %r has an unexpected value %r, using the default", key, value)
            continue
        if isinstance(value, list) and key in _LIST_ITEM_TYPE:
            kind = _LIST_ITEM_TYPE[key]
            value = [v for v in value if isinstance(v, kind)]
        out[key] = value
    return out


class Settings:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config_dir() / "settings.json")
        self.data: dict[str, Any] = json.loads(json.dumps(DEFAULTS))
        self.load_error: str = ""  # set when a damaged settings file was moved aside
        self.load()

    def load(self) -> None:
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except OSError as e:
            self.load_error = str(e)
            return
        try:
            stored = json.loads(text)
            if not isinstance(stored, dict):
                raise ValueError("not a JSON object")
        except ValueError as e:
            # Keep the damaged file for the user instead of silently overwriting it with defaults.
            backup = self.path.with_name(f"{self.path.name}.bad-{datetime.now():%Y%m%d-%H%M%S}")
            try:
                self.path.replace(backup)
            except OSError:
                backup = self.path
            self.load_error = f"{e} → {backup}"
            logging.getLogger("dxclient").error("damaged settings file moved to %s: %s", backup, e)
            return
        self.data.update(_sanitize(stored))

    def save(self) -> None:
        # The file holds the cluster password, so it is readable by the owner only.
        atomic_write(self.path, json.dumps(self.data, ensure_ascii=False, indent=2), mode=0o600)

    def __getitem__(self, key: str) -> Any:
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value
