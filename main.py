from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from src.audio.metadata import scan_music
from src.config.settings import SettingsStore
from src.ui.main_window import MainWindow
from src.ui.theme import APP_STYLE
from src.utils.logger import configure_logging


def main() -> int:
    root = Path(__file__).resolve().parent
    for directory in (root / "music", root / "assets", root / "logs"):
        directory.mkdir(parents=True, exist_ok=True)
    configure_logging(root / "logs")
    settings_store = SettingsStore(root / "settings.json")
    app = QApplication(sys.argv)
    app.setApplicationName("HandWave Music")
    app.setOrganizationName("Arjunren")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(APP_STYLE)
    window = MainWindow(root, scan_music(root / "music"), settings_store.load(), settings_store)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
