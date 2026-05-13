"""Download videos/audio from YouTube and other yt-dlp supported sites."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import yt_dlp


@dataclass
class DownloadResult:
    media_path: Path
    title: str
    source_url: str
    is_audio_only: bool


_INVALID_FN_CHARS = re.compile(r"[\\/:*?\"<>|]+")


def _safe_filename(name: str) -> str:
    cleaned = _INVALID_FN_CHARS.sub("_", name).strip().rstrip(".")
    return cleaned[:120] or "video"


def download(
    url: str,
    output_dir: str | Path,
    audio_only: bool = True,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> DownloadResult:
    """Download a remote video.

    If `audio_only` is True, extract a 16kHz mono wav directly (Whisper-ready).
    Otherwise download the best video+audio merged file.

    `progress_cb(fraction, status_text)` is called periodically when supplied.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def _hook(d):
        if progress_cb is None:
            return
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            frac = (done / total) if total else 0.0
            speed = d.get("speed") or 0
            mb_s = f"{speed / 1e6:.1f} MB/s" if speed else "?"
            progress_cb(frac, f"下載中 {frac * 100:.1f}% ({mb_s})")
        elif status == "finished":
            progress_cb(1.0, "下載完成，後製轉檔中…")

    ydl_opts: dict = {
        "outtmpl": str(out_dir / "%(title).100s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [_hook],
        "noplaylist": True,
        "restrictfilenames": False,
    }

    if audio_only:
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }],
            "postprocessor_args": ["-ar", "16000", "-ac", "1"],
        })
    else:
        ydl_opts.update({
            "format": "bestvideo*+bestaudio/best",
            "merge_output_format": "mp4",
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title") or "video"

        if audio_only:
            base = Path(ydl.prepare_filename(info))
            media_path = base.with_suffix(".wav")
        else:
            media_path = Path(ydl.prepare_filename(info))
            if not media_path.exists():
                merged = media_path.with_suffix(".mp4")
                if merged.exists():
                    media_path = merged

    if not media_path.exists():
        raise FileNotFoundError(
            f"yt-dlp finished but expected output not found: {media_path}"
        )

    return DownloadResult(
        media_path=media_path,
        title=_safe_filename(title),
        source_url=url,
        is_audio_only=audio_only,
    )
