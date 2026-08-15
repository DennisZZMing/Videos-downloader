# Videos Downloader

A small Windows desktop GUI for downloading videos through
[yt-dlp](https://github.com/yt-dlp/yt-dlp). The app provides link parsing,
format selection, progress display, fallback to `best`, and basic cleanup of
failed partial downloads.

## Features

- Parse single video links and playlists.
- Choose preset quality or a concrete format exposed by yt-dlp.
- Read cookies from Chrome, Edge, or Firefox for sites that need login state.
- Download selected rows to a chosen output directory.
- Merge audio/video streams to MP4 when ffmpeg is available.
- Show friendlier messages for common yt-dlp failures.

## Requirements

- Python 3.11 or newer is recommended.
- Dependencies from `requirements.txt`.
- `ffmpeg` available on PATH for audio/video merging or MP4 conversion.

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Run from source:

```powershell
python main.py
```

Run with a preset output directory:

```powershell
python main.py --output "$env:USERPROFILE\Downloads"
```

## Cookies / Login State

Some sites, especially Bilibili, may reject unauthenticated yt-dlp requests even
when the same video plays in your browser. In the app, choose a browser under
`登录态` before parsing the link:

- `从 Chrome 读取`
- `从 Edge 读取`
- `从 Firefox 读取`

Use a browser where you are already logged in to the target site. If cookie
loading fails, close that browser completely and try again.

For command-line comparison, the equivalent yt-dlp option is:

```powershell
python -m yt_dlp --cookies-from-browser chrome -F "https://www.bilibili.com/video/..."
```

## Building a Windows Package

Install PyInstaller in your build environment:

```powershell
python -m pip install pyinstaller
```

Build:

```powershell
pyinstaller videos-downloader.spec
```

The single-file executable is written to:

```text
dist/videos-downloader.exe
```

Before sharing a binary release, include:

- `LICENSE`
- `THIRD_PARTY_NOTICES.md`
- any third-party license files required by bundled runtime components
- a note about whether ffmpeg is bundled or must be installed separately

For GitHub Releases, prefer uploading a zip that contains the executable plus
`LICENSE`, `README.md`, and `THIRD_PARTY_NOTICES.md`. The executable can run by
itself, but the notices should stay available to users.

## Logs

Logs are written to:

```text
%USERPROFILE%\.videos_downloader\videos_downloader.log
```

The app does not upload links, logs, or download history.

## Legal Notice

This project is not affiliated with yt-dlp or any video platform. Users are
responsible for making sure they have the right to download requested content
and for complying with applicable laws and platform terms.
