"""Maidenhead locator, great-circle bearing and distance."""
from __future__ import annotations

import math
import re

EARTH_RADIUS_KM = 6371.0
_LOC_RE = re.compile(r"^[A-R]{2}\d{2}([A-X]{2})?$", re.I)


def is_locator(text: str) -> bool:
    return bool(_LOC_RE.match(text.strip()))


def locator_to_latlon(loc: str) -> tuple[float, float] | None:
    """Centre of a 4- or 6-character Maidenhead square → (lat, lon)."""
    loc = loc.strip().upper()
    if not _LOC_RE.match(loc):
        return None
    lon = (ord(loc[0]) - 65) * 20 - 180 + int(loc[2]) * 2
    lat = (ord(loc[1]) - 65) * 10 - 90 + int(loc[3])
    if len(loc) == 6:
        lon += (ord(loc[4]) - 65) * (2 / 24) + 1 / 24
        lat += (ord(loc[5]) - 65) * (1 / 24) + 1 / 48
    else:
        lon += 1
        lat += 0.5
    return lat, lon


def bearing_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[int, int]:
    """Initial great-circle bearing (degrees 0..359) and distance (km) from point 1 to point 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    bearing = (math.degrees(math.atan2(x, y)) + 360) % 360
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    dist = 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))
    return int(round(bearing)) % 360, int(round(dist))
