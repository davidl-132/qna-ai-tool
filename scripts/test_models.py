"""Thử gọi từng model Gemini bằng 1 câu ngắn để biết model nào THẬT SỰ dùng được với key của bạn.

Chạy:  py -m scripts.test_models                  (thử các model gợi ý)
       py -m scripts.test_models gemini-3.5-flash  (thử model chỉ định)
"""
import sys
import time

from core import config

CANDIDATES = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
]


def main() -> None:
    if not config.GEMINI_API_KEY:
        sys.exit("Thiếu GEMINI_API_KEY trong .env")
    from google import genai

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    models = sys.argv[1:] or CANDIDATES
    for m in models:
        t = time.time()
        try:
            r = client.models.generate_content(model=m, contents="Trả lời đúng 1 từ: xin chào")
            text = (r.text or "").strip().replace("\n", " ")[:40]
            print(f"OK    {m:28} {time.time() - t:4.1f}s  → {text}")
        except Exception as e:  # noqa: BLE001
            msg = " ".join(str(e).split())[:110]
            print(f"LỖI   {m:28} {msg}")


if __name__ == "__main__":
    main()
