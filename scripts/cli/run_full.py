"""Full pipeline: audio → whisper(+VAD) → translate(mtplx) → zh SRT."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_ROOT))
PROJECT_ROOT = SCRIPTS_ROOT.parent

from audio import extract as audio
from postprocess import srt_ops as srt
from whisper import transcribe
from translate import translate


def stamp(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--video",
        type=Path,
        default=PROJECT_ROOT / "inputs" / "nsps-808.mp4",
        help="path to input video",
    )
    parser.add_argument("--language", default="ja", help="whisper source language")
    parser.add_argument(
        "--stop-backend",
        action="store_true",
        help="kill MTPLX after pipeline completes to free RAM",
    )
    args = parser.parse_args()

    video = args.video.resolve()
    if not video.exists():
        stamp(f"video not found: {video}")
        return 1
    stem = video.stem
    out_final = PROJECT_ROOT / "output" / f"{stem}-full"
    out_intermediate = PROJECT_ROOT / "output" / "intermediate" / f"{stem}-full"
    out_final.mkdir(parents=True, exist_ok=True)
    out_intermediate.mkdir(parents=True, exist_ok=True)

    t_overall = time.perf_counter()

    wav = out_intermediate / f"{stem}.wav"
    if wav.exists() and wav.stat().st_size > 0:
        stamp(f"audio cached: {wav.name} ({wav.stat().st_size//1024//1024} MB)")
    else:
        stamp(f"audio extract → {wav.name}")
        t = time.perf_counter()
        audio.to_wav_16k_mono(video, wav)
        stamp(f"  done in {time.perf_counter()-t:.1f}s")

    src_srt_target = out_final / f"{stem}.source.srt"
    if src_srt_target.exists():
        stamp(f"whisper cached: {src_srt_target.name}")
        items = srt.parse(src_srt_target)
    else:
        stamp(f"whisper (large-v3, {args.language}, vad=True)")
        t = time.perf_counter()
        res = transcribe.transcribe(
            wav, language=args.language, output_dir=out_intermediate, vad=True
        )
        stamp(f"  done in {time.perf_counter()-t:.1f}s  srt={res.srt_path.name}")
        items = srt.parse(res.srt_path)
        srt.write(items, src_srt_target)

    stamp(f"loaded {len(items)} segments")

    stamp("translate (mtplx, batch=25)")
    t = time.perf_counter()
    last_pct = -1

    def cb(frac: float, msg: str) -> None:
        nonlocal last_pct
        pct = int(frac * 100)
        if pct != last_pct and pct % 2 == 0:
            stamp(f"  {msg}  ({pct}%)")
            last_pct = pct

    texts = [it.text for it in items]
    zh = translate.translate_lines(texts, backend="mtplx", progress_cb=cb)
    stamp(f"  done in {time.perf_counter()-t:.1f}s")

    zh_items = srt.replace_texts(items, zh)
    zh_srt = out_final / f"{stem}.zh-Hant.srt"
    srt.write(zh_items, zh_srt)
    stamp(f"DONE → {zh_srt.name}  segments={len(zh_items)}")
    stamp(f"TOTAL elapsed: {time.perf_counter()-t_overall:.1f}s")

    if args.stop_backend:
        stamp("stopping MTPLX backend")
        translate.stop_backend("mtplx")
    return 0


if __name__ == "__main__":
    sys.exit(main())
