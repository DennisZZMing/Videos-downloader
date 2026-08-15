from __future__ import annotations

import logging
import sys
from pathlib import Path

_LOG_FMT_CONSOLE = "%(levelname)-8s | %(message)s"
_LOG_FMT_FILE = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"


def _build_handlers(level: int, log_file: Path | None) -> list[logging.Handler]:
    handlers: list[logging.Handler] = []

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_LOG_FMT_CONSOLE))
    handlers.append(console)

    if log_file is None:
        log_file = Path.home() / ".videos_downloader" / "videos_downloader.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_LOG_FMT_FILE))
    handlers.append(file_handler)

    return handlers


def init_logger(*, debug: bool = False, log_file: str | Path | None = None) -> None:
    level = logging.DEBUG if debug else logging.INFO

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    for handler in _build_handlers(level, Path(log_file) if log_file else None):
        root.addHandler(handler)

    logging.getLogger("asyncio").setLevel(logging.WARNING)
