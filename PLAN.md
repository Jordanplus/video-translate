# 專案計畫：影片字幕抽取與翻譯（繁體中文）

## Context

從零打造一個本地端影片字幕工具：**上傳本地影片 或 貼上 YouTube/網路影片 URL** → 用語音辨識抽取字幕 → 翻譯成繁體中文 → 輸出 SRT 檔。

**動機**：

- 避免雲端服務的隱私／費用問題
- 要能離線處理
- 品質要能保留口語的上下文與語氣

**目標機器**：MacBook M5 32GB（Apple Silicon arm64）。

---

## 技術選型

| 元件 | 選擇 | 原因 |
|---|---|---|
| 影片下載 | **yt-dlp** | 支援 YouTube、Bilibili、Vimeo 等上千網站 |
| 語音辨識 | **whisper.cpp** | Apple Silicon Metal 加速，速度與記憶體最佳 |
| 翻譯後端（推薦） | **MTPLX + Qwen3.6-27B** | Native MTP speculative decoding，~2.24× vs AR；4-bit 16.4GB 在 32GB 可跑 |
| 翻譯後端（備援） | **Ollama + Qwen3** | 更輕量，記憶體需求低，安裝簡單 |
| GUI | **Gradio** | Python 原生、拖拉檔案、進度條 |
| 輸出 | **SRT** | 通用字幕格式 |

兩個翻譯後端皆走 **OpenAI 相容 `/v1/chat/completions`**，所以 `pipeline/translate.py` 共用同一條程式碼，只差 base URL 與 model id。

---

## 處理流程

```
本地影片檔 (.mp4/.mkv/...)        YouTube / 其他 URL
        │                              │
        │                              ▼  [yt-dlp]
        │                       影片或音訊檔（依使用者選擇）
        │                              │
        └──────────────┬───────────────┘
                       ▼  [ffmpeg]
              音訊 (.wav, 16kHz mono)
                       │
                       ▼  [whisper.cpp / large-v3]
              原文 SRT（含時間軸 + 自動偵測語言）
                       │
                       ▼  [MTPLX 或 Ollama，分批翻譯，保留時間軸]
              繁體中文 SRT
                       │
                       ▼
              使用者下載
```

---

## 專案結構

```
video_translate/
├── app.py                  # Gradio GUI 入口（兩個 Tab：File / URL）
├── pipeline/
│   ├── __init__.py
│   ├── download.py         # yt-dlp wrapper
│   ├── audio.py            # ffmpeg 音訊抽取
│   ├── transcribe.py       # 包裝 whisper.cpp subprocess
│   ├── translate.py        # OpenAI-compatible chat API（雙後端）
│   └── srt.py              # SRT 解析／組裝
├── config.py               # 模型路徑、後端設定、預設參數
├── requirements.txt        # gradio, yt-dlp, pysrt, requests
├── setup.sh                # 一鍵安裝（BACKEND=mtplx|ollama|both）
├── PLAN.md                 # 本檔
├── STATUS.md               # 實作進度與待驗證項目
└── README.md               # 使用文件
```

執行期會產生（已 `.gitignore`）：

- `whisper.cpp/` — 由 setup.sh clone & build
- `work/` — Gradio session 暫存

---

## 設計重點

### 1. `pipeline/download.py` — YouTube / URL 下載

- 用 `yt-dlp` Python API（不用 subprocess，能取得 metadata、progress hook）
- 兩種模式：
  - **Audio-only**（預設）：`format='bestaudio/best'` + postprocessor 轉 16kHz mono wav，直接餵 whisper
  - **Full video**：`bestvideo+bestaudio` 合併成 mp4，保留影片供日後使用
- 影片標題清理掉非法字元當作預設 SRT 檔名

### 2. `pipeline/audio.py` — 音訊抽取

- 本地檔走這條：`ffmpeg -ar 16000 -ac 1 -c:a pcm_s16le`
- 用 subprocess + `capture_output`，失敗時回傳 stderr 後段

### 3. `pipeline/transcribe.py` — 語音辨識

- 呼叫 whisper.cpp CLI（自動找 `whisper-cli` / `main`）
- `subprocess.Popen` 串流 stdout，regex 解析 `progress=NN%` 餵 Gradio progress bar
- 同步偵測 `auto-detected language: xx` 回傳語言碼

### 4. `pipeline/translate.py` — 翻譯（雙後端）

- 走 OpenAI 相容 `/v1/chat/completions`，兩個後端共用
- 用 `response_format={"type": "json_object"}` 強制 JSON
- **分批策略**：每批 15 條，附帶前 2 條的「原文+譯文」當上下文（讓代名詞、語氣連貫）
- **System prompt** 強調：繁體中文（台灣用語）、保持口語、保留編號、不加說明
- **JSON 解析容錯**：支援 markdown code fence、額外文字夾雜
- **失敗 fallback**：若批次回傳條數不對，逐句重譯；若仍失敗就保留原文

### 5. `pipeline/srt.py` — SRT I/O

- 用 `pysrt`（成熟、處理時間格式邊角案例）
- `replace_texts()` 保留 timestamps 換內容，避免時間軸偏移

### 6. `app.py` — Gradio GUI

- `gr.Blocks` + `gr.Tabs`：本地檔案 / URL
- 右側設定欄：Whisper 模型、翻譯後端、翻譯模型
- 後端切換時用 `.change()` callback 自動更新可用模型清單
- `gr.Progress` 串四階段：下載 → 抽音 → 辨識 → 翻譯
- 結果預覽（前 20 條原文 + 譯文並排）+ 多檔下載

### 7. `setup.sh` — 一鍵安裝

- 環境變數：`BACKEND={mtplx|ollama|both}`、`WHISPER_MODEL`、`OLLAMA_MODEL`、`MTPLX_MODEL`
- 步驟：
  1. 確認 Homebrew
  2. 裝 ffmpeg、cmake
  3. 依 `BACKEND` 裝 MTPLX 或 Ollama 或兩者
  4. Clone & build whisper.cpp（`cmake -B build -DGGML_METAL=ON`）
  5. 下載 ggml-large-v3.bin
  6. `pip install -r requirements.txt`

---

## 32GB MacBook M5 注意事項

- **MTPLX**：Qwen3.6-27B 4-bit 量化磁碟 16.4GB，推論時加 KV cache 約 22–25GB。可跑，但須用 `--profile sustained`，**不要用 `burst`**（會把 32GB 吃光）
- **MTPLX 內建 preflight**：預估超過 80% unified memory 會直接報錯，不會默默崩潰
- 若不放心可改用 Ollama + Qwen3:14B（~10GB）

---

## 已驗證

- 所有 Python 檔語法正確（`ast.parse` 全通過）
- `setup.sh` shell 語法正確（`bash -n`）
- 開發機（macOS 26.4.1, arm64）已有 ffmpeg 8.1.1、Python 3.14.3、Homebrew

## 待驗證（在 MacBook 上）

見 `STATUS.md`。

---

## Roadmap（效能優化）

實測基準：M5 32GB，`nsps-808.mp4`（2h09m 影片 → 3478 段字幕）

| 階段 | 現況 | 觀察 |
|---|---|---|
| Whisper large-v3（whisper.cpp） | ~4h | ~0.5× realtime，慢於預期 |
| 翻譯（MTPLX + Qwen3.6-27B，reasoning off） | ~100 min 估 | ~16 tok/s、~26s/batch（15 行） |
| 翻譯（Ollama + qwen3.6_translate） | 已驗證至少慢 17× | Batch JSON 在 Ollama 上穩定性差，會 fallback 到單行重試 |

### [P1] 換 MLX-Whisper backend — 評估後不採用

**動機**：whisper.cpp 在 M5 上跑 large-v3 約 0.5× realtime，瓶頸明顯。MLX-Whisper（Apple 自家 framework）原生吃 unified memory + AMX，社群實測在 M-series 上對 large-v3 比 whisper.cpp 快 1.5–2.5×。

**實測結果（2026-05-13，10-min 日文 sample）**：

| Backend | Transcribe wall time | Segments | Hallucination |
|---|---|---|---|
| whisper.cpp `-l ja -mc 0`（baseline） | 41.5 s | 115 | 正常（max repeat 2） |
| mlx-whisper large-v3 (condition_on_previous_text=False) | ~38 s | 105 | `女女女...` 200+ 字、`ご視聴ありがとうございました` 開頭 outro hallucination |

**結論**：加速只有 1.09×，未達「顯著快」門檻；hallucination 反而比 `-mc 0` 的 whisper.cpp 嚴重；增加維護成本（切換邏輯、~3 GB 額外模型）。**不整合到 pipeline**。

**留作日後重試的素材**：
- 模型已存在 `~/.cache/huggingface/hub/models--mlx-community--whisper-large-v3-mlx/`（~3 GB），未來 mlx-whisper 升版可再 smoke test
- smoke test 腳本：`work/mlx_smoke.py`

---

### [P2] 翻譯加速組合 — 完成（實測 1.14×）

**動機**：MTPLX 27B 模型再大幅提速空間有限。原本期望 `--depth 5` + `batch_size 25` 是 1.5–2× 提速組合，實際做下來只剩 batch_size 有效。

**實測結果（2026-05-13，60-line benchmark）**：

| 設定 | Elapsed | Lines/s | 備註 |
|---|---|---|---|
| baseline（batch=15, depth=3, reasoning off） | 138.06 s | 0.43 | |
| + batch=25（depth 維持 3） | 121.28 s | 0.49 | **採用，14% 加速** |

**已採取的步驟**：
- `config.py` 改 `TRANSLATE_BATCH_SIZE = 25`：1.14× 加速、fallback 觸發率正常
- depth=5 嘗試失敗：mtplx quickstart `--depth` 上限為 3，runtime 拒絕更高值。其餘 flag 不動

**預期效益（重新估）**：3478 行 ÷ 0.49 lines/s ≈ 約 119 min。離原本 50–65 min 目標還差一截，剩下的提速要靠 P1 (MLX-Whisper) + 後續探索。

---

### [P3]（探索）`--profile performance-cold --max` 或 burst

**動機**：MTPLX 的 burst-class profile 可能進一步提速 1.5–2×，但 README 明確警告 32GB 機器禁用 burst。

**評估前提**：要等 P1+P2 完成後仍嫌慢才做。

**步驟**：
1. 不關 Ollama，先測 `--profile performance-cold` 是否會超記憶體 → verify: `vm_stat` 在跑滿 batch 時 free pages 仍 > 1GB
2. 若安全，加 `--max` 再測 → verify: 同上
3. 任一階段 OOM 立即退回 sustained

**風險**：可能爆記憶體導致系統 swap、kernel panic。

---

### [P4] VAD 預過濾靜音段 — 完成（實測 1.68× + 副作用是改善品質）

**動機**：whisper.cpp 內建 silero VAD，可跳過靜音段。對講座/訪談類影片（含大量空白）可省 20–50% 辨識時間，與 backend 選擇正交。

**實測結果（2026-05-13，10-min 日文 sample，silero-v6.2.0）**：

| 設定 | Wall time | Segments | Hallucination |
|---|---|---|---|
| baseline `-mc 0` | 41.5 s | 115 | 開頭/結尾各幾條 outro hallucination（`おやすみなさい`、`ご視聴ありがとうございました` ×2、`あなた`、結尾 `はい`） |
| **VAD + `-mc 0`** | **24.75 s** | 96 | 開頭/結尾 hallucination 全消除，從真實第一句 1:52 開始 |

**結論**：1.68× 加速，且 19 段差距全是被消除的開頭/結尾靜音 hallucination。VAD 是品質與速度雙贏，**設為預設開啟**。

**已採取的步驟**：
- `pipeline/transcribe.py` 加 `vad` 參數，預設 `True`
- `config.py` 加 `WHISPER_VAD_MODEL`、`ENABLE_VAD_DEFAULT`
- `app.py` 加 GUI checkbox（預設勾選）
- `Makefile` 把 `ggml-silero-v6.2.0.bin` 加入 `whisper` target，`make check` 顯示 VAD model 狀態

---

### 優先順序總結（2026-05-13 更新）

1. ~~**P1 MLX-Whisper**~~：實測加速僅 1.09× + hallucination 較重，不採用
2. **P2 翻譯 depth+batch**：✅ 完成（batch=25，1.14×；depth=5 不支援）
3. **P4 VAD pre-filter**：✅ 完成（1.68× + 開頭/結尾 hallucination 全消）
4. **P3 burst profile**：高風險，僅在還不夠快時試
