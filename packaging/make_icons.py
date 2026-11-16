"""Render dxclient/data/icon.svg to packaging/icon.png (256px) and packaging/icon.ico (multi-size)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QSize  # noqa: E402
from PySide6.QtGui import QGuiApplication, QIcon  # noqa: E402

root = Path(__file__).resolve().parent.parent
app = QGuiApplication(sys.argv)
icon = QIcon(str(root / "dxclient" / "data" / "icon.svg"))
out = root / "packaging"
assert icon.pixmap(QSize(256, 256)).save(str(out / "icon.png")), "png failed"
assert icon.pixmap(QSize(256, 256)).toImage().save(str(out / "icon.ico")), "ico failed"
print("icons written to", out)
