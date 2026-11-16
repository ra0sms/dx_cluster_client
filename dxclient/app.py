"""Application entry point."""
from __future__ import annotations

import logging
import logging.handlers
import sys
import traceback

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_NAME, __version__
from .core.settings import Settings, config_dir
from .i18n import tr, translator

log = logging.getLogger("dxclient")


def log_path():
    return config_dir() / "dxclient.log"


def setup_logging() -> None:
    handler = logging.handlers.RotatingFileHandler(log_path(), maxBytes=1_000_000, backupCount=3,
                                                   encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    if sys.stderr is not None:  # windowed exe has no stderr
        root.addHandler(logging.StreamHandler())


_dialog_open = False


def _excepthook(exc_type, exc, tb) -> None:
    """Log uncaught exceptions (also those raised inside Qt slots) and show them once."""
    global _dialog_open
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    log.error("Uncaught exception:\n%s", text)
    if _dialog_open or QApplication.instance() is None:
        return
    _dialog_open = True
    try:
        box = QMessageBox(QMessageBox.Icon.Critical, tr("Error"),
                          tr("An unexpected error occurred. Details are saved to the log:\n{path}",
                             path=log_path()))
        box.setDetailedText(text)
        box.exec()
    finally:
        _dialog_open = False


def main() -> int:
    setup_logging()
    log.info("%s %s starting (Python %s)", APP_NAME, __version__, sys.version.split()[0])
    sys.excepthook = _excepthook
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setDesktopFileName("dxclusterclient")
    settings = Settings()
    translator.set_language(settings["language"])

    from .ui.main_window import MainWindow

    win = MainWindow(settings)
    win.show()
    QTimer.singleShot(0, lambda: log.info("main window shown"))
    code = app.exec()
    log.info("exit code %s", code)
    return code


if __name__ == "__main__":
    sys.exit(main())
