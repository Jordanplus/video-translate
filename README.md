# 🎬 video_translate — 影片字幕抽取與翻譯（繁體中文）

完全在本地運行的影片字幕工具。輸入影片或 YouTube 連結，輸出繁體中文 SRT。

## 功能

- 📁 上傳本地影片 / 音訊檔
- 🔗 貼上 YouTube、Bilibili、Vimeo 等 [yt-dlp 支援的網站](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)
- 🎙️ 用 **whisper.cpp**（Apple Silicon Metal 加速）抽取字幕，多語言自動偵測
- 🌏 用本地 **MTPLX (Qwen3.6-27B)** 或 **Ollama (Qwen3)** 翻譯成繁體中文（台灣用語）
- 📥 同時下載原文與譯文 SRT

## 系統需求

- macOS（Apple Silicon；MacBook M5 32GB 為驗證目標）
- Homebrew
- Python 3.10+
- RAM：
  - **MTPLX + Qwen3.6-27B**（推薦）：模型 4-bit 量化約 16GB，推論時 32GB 機器可勉強跑（建議用 `sustained` profile，**避免 `burst`**）
  - **Ollama + Qwen3:14B**：~10GB
  - **Ollama + Qwen3:8B**：~6GB（最省記憶體）

## 翻譯後端比較

| 後端 | 模型 | 速度 | 品質 | 32GB 適用 |
|---|---|---|---|---|
| **MTPLX** | Qwen3.6-27B (Optimized-Speed) | ⚡⚡⚡ (~2.24× AR) | ⭐⭐⭐⭐ | ✅ sustained 模式 |
| **Ollama** | Qwen3:14B | ⚡⚡ | ⭐⭐⭐ | ✅ |
| **Ollama** | Qwen3:8B | ⚡⚡⚡ | ⭐⭐ | ✅ |

MTPLX 在 Apple Silicon 上用 native MTP speculative decoding（不依賴外部 drafter），對長字幕批次的吞吐量最快。

## 安裝

```bash
git clone <this-repo>
cd video_translate
bash setup.sh                    # 預設裝 MTPLX
# 或
BACKEND=ollama bash setup.sh     # 只裝 Ollama
BACKEND=both   bash setup.sh     # 兩個都裝
```

`setup.sh` 會：

1. 用 Homebrew 裝 `ffmpeg`、`cmake`
2. 視 `BACKEND` 安裝 MTPLX / Ollama（或兩者）
3. 拉取對應的翻譯模型
4. Clone & 編譯 whisper.cpp（啟用 Metal）
5. 下載 `ggml-large-v3.bin` 語音辨識模型
6. 安裝 Python 套件

可用環境變數覆蓋預設：

```bash
WHISPER_MODEL=medium BACKEND=mtplx bash setup.sh
```

## 使用

**啟動翻譯後端**（擇一）：

```bash
# MTPLX（推薦，Apple Silicon 加速）
mtplx quickstart --profile sustained --port 8000

# 或 Ollama
brew services start ollama
```

**啟動 GUI**：

```bash
python3 app.py
```

開啟瀏覽器： <http://127.0.0.1:7860>

1. 選「本地檔案」或「URL」頁籤
2. 設定 Whisper 與翻譯模型大小（預設即可）
3. 點「🚀 開始處理」
4. 等四個階段：下載 → 抽音 → 辨識 → 翻譯
5. 在下方下載 `xxx.zh-Hant.srt`

## 處理流程

```
影片 / URL → ffmpeg/yt-dlp → 16kHz mono wav
         → whisper.cpp → 原文 SRT
         → Ollama Qwen3 → 繁中 SRT
```

## 專案結構

```
video_translate/
├── app.py                  # Gradio GUI
├── pipeline/
│   ├── download.py         # yt-dlp wrapper
│   ├── audio.py            # ffmpeg wrapper
│   ├── transcribe.py       # whisper.cpp wrapper
│   ├── translate.py        # Ollama / Qwen3 wrapper
│   └── srt.py              # SRT I/O
├── config.py               # 預設參數
├── requirements.txt
├── setup.sh
└── whisper.cpp/            # setup.sh clone & 編譯
```

## Model 儲存位置

所有大型 model 集中存放在 `~/LLM/models/`，原 runtime 路徑用 symlink 接回，所以不必改任何 runtime 設定：

| Model | 實際位置 | Symlink 來源 | 大小 |
|---|---|---|---|
| Whisper `ggml-large-v3.bin` | `~/LLM/models/ggml-large-v3.bin` | `whisper.cpp/models/ggml-large-v3.bin` | 2.9 GB |
| Ollama (`qwen3.6_translate` 等) | `~/LLM/models/ollama/` | `~/.ollama/models` | 21 GB |
| MTPLX (`Qwen3.6-27B-MTPLX-Optimized-Speed`) | `~/LLM/models/mtplx/` | `~/.mtplx/models` | 15 GB |

重新下載模型（`make whisper`、`ollama pull`、`mtplx pull`）會寫進 symlink 的目標，無需額外處理。

## 常見問題

**Q：MTPLX 沒在跑？**

```bash
mtplx quickstart --profile sustained --port 8000
# 或互動式啟動
mtplx start
```

GUI 會在連線失敗時顯示提示。32GB 機器**請用 `sustained` profile**，不要用 `burst`（會把所有資源吃光）。

**Q：Ollama 沒在跑？**

```bash
brew services start ollama
# 或
ollama serve
```

**Q：whisper.cpp 編譯失敗？**

確認 Xcode Command Line Tools 已裝：`xcode-select --install`，再重跑 `bash setup.sh`。

**Q：翻譯太慢？**

- 切到 MTPLX 後端（~2.24× 比一般 AR 快）
- 把 Whisper 模型換成 `medium`（速度約 2 倍）
- 把翻譯模型換成 `qwen3:8b`（速度約 2 倍，品質略降）
- 在 `config.py` 把 `TRANSLATE_BATCH_SIZE` 調大（更省 round-trip，但需更多 VRAM）

**Q：32GB M5 跑 MTPLX 會爆記憶體嗎？**

Qwen3.6-27B 4-bit 量化模型 ~16GB，加上 KV cache 與 Python overhead，理論上能跑。但要注意：

- 用 `--profile sustained`（不要用 `burst`）
- 不要同時開太多應用程式
- MTPLX 內建記憶體 preflight：如果預估超過 80% unified memory 會直接報錯，不會偷偷崩潰
- 如果還是吃緊，改用 Ollama + Qwen3:14B 比較保險

**Q：產出的字幕怎麼用？**

在 VLC / IINA / mpv 中播放影片，把同名 `.srt` 放在影片同資料夾即會自動載入；
或在播放器選單「字幕 → 加入字幕檔」手動載入。
