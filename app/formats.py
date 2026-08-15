from __future__ import annotations

import logging
from typing import Any, TypedDict

from PySide6.QtCore import QThread, Signal

log = logging.getLogger(__name__)


class VideoFormat(TypedDict):
    label: str
    format_id: str
    download_expr: str
    height: int | None
    ext: str | None
    filesize: int | None


class VideoItem(TypedDict):
    title: str
    url: str
    duration: int | None
    formats: list[VideoFormat]


QUALITY_PRESETS: list[VideoFormat] = [
    {
        "label": "最佳质量",
        "format_id": "best",
        "download_expr": "best",
        "height": None,
        "ext": None,
        "filesize": None,
    },
    {
        "label": "最高 1080p",
        "format_id": "1080p",
        "download_expr": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "height": 1080,
        "ext": None,
        "filesize": None,
    },
    {
        "label": "最高 720p",
        "format_id": "720p",
        "download_expr": "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "height": 720,
        "ext": None,
        "filesize": None,
    },
    {
        "label": "最高 480p",
        "format_id": "480p",
        "download_expr": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
        "height": 480,
        "ext": None,
        "filesize": None,
    },
    {
        "label": "仅音频",
        "format_id": "audio",
        "download_expr": "bestaudio/best",
        "height": None,
        "ext": None,
        "filesize": None,
    },
]


class YtdlpLogBridge:
    def debug(self, msg: str) -> None:
        log.debug("yt-dlp: %s", msg)

    def info(self, msg: str) -> None:
        log.info("yt-dlp: %s", msg)

    def warning(self, msg: str) -> None:
        log.warning("yt-dlp: %s", msg)

    def error(self, msg: str) -> None:
        log.error("yt-dlp: %s", msg)


def _duration_text(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02}:{secs:02}"
    return f"{minutes}:{secs:02}"


def _size_text(size: int | None) -> str:
    if not size:
        return ""
    mib = size / 1024 / 1024
    if mib >= 1024:
        return f"{mib / 1024:.2f} GiB"
    return f"{mib:.1f} MiB"


def _entry_url(entry: dict[str, Any]) -> str | None:
    url = entry.get("webpage_url") or entry.get("original_url")
    if url:
        return str(url)

    raw_url = entry.get("url")
    if not raw_url:
        return None
    if str(raw_url).startswith(("http://", "https://")):
        return str(raw_url)
    return None


def _format_label(fmt: dict[str, Any]) -> str:
    height = fmt.get("height")
    width = fmt.get("width")
    fps = fmt.get("fps")
    ext = fmt.get("ext") or "?"
    vcodec = fmt.get("vcodec")
    acodec = fmt.get("acodec")
    filesize = fmt.get("filesize") or fmt.get("filesize_approx")

    parts: list[str] = []
    if height:
        resolution = f"{height}p"
        if width:
            resolution += f" ({width}x{height})"
        parts.append(resolution)
    elif vcodec == "none":
        abr = fmt.get("abr")
        parts.append(f"音频 {abr:.0f}k" if abr else "音频")
    else:
        parts.append("未知清晰度")

    if fps:
        parts.append(f"{fps:g}fps")
    parts.append(ext)

    codecs: list[str] = []
    if vcodec and vcodec != "none":
        codecs.append("视频")
    if acodec and acodec != "none":
        codecs.append("音频")
    if codecs:
        parts.append("+".join(codecs))

    size = _size_text(filesize)
    if size:
        parts.append(size)
    return " / ".join(parts)


def _download_expr(fmt: dict[str, Any]) -> str:
    format_id = str(fmt["format_id"])
    has_video = fmt.get("vcodec") != "none"
    has_audio = fmt.get("acodec") != "none"
    if has_video and not has_audio:
        return f"{format_id}+bestaudio/best"
    return format_id


def build_format_options(info: dict[str, Any]) -> list[VideoFormat]:
    formats: list[VideoFormat] = [dict(item) for item in QUALITY_PRESETS]
    seen: set[str] = {item["download_expr"] for item in formats}

    raw_formats = info.get("formats") or []
    sorted_formats = sorted(
        raw_formats,
        key=lambda f: (
            f.get("height") or 0,
            f.get("tbr") or 0,
            f.get("abr") or 0,
        ),
        reverse=True,
    )

    for fmt in sorted_formats:
        if not fmt.get("format_id"):
            continue
        if fmt.get("vcodec") == "none" and fmt.get("acodec") == "none":
            continue

        expr = _download_expr(fmt)
        if expr in seen:
            continue
        seen.add(expr)

        formats.append(
            {
                "label": _format_label(fmt),
                "format_id": str(fmt["format_id"]),
                "download_expr": expr,
                "height": fmt.get("height"),
                "ext": fmt.get("ext"),
                "filesize": fmt.get("filesize") or fmt.get("filesize_approx"),
            }
        )

    return formats


class FormatsFetcher(QThread):
    result_sig = Signal(list)
    status_sig = Signal(str)
    error_sig = Signal(str)

    def __init__(self, url: str, cookies_browser: str | None = None):
        super().__init__()
        self._url = url.strip()
        self._cookies_browser = cookies_browser

    def run(self) -> None:
        try:
            self.result_sig.emit(self._fetch_items())
        except Exception as exc:  # pragma: no cover
            log.exception("fetch formats failed")
            self.error_sig.emit(_friendly_extract_error(str(exc)))

    def _ydl_opts(self, *, noplaylist: bool = False) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": False,
            "ignoreerrors": False,
            "logger": YtdlpLogBridge(),
        }
        if noplaylist:
            opts["noplaylist"] = True
        if self._cookies_browser:
            opts["cookiesfrombrowser"] = (self._cookies_browser,)
        return opts

    def _fetch_items(self) -> list[VideoItem]:
        from yt_dlp import YoutubeDL

        with YoutubeDL(self._ydl_opts()) as ydl:
            info = ydl.extract_info(self._url, download=False)

        if not info:
            return []

        entries = info.get("entries")
        if entries is None:
            entries = [info]

        items: list[VideoItem] = []
        total = len(entries)
        for index, entry in enumerate(entries, 1):
            if not entry:
                continue

            title = str(entry.get("title") or "未命名视频")
            self.status_sig.emit(f"正在读取格式 ({index}/{total})：{title}")

            video_info = entry
            if not video_info.get("formats"):
                url = _entry_url(video_info)
                if url:
                    video_info = self._fetch_single(url)

            url = _entry_url(video_info) or _entry_url(entry)
            if not url:
                log.warning("skip entry without url: %s", title)
                continue

            items.append(
                {
                    "title": title,
                    "url": url,
                    "duration": video_info.get("duration") or entry.get("duration"),
                    "formats": build_format_options(video_info),
                }
            )

        return items

    def _fetch_single(self, url: str) -> dict[str, Any]:
        from yt_dlp import YoutubeDL

        with YoutubeDL(self._ydl_opts(noplaylist=True)) as ydl:
            info = ydl.extract_info(url, download=False)
        return info or {}


def _friendly_extract_error(message: str) -> str:
    lower = message.lower()
    hints: list[str] = []

    if "http error 412" in lower and "bilibili" in lower:
        hints.append("B 站接口返回 412，通常是风控、登录态或 yt-dlp 版本适配问题。请更新 yt-dlp，并尝试启用浏览器 cookies。")
    if "failed to load cookies" in lower:
        hints.append("读取浏览器 cookies 失败。请确认浏览器已安装并登录，必要时关闭浏览器后重试。")
    if "unsupported url" in lower:
        hints.append("当前链接不受 yt-dlp 支持，或链接格式不正确。")
    if "sign in" in lower or "login" in lower or "cookies" in lower:
        hints.append("该链接可能需要登录或浏览器 cookies。")
    if "private video" in lower or "not available" in lower or "unavailable" in lower:
        hints.append("该视频可能不可访问、被设为私有、下架，或受到地区限制。")
    if "http error 403" in lower or "forbidden" in lower:
        hints.append("服务器拒绝访问，可能是链接过期、需要登录、地区限制或反爬策略导致。")
    if "timed out" in lower or "timeout" in lower or "connection" in lower:
        hints.append("网络连接超时或中断，请检查网络后重试。")

    if not hints:
        return message

    return "\n".join([*hints, "", "yt-dlp 原始错误：", message])


__all__ = [
    "FormatsFetcher",
    "QUALITY_PRESETS",
    "VideoFormat",
    "VideoItem",
    "_duration_text",
]
