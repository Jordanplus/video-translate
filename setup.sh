#!/usr/bin/env bash
# One-shot environment setup for video_translate on macOS (Apple Silicon).
#
# Backend selection (env vars):
#   BACKEND=mtplx (default) | ollama | both
#   WHISPER_MODEL=large-v3 (default) | medium | small
#   OLLAMA_MODEL=qwen3:14b (default)
#
# Examples:
#   bash setup.sh                              # MTPLX + Whisper large-v3
#   BACKEND=ollama bash setup.sh               # Ollama only
#   BACKEND=both bash setup.sh                 # install both backends
#   WHISPER_MODEL=medium BACKEND=mtplx bash setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

BACKEND="${BACKEND:-mtplx}"
WHISPER_MODEL="${WHISPER_MODEL:-large-v3}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3:14b}"
MTPLX_MODEL="${MTPLX_MODEL:-Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed}"

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
info() { printf "→ %s\n" "$*"; }

want_mtplx() { [[ "$BACKEND" == "mtplx" || "$BACKEND" == "both" ]]; }
want_ollama() { [[ "$BACKEND" == "ollama" || "$BACKEND" == "both" ]]; }

bold "==> 1. 檢查 Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  echo "請先安裝 Homebrew: https://brew.sh"
  exit 1
fi

bold "==> 2. 安裝基礎工具 (ffmpeg, cmake)"
for pkg in ffmpeg cmake; do
  if brew list --formula | grep -qx "$pkg"; then
    info "$pkg 已安裝"
  else
    info "安裝 $pkg"
    brew install "$pkg"
  fi
done

if want_ollama; then
  bold "==> 3a. 安裝並啟動 Ollama"
  if ! brew list --formula | grep -qx ollama; then
    brew install ollama
  fi
  if ! pgrep -x ollama >/dev/null 2>&1; then
    info "啟動 ollama serve"
    brew services start ollama || nohup ollama serve >/tmp/ollama.log 2>&1 &
    sleep 2
  fi
  info "拉取 $OLLAMA_MODEL"
  ollama pull "$OLLAMA_MODEL"
fi

if want_mtplx; then
  bold "==> 3b. 安裝 MTPLX (Apple Silicon native MTP speculative decoding)"
  if ! command -v mtplx >/dev/null 2>&1; then
    info "透過 Homebrew tap 安裝 mtplx"
    brew install youssofal/mtplx/mtplx
  else
    info "mtplx 已安裝"
  fi
  info "預先下載翻譯模型 $MTPLX_MODEL（首次約需 16 GB 磁碟）"
  mtplx pull "$MTPLX_MODEL" || {
    echo "⚠️  mtplx pull 失敗。可稍後在 GUI 啟動時自動下載，或手動執行："
    echo "    mtplx pull $MTPLX_MODEL"
  }
  cat <<EOF

ℹ️  MTPLX 服務需要手動啟動：
    mtplx quickstart --model $MTPLX_MODEL --profile sustained --port 8000 --reasoning off
  （--reasoning off 關掉 thinking，批次翻譯快 ~17x。32GB 機器建議用 sustained，不要用 burst。）

EOF
fi

bold "==> 4. Clone & build whisper.cpp（Metal 加速）"
if [ ! -d whisper.cpp ]; then
  git clone --depth=1 https://github.com/ggml-org/whisper.cpp.git
fi
cd whisper.cpp
if [ ! -f build/bin/whisper-cli ] && [ ! -f build/bin/main ] && [ ! -f main ]; then
  info "編譯 whisper.cpp"
  cmake -B build -DGGML_METAL=ON >/dev/null
  cmake --build build --config Release -j
fi

bold "==> 5. 下載 Whisper 模型 $WHISPER_MODEL"
if [ ! -f "models/ggml-${WHISPER_MODEL}.bin" ]; then
  bash models/download-ggml-model.sh "$WHISPER_MODEL"
else
  info "模型已存在 models/ggml-${WHISPER_MODEL}.bin"
fi
cd "$SCRIPT_DIR"

bold "==> 6. 安裝 Python 套件"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

bold "==> ✅ 完成"
echo
echo "下一步："
if want_mtplx; then
  echo "  1. 啟動 MTPLX：mtplx quickstart --model $MTPLX_MODEL --profile sustained --port 8000 --reasoning off"
fi
echo "  2. 啟動 GUI：  python3 app.py"
echo "  3. 開瀏覽器：  http://127.0.0.1:7860"
