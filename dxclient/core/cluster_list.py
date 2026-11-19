"""List of DX cluster nodes from clusters.ra3co.com plus user-defined nodes."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CLUSTERS_URL = "https://clusters.ra3co.com/clusters.json"
DEFAULT_CLUSTER = ("RA3CO-2", "ra3co.com", 7373)


@dataclass
class ClusterNode:
    name: str
    host: str
    port: int
    region: str = ""
    kind: str = "cluster"  # cluster / skimmer
    up: bool | None = None
    stars: float | None = None
    spots_per_min: float | None = None
    users: int | None = None
    uptime_7d: float | None = None
    custom: bool = False

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


# ---------------------------------------------------------------- tolerant accessors
# clusters.json comes from the network or from a cache file the user may have damaged,
# so every field is checked: a wrong type is treated as "missing", never as a crash.

def _dict(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _dicts(v: Any) -> list[dict]:
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _str(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def _float(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v)
    return None


def _bool(v: Any) -> bool | None:
    return v if isinstance(v, bool) else None


def parse_clusters_json(data: bytes | str) -> list[ClusterNode]:
    """Merge 'nodes' (detailed stats), 'directory' and 'directory_down' lists.

    Raises ValueError when the document is not JSON or not a JSON object."""
    try:
        d = json.loads(data)
    except (TypeError, UnicodeDecodeError) as e:
        raise ValueError(str(e)) from e
    if not isinstance(d, dict):
        raise ValueError("clusters.json is not a JSON object")
    nodes = _parse_detailed(d.get("nodes"))
    seen = {n.address.lower() for n in nodes}
    for n in (_parse_directory(d.get("directory"), True)
              + _parse_directory(d.get("directory_down"), False)):
        if n.address.lower() not in seen:
            seen.add(n.address.lower())
            nodes.append(n)
    return nodes


def _parse_directory(items: Any, default_up: bool) -> list[ClusterNode]:
    out: list[ClusterNode] = []
    for n in _dicts(items):
        host, _, port = _str(n.get("addr")).rpartition(":")
        port_i = _int(port)
        if port_i is None or not host:
            continue
        state = n.get("state")
        region = _str(n.get("region"))
        out.append(
            ClusterNode(
                name=_str(n.get("call")) or host,
                host=host,
                port=port_i,
                region=region,
                kind="skimmer" if region == "Skimmer feed" else "cluster",
                up=(state == "up") if isinstance(state, str) and state else default_up,
                stars=_float(_dict(n.get("stars")).get("value")),
                uptime_7d=_float(n.get("u")),
            )
        )
    return out


def _parse_detailed(items: Any) -> list[ClusterNode]:
    nodes: list[ClusterNode] = []
    for n in _dicts(items):
        host = _str(n.get("host"))
        port = _int(n.get("port"))
        if not host or port is None:
            continue
        status = _dict(n.get("status"))
        stars = _dict(n.get("stars"))
        spm = _dict(n.get("spots_per_min"))
        users = _dict(n.get("users"))
        uptime = _dict(n.get("uptime"))
        nodes.append(
            ClusterNode(
                name=_str(n.get("name")) or host,
                host=host,
                port=port,
                region=_str(n.get("region")),
                kind=_str(n.get("kind")) or "cluster",
                up=_bool(status.get("up")),
                stars=_float(stars.get("value")),
                spots_per_min=_float(spm.get("median")),
                users=_int(users.get("local")),
                uptime_7d=_float(uptime.get("d7")),
            )
        )
    return nodes


def parse_custom_nodes(items: Any) -> list[ClusterNode]:
    """User-defined nodes from settings. Damaged items are skipped, never raised."""
    out: list[ClusterNode] = []
    seen: set[str] = set()
    for n in _dicts(items):
        host = _str(n.get("host"))
        port = _int(n.get("port"))
        if not host or port is None or not 1 <= port <= 65535:
            continue
        key = f"{host.lower()}:{port}"
        if key in seen:
            continue
        seen.add(key)
        out.append(ClusterNode(_str(n.get("name")) or host, host, port, custom=True))
    return out


def load_cache(path: Path) -> list[ClusterNode]:
    try:
        return parse_clusters_json(path.read_bytes())
    except (OSError, ValueError):
        return []


def parse_address(text: str, default_port: int = 7300) -> tuple[str, int] | None:
    """'host:port' or 'host port' or 'host' → (host, port)."""
    text = text.strip()
    if not text:
        return None
    for sep in (":", " "):
        if sep in text:
            host, _, port = text.rpartition(sep)
            host = host.strip()
            try:
                return (host, int(port)) if host else None
            except ValueError:
                return None
    return text, default_port
