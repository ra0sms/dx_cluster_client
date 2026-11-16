"""Persistent settings stored as JSON in the user's config directory."""
from __future__ import annotations

import json
import os
import sys
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
    "geometry": None,
    "window_state": None,
}


class Settings:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (config_dir() / "settings.json")
        self.data: dict[str, Any] = json.loads(json.dumps(DEFAULTS))
        self.load()

    def load(self) -> None:
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                self.data.update(stored)
        except (OSError, ValueError):
            pass

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def __getitem__(self, key: str) -> Any:
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value: Any) -> None:
        self.data[key] = value
