"""Frequency → band and mode detection."""
from __future__ import annotations

import re

# (name, low kHz, high kHz, cw_end kHz, digi_end kHz)
# cw_end: below it the segment is treated as CW;
# between cw_end and digi_end the segment is treated as DIGI; above — PHONE.
BANDS: list[tuple[str, float, float, float, float]] = [
    ("2200m", 135.7, 137.8, 137.8, 137.8),
    ("630m", 472.0, 479.0, 479.0, 479.0),
    ("160m", 1800.0, 2000.0, 1838.0, 1843.0),
    ("80m", 3500.0, 4000.0, 3570.0, 3600.0),
    ("60m", 5250.0, 5450.0, 5354.0, 5366.0),
    ("40m", 7000.0, 7300.0, 7040.0, 7060.0),
    ("30m", 10100.0, 10150.0, 10130.0, 10150.0),
    ("20m", 14000.0, 14350.0, 14070.0, 14100.0),
    ("17m", 18068.0, 18168.0, 18095.0, 18110.0),
    ("15m", 21000.0, 21450.0, 21070.0, 21150.0),
    ("12m", 24890.0, 24990.0, 24915.0, 24930.0),
    ("10m", 28000.0, 29700.0, 28070.0, 28300.0),
    ("6m", 50000.0, 54000.0, 50100.0, 50100.0),
    ("4m", 70000.0, 71000.0, 70100.0, 70100.0),
    ("2m", 144000.0, 148000.0, 144150.0, 144150.0),
    ("70cm", 420000.0, 450000.0, 432150.0, 432150.0),
    ("QO-100", 10489500.0, 10490000.0, 10489550.0, 10489550.0),
]

BAND_NAMES = [b[0] for b in BANDS]
# HF + 6m are shown as toggle buttons by default
MAIN_BANDS = ["160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m", "6m"]

MODES = ["CW", "PHONE", "DIGI", "FT8"]

# Well-known FT8/FT4 dial frequencies (kHz). A spot within ±3 kHz is FT8/FT4.
_FT8_FREQS = [
    1840, 3573, 5357, 7074, 10136, 14074, 18100, 21074, 24915, 28074, 50313, 50323,
    70154, 144174,
    3575.5, 7047.5, 10140, 14080, 18104, 21140, 24919, 28180, 50318,  # FT4
]

_MODE_WORDS = {
    "CW": "CW",
    "SSB": "PHONE", "USB": "PHONE", "LSB": "PHONE", "AM": "PHONE", "FM": "PHONE",
    "PHONE": "PHONE",
    "FT8": "FT8", "FT4": "FT8",
    "RTTY": "DIGI", "PSK": "DIGI", "PSK31": "DIGI", "PSK63": "DIGI", "BPSK": "DIGI",
    "JT65": "DIGI", "JT9": "DIGI", "Q65": "DIGI", "MSK144": "DIGI", "JS8": "DIGI",
    "OLIVIA": "DIGI", "SSTV": "DIGI", "MFSK": "DIGI", "FSK441": "DIGI", "DIGI": "DIGI",
    "WSPR": "DIGI", "VARAC": "DIGI", "FST4": "DIGI", "THOR": "DIGI", "HELL": "DIGI",
}
_WORD_RE = re.compile(r"[A-Z0-9]+")
# Skimmer comments look like "CW 23 dB 25 WPM CQ"
_WPM_RE = re.compile(r"\bWPM\b")


def band_of(freq_khz: float) -> str | None:
    for name, lo, hi, _cw, _dg in BANDS:
        if lo <= freq_khz <= hi:
            return name
    return None


def mode_of(freq_khz: float, comment: str = "") -> str:
    """Detect mode group (CW / PHONE / DIGI / FT8) from comment, falling back to band plan."""
    up = comment.upper()
    for word in _WORD_RE.findall(up):
        m = _MODE_WORDS.get(word)
        if m:
            return m
    if _WPM_RE.search(up):
        return "CW"
    for f in _FT8_FREQS:
        if abs(freq_khz - f) <= 3.0:
            return "FT8"
    for name, lo, hi, cw_end, dg_end in BANDS:
        if lo <= freq_khz <= hi:
            if freq_khz < cw_end:
                return "CW"
            if freq_khz < dg_end:
                return "DIGI"
            return "PHONE"
    return "PHONE"
