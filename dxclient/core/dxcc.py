"""Callsign → DXCC entity lookup using cty.dat (https://www.country-files.com/)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CONTINENTS = ["EU", "AS", "NA", "SA", "AF", "OC", "AN"]


@dataclass(frozen=True)
class Entity:
    name: str
    prefix: str  # primary prefix, e.g. "UA9"
    continent: str
    cq: int
    itu: int


_OVERRIDE_RE = re.compile(r"\((\d+)\)|\[(\d+)\]|\{(\w+)\}|<[^>]*>|~[^~]*~")
# Suffixes that do not change the DXCC entity
_IGNORED_SUFFIXES = {"P", "M", "MM", "AM", "QRP", "A", "B", "LH", "J", "R", "T"}


class DxccDB:
    def __init__(self) -> None:
        self.entities: list[Entity] = []
        self._prefixes: dict[str, Entity] = {}
        self._exact: dict[str, Entity] = {}
        self._max_len = 0

    # ------------------------------------------------------------------ loading
    @classmethod
    def from_file(cls, path: str | Path) -> "DxccDB":
        db = cls()
        db.load_text(Path(path).read_text(encoding="latin-1"))
        return db

    def load_text(self, text: str) -> None:
        self.entities.clear()
        self._prefixes.clear()
        self._exact.clear()
        # Records end with ';'. The header line holds 8 colon-separated fields,
        # the alias list follows.
        for record in text.split(";"):
            record = record.strip()
            if not record:
                continue
            parts = record.split(":")
            if len(parts) < 9:
                continue
            name = parts[0].strip()
            try:
                cq = int(parts[1])
                itu = int(parts[2])
            except ValueError:
                continue
            cont = parts[3].strip()
            primary = parts[7].strip().lstrip("*")
            base = Entity(name, primary, cont, cq, itu)
            self.entities.append(base)
            aliases = ":".join(parts[8:]).replace("\n", " ").replace("\r", " ")
            for alias in aliases.split(","):
                alias = alias.strip()
                if not alias:
                    continue
                exact = alias.startswith("=")
                if exact:
                    alias = alias[1:]
                ent = base
                if any(c in alias for c in "([{<~"):
                    cq_o, itu_o, cont_o = cq, itu, cont
                    for m in _OVERRIDE_RE.finditer(alias):
                        if m.group(1):
                            cq_o = int(m.group(1))
                        elif m.group(2):
                            itu_o = int(m.group(2))
                        elif m.group(3):
                            cont_o = m.group(3)
                    alias = _OVERRIDE_RE.sub("", alias)
                    ent = Entity(name, primary, cont_o, cq_o, itu_o)
                alias = alias.upper()
                if exact:
                    self._exact[alias] = ent
                else:
                    self._prefixes[alias] = ent
                    self._max_len = max(self._max_len, len(alias))
        self.entities.sort(key=lambda e: e.name)

    @property
    def country_names(self) -> list[str]:
        return sorted({e.name for e in self.entities})

    # ------------------------------------------------------------------ lookup
    def _by_prefix(self, call: str) -> Entity | None:
        for n in range(min(len(call), self._max_len), 0, -1):
            ent = self._prefixes.get(call[:n])
            if ent:
                return ent
        return None

    def lookup(self, call: str) -> Entity | None:
        call = call.strip().upper()
        if not call:
            return None
        ent = self._exact.get(call)
        if ent:
            return ent
        if "/" in call:
            parts = [p for p in call.split("/") if p and p not in _IGNORED_SUFFIXES]
            if not parts:
                return None
            if len(parts) == 1:
                call = parts[0]
            else:
                # e.g. UA0/DL1ABC, DL1ABC/UA0, W1ABC/4
                first, second = parts[0], parts[-1]
                if second.isdigit() and len(second) == 1:
                    # W1ABC/4 → W4ABC-like; replace the digit in the base call
                    m = re.match(r"^([A-Z0-9]*?[A-Z])(\d)", first)
                    call = (m.group(1) + second) if m else first
                else:
                    ent = self._exact.get(first) or self._exact.get(second)
                    if ent:
                        return ent
                    call = first if len(first) <= len(second) else second
        return self._by_prefix(call)
