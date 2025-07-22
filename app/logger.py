"""
统一日志初始化：同时输出到控制台和文件

用法示例：
    from app.logger import init_logger
    init_logger(debug=True)        # DEBUG 级别，控制台彩色输出
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import List


_LOG_FMT_CONSOLE = "%(levelname)-8s | %(message)s"
_LOG_FMT_FILE = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"


def _build_handlers(level: int, log_file: Path | None) -> List[logging.Handler]:
    """根据配置创建 console/file handler 列表"""
    handlers: list[logging.Handler] = []

    # —— 控制台 —— #
    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_LOG_FMT_CONSOLE))
    handlers.append(console)

    # —— 文件 —— #
    if log_file is None:
        log_file = Path.home() / ".videos_downloader" / "videos_downloader.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(_LOG_FMT_FILE))
    handlers.append(file_handler)

    return handlers


def init_logger(*, debug: bool = False, log_file: str | Path | None = None) -> None:
    """
    初始化根 logger。

    Parameters
    ----------
    debug : bool, default False
        True ⇒ logging.DEBUG，否则 logging.INFO
    log_file : str | Path | None
        自定义日志文件路径；None 时默认写入 ~/.videos_downloader/videos_downloader.log
    """
    level = logging.DEBUG if debug else logging.INFO

    # 先清空已有 handler，防止重复初始化
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)

    for h in _build_handlers(level, Path(log_file) if log_file else None):
        root.addHandler(h)

    # 可选：抑制某些 noisy 三方库
    logging.getLogger("asyncio").setLevel(logging.WARNING)
