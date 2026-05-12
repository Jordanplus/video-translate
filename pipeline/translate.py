"""Translate subtitle lines to Traditional Chinese.

Supports any OpenAI-compatible chat-completions endpoint. The two configured
backends are:

  * MTPLX  — Apple-Silicon native MTP speculative decoding (Qwen3.6-27B)
  * Ollama — generic local LLM runtime (Qwen3 variants)

Both expose `POST /v1/chat/completions` so the wire format is identical.
"""
from __future__ import annotations

import json
import re
from typing import Callable, List, Optional

import requests

from config import (
    BACKENDS,
    DEFAULT_BACKEND,
    TRANSLATE_BATCH_SIZE,
    TRANSLATE_CONTEXT_WINDOW,
    TRANSLATE_TEMPERATURE,
)


class BackendUnavailableError(RuntimeError):
    pass


class TranslationError(RuntimeError):
    pass


SYSTEM_PROMPT = (
    "你是專業的影片字幕翻譯員，請將以下字幕翻譯為**繁體中文（台灣用語）**。\n"
    "翻譯原則：\n"
    "1. 保持口語自然流暢，避免生硬的逐字直譯。\n"
    "2. 保留原文的語氣與情緒（如笑、嘆氣、強調等）。\n"
    "3. 使用台灣常見用語（例如「影片」而非「視頻」、「軟體」而非「軟件」）。\n"
    "4. 不要加上任何額外說明、註解或前後綴。\n"
    "5. **必須保留每條字幕的編號**，逐條翻譯，不可合併或拆分句子。\n"
    "請以下列 JSON 格式輸出：{\"translations\": [{\"id\": 1, \"text\": \"…\"}, …]}"
)


def _backend_cfg(backend: str) -> dict:
    cfg = BACKENDS.get(backend)
    if cfg is None:
        raise ValueError(f"Unknown backend: {backend}")
    return cfg


def check_backend(backend: str) -> None:
    cfg = _backend_cfg(backend)
    url = cfg["base_url"] + cfg["health_path"]
    try:
        r = requests.get(url, timeout=3)
        r.raise_for_status()
    except Exception as e:
        if backend == "mtplx":
            hint = (
                "啟動： `mtplx quickstart --model "
                "Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed "
                "--profile sustained --port 8000 --reasoning off`"
            )
        else:
            hint = "啟動： `brew services start ollama` 或 `ollama serve`"
        raise BackendUnavailableError(
            f"{cfg['label']} 無法連線（{url}）。{hint}\n錯誤：{e}"
        )


def _build_user_message(
    batch: List[str], prev_context: List[tuple[str, str]]
) -> str:
    parts = []
    if prev_context:
        parts.append("前文上下文（已翻譯，僅供參考、不要重複輸出）：")
        for src, tgt in prev_context:
            parts.append(f"  原文：{src}")
            parts.append(f"  譯文：{tgt}")
        parts.append("")
    parts.append("請翻譯以下字幕：")
    for i, line in enumerate(batch, start=1):
        parts.append(f"{i}. {line}")
    return "\n".join(parts)


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_json(text: str) -> dict:
    """Tolerate models that wrap JSON in code fences or add stray text."""
    candidates = []
    fenced = _JSON_FENCE_RE.findall(text)
    candidates.extend(fenced)
    candidates.append(text)
    for c in candidates:
        c = c.strip()
        start = c.find("{")
        end = c.rfind("}")
        if start == -1 or end == -1:
            continue
        try:
            return json.loads(c[start:end + 1])
        except json.JSONDecodeError:
            continue
    raise TranslationError(f"Could not parse JSON from model output:\n{text[:500]}")


def _call_chat(
    backend: str,
    model: str,
    system: str,
    user: str,
    timeout: int = 600,
) -> str:
    cfg = _backend_cfg(backend)
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": TRANSLATE_TEMPERATURE,
        "stream": False,
    }
    if cfg.get("supports_json_format"):
        payload["response_format"] = {"type": "json_object"}
    if backend == "ollama":
        payload["think"] = False

    try:
        r = requests.post(
            cfg["base_url"] + "/chat/completions",
            json=payload,
            timeout=timeout,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        raise TranslationError(f"{cfg['label']} request failed: {e}")

    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise TranslationError(f"Unexpected response shape: {data}")


def _translate_batch(
    batch: List[str],
    prev_context: List[tuple[str, str]],
    backend: str,
    model: str,
) -> List[str]:
    user = _build_user_message(batch, prev_context)
    raw = _call_chat(backend, model, SYSTEM_PROMPT, user)
    parsed = _extract_json(raw)
    items = parsed.get("translations") or parsed.get("items") or []
    if not isinstance(items, list):
        raise TranslationError(f"unexpected translations field: {items!r}")

    by_id = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        idx = it.get("id")
        text = it.get("text") or it.get("translation") or ""
        if isinstance(idx, int) and 1 <= idx <= len(batch):
            by_id[idx] = str(text).strip()

    result = []
    for i in range(1, len(batch) + 1):
        result.append(by_id.get(i, ""))
    return result


def _translate_single(line: str, backend: str, model: str) -> str:
    """Fallback for individual lines when batch returns mismatched count."""
    user = (
        f"請將下列一句字幕翻譯成繁體中文（台灣用語），"
        f"只輸出 JSON：{{\"text\": \"…\"}}\n\n原文：{line}"
    )
    raw = _call_chat(backend, model, SYSTEM_PROMPT, user)
    try:
        parsed = _extract_json(raw)
        return str(parsed.get("text") or parsed.get("translation") or "").strip()
    except TranslationError:
        return ""


def translate_lines(
    lines: List[str],
    backend: str = DEFAULT_BACKEND,
    model: Optional[str] = None,
    batch_size: int = TRANSLATE_BATCH_SIZE,
    progress_cb: Optional[Callable[[float, str], None]] = None,
) -> List[str]:
    """Translate a flat list of subtitle strings → Traditional Chinese."""
    cfg = _backend_cfg(backend)
    model = model or cfg["default_model"]

    check_backend(backend)
    if not lines:
        return []

    results: List[str] = []
    total = len(lines)
    pos = 0

    while pos < total:
        batch = lines[pos:pos + batch_size]
        prev_window = TRANSLATE_CONTEXT_WINDOW
        prev_context = []
        for j in range(max(0, pos - prev_window), pos):
            prev_context.append((lines[j], results[j]))

        try:
            translated = _translate_batch(batch, prev_context, backend, model)
        except TranslationError:
            translated = [""] * len(batch)

        for k, t in enumerate(translated):
            if not t.strip():
                translated[k] = (
                    _translate_single(batch[k], backend, model) or batch[k]
                )

        results.extend(translated)
        pos += len(batch)

        if progress_cb:
            frac = pos / total
            progress_cb(frac, f"翻譯中 {pos}/{total}（{cfg['label']}）")

    return results
