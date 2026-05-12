# 實作進度與待驗證項目

## 進度總覽

| 模組 | 狀態 | 備註 |
|---|---|---|
| 專案骨架 / config.py / requirements.txt | ✅ 完成 | |
| `pipeline/srt.py` | ✅ 完成 | pysrt 包裝、replace_texts、preview |
| `pipeline/audio.py` | ✅ 完成 | ffmpeg → 16kHz mono wav |
| `pipeline/download.py` | ✅ 完成 | yt-dlp，audio-only / full-video |
| `pipeline/transcribe.py` | ✅ 完成 | whisper.cpp CLI、progress 解析 |
| `pipeline/translate.py` | ✅ 完成 | OpenAI 相容雙後端、批次 + fallback |
| `app.py` Gradio GUI | ✅ 完成 | Tabs、後端切換、4 階段進度 |
| `setup.sh` 一鍵安裝 | ✅ 完成 | `BACKEND=mtplx\|ollama\|both` |
| MTPLX 後端支援 | ✅ 完成 | OpenAI-compatible，預設 backend |
| `README.md` / `PLAN.md` / `STATUS.md` | ✅ 完成 | |

**目前狀態**：MacBook 實機 e2e 跑通（Ollama 後端）。MTPLX 後端阻塞中。

---

## 實測結果（2026-05-13）

### 環境
- MacBook M5 32GB，macOS 15.4 (Darwin 25.4.0)
- 測試素材：`nsps-808.mp4` 內第 10 分鐘起 60s clip（日文對白）

### Pipeline 計時

| 階段 | 耗時 | 備註 |
|---|---|---|
| audio (ffmpeg) | 0.1 s | |
| whisper transcribe (large-v3, Metal) | 9.4 s | ~6.4× 實時；自動偵測 `ja` |
| translate (Ollama Qwen3.6, **think=false**) | 192.6 s | 14 條全部成功 |
| write SRT | 0.0 s | |
| **總計** | **202 s（60s 影片 ≈ 3.4× 實時）** | |

### Ollama tokens/sec（qwen3.6_translate, 22GB）
- Prompt eval: **243 tok/s**
- Generation: **23.3 tok/s**

### 翻譯品質抽樣
- そうカリカリすんなよ → 別那麼火大啦 ✅
- 理想と現実ってやつだよ → 這就是理想跟現實的落差啦 ✅
- まああの人の言う通りにすれば間違いないから → 嘛，只要照他說的做就不會出錯 ✅

---

## 重要發現 / 修正

### 1. Reasoning model 必須關 thinking（`pipeline/translate.py`）
Qwen3.6 reasoning 模型預設無限 chain-of-thought，把所有 num_predict 燒在 `<think>...</think>` 區塊，`response` 是空字串。表現：14 條字幕 batch 跑 34 分鐘只成功 1 條。
- 修法：Ollama backend 的 chat payload 加 `"think": false`
- 效果：34 分鐘 → 3.2 分鐘（**10.7× 加速**），成功率 1/14 → 14/14
- 注意：這是 per-request 旗標，不影響其他用戶（coding agent 仍可開 thinking）

### 2. MTPLX 後端目前無法啟動（阻塞中）
`mtplx inspect` 認模型（tier=verified, mtp_layers=1），但 `mtplx quickstart` 進 loading 階段就拒絕（tier=no-MTP）。
- 已試：profile `sustained`、`performance-cold`、`--no-mtp`、`--unsafe-force-unverified` — 4 種 flag 組合全失敗
- 已試：mtplx 0.3.3 → 降到 0.3.2 → 同樣失敗
- 結論：疑似 MTPLX 0.3.x 的 inspect / runtime gate 邏輯不一致
- 暫時對策：`DEFAULT_BACKEND = "ollama"`

### 3. 已知小 bug
- Whisper 偶爾轉錯日文罕用詞（測試中「逆鱗 げきりん」變成「激霖」）；不是翻譯端問題

---

## 待驗證項目

### A. 環境安裝（`setup.sh` / `Makefile`）

- [x] Homebrew 裝起 ffmpeg、cmake
- [x] `brew install youssofal/mtplx/mtplx` 成功（但 runtime 有 bug，見上）
- [x] `mtplx pull` 完成（16.4 GB）
- [x] whisper.cpp Metal 編譯成功
- [x] `ggml-large-v3.bin` 下載（2.9 GB）
- [x] `pip install -r requirements.txt`

### B. 後端服務

- [ ] ~~MTPLX 啟動~~ — **阻塞**：見上「重要發現 #2」
- [x] Ollama daemon 健康、`qwen3.6_translate:latest` 載入正常（23 GB RSS）

### C. 模組單元驗證（建議手動跑）

- [ ] `pipeline/audio.py`：丟 30 秒 mp4，產出 16kHz mono wav，`ffprobe` 確認規格
- [ ] `pipeline/transcribe.py`：對該 wav 跑 whisper，SRT 內容合理、時間軸正確
- [ ] `pipeline/srt.py`：parse → write round-trip 內容一致
- [ ] `pipeline/translate.py`：固定 5 條英文字幕，回傳 5 條繁中、編號對齊
- [ ] `pipeline/download.py`：YouTube 短連結（audio-only）能拉成 wav

### D. 端到端（最重要）

- [ ] **本地檔案路徑**：1 分鐘英文 mp4 → 繁中 SRT，VLC 載入時間軸正確
- [ ] **URL 路徑**：1 分鐘 YouTube 短片 → 繁中 SRT
- [ ] **多語言**：1 分鐘日文短片 → Whisper 自動偵測 `ja` → 繁中
- [ ] **GUI 顯示**：4 階段 progress bar、結果預覽、SRT 下載按鈕都動作正常
- [ ] **後端切換**：GUI 從 MTPLX 切到 Ollama，模型清單會自動換

### E. 品質檢查（人工）

- [ ] 翻譯用台灣用語（「影片」非「視頻」、「軟體」非「軟件」）
- [ ] 不會出現 markdown / JSON 殘留在字幕裡
- [ ] 長句子（>50 字）不會被合併或拆開（時間軸不會偏）
- [ ] 笑聲、嘆氣等情緒詞有保留

---

## 已知風險與緩解

| 風險 | 影響 | 緩解 |
|---|---|---|
| 32GB 跑 MTPLX 27B 太緊 | 翻譯後端起不來 | fallback 到 Ollama Qwen3:14B，setup.sh 跑 `BACKEND=both` 預先裝好 |
| whisper.cpp Metal 編譯失敗 | 辨識速度大幅變慢 | 退回 CPU build；或裝 `xcode-select --install` 後重試 |
| yt-dlp 對特定網站失效 | URL 路徑無法用 | yt-dlp 常更新，`pip install -U yt-dlp` 即可 |
| Qwen 翻譯 JSON 格式偶爾跑掉 | 部分字幕保留原文 | translate.py 已有 markdown fence + 單句 fallback，最後保底用原文 |
| MTPLX 模型 id 不是 `mtplx` | 翻譯 API 報 model not found | 在 GUI 模型下拉手動填正確 id；或改 `config.py` `BACKENDS["mtplx"]["models"]` |

---

## 可日後擴充（本次刻意不做）

- 雙語字幕（原文 + 譯文同時顯示）
- VTT 輸出
- 燒錄字幕回影片（ffmpeg subtitle filter）
- 批次處理多個影片
- 翻譯結果手動編輯介面
- 字幕風格選項（口語 vs 正式）
