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
}


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
        self.data.update(stored)

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def __getitem__(self, key: str) -> Any:
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value
