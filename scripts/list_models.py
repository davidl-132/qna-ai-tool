"""In ra các model Gemini mà key của bạn dùng được.

    python -m scripts.list_models

Chọn một tên (bỏ tiền tố "models/") rồi điền vào GEMINI_MODEL trong .env.
"""
from google import genai

from core import config

if not config.GEMINI_API_KEY:
    raise SystemExit("Chưa có GEMINI_API_KEY trong .env")

client = genai.Client(api_key=config.GEMINI_API_KEY)
for m in client.models.list():
    actions = getattr(m, "supported_actions", None) or []
    if not actions or "generateContent" in actions:
        print(m.name.removeprefix("models/"))
