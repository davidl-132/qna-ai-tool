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

## M2: chạy server cục bộ

```bash
python -m api.main
```

Lần chạy đầu, server tự tạo `LOCAL_TOKEN`, ghi vào `.env` và in ra màn hình (sẽ dán vào extension).
Server chỉ nghe trên `127.0.0.1:8765`, mọi request phải kèm header `X-Local-Token`.

```bash
curl http://127.0.0.1:8765/health
curl -X POST http://127.0.0.1:8765/ask -H "Content-Type: application/json" \
     -H "X-Local-Token: <token>" -d '{"selection": "TCP handshake", "mode": "explain"}'
```

## Cấu trúc

```
core/       logic AI dùng chung (extension + desktop app sau này)
api/        FastAPI server cho extension
scripts/    công cụ chạy thử trong terminal
```
