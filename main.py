from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app.gui import MainWindow
from app.logger import init_logger

log = logging.getLogger(__name__)


def resource_path(rel: str | Path) -> Path:
    base = Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent
    return base / rel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="videos-downloader")
    parser.add_argument("-o", "--output", type=Path, help="预设下载目录")
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def excepthook(exc_type, exc_value, exc_tb):  # noqa: N802
    log.exception("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))


def main() -> None:
    args = parse_args()
    init_logger(debug=args.debug)
    sys.excepthook = excepthook

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    qss_file = resource_path("resources/dark.qss")
    if qss_file.exists():
        app.setStyleSheet(qss_file.read_text(encoding="utf-8"))
    else:
        log.warning("dark.qss not found: %s", qss_file)

    window = MainWindow()
    if args.output:
        window.output_edit.setText(str(args.output.expanduser()))
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
