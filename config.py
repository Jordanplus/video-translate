"""Central configuration for the video-translate tool."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

# ---- Whisper / whisper.cpp ----
WHISPER_CPP_DIR = PROJECT_ROOT / "whisper.cpp"
WHISPER_BINARY_CANDIDATES = [
    WHISPER_CPP_DIR / "build" / "bin" / "whisper-cli",
    WHISPER_CPP_DIR / "build" / "bin" / "main",
    WHISPER_CPP_DIR / "main",
]
WHISPER_MODELS_DIR = WHISPER_CPP_DIR / "models"

WHISPER_MODELS = {
    "large-v3": "ggml-large-v3.bin",
    "medium": "ggml-medium.bin",
    "small": "ggml-small.bin",
}
DEFAULT_WHISPER_MODEL = "large-v3"

WHISPER_VAD_MODEL = WHISPER_MODELS_DIR / "ggml-silero-v6.2.0.bin"
ENABLE_VAD_DEFAULT = True

SRT_TIGHTEN_MAX_CHARS_PER_SEC = 3.0
SRT_TIGHTEN_TRIGGER_S = 5.0

WHISPER_LANGUAGES = {
    "auto": "自動偵測",
    "ja": "日文 / Japanese",
    "zh": "中文 / Chinese",
    "en": "英文 / English",
    "ko": "韓文 / Korean",
    "es": "西班牙文 / Spanish",
    "fr": "法文 / French",
    "de": "德文 / German",
    "ru": "俄文 / Russian",
}
DEFAULT_WHISPER_LANGUAGE = "auto"

# ---- Translation backends ----
# Both backends speak OpenAI-compatible chat completions API.
BACKENDS = {
    "mtplx": {
        "label": "MTPLX (Qwen3.6-27B, Apple Silicon 加速)",
        "base_url": "http://127.0.0.1:8000/v1",
        "default_model": "mtplx",
        "models": ["mtplx"],
        "supports_json_format": True,
        "health_path": "/models",
    },
    "ollama": {
        "label": "Ollama (Qwen3 etc.)",
        "base_url": "http://127.0.0.1:11434/v1",
        "default_model": "qwen3.6_translate",
        "models": ["qwen3.6_translate", "qwen3:14b", "qwen3:32b", "qwen3:8b"],
        "supports_json_format": True,
        "health_path": "/models",
    },
}
DEFAULT_BACKEND = "mtplx"

TRANSLATE_BATCH_SIZE = 25
TRANSLATE_CONTEXT_WINDOW = 2
TRANSLATE_TEMPERATURE = 0.3

# ---- Working dir ----
WORK_DIR = PROJECT_ROOT / "work"
WORK_DIR.mkdir(exist_ok=True)


def find_whisper_binary() -> Path | None:
    """Return the first existing whisper.cpp binary, or None."""
    for path in WHISPER_BINARY_CANDIDATES:
        if path.exists() and path.is_file():
            return path
    return None
