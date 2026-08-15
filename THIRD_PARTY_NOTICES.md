# Third-Party Notices

This project uses third-party software. Keep this file with source or binary
distributions.

## Runtime Dependencies

| Component | Purpose | License | Source |
| --- | --- | --- | --- |
| yt-dlp | Video metadata extraction and downloading | Unlicense for the PyPI source/wheel distribution | https://github.com/yt-dlp/yt-dlp |
| PySide6 / Qt for Python | Desktop GUI toolkit | LGPLv3/GPLv3 or Qt commercial license | https://doc.qt.io/qtforpython-6/ |
| qtawesome | Icon font integration for Qt | MIT License; bundled icon fonts use their own licenses | https://pypi.org/project/QtAwesome/ |
| Python | Runtime | Python Software Foundation License | https://www.python.org/ |

## Optional External Tool

`ffmpeg` is required when yt-dlp needs to merge separate audio/video streams or
convert the downloaded media container to MP4. If a release bundles ffmpeg,
include ffmpeg's license files and build information with that release. If
ffmpeg is not bundled, tell users to install it separately and ensure the
`ffmpeg` command is available on PATH.

## yt-dlp Packaging Note

yt-dlp itself is licensed under the Unlicense. The yt-dlp project notes that
some of its own release files may contain third-party code under different
licenses, and PyInstaller-bundled yt-dlp executables may be GPLv3+ combined
works. This application depends on the PyPI package form of yt-dlp rather than
bundling yt-dlp's standalone executable.

## Qt / PySide6 Distribution Note

PySide6 wheels include Qt libraries. When distributing a packaged desktop build,
review and satisfy the LGPLv3 obligations for Qt/PySide6, or use an appropriate
commercial Qt license. Typical LGPL distribution hygiene includes preserving
license notices and allowing users to replace or relink the LGPL-covered
libraries where required.

## Content Usage Notice

This application is a GUI wrapper around yt-dlp. Users are responsible for
making sure they have the right to download the content they request and for
complying with applicable laws and each service's terms.
