"""Client-side spot filters."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .bands import BAND_NAMES, MODES
from .dxcc import CONTINENTS
from .spot import Spot

COUNTRY_ALL = "all"
COUNTRY_ONLY = "only"
COUNTRY_EXCLUDE = "exclude"


@dataclass
class SpotFilter:
    bands: set[str] = field(default_factory=lambda: set(BAND_NAMES))
    modes: set[str] = field(default_factory=lambda: set(MODES))
    dx_continents: set[str] = field(default_factory=lambda: set(CONTINENTS))
    spotter_continents: set[str] = field(default_factory=lambda: set(CONTINENTS))
    country_mode: str = COUNTRY_ALL
    countries: set[str] = field(default_factory=set)
    show_unknown_band: bool = False

    def match(self, s: Spot) -> bool:
        if s.band is None:
            if not self.show_unknown_band:
                return False
        elif s.band not in self.bands:
            return False
        if s.mode not in self.modes:
            return False
        # Unknown continent (entity not resolved) passes the continent filters
        if s.continent and s.continent not in self.dx_continents:
            return False
        if s.spotter_continent and s.spotter_continent not in self.spotter_continents:
            return False
        if self.country_mode == COUNTRY_ONLY and s.country not in self.countries:
            return False
        if self.country_mode == COUNTRY_EXCLUDE and s.country in self.countries:
            return False
        return True

    # ---------------------------------------------------------------- persist
    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, set):
                d[k] = sorted(v)
        return d

    @classmethod
    def from_dict(cls, d: dict | None) -> "SpotFilter":
        f = cls()
        if not d:
            return f
        for k in ("bands", "modes", "dx_continents", "spotter_continents", "countries"):
            if k in d:
                setattr(f, k, set(d[k]))
        f.country_mode = d.get("country_mode", COUNTRY_ALL)
        f.show_unknown_band = bool(d.get("show_unknown_band", False))
        return f
