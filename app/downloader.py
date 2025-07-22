"""
在独立 QThread 中运行 yt-dlp，向 GUI 回传进度 / 状态
"""
from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)

# yt-dlp 在子进程中运行，可避免与 Qt 事件循环冲突
YTDLP_BIN = sys.executable  # 若你愿意可改为本地的 yt-dlp.exe
#YTDLP_ARGS_BASE = ["-f", "best", "-N", "4", "--no-mtime"]
YTDLP_ARGS_BASE = ["--no-mtime"]

QUALITY_PRESETS = {
    "best":  "best",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p":  "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "audio": "bestaudio/best",
}


class DownloaderWorker(QThread):
    progress_sig = Signal(float)  # 0.0 – 1.0
    status_sig = Signal(str)
    finished_sig = Signal(bool, object)  # success, err_msg

    _PROGRESS_RE = re.compile(
        r"\[download\]\s+(\d{1,3}\.\d)%\s+of\s+.*?\s+at\s+.*?\s+ETA\s+.*"
    )

    def __init__(self, urls: str, out_dir: Path):
        super().__init__()
        self._urls = urls
        self._out_dir = out_dir
        # self._quality = quality

    # ---------- 线程入口 ----------
    def run(self) -> None:  # noqa: D401
        try:
            for idx, (url, q) in enumerate(self._urls, 1):
                self.status_sig.emit(f"({idx}/{len(self._urls)}) 开始下载：{url}")
                self._invoke_ytdlp(url, q)
            self.finished_sig.emit(True, None)
        except Exception as exc:  # pragma: no cover
            log.exception("Download failed")
            self.finished_sig.emit(False, str(exc))

    # ---------- 私有 ----------
    def _invoke_ytdlp(self, url:str, quality: str) -> None:
        fmt_expr = QUALITY_PRESETS.get(quality, "best")
        cmd: list[str | Path] = [
            #YTDLP_BIN,
            sys.executable,
            "-m",  # 调用模块：python -m yt_dlp …
            "yt_dlp",
            "-f",
            fmt_expr,
            *YTDLP_ARGS_BASE,
            "-P",
            str(self._out_dir),
            "--newline",  # 强制逐行输出，方便解析进度
            url,
        ]
        log.debug("Run: %s", " ".join(map(str, cmd)))

        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",          # ★ 指定解码用 UTF-8
            errors="replace",          # ★ 遇到极端字符用 � 占位而不是炸
            bufsize=1,  # 行缓冲
            # universal_newlines=True,
        ) as proc:
            for line in proc.stdout:  # type: ignore[arg-type]
                self._handle_output(line.strip())

            proc.wait()
            if proc.returncode != 0:  # pragma: no cover
                raise RuntimeError(f"yt-dlp exit code {proc.returncode}")

    def _handle_output(self, line: str) -> None:
        log.debug("yt-dlp: %s", line)
        # 解析进度百分比
        m = self._PROGRESS_RE.match(line)
        if m:
            percent = float(m.group(1)) / 100.0
            self.progress_sig.emit(percent)
            self.status_sig.emit(f"下载中… {m.group(1)}%")
        elif line.startswith("[download] Destination:"):
            fname = line.split("Destination:", 1)[1].strip()
            self.status_sig.emit(f"保存为：{Path(fname).name}")
        elif line.startswith("[download]"):
            # 其余 download 消息
            pass
        elif line.startswith("ERROR:"):
            raise RuntimeError(line)
