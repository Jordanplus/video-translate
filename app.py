"""Gradio GUI: video → Traditional Chinese SRT."""
from __future__ import annotations

import shutil
import tempfile
import traceback
from pathlib import Path
from typing import Optional

import gradio as gr

from config import (
    BACKENDS,
    DEFAULT_BACKEND,
    DEFAULT_WHISPER_LANGUAGE,
    DEFAULT_WHISPER_MODEL,
    ENABLE_VAD_DEFAULT,
    WHISPER_LANGUAGES,
    WHISPER_MODELS,
    WORK_DIR,
)
from pipeline import audio, download, srt, transcribe, translate


def _session_dir() -> Path:
    d = Path(tempfile.mkdtemp(prefix="vt_", dir=str(WORK_DIR)))
    return d


def _backend_key_from_label(label: str) -> str:
    for key, cfg in BACKENDS.items():
        if cfg["label"] == label:
            return key
    return DEFAULT_BACKEND


def _prepare_audio_from_local(
    video_path: str, work: Path, progress: gr.Progress
) -> tuple[Path, str]:
    """Returns (wav_path, base_name)."""
    src = Path(video_path)
    wav = work / f"{src.stem}.wav"
    progress(0.05, desc="抽取音訊…")
    audio.to_wav_16k_mono(src, wav)
    return wav, src.stem


def _prepare_audio_from_url(
    url: str, audio_only: bool, work: Path, progress: gr.Progress
) -> tuple[Path, str, Optional[Path]]:
    """Returns (wav_path, base_name, full_video_path_or_none)."""
    def cb(frac: float, msg: str):
        progress(0.05 + frac * 0.25, desc=msg)

    res = download.download(url, work, audio_only=audio_only, progress_cb=cb)
    base = res.title

    if audio_only:
        return res.media_path, base, None

    wav = work / f"{base}.wav"
    progress(0.30, desc="從影片抽取音訊…")
    audio.to_wav_16k_mono(res.media_path, wav)
    return wav, base, res.media_path


def process(
    file_input: Optional[str],
    url_input: Optional[str],
    srt_input: Optional[str],
    url_download_mode: str,
    whisper_model: str,
    whisper_language: str,
    enable_vad: bool,
    backend_label: str,
    backend_model: str,
    stop_backend_after: bool,
    progress: gr.Progress = gr.Progress(),
):
    backend_key = _backend_key_from_label(backend_label)
    has_file = bool(file_input)
    has_url = bool(url_input and url_input.strip())
    has_srt = bool(srt_input)
    n_inputs = sum([has_file, has_url, has_srt])
    if n_inputs == 0:
        raise gr.Error("請擇一輸入：上傳影片/音訊、貼上 URL、或上傳 .srt")
    if n_inputs > 1:
        raise gr.Error("請只使用其中一種輸入方式")

    work = _session_dir()
    full_video: Optional[Path] = None
    try:
        progress(0.0, desc="準備中…")
        if has_srt:
            src = Path(srt_input)
            if src.suffix.lower() != ".srt":
                raise gr.Error("請上傳 .srt 字幕檔")
            base = src.stem
            items = srt.parse(src)
            if not items:
                raise gr.Error("SRT 檔為空或格式錯誤")
            source_srt = work / f"{base}.source.srt"
            srt.write(items, source_srt)
            source_lang = "(來自外部 SRT)"
            progress(0.65, desc=f"已載入 {len(items)} 條字幕")
        else:
            if has_file:
                wav, base = _prepare_audio_from_local(file_input, work, progress)
            else:
                audio_only = url_download_mode == "只下載音訊（較快）"
                wav, base, full_video = _prepare_audio_from_url(
                    url_input.strip(), audio_only, work, progress
                )

            def trans_cb(frac: float, msg: str):
                progress(0.30 + frac * 0.40, desc=msg)

            trans_res = transcribe.transcribe(
                wav,
                model_name=whisper_model,
                output_dir=work,
                language=whisper_language,
                progress_cb=trans_cb,
                vad=enable_vad,
            )

            items = srt.parse(trans_res.srt_path)
            if not items:
                raise gr.Error("辨識結果為空，影片可能沒有語音內容。")

            source_srt = work / f"{base}.source.srt"
            srt.write(items, source_srt)
            source_lang = trans_res.language or "auto"

        progress(0.70, desc=f"開始翻譯（{source_lang} → 繁中）…")

        def tr_cb(frac: float, msg: str):
            progress(0.70 + frac * 0.28, desc=msg)

        original_texts = [it.text for it in items]
        try:
            zh_texts = translate.translate_lines(
                original_texts,
                backend=backend_key,
                model=backend_model,
                progress_cb=tr_cb,
            )
        except (translate.BackendUnavailableError, translate.TranslationError) as tx_err:
            preview_orig = srt.preview(items, limit=20)
            downloads = [str(source_srt)]
            if full_video and full_video.exists():
                downloads.append(str(full_video))
            info_md = (
                f"⚠️ **翻譯失敗 — 但原文字幕已產出**  \n"
                f"**來源語言**：`{source_lang}`  \n"
                f"**字幕條數**：{len(items)}  \n"
                f"**原文檔**：`{source_srt.name}`（可從下方下載，重跑無須再做語音辨識）  \n\n"
                f"錯誤訊息：{tx_err}"
            )
            return info_md, preview_orig, "(翻譯失敗 — 換後端後可重跑，或用外部工具翻譯此 .srt)", downloads

        zh_items = srt.replace_texts(items, zh_texts)
        zh_srt = work / f"{base}.zh-Hant.srt"
        srt.write(zh_items, zh_srt)

        progress(1.0, desc="完成 ✅")

        preview_orig = srt.preview(items, limit=20)
        preview_zh = srt.preview(zh_items, limit=20)

        downloads = [str(zh_srt), str(source_srt)]
        if full_video and full_video.exists():
            downloads.append(str(full_video))

        info_md = (
            f"**來源語言**：`{source_lang}`  \n"
            f"**字幕條數**：{len(items)}  \n"
            f"**輸出檔名**：`{zh_srt.name}`"
        )
        return info_md, preview_orig, preview_zh, downloads
    except gr.Error:
        raise
    except Exception as e:
        tb = traceback.format_exc()
        raise gr.Error(f"處理失敗：{e}\n\n{tb[-1500:]}")
    finally:
        if stop_backend_after:
            translate.stop_backend(backend_key)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="影片字幕翻譯（繁中）") as demo:
        gr.Markdown(
            "# 🎬 影片字幕抽取與翻譯（繁體中文）\n"
            "上傳影片或貼上 YouTube/Bilibili/Vimeo 等連結，本工具會用 "
            "**whisper.cpp** 抽取字幕，再用本地 **Qwen3** 翻譯成繁體中文。"
        )

        with gr.Row():
            with gr.Column(scale=2):
                with gr.Tabs():
                    with gr.Tab("📁 本地檔案"):
                        file_input = gr.File(
                            label="影片或音訊檔",
                            file_types=["video", "audio"],
                            type="filepath",
                        )
                    with gr.Tab("🔗 URL（YouTube 等）"):
                        url_input = gr.Textbox(
                            label="影片連結",
                            placeholder="https://www.youtube.com/watch?v=...",
                        )
                        url_download_mode = gr.Radio(
                            choices=["只下載音訊（較快）", "下載完整影片"],
                            value="只下載音訊（較快）",
                            label="下載模式",
                        )
                    with gr.Tab("📝 字幕檔（.srt 直接翻譯）"):
                        srt_input = gr.File(
                            label="SRT 字幕檔（任意語言 → 繁中）",
                            file_types=[".srt"],
                            type="filepath",
                        )
                        gr.Markdown(
                            "*跳過語音辨識，直接翻譯。適合：先前翻譯失敗、外部來源字幕、手工字幕。*"
                        )
            with gr.Column(scale=1):
                whisper_model = gr.Dropdown(
                    choices=list(WHISPER_MODELS.keys()),
                    value=DEFAULT_WHISPER_MODEL,
                    label="Whisper 模型",
                )
                whisper_language = gr.Dropdown(
                    choices=[(v, k) for k, v in WHISPER_LANGUAGES.items()],
                    value=DEFAULT_WHISPER_LANGUAGE,
                    label="影片語言（auto 偵測錯誤時請手動指定）",
                )
                enable_vad = gr.Checkbox(
                    value=ENABLE_VAD_DEFAULT,
                    label="啟用 VAD 預過濾（跳過靜音、降低 hallucination）",
                )
                backend_labels = [cfg["label"] for cfg in BACKENDS.values()]
                default_label = BACKENDS[DEFAULT_BACKEND]["label"]
                backend = gr.Dropdown(
                    choices=backend_labels,
                    value=default_label,
                    label="翻譯後端",
                )
                backend_model = gr.Dropdown(
                    choices=BACKENDS[DEFAULT_BACKEND]["models"],
                    value=BACKENDS[DEFAULT_BACKEND]["default_model"],
                    label="翻譯模型",
                )
                stop_backend_after = gr.Checkbox(
                    value=False,
                    label="跑完關閉 MTPLX backend（釋放 ~22 GB RAM）",
                )

                def _update_models(label):
                    key = _backend_key_from_label(label)
                    cfg = BACKENDS[key]
                    return gr.update(
                        choices=cfg["models"], value=cfg["default_model"]
                    )

                backend.change(
                    fn=_update_models, inputs=backend, outputs=backend_model
                )
                run_btn = gr.Button("🚀 開始處理", variant="primary")

        info_md = gr.Markdown()
        with gr.Row():
            with gr.Column():
                gr.Markdown("### 原文字幕（前 20 條）")
                preview_orig = gr.Code(label="原文 SRT", language=None, lines=18)
            with gr.Column():
                gr.Markdown("### 繁中字幕（前 20 條）")
                preview_zh = gr.Code(label="譯文 SRT", language=None, lines=18)

        downloads = gr.Files(label="下載", interactive=False)

        run_btn.click(
            fn=process,
            inputs=[
                file_input,
                url_input,
                srt_input,
                url_download_mode,
                whisper_model,
                whisper_language,
                enable_vad,
                backend,
                backend_model,
                stop_backend_after,
            ],
            outputs=[info_md, preview_orig, preview_zh, downloads],
        )

    return demo


if __name__ == "__main__":
    build_ui().launch(server_name="127.0.0.1", server_port=7860)
