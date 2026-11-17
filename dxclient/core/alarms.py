"""Watch list ("Alarm"): callsign masks / countries the user wants to be notified about."""
from __future__ import annotations

import fnmatch
import time
from dataclasses import dataclass, field

from .spot import Spot

KIND_CALL = "call"
KIND_COUNTRY = "country"


@dataclass
class AlarmEntry:
    pattern: str  # callsign or mask (JA1ABC, 3Y0*, */P) or country name
    kind: str = KIND_CALL
    bands: set[str] = field(default_factory=set)  # empty = any band
    modes: set[str] = field(default_factory=set)  # empty = any mode
    note: str = ""
    enabled: bool = True

    def match(self, s: Spot) -> bool:
        if not self.enabled:
            return False
        if self.bands and s.band not in self.bands:
            return False
        if self.modes and s.mode not in self.modes:
            return False
        if self.kind == KIND_COUNTRY:
            return s.country.lower() == self.pattern.lower()
        pat = self.pattern.upper().strip()
        if any(c in pat for c in "*?["):
            return fnmatch.fnmatchcase(s.dx, pat)
        # exact call, or the call with a portable prefix/suffix (UA0/JA1ABC, JA1ABC/P)
        return s.dx == pat or pat in s.dx.split("/")

    def to_dict(self) -> dict:
        return {
            "pattern": self.pattern,
            "kind": self.kind,
            "bands": sorted(self.bands),
            "modes": sorted(self.modes),
            "note": self.note,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AlarmEntry":
        def strs(v) -> set[str]:
            return {x for x in v if isinstance(x, str)} if isinstance(v, list) else set()

        pattern = d.get("pattern")
        kind = d.get("kind")
        note = d.get("note")
        return cls(
            pattern=pattern if isinstance(pattern, str) else "",
            kind=kind if kind in (KIND_CALL, KIND_COUNTRY) else KIND_CALL,
            bands=strs(d.get("bands")),
            modes=strs(d.get("modes")),
            note=note if isinstance(note, str) else "",
            enabled=bool(d.get("enabled", True)),
        )


class AlarmList:
    """Matches spots against entries; suppresses repeated notifications."""

    def __init__(self, entries: list[AlarmEntry] | None = None, repeat_minutes: int = 10):
        self.entries: list[AlarmEntry] = entries or []
        self.repeat_minutes = repeat_minutes
        self._last: dict[tuple[str, str | None, str], float] = {}

    def find(self, s: Spot) -> AlarmEntry | None:
        for e in self.entries:
            if e.match(s):
                return e
        return None

    def should_notify(self, s: Spot, now: float | None = None) -> bool:
        """True if this call/band/mode was not notified within repeat_minutes."""
        now = time.monotonic() if now is None else now
        window = self.repeat_minutes * 60
        key = (s.dx, s.band, s.mode)
        last = self._last.get(key)
        if last is not None and now - last < window:
            return False
        self._last[key] = now
        if len(self._last) > 500:  # forget stations not heard within the window
            self._last = {k: t for k, t in self._last.items() if now - t < window}
        return True
