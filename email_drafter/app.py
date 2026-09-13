"""Desktop application startup."""

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from .gui.main_window import EmailDrafterGUI


def main(argv=None):
    app = QApplication(sys.argv if argv is None else argv)
    window = EmailDrafterGUI()
    window.show()
    if not window.has_any_api_key():
        QTimer.singleShot(0, window.open_settings)
    return app.exec()
