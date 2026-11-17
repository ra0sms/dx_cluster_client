"""Compatibility helpers for Qt 6.6–6.8, where QSortFilterProxyModel has no beginFilterChange()."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSortFilterProxyModel


def change_filter(proxy: QSortFilterProxyModel, change: Callable[[], None]) -> None:
    """Run `change` (which updates the filter parameters) and re-filter the proxy.

    Qt >= 6.9 has beginFilterChange/endFilterChange, which re-filter only the rows that changed.
    Older Qt needs invalidateFilter() instead."""
    if hasattr(proxy, "beginFilterChange"):
        proxy.beginFilterChange()
        change()
        proxy.endFilterChange(QSortFilterProxyModel.Direction.Rows)
    else:
        change()
        proxy.invalidateFilter()
