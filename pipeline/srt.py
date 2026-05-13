"""SRT subtitle parsing and writing, backed by pysrt."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import pysrt


def parse(path: str | Path) -> List[pysrt.SubRipItem]:
    """Read an SRT file and return its items (1-indexed by pysrt)."""
    return list(pysrt.open(str(path), encoding="utf-8"))


def write(items: Iterable[pysrt.SubRipItem], path: str | Path) -> Path:
    """Write SRT items to disk. Renumbers indices to be sequential from 1."""
    file = pysrt.SubRipFile()
    for i, item in enumerate(items, start=1):
        new_item = pysrt.SubRipItem(
            index=i,
            start=item.start,
            end=item.end,
            text=item.text,
        )
        file.append(new_item)
    out = Path(path)
    file.save(str(out), encoding="utf-8")
    return out


def replace_texts(
    items: List[pysrt.SubRipItem], texts: List[str]
) -> List[pysrt.SubRipItem]:
    """Return new items with `texts` substituted, preserving timestamps."""
    if len(items) != len(texts):
        raise ValueError(
            f"item count {len(items)} does not match text count {len(texts)}"
        )
    new_items = []
    for src, txt in zip(items, texts):
        new_items.append(
            pysrt.SubRipItem(
                index=src.index, start=src.start, end=src.end, text=txt
            )
        )
    return new_items


def is_repetition_hallucination(
    text: str, min_len: int = 15, max_unique_ratio: float = 0.05
) -> bool:
    """Detect whisper hallucinations like '女女女...' or '痛い痛い痛い...'.

    Uses unique-char ratio so both single-char and short-ngram repetitions
    are caught (e.g. 200 chars of '痛い' has only 2 unique chars → ratio 0.01).
    """
    s = text.strip()
    if len(s) < min_len:
        return False
    return len(set(s)) / len(s) <= max_unique_ratio


def tighten_long_segments(
    items: List[pysrt.SubRipItem],
    max_chars_per_second: float,
    trigger_s: float,
) -> int:
    """Shrink segments whose duration is wildly disproportionate to text length.

    Whisper.cpp + VAD sometimes emits one short utterance covering a long
    VAD speech region (a few characters spanning tens of seconds or minutes).
    For each item whose duration exceeds `trigger_s`, cap it to
    `chars / max_chars_per_second + 1.0s`. Repetition hallucinations are
    measured by unique-char count, not raw length, so '痛い×100' caps to
    ~2 chars worth of duration. Returns number tightened.
    """
    n_changed = 0
    for it in items:
        duration_s = (it.end.ordinal - it.start.ordinal) / 1000.0
        if duration_s <= trigger_s:
            continue
        stripped = it.text.strip()
        if not stripped:
            continue
        chars = (
            len(set(stripped))
            if is_repetition_hallucination(stripped)
            else len(stripped)
        )
        expected_s = chars / max_chars_per_second + 1.0
        if duration_s <= expected_s:
            continue
        new_end_ms = it.start.ordinal + int(expected_s * 1000)
        it.end = pysrt.SubRipTime.from_ordinal(new_end_ms)
        n_changed += 1
    return n_changed


def preview(items: List[pysrt.SubRipItem], limit: int = 20) -> str:
    """Render up to `limit` items as a readable preview string."""
    lines = []
    for item in items[:limit]:
        lines.append(f"[{item.start} --> {item.end}]")
        lines.append(item.text)
        lines.append("")
    return "\n".join(lines).rstrip()
