# Release Checklist

Use this checklist before publishing a shareable build.

## Source Hygiene

- Ensure source files are saved as UTF-8.
- Do not publish `build/`, `dist/`, `__pycache__/`, virtual environments, or IDE
  caches as source artifacts.
- Keep `requirements.txt`, `LICENSE`, `README.md`, and
  `THIRD_PARTY_NOTICES.md` in the release.

## Manual Verification

- Parse one normal single-video link.
- Parse one playlist link.
- Download with `最佳质量`.
- Download with `最高 720p` or `最高 1080p`.
- Download `仅音频`.
- Parse and download one Bilibili link with `登录态` set to the browser where
  the account is logged in.
- Try a missing or invalid URL and confirm the error message is understandable.
- Try a Bilibili 412/error case and confirm the app suggests browser cookies.
- Try a video requiring separate audio/video streams with ffmpeg installed.
- Try the same ffmpeg case without ffmpeg and confirm the app blocks with a
  clear message.
- Confirm files are saved under the selected directory.
- Confirm failed attempts do not leave empty or partial files behind.

## Binary Release

- Rebuild from a clean environment.
- Decide whether ffmpeg is bundled. If bundled, include ffmpeg license notices.
- Include third-party notices for PySide6/Qt, qtawesome, yt-dlp, Python, and any
  packaged runtime components.
- Make clear that this is not an official yt-dlp client.
- Add a usage notice reminding users to respect copyright, local law, and
  platform terms.
