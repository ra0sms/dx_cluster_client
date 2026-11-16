"""List of DX cluster nodes from clusters.ra3co.com plus user-defined nodes."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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


def parse_clusters_json(data: bytes | str) -> list[ClusterNode]:
    """Merge 'nodes' (detailed stats), 'directory' and 'directory_down' lists."""
    d = json.loads(data)
    nodes = _parse_detailed(d.get("nodes", []))
    seen = {n.address.lower() for n in nodes}
    for n in _parse_directory(d.get("directory", []), True) + _parse_directory(d.get("directory_down", []), False):
        if n.address.lower() not in seen:
            seen.add(n.address.lower())
            nodes.append(n)
    return nodes


def _parse_directory(items: list, default_up: bool) -> list[ClusterNode]:
    out: list[ClusterNode] = []
    for n in items:
        addr = n.get("addr") or ""
        host, _, port = addr.rpartition(":")
        try:
            port_i = int(port)
        except ValueError:
            continue
        if not host:
            continue
        state = n.get("state")
        stars = n.get("stars") or {}
        out.append(
            ClusterNode(
                name=n.get("call") or host,
                host=host,
                port=port_i,
                region=n.get("region") or "",
                kind="skimmer" if (n.get("region") == "Skimmer feed") else "cluster",
                up=(state == "up") if state else default_up,
                stars=stars.get("value"),
                uptime_7d=n.get("u"),
            )
        )
    return out


def _parse_detailed(items: list) -> list[ClusterNode]:
    nodes: list[ClusterNode] = []
    for n in items:
        try:
            host, port = n["host"], int(n["port"])
        except (KeyError, TypeError, ValueError):
            continue
        status = n.get("status") or {}
        stars = n.get("stars") or {}
        spm = n.get("spots_per_min") or {}
        users = n.get("users") or {}
        uptime = n.get("uptime") or {}
        nodes.append(
            ClusterNode(
                name=n.get("name") or host,
                host=host,
                port=port,
                region=n.get("region") or "",
                kind=n.get("kind") or "cluster",
                up=status.get("up"),
                stars=stars.get("value"),
                spots_per_min=spm.get("median"),
                users=users.get("local"),
                uptime_7d=uptime.get("d7"),
            )
        )
    return nodes


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
