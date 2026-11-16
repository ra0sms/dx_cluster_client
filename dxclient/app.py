"""Application entry point."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from . import APP_NAME
from .core.settings import Settings
from .i18n import translator


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setDesktopFileName("dxclusterclient")
    settings = Settings()
    translator.set_language(settings["language"])

    from .ui.main_window import MainWindow

    win = MainWindow(settings)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
