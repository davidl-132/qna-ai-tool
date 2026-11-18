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

# App popup (desktop/app.py): phím tắt toàn cục và hành vi khung đáp án
# Phím tắt duy nhất còn lại ngoài Left Alt/Left Shift bấm đơn (HOTKEY_SHOW/HIDE/CAPTURE đã bỏ, có trong .env cũng bị bỏ qua)
HOTKEY_TOGGLE = _get("HOTKEY_TOGGLE", "ctrl+alt+0")  # bật/tắt toàn bộ app; để trống = không dùng
# Vòng tự kiểm tra: AI viết nháp rồi xem lại ảnh một lượt nữa (tốn thêm 1 lượt gọi AI mỗi lần chụp)
AGENT_REVIEW = _get("AGENT_REVIEW", "1").lower() in ("1", "true", "yes", "on")
# Độ đậm của khung popup (1.0 = đặc, 0.2 = rất mờ) và chế độ "ghost" (Windows, mặc định BẬT): nền biến mất, chỉ còn chữ
POPUP_OPACITY = float(_get("POPUP_OPACITY", "0.96"))
POPUP_GHOST = _get("POPUP_GHOST", "1").lower() in ("1", "true", "yes", "on")
# Bấm đơn một phím bổ trợ (lalt, ralt, lshift, rshift, lctrl, rctrl; để trống = không dùng)
TAP_CAPTURE = _get("TAP_CAPTURE", "lalt")  # chụp màn hình rồi hỏi AI
TAP_POPUP = _get("TAP_POPUP", "lshift")  # ẩn/hiện khung popup
# Tự tra chữ bôi đen ở mọi app: giữ nguyên vùng chọn SELECT_SETTLE giây thì tra
SELECT_AUTO = _get("SELECT_AUTO", "1").lower() in ("1", "true", "yes", "on")
SELECT_SETTLE = float(_get("SELECT_SETTLE", "1.0"))
SELECT_BLOCK_APPS = _get("SELECT_BLOCK_APPS", "")  # để trống = dùng danh sách mặc định (terminal, explorer, mstsc)
SELECT_ONLY_APPS = _get("SELECT_ONLY_APPS", "")  # nếu điền (vd. chrome.exe,winword.exe): chỉ tra trong các app này
# Khi khung đang hiện: mũi tên Trái/Phải = xem câu trước/sau (app nuốt 2 phím này lúc đó; ẩn khung để dùng lại bình thường)
NAV_KEYS = _get("NAV_KEYS", "1").lower() in ("1", "true", "yes", "on")
POPUP_AUTO_SHOW = _get("POPUP_AUTO_SHOW", "0").lower() in ("1", "true", "yes", "on")

# Ngôn ngữ trả lời mặc định
DEFAULT_LANG = _get("DEFAULT_LANG", "vi")

# Server cục bộ cho extension
PORT = int(_get("PORT", "8765"))
LOCAL_TOKEN = _get("LOCAL_TOKEN")
