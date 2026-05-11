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

**目前狀態**：程式碼完成、commit 完成（`4432114`），等待在 MacBook 上實機驗證。

---

## 待驗證項目（部署到 MacBook M5 32GB 後）

### A. 環境安裝（`setup.sh`）

- [ ] Homebrew 裝得起 ffmpeg、cmake
- [ ] `brew install youssofal/mtplx/mtplx` 成功
- [ ] `mtplx pull Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed` 完成（~16GB）
- [ ] whisper.cpp clone & cmake build 成功（Metal 加速應自動偵測）
- [ ] `ggml-large-v3.bin` 下載成功（~3GB）
- [ ] `pip install -r requirements.txt` 全裝完

### B. 後端服務

- [ ] `mtplx quickstart --profile sustained --port 8000` 能起來
- [ ] `curl http://127.0.0.1:8000/v1/models` 回 200
- [ ] **記憶體實測**：在 32GB 機器上載入模型，活動監視器看 unified memory 用量是否在 80% 以下
- [ ] 若 MTPLX 過於吃緊：fallback 改用 `BACKEND=ollama` + qwen3:14b（~10GB）

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
