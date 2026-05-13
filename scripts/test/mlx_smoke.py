"""Quick MLX-Whisper smoke test against the same 10-min Japanese slice."""
from __future__ import annotations

import time
from pathlib import Path

import mlx_whisper

WAV = Path(__file__).resolve().parent / "vt_c1h47m_y" / "nsps-808-10min.wav"
MODEL = "mlx-community/whisper-large-v3-mlx"

print(f"Audio : {WAV}")
print(f"Model : {MODEL}")
print(f"Lang  : ja")
print()
print("Running transcribe()...")

t0 = time.perf_counter()
result = mlx_whisper.transcribe(
    str(WAV),
    path_or_hf_repo=MODEL,
    language="ja",
    condition_on_previous_text=False,  # equivalent to whisper.cpp -mc 0
    verbose=False,
)
elapsed = time.perf_counter() - t0

segments = result.get("segments", [])
print(f"\nElapsed       : {elapsed:.2f} s")
print(f"Segments      : {len(segments)}")
print()
print("=== HEAD 10 segments ===")
for s in segments[:10]:
    print(f"[{s['start']:6.2f} -> {s['end']:6.2f}] {s['text'].strip()}")
print()
print("=== TAIL 5 segments ===")
for s in segments[-5:]:
    print(f"[{s['start']:6.2f} -> {s['end']:6.2f}] {s['text'].strip()}")

texts = [s["text"].strip() for s in segments]
from collections import Counter
top = Counter(texts).most_common(3)
print()
print("=== top-3 repeated lines ===")
for text, n in top:
    print(f"  {n}x  {text}")
