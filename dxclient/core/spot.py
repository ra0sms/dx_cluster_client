"""DX spot model and cluster line parser."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .bands import band_of, mode_of
from .dxcc import DxccDB, Entity


@dataclass
class Spot:
    freq: float  # kHz
    dx: str
    spotter: str
    comment: str
    time: str  # "HH:MM" UTC as reported by the cluster
    band: str | None = None
    mode: str = ""
    dx_entity: Entity | None = None
    spotter_entity: Entity | None = None
    received: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    alarm: bool = False
    raw: str = ""  # original cluster line

    def to_dx_line(self) -> str:
        """Spot as a standard 'DX de' line (the original one when it already was)."""
        if self.raw.startswith("DX de "):
            return self.raw
        return format_dx_line(self.spotter, self.freq, self.dx, self.comment, self.time)

    @property
    def country(self) -> str:
        return self.dx_entity.name if self.dx_entity else ""

    @property
    def continent(self) -> str:
        return self.dx_entity.continent if self.dx_entity else ""

    @property
    def spotter_continent(self) -> str:
        return self.spotter_entity.continent if self.spotter_entity else ""


# DX de RA3CO-#:    14025.0  JA1ABC       CW 23 dB 25 WPM CQ             1234Z
# DX de SV1ABC-#:14025.0  JA1ABC  comment  1234Z KN18
_DX_RE = re.compile(
    r"^DX de\s+(?P<spotter>[A-Za-z0-9/\-#_]+):?\s*"
    r"(?P<freq>\d+(?:\.\d+)?)\s+"
    r"(?P<dx>[A-Za-z0-9/]+)\s*"
    r"(?P<comment>.*?)\s*"
    r"(?P<time>\d{4})Z(?:\s+(?P<loc>[A-Ra-r]{2}\d{2}))?\s*$"
)
# sh/dx output:
#   14025.0  JA1ABC      16-Nov-2026 1234Z  CW 599                  <RA3CO>
_SHDX_RE = re.compile(
    r"^\s*(?P<freq>\d+(?:\.\d+)?)\s+(?P<dx>[A-Za-z0-9/]+)\s+"
    r"\d{1,2}-[A-Za-z]{3}-\d{4}\s+(?P<time>\d{4})Z\s*"
    r"(?P<comment>.*?)\s*<(?P<spotter>[^>]+)>\s*$"
)


def _clean_spotter(call: str) -> str:
    call = call.rstrip(":").upper()
    # strip skimmer / node suffixes: RA3CO-#, DL1ABC-2
    return re.sub(r"-(#|\d+)$", "", call)


def format_dx_line(spotter: str, freq: float, dx: str, comment: str, time: str) -> str:
    """DXSpider-style fixed-column line: DX de CALL:     14025.0  DXCALL       comment   1234Z"""
    hhmm = time.replace(":", "")[:4].rjust(4, "0")
    return f"DX de {spotter + ':':<10}{freq:>8.1f}  {dx:<12} {comment[:30]:<30} {hhmm}Z"


def parse_spot(line: str, db: DxccDB | None = None) -> Spot | None:
    line = line.rstrip()
    m = _DX_RE.match(line) or _SHDX_RE.match(line)
    if not m:
        return None
    try:
        freq = float(m.group("freq"))
    except ValueError:
        return None
    t = m.group("time")
    comment = m.group("comment").strip()
    spot = Spot(
        freq=freq,
        dx=m.group("dx").upper(),
        spotter=_clean_spotter(m.group("spotter")),
        comment=comment,
        time=f"{t[:2]}:{t[2:]}",
        raw=line,
    )
    spot.band = band_of(freq)
    spot.mode = mode_of(freq, comment)
    if db is not None:
        spot.dx_entity = db.lookup(spot.dx)
        spot.spotter_entity = db.lookup(spot.spotter)
    return spot
