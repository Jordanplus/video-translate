"""Extract 16kHz mono WAV audio from a video/audio file via ffmpeg."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FFmpegNotFoundError(RuntimeError):
    pass


class AudioExtractionError(RuntimeError):
    pass


def ensure_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise FFmpegNotFoundError(
            "ffmpeg not found in PATH. Install via `brew install ffmpeg`."
        )
    return path


def to_wav_16k_mono(src: str | Path, dst: str | Path) -> Path:
    """Convert any audio/video file to 16kHz mono PCM WAV — Whisper's native input."""
    ffmpeg = ensure_ffmpeg()
    src_path = Path(src)
    dst_path = Path(dst)
    if not src_path.exists():
        raise FileNotFoundError(src_path)

    cmd = [
        ffmpeg,
        "-y",
        "-i", str(src_path),
        "-vn",
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(dst_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AudioExtractionError(
            f"ffmpeg failed (exit {proc.returncode}):\n{proc.stderr[-2000:]}"
        )
    return dst_path
