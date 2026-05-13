"""Wrap whisper.cpp CLI to transcribe audio to SRT."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from config import (
    WHISPER_MODELS,
    WHISPER_MODELS_DIR,
    find_whisper_binary,
)


class WhisperNotInstalledError(RuntimeError):
    pass


class TranscriptionError(RuntimeError):
    pass


@dataclass
class TranscriptionResult:
    srt_path: Path
    language: Optional[str]


_PROGRESS_RE = re.compile(r"progress\s*=\s*(\d+)%")
_LANG_RE = re.compile(
    r"auto-detected language:\s*([a-z]{2,3})", re.IGNORECASE
)


def transcribe(
    wav_path: str | Path,
    model_name: str = "large-v3",
    output_dir: str | Path | None = None,
    language: str = "auto",
    progress_cb: Optional[Callable[[float, str], None]] = None,
    threads: int = 8,
) -> TranscriptionResult:
    """Run whisper.cpp and produce an SRT file. Returns (srt_path, detected_language)."""
    binary = find_whisper_binary()
    if binary is None:
        raise WhisperNotInstalledError(
            "whisper.cpp binary not found. Run `bash setup.sh` to build it."
        )

    if model_name not in WHISPER_MODELS:
        raise ValueError(f"Unknown whisper model: {model_name}")

    model_path = WHISPER_MODELS_DIR / WHISPER_MODELS[model_name]
    if not model_path.exists():
        raise WhisperNotInstalledError(
            f"Whisper model file missing: {model_path}. Run setup.sh to download."
        )

    wav = Path(wav_path).resolve()
    out_dir = Path(output_dir).resolve() if output_dir else wav.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_base = out_dir / wav.stem

    cmd = [
        str(binary),
        "-m", str(model_path),
        "-f", str(wav),
        "-l", language,
        "-mc", "0",
        "-osrt",
        "-of", str(out_base),
        "-t", str(threads),
        "-pp",
    ]

    detected_lang: Optional[str] = None
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip()
        if not line:
            continue
        m = _PROGRESS_RE.search(line)
        if m and progress_cb:
            pct = int(m.group(1)) / 100.0
            progress_cb(pct, f"語音辨識中 {int(m.group(1))}%")
        lm = _LANG_RE.search(line)
        if lm:
            detected_lang = lm.group(1).lower()

    rc = proc.wait()
    if rc != 0:
        raise TranscriptionError(f"whisper.cpp exited {rc}")

    srt_path = out_base.with_suffix(out_base.suffix + ".srt")
    if not srt_path.exists():
        srt_path = Path(str(out_base) + ".srt")
    if not srt_path.exists():
        raise TranscriptionError(f"SRT not produced at {srt_path}")

    if progress_cb:
        progress_cb(1.0, "語音辨識完成")

    return TranscriptionResult(srt_path=srt_path, language=detected_lang)
