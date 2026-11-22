"""Small helpers shared by the spot tables."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QTableView

from ..core.spot import Spot


def remove_preserving_view(
    view: QTableView,
    remove: Callable[[], int],
    current: Spot | None,
    will_remove: Callable[[Spot], bool],
) -> int:
    """Run a row-removing model operation while keeping the visible scroll position.

    QTableView selects the last remaining row when its current row disappears.  In a table
    ordered newest-first that row is the oldest spot, so the view jumps to the bottom.  Clear
    the current row first when it is about to be removed, then restore the scrollbar offset.
    """
    bar = view.verticalScrollBar()
    offset = bar.value()
    if current is not None and will_remove(current):
        selection = view.selectionModel()
        if selection is not None:
            selection.clearSelection()
        view.setCurrentIndex(QModelIndex())
    removed = remove()
    if removed:
        bar.setValue(min(offset, bar.maximum()))
    return removed
