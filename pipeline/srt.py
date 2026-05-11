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


def preview(items: List[pysrt.SubRipItem], limit: int = 20) -> str:
    """Render up to `limit` items as a readable preview string."""
    lines = []
    for item in items[:limit]:
        lines.append(f"[{item.start} --> {item.end}]")
        lines.append(item.text)
        lines.append("")
    return "\n".join(lines).rstrip()
