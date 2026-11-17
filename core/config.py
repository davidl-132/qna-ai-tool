"""Đọc cấu hình từ file .env (một chỗ duy nhất cho mọi cài đặt)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# Nhà cung cấp chính và dự phòng: "gemini" | "groq" | "grok" | "mock" ("" = tắt dự phòng)
PROVIDER = _get("PROVIDER", "gemini").lower()
FALLBACK_PROVIDER = _get("FALLBACK_PROVIDER", "grok").lower()

GEMINI_API_KEY = _get("GEMINI_API_KEY")
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-2.5-flash")
# Model dự phòng (cách nhau bằng dấu phẩy) khi model chính quá tải (503) hoặc không tồn tại
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in _get("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash-lite").split(",") if m.strip()
]
# Số lần thử lại cho MỖI model khi gặp lỗi tạm thời (429/500/502/503/504)
GEMINI_RETRIES = int(_get("GEMINI_RETRIES", "2"))

XAI_API_KEY = _get("XAI_API_KEY")
XAI_MODEL = _get("XAI_MODEL", "grok-4.3")
XAI_BASE_URL = _get("XAI_BASE_URL", "https://api.x.ai/v1")

# Groq (groq.com, KHÁC Grok của xAI) - có gói miễn phí, API kiểu OpenAI
GROQ_API_KEY = _get("GROQ_API_KEY")
GROQ_MODEL = _get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = _get("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
# Model Groq có đọc được ảnh (để trống = Groq chỉ trả lời bằng chữ). Xem console.groq.com/docs/models
GROQ_VISION_MODEL = _get("GROQ_VISION_MODEL")

# Giới hạn độ dài để tiết kiệm quota
MAX_SELECTION_CHARS = int(_get("MAX_SELECTION_CHARS", "4000"))
MAX_CONTEXT_CHARS = int(_get("MAX_CONTEXT_CHARS", "1500"))

# Ảnh chụp màn hình: giới hạn dung lượng gửi đi (byte)
MAX_IMAGE_BYTES = int(_get("MAX_IMAGE_BYTES", "7000000"))

# Ngôn ngữ trả lời mặc định
DEFAULT_LANG = _get("DEFAULT_LANG", "vi")

# Server cục bộ cho extension
PORT = int(_get("PORT", "8765"))
LOCAL_TOKEN = _get("LOCAL_TOKEN")
