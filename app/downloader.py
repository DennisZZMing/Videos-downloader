from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import TypedDict

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)


class DownloadTask(TypedDict):
    title: str
    url: str
    format_expr: str
    format_label: str


class DownloaderWorker(QThread):
    progress_sig = Signal(float)
    status_sig = Signal(str)
    finished_sig = Signal(bool, object)

    def __init__(self, tasks: list[DownloadTask], out_dir: Path, cookies_browser: str | None = None):
        super().__init__()
        self._tasks = tasks
        self._out_dir = out_dir
        self._cookies_browser = cookies_browser

    def run(self) -> None:
        try:
            for index, task in enumerate(self._tasks, 1):
                self.status_sig.emit(
                    f"正在下载 ({index}/{len(self._tasks)})：{task['title']} - {task['format_label']}"
                )
                self.progress_sig.emit(0.0)
                self._download_one(task)
            self.progress_sig.emit(1.0)
            self.finished_sig.emit(True, None)
        except Exception as exc:  # pragma: no cover
            log.exception("download failed")
            self.finished_sig.emit(False, str(exc))

    def _download_one(self, task: DownloadTask) -> None:
        from yt_dlp.utils import DownloadError

        errors: list[str] = []
        candidates = self._format_candidates(task["format_expr"])
        for attempt, format_expr in enumerate(candidates, 1):
            before = self._output_snapshot()

            try:
                self._run_ytdlp(format_expr, task["url"])
                return
            except DownloadError as exc:
                errors.append(str(exc))
                self._cleanup_failed_attempt(before)
                if attempt < len(candidates):
                    self.status_sig.emit("当前格式下载失败，正在尝试备用格式...")
                    log.warning("download failed with format %s; trying fallback", format_expr)
                else:
                    log.warning("download failed with format %s", format_expr)

        raise DownloadError(_friendly_ytdlp_error(errors[-1] if errors else "download failed"))

    def _format_candidates(self, format_expr: str) -> list[str]:
        candidates = [format_expr]
        fallback = "best"
        if fallback not in candidates:
            candidates.append(fallback)
        return candidates

    def _run_ytdlp(self, format_expr: str, url: str) -> None:
        from yt_dlp.utils import DownloadError

        cmd = [
            sys.executable,
            "-m",
            "yt_dlp",
            "-f",
            format_expr,
            "--no-mtime",
            "--newline",
            "--no-playlist",
            "--merge-output-format",
            "mp4",
            "-N",
            "4",
            "-P",
            str(self._out_dir),
            "-o",
            "%(title).200B [%(id)s].%(ext)s",
        ]
        if self._cookies_browser:
            cmd.extend(["--cookies-from-browser", self._cookies_browser])
        cmd.append(url)

        safe_cmd = ["***" if item == self._cookies_browser else item for item in cmd]
        log.debug("run yt-dlp: %s", " ".join(safe_cmd))

        with subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        ) as proc:
            assert proc.stdout is not None
            tail: list[str] = []
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                self._handle_ytdlp_line(line)
                tail.append(line)
                tail = tail[-20:]

            proc.wait()
            if proc.returncode:
                message = "\n".join(tail) or f"yt-dlp exit code {proc.returncode}"
                raise DownloadError(_friendly_ytdlp_error(message))

    def _handle_ytdlp_line(self, line: str) -> None:
        log.debug("yt-dlp: %s", line)
        if line.startswith("WARNING:"):
            log.warning("yt-dlp: %s", line)
        elif line.startswith("ERROR:"):
            log.error("yt-dlp: %s", line)

        match = re.search(r"\[download\]\s+(\d{1,3}(?:\.\d+)?)%", line)
        if match:
            self.progress_sig.emit(float(match.group(1)) / 100.0)
            return

        if line.startswith("[download] Destination:"):
            filename = line.split("Destination:", 1)[1].strip()
            self.status_sig.emit(f"下载中：{Path(filename).name}")
        elif line.startswith("[Merger]") or line.startswith("[ExtractAudio]"):
            self.status_sig.emit("正在合并音视频或转换封装...")

    def _output_snapshot(self) -> set[Path]:
        if not self._out_dir.exists():
            return set()
        return {path for path in self._out_dir.iterdir() if path.is_file()}

    def _cleanup_failed_attempt(self, before: set[Path]) -> None:
        if not self._out_dir.exists():
            return

        for path in self._out_dir.iterdir():
            if path in before or not path.is_file():
                continue
            try:
                if path.suffix in {".part", ".ytdl", ".temp"} or path.stat().st_size == 0:
                    path.unlink()
            except OSError:
                log.debug("failed to clean partial download: %s", path, exc_info=True)


def _friendly_ytdlp_error(message: str) -> str:
    lower = message.lower()
    hints: list[str] = []

    if "http error 412" in lower and "bilibili" in lower:
        hints.append("B 站接口返回 412，通常是风控、登录态或 yt-dlp 版本适配问题。请更新 yt-dlp，并尝试启用浏览器 cookies。")
    if "failed to load cookies" in lower:
        hints.append("读取浏览器 cookies 失败。请确认浏览器已安装并登录，必要时关闭浏览器后重试。")
    if "ffmpeg" in lower or "ffprobe" in lower:
        hints.append("未找到 ffmpeg，或 ffmpeg 无法正常运行。需要合并音视频或转为 MP4 时必须安装 ffmpeg。")
    if "sign in" in lower or "login" in lower or "cookies" in lower:
        hints.append("该视频可能需要登录或浏览器 cookies。")
    if "private video" in lower or "not available" in lower or "unavailable" in lower:
        hints.append("该视频可能不可访问、被设为私有、下架，或受到地区限制。")
    if "requested format is not available" in lower or "format is not available" in lower:
        hints.append("所选清晰度或格式不可用，可以尝试选择“最佳质量”。")
    if "http error 403" in lower or "forbidden" in lower:
        hints.append("服务器拒绝访问，可能是链接过期、需要登录、地区限制或反爬策略导致。")
    if "timed out" in lower or "timeout" in lower or "connection" in lower:
        hints.append("网络连接超时或中断，请检查网络后重试。")

    if not hints:
        return message

    return "\n".join([*hints, "", "yt-dlp 原始错误：", message])


__all__ = ["DownloadTask", "DownloaderWorker"]
