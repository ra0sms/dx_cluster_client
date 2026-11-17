"""Correct the PC clock against the cluster.

Live 'DX de' lines carry the spot time (HHMM UTC) and arrive within seconds, so the median
difference between that time and the PC's UTC clock is the PC clock error. Spot ages are then
computed with the corrected time, so a slow / fast clock or a wrong Windows time zone does not
make every spot look old (and get dropped) or come from the future.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median


class ClockSync:
    WARN_MINUTES = 5  # show a warning when the PC clock is off by more than this

    def __init__(self, size: int = 25, min_samples: int = 5) -> None:
        self._diffs: deque[int] = deque(maxlen=size)
        self.min_samples = min_samples

    def feed(self, hhmm: str, local: datetime) -> None:
        """Add one live spot time ('1234' or '12:34') seen at local UTC time `local`."""
        hhmm = hhmm.replace(":", "")
        try:
            spot_min = int(hhmm[:2]) * 60 + int(hhmm[2:4])
        except ValueError:
            return
        local_min = local.hour * 60 + local.minute
        diff = (spot_min - local_min + 720) % 1440 - 720  # wrap to [-720, 720)
        self._diffs.append(diff)

    @property
    def calibrated(self) -> bool:
        return len(self._diffs) >= self.min_samples

    @property
    def offset_minutes(self) -> int:
        """Cluster time minus PC time, in minutes (0 until enough samples)."""
        return int(round(median(self._diffs))) if self.calibrated else 0

    @property
    def clock_is_off(self) -> bool:
        return abs(self.offset_minutes) > self.WARN_MINUTES

    def now(self, local: datetime | None = None) -> datetime:
        local = local or datetime.now(timezone.utc)
        return local + timedelta(minutes=self.offset_minutes)


@dataclass(frozen=True)
class SpotVerdict:
    drop: bool  # not shown at all
    fresh: bool  # new enough to alarm and to forward to loggers


def judge_spot(*, live: bool, calibrated: bool, age_min: float, max_age_min: int, fresh_min: int) -> SpotVerdict:
    """Decide what to do with an arriving spot.

    Until the clock is calibrated, the PC clock may be wrong by hours, so its idea of a spot's
    age means nothing. A live 'DX de' line is current by definition: keep it and treat it as fresh.
    A history line (sh/dx right after login) may be arbitrarily old: keep it, but never treat it
    as fresh, otherwise a 3-hour-old spot would raise an Alarm when the PC clock is 3 hours slow.
    Once calibrated, age is computed with the cluster time and the normal rules apply."""
    if not calibrated:
        return SpotVerdict(drop=False, fresh=live)
    drop = bool(max_age_min) and age_min > max_age_min
    fresh = not fresh_min or age_min <= fresh_min
    return SpotVerdict(drop=drop, fresh=fresh)
