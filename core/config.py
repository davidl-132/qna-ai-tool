"""Đọc cấu hình từ file .env (một chỗ duy nhất cho mọi cài đặt)."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# Nhà cung cấp chính và dự phòng: "gemini" | "grok" | "mock" ("" = tắt dự phòng)
PROVIDER = _get("PROVIDER", "gemini").lower()
FALLBACK_PROVIDER = _get("FALLBACK_PROVIDER", "grok").lower()

GEMINI_API_KEY = _get("GEMINI_API_KEY")
GEMINI_MODEL = _get("GEMINI_MODEL", "gemini-2.5-flash")

XAI_API_KEY = _get("XAI_API_KEY")
XAI_MODEL = _get("XAI_MODEL", "grok-4.3")
XAI_BASE_URL = _get("XAI_BASE_URL", "https://api.x.ai/v1")

# Giới hạn độ dài để tiết kiệm quota
MAX_SELECTION_CHARS = int(_get("MAX_SELECTION_CHARS", "4000"))
MAX_CONTEXT_CHARS = int(_get("MAX_CONTEXT_CHARS", "1500"))

# Ngôn ngữ trả lời mặc định
DEFAULT_LANG = _get("DEFAULT_LANG", "vi")

# Server cục bộ cho extension
PORT = int(_get("PORT", "8765"))
LOCAL_TOKEN = _get("LOCAL_TOKEN")
