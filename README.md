# Highlight AI

Bôi đen text bất kì → AI giải thích / dịch / tóm tắt ngay cạnh vùng chọn.

Kiến trúc: **Chrome extension (JS)** chỉ lo giao diện, **Python backend** lo toàn bộ logic AI.
Gemini là nhà cung cấp mặc định, Grok là dự phòng.

## Cài đặt (M1: thử core trong terminal)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # Windows: copy .env.example .env
# mở .env, điền GEMINI_API_KEY (và XAI_API_KEY nếu có)

python -m scripts.list_models               # xem model Gemini key của bạn dùng được
python -m scripts.try_core "Normalization in database" --mode explain
```

Chưa có key? Đặt `PROVIDER=mock` trong `.env` để chạy thử với câu trả lời giả.

## Cấu trúc

```
core/       logic AI dùng chung (extension + desktop app sau này)
scripts/    công cụ chạy thử trong terminal
```
