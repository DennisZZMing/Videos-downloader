# app/formats_fetcher.py
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import List, TypedDict

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)

class VideoItem(TypedDict):
    title: str
    url: str          # webpage_url
    duration: int | None   # 秒；可能为 None

class FormatsFetcher(QThread):
    result_sig = Signal(list)   # list[VideoItem] 解析成功 → GUI
    error_sig = Signal(str)     # 异常文本 → GUI

    def __init__(self, url: str):
        super().__init__()
        self._url = url.strip()

    # --------- 线程入口 ---------
    def run(self) -> None:
        try:
            items = self._fetch()
            self.result_sig.emit(items)
        except Exception as e:  # pragma: no cover
            log.exception("fetch formats failed")
            self.error_sig.emit(str(e))

    # --------- 私有 ---------
    def _fetch(self) -> List[VideoItem]:
        # 调用: python -m yt_dlp -J --flat-playlist URL
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "-J",               # JSON
            "--flat-playlist",  # 只列条目，快
            self._url,
        ]
        try:
            out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            # 把 yt-dlp 的报错内容打印到日志 & 转给 GUI
            log.error("yt-dlp error output:\n%s", e.output)
            raise RuntimeError(e.output.strip())  # 让 GUI 弹窗
        info = json.loads(out)
        #out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
        #info = json.loads(out)

        # 单视频时 info 直接是条目；播放列表有 "entries"
        entries = info.get("entries", [info])
        result: list[VideoItem] = []
        for ent in entries:
            result.append(
                VideoItem(
                    title=ent.get("title", "(无标题)"),
                    url=ent.get("url") or ent.get("webpage_url"),
                    duration=ent.get("duration"),
                )
            )
        return result
