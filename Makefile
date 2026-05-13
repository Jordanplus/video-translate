# Makefile — video-translate one-shot setup (macOS Apple Silicon)
#
# 常用：
#   make            一次裝齊 brew deps + whisper.cpp + python venv + ollama 翻譯模型
#   make mtplx      （選用）裝 MTPLX + 拉 Optimized-Speed 模型
#   make check      檢查各元件就緒狀態
#   make clean      移除 venv 與 whisper build（保留模型快取）
#
# 變數可在命令列覆蓋：
#   make whisper WHISPER_MODEL=medium
#   make ollama MODELFILE_TRANSLATE=/somewhere/else/Modelfile.translate

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := all

PROJECT_ROOT       := $(shell pwd)
VENV               := $(PROJECT_ROOT)/.venv
PY                 := $(VENV)/bin/python3
PIP                := $(VENV)/bin/pip

WHISPER_DIR        := $(PROJECT_ROOT)/third-party/whisper.cpp
WHISPER_BIN        := $(WHISPER_DIR)/build/bin/whisper-cli
WHISPER_MODEL      ?= large-v3
WHISPER_MODEL_FILE := $(WHISPER_DIR)/models/ggml-$(WHISPER_MODEL).bin
WHISPER_VAD_MODEL  ?= silero-v6.2.0
WHISPER_VAD_FILE   := $(WHISPER_DIR)/models/ggml-$(WHISPER_VAD_MODEL).bin

OLLAMA_BASE        ?= fredrezones55/Qwen3.6-35B-A3B-Uncensored-HauhauCS-Aggressive:Q4
OLLAMA_TARGET      ?= qwen3.6_translate
MODELFILE_TRANSLATE ?= /Users/mcgrady/LLM/Qwen/Modelfile.translate

MTPLX_MODEL        ?= Youssofal/Qwen3.6-27B-MTPLX-Optimized-Speed

.PHONY: all help brew-deps whisper python ollama mtplx check clean

all: brew-deps whisper python ollama
	@echo ""
	@echo "✅ 全部就緒"
	@echo "啟動 GUI:  $(PY) scripts/gui/app.py"
	@echo "想用 MTPLX 後端：make mtplx 後執行 mtplx quickstart --profile sustained --port 8000"

help:
	@echo "Targets:"
	@echo "  all          install brew deps + whisper.cpp + python venv + ollama 翻譯模型"
	@echo "  brew-deps    install ffmpeg, cmake"
	@echo "  whisper      clone+build whisper.cpp (Metal)；下載 ggml-$(WHISPER_MODEL).bin + VAD"
	@echo "  python       建立 .venv 並裝 requirements.txt"
	@echo "  ollama       pull base + create $(OLLAMA_TARGET)"
	@echo "  mtplx        (optional) install mtplx + pull $(MTPLX_MODEL)"
	@echo "  check        檢查所有元件就緒"
	@echo "  clean        移除 venv 和 whisper build（保留模型）"

# ---- brew dependencies ----
brew-deps:
	@command -v brew >/dev/null || { echo "請先裝 Homebrew: https://brew.sh"; exit 1; }
	@for pkg in ffmpeg cmake; do \
	  if brew list --formula 2>/dev/null | grep -qx "$$pkg"; then \
	    echo "✓ $$pkg"; \
	  else \
	    echo "→ brew install $$pkg"; brew install $$pkg; \
	  fi; \
	done

# ---- whisper.cpp ----
$(WHISPER_DIR)/.git:
	git clone --depth=1 https://github.com/ggml-org/whisper.cpp.git $(WHISPER_DIR)

$(WHISPER_BIN): | $(WHISPER_DIR)/.git
	cd $(WHISPER_DIR) && cmake -B build -DGGML_METAL=ON && cmake --build build --config Release -j$$(sysctl -n hw.ncpu)

$(WHISPER_MODEL_FILE): | $(WHISPER_DIR)/.git
	cd $(WHISPER_DIR) && bash models/download-ggml-model.sh $(WHISPER_MODEL)

$(WHISPER_VAD_FILE): | $(WHISPER_DIR)/.git
	cd $(WHISPER_DIR) && bash models/download-vad-model.sh $(WHISPER_VAD_MODEL)

whisper: brew-deps $(WHISPER_BIN) $(WHISPER_MODEL_FILE) $(WHISPER_VAD_FILE)
	@echo "✓ whisper.cpp + ggml-$(WHISPER_MODEL).bin + ggml-$(WHISPER_VAD_MODEL).bin"

# ---- Python venv ----
$(VENV)/bin/python3:
	python3 -m venv $(VENV)

$(VENV)/.deps.stamp: requirements.txt | $(VENV)/bin/python3
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@touch $@

python: $(VENV)/.deps.stamp
	@echo "✓ python venv at $(VENV)"

# ---- Ollama ----
ollama:
	@command -v ollama >/dev/null || { echo "→ brew install ollama"; brew install ollama; }
	@brew services start ollama >/dev/null 2>&1 || true
	@curl -s --retry 5 --retry-delay 1 http://127.0.0.1:11434/api/tags >/dev/null || { echo "ollama daemon 未啟動"; exit 1; }
	@if ollama list 2>/dev/null | awk '{print $$1}' | grep -qx "$(OLLAMA_TARGET):latest"; then \
	  echo "✓ $(OLLAMA_TARGET) 已存在"; \
	else \
	  echo "→ ollama pull $(OLLAMA_BASE)"; \
	  ollama pull $(OLLAMA_BASE); \
	  if [ ! -f "$(MODELFILE_TRANSLATE)" ]; then \
	    echo "✗ 找不到 Modelfile: $(MODELFILE_TRANSLATE)"; \
	    echo "  覆蓋路徑：make ollama MODELFILE_TRANSLATE=/path/to/Modelfile.translate"; \
	    exit 1; \
	  fi; \
	  cd "$$(dirname $(MODELFILE_TRANSLATE))" && ollama create $(OLLAMA_TARGET) -f "$$(basename $(MODELFILE_TRANSLATE))"; \
	  echo "✓ ollama 翻譯模型 $(OLLAMA_TARGET) 建立完成"; \
	fi

# ---- MTPLX (Apple Silicon native MTP, optional) ----
mtplx:
	@command -v mtplx >/dev/null || { echo "→ brew install youssofal/mtplx/mtplx"; brew install youssofal/mtplx/mtplx; }
	@mtplx --help >/dev/null 2>&1 || true
	@if mtplx models 2>/dev/null | grep -q "$(MTPLX_MODEL)"; then \
	  echo "✓ MTPLX 模型已存在"; \
	else \
	  echo "→ mtplx pull $(MTPLX_MODEL) (~16 GB)"; \
	  mtplx pull $(MTPLX_MODEL); \
	fi
	@echo ""
	@echo "啟動 MTPLX 服務（手動）："
	@echo "  mtplx quickstart --profile sustained --port 8000"

# ---- Health check ----
check:
	@printf "ffmpeg            : "; command -v ffmpeg >/dev/null && echo "✓" || echo "✗"
	@printf "cmake             : "; command -v cmake >/dev/null && echo "✓" || echo "✗"
	@printf "whisper binary    : "; [ -f $(WHISPER_BIN) ] && echo "✓" || echo "✗  → make whisper"
	@printf "whisper model     : "; [ -f $(WHISPER_MODEL_FILE) ] && echo "✓  $$(du -h $(WHISPER_MODEL_FILE) | awk '{print $$1}')" || echo "✗  → make whisper"
	@printf "whisper VAD model : "; [ -f $(WHISPER_VAD_FILE) ] && echo "✓  $$(du -h $(WHISPER_VAD_FILE) | awk '{print $$1}')" || echo "✗  → make whisper"
	@printf "python venv       : "; [ -x $(PY) ] && echo "✓  $$($(PY) --version)" || echo "✗  → make python"
	@printf "gradio installed  : "; $(PY) -c "import gradio" 2>/dev/null && echo "✓" || echo "✗  → make python"
	@printf "ollama daemon     : "; curl -s --max-time 2 http://127.0.0.1:11434/api/tags >/dev/null && echo "✓" || echo "✗  → brew services start ollama"
	@printf "ollama translate  : "; ollama list 2>/dev/null | awk '{print $$1}' | grep -qx "$(OLLAMA_TARGET):latest" && echo "✓" || echo "✗  → make ollama"
	@printf "mtplx (optional)  : "; command -v mtplx >/dev/null && echo "✓" || echo "(未安裝；make mtplx 啟用)"
	@printf "mtplx model       : "; \
	  if command -v mtplx >/dev/null && mtplx models 2>/dev/null | grep -q "$(MTPLX_MODEL)"; then \
	    if find ~/.mtplx/models -name "*.incomplete" 2>/dev/null | grep -q .; then \
	      echo "下載中（仍有 incomplete shards）"; \
	    else \
	      echo "✓"; \
	    fi; \
	  else echo "(未下載；make mtplx 啟用)"; fi

# ---- Clean (preserves models) ----
clean:
	rm -rf $(VENV)
	rm -rf $(WHISPER_DIR)/build
	@echo "cleaned: .venv + third-party/whisper.cpp/build（模型保留）"
