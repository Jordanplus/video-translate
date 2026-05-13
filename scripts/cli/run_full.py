"""Full nsps-808 pipeline: audio → whisper(+VAD) → translate(mtplx) → zh SRT."""
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

VIDEO = PROJECT_ROOT / "inputs" / "nsps-808.mp4"
OUT_FINAL = PROJECT_ROOT / "output" / "nsps-808-full"
OUT_INTERMEDIATE = PROJECT_ROOT / "output" / "intermediate" / "nsps-808-full"
OUT_FINAL.mkdir(parents=True, exist_ok=True)
OUT_INTERMEDIATE.mkdir(parents=True, exist_ok=True)


def stamp(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stop-backend",
        action="store_true",
        help="kill MTPLX after pipeline completes to free RAM",
    )
    args = parser.parse_args()

    t_overall = time.perf_counter()

    wav = OUT_INTERMEDIATE / "nsps-808.wav"
    if wav.exists() and wav.stat().st_size > 0:
        stamp(f"audio cached: {wav.name} ({wav.stat().st_size//1024//1024} MB)")
    else:
        stamp(f"audio extract → {wav.name}")
        t = time.perf_counter()
        audio.to_wav_16k_mono(VIDEO, wav)
        stamp(f"  done in {time.perf_counter()-t:.1f}s")

    src_srt_target = OUT_FINAL / "nsps-808.source.srt"
    if src_srt_target.exists():
        stamp(f"whisper cached: {src_srt_target.name}")
        items = srt.parse(src_srt_target)
    else:
        stamp("whisper (large-v3, ja, vad=True)")
        t = time.perf_counter()
        res = transcribe.transcribe(
            wav, language="ja", output_dir=OUT_INTERMEDIATE, vad=True
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
    zh_srt = OUT_FINAL / "nsps-808.zh-Hant.srt"
    srt.write(zh_items, zh_srt)
    stamp(f"DONE → {zh_srt.name}  segments={len(zh_items)}")
    stamp(f"TOTAL elapsed: {time.perf_counter()-t_overall:.1f}s")

    if args.stop_backend:
        stamp("stopping MTPLX backend")
        translate.stop_backend("mtplx")
    return 0


if __name__ == "__main__":
    sys.exit(main())
