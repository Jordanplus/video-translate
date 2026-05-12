# 影片字幕翻譯工具 — 使用手冊

完全在本地運行的影片字幕工具。輸入影片、音訊或 URL，輸出繁體中文（台灣慣用語）SRT。

---

## 系統需求

- macOS Apple Silicon（M-series；M5 32 GB 為驗證目標）
- Homebrew
- 統一記憶體建議 32 GB（最低 16 GB 但需用較小模型）

---

## 安裝

一行裝齊核心元件：

```bash
make
```

會自動處理：

| 元件 | 用途 |
|---|---|
| `ffmpeg`、`cmake` | 音訊處理與編譯 |
| `whisper.cpp`（Metal 加速） | 語音辨識 |
| `ggml-large-v3.bin`（~3 GB） | Whisper 模型 |
| Python `.venv` + 依賴 | Gradio GUI、yt-dlp、pysrt |
| Ollama daemon + `qwen3.6_translate` | 翻譯後端（預設） |

選用：安裝 MTPLX 加速後端（~16 GB 額外模型）

```bash
make mtplx
```

MTPLX 服務需要**手動啟動**（不會跟著 daemon 跑）：

```bash
mtplx quickstart --model Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed --profile sustained --port 8000 --reasoning off
```

驗證所有元件就緒：

```bash
make check
```

預期輸出：

```
ffmpeg            : ✓
cmake             : ✓
whisper binary    : ✓
whisper model     : ✓  2.9G
python venv       : ✓  Python 3.14.x
gradio installed  : ✓
ollama daemon     : ✓
ollama translate  : ✓
mtplx (optional)  : ✓
mtplx model       : ✓
```

---

## 啟動 GUI

```bash
.venv/bin/python3 app.py
```

或啟用 venv 後執行：

```bash
source .venv/bin/activate
python3 app.py
```

開瀏覽器 <http://127.0.0.1:7860>。

---

## 三種輸入模式

GUI 左欄有三個 tab，**擇一**使用：

### 1. `📁 本地檔案`

拖入影片或音訊（mp4、mov、mkv、mp3、wav、m4a 等 ffmpeg 支援的格式）。

流程：抽音訊 → whisper 辨識 → 翻譯。

### 2. `🔗 URL（YouTube 等）`

貼上 YouTube、Bilibili、Vimeo 或任何 [yt-dlp 支援的網站](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)連結。

下載模式：

- **只下載音訊（較快）** — 不保留影片檔，純做字幕
- **下載完整影片** — 保留 mp4，可下載

### 3. `📝 字幕檔（.srt 直接翻譯）`

跳過語音辨識，直接翻譯既有 SRT。用於：

- **先前翻譯失敗想重跑**：把上次產出的 `xxx.source.srt` 拖進去
- **外部來源字幕**：影片網站下載、手動製作的 SRT
- **比較不同後端**：同一份原文丟給 Ollama 或 MTPLX 看品質差異

選此模式時，「Whisper 模型」下拉值會被忽略。

---

## 翻譯後端

| 後端 | 模型 | 速度 | Uncensored | 記憶體 |
|---|---|---|---|---|
| **Ollama** | `qwen3.6_translate`（35B-A3B Q4，abliterated 微調） | 常速 | 是 | ~22 GB |
| **MTPLX** | `Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed` | ~2.24× AR | 否 | ~16 GB |

### 切換後端

GUI 右欄「翻譯後端」下拉即時切換；無需重啟。

### 預設後端

設於 `config.py:42` 的 `DEFAULT_BACKEND`：

```python
DEFAULT_BACKEND = "ollama"   # 或 "mtplx"
```

修改後需重啟 GUI 才生效。

### Ollama vs MTPLX 怎麼選

- 翻譯內容**普通**（中性對話、教學、新聞）→ MTPLX 更快
- 翻譯內容**可能觸發 safety**（成人、激烈言論、敏感議題）→ Ollama（uncensored）
- 不確定 → 預設 Ollama 試一遍，覺得太慢再換

---

## 翻譯失敗的補救

語音辨識成功、翻譯途中失敗時，GUI 行為：

1. 顯示**原文字幕預覽**與錯誤訊息
2. 下載區提供 `xxx.source.srt`（原文 SRT，已產出）
3. 譯文預覽顯示「(翻譯失敗 — 換後端後可重跑)」

**補救步驟**：

1. 下載 `xxx.source.srt`
2. 排除錯誤原因（檢查後端是否啟動、模型是否正確、可在 terminal 用 `make check` 確認）
3. 切到「📝 字幕檔」tab，把剛下載的 `xxx.source.srt` 拖入
4. 換不同的翻譯後端或調整模型
5. 按「🚀 開始處理」

不會重新做語音辨識，省掉幾分鐘到十幾分鐘。

---

## 檔案輸出

每次處理建立一個新的工作目錄：

```
work/vt_<random>/
├── xxx.source.srt        ← 原文字幕（whisper 結果或上傳的 SRT）
├── xxx.zh-Hant.srt       ← 繁中譯文
└── （URL 完整影片模式才有）完整影片檔
```

可從 GUI「下載」區直接取得，或開檔案總管到 `work/` 找。

工作目錄**不會自動清除**，建議定期手動清理：

```bash
rm -rf work/vt_*
```

---

## Makefile targets

| target | 作用 |
|---|---|
| `make` 或 `make all` | 一次裝齊（不含 MTPLX） |
| `make brew-deps` | ffmpeg、cmake |
| `make whisper` | clone + 編譯 whisper.cpp + 下載模型 |
| `make python` | 建 `.venv` + 裝依賴 |
| `make ollama` | Ollama daemon + 建 `qwen3.6_translate` |
| `make mtplx` | （選用）裝 MTPLX + 拉 16 GB 模型 |
| `make check` | 檢查所有元件就緒狀態 |
| `make clean` | 移除 `.venv` 和 whisper build（**保留模型快取**） |

可覆蓋變數（不常用）：

```bash
make whisper WHISPER_MODEL=medium                # 用 medium 取代 large-v3
make ollama MODELFILE_TRANSLATE=/path/to/file    # Modelfile 換位置
```

---

## 設定檔位置

| 檔案 | 內容 |
|---|---|
| `config.py` | 後端 URL、模型清單、預設值、批次大小、context window、temperature |
| `pipeline/translate.py` | 翻譯邏輯、`SYSTEM_PROMPT`（要改翻譯口吻在此） |
| `pipeline/transcribe.py` | whisper.cpp 呼叫邏輯 |
| `Makefile` | 安裝編排 |
| `/Users/mcgrady/LLM/Qwen/Modelfile.translate` | Ollama 翻譯模型建立藍圖（參數 + system prompt） |

---

## 常見問題

### `MTPLX (Qwen3.6-27B, Apple Silicon 加速) 無法連線（http://127.0.0.1:8000）`

訊息看起來像 Apple Silicon 錯誤但其實是**後端服務沒啟動**。

兩條路：

- 啟動 MTPLX：`mtplx quickstart --model Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed --profile sustained --port 8000 --reasoning off`
- 在 GUI 切到 Ollama 後端（Ollama daemon 預設常駐）

### 記憶體不夠 / 機器卡頓

32 GB 機器跑 MTPLX 建議 `--profile sustained`，**不要用 `burst`**（會搶光記憶體導致 swap）。

若仍吃緊：

- Whisper 改用 medium（~1.5 GB）或 small（~500 MB）
- 翻譯改用 MTPLX（27B，比 Ollama 35B 省 6 GB）

### 翻譯品質不滿意

- 換後端比較
- 調整 `config.py`：
  - `TRANSLATE_BATCH_SIZE`（預設 15，調小語意更連貫但慢）
  - `TRANSLATE_CONTEXT_WINDOW`（預設 2，上下文視窗越大越連貫）
  - `TRANSLATE_TEMPERATURE`（預設 0.3，調高更自由但容易跑題）
- 改 `pipeline/translate.py` 的 `SYSTEM_PROMPT`（影響整體口吻 / 風格 / 用語規則）
- 改 `Modelfile.translate` 的 system prompt 並重建：
  ```bash
  cd /Users/mcgrady/LLM/Qwen
  ollama create qwen3.6_translate -f Modelfile.translate
  ```

### Whisper 辨識結果有錯字 / 漏句

- 影片有背景音樂或多人重疊講話 → 試 `large-v3`（已是預設最大）
- 純人聲品質仍差 → 影片可能需要先降噪（用 ffmpeg 或 Audacity 預處理）
- 特定語言辨識差 → Whisper 對該語言原本就弱（如方言、低資源語言）

### Gradio Tab 切換後欄位沒清空

Gradio 預期行為。要乾淨重來，重整瀏覽器頁面即可。

### Ollama pull 中斷

`Connection reset by peer` 等網路錯誤是 HF/Cloudflare 偶發節流。直接重跑 `ollama pull <model>` 會續傳（manifest 記錄已下載 chunk）。

---

## 升級流程

### 升級翻譯模型

1. 修改 `/Users/mcgrady/LLM/Qwen/Modelfile.translate`（換 base、改 system prompt 等）
2. 重建：
   ```bash
   make ollama
   ```
   `make ollama` 看到 `qwen3.6_translate` 已存在會跳過。**要強制重建**：先 `ollama rm qwen3.6_translate`，再 `make ollama`。

### 升級 Python 依賴

```bash
.venv/bin/pip install --upgrade -r requirements.txt
```

### 升級 whisper.cpp

```bash
cd whisper.cpp && git pull && cmake --build build --config Release -j$(sysctl -n hw.ncpu)
```

---

## 模型管理

### 查看已安裝模型

```bash
ollama list                    # Ollama 模型
mtplx models                   # MTPLX 模型
ls whisper.cpp/models/         # Whisper 模型
```

### 刪除模型省空間

```bash
ollama rm <model-name>
rm -rf ~/.mtplx/models/<model-dir>
rm whisper.cpp/models/ggml-<size>.bin
```

Ollama 用 content-addressed blob，多個模型共享 base layer，`ollama rm` 不會立刻釋放共享 layer 空間。要徹底清：`ollama prune`（如版本支援）。
