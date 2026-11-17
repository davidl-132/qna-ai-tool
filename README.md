# Highlight AI

Bôi đen text bất kì trên trang web → AI giải thích / dịch / tóm tắt / giải bài ngay cạnh vùng chọn.

- **Chrome extension (JS)** chỉ lo giao diện: nút nổi, popup, menu chuột phải.
- **Python backend (FastAPI)** lo toàn bộ logic AI, chạy trên máy bạn ở `127.0.0.1`.
- **Gemini** là nhà cung cấp mặc định, **Grok** tự động dự phòng khi Gemini lỗi (hết quota, sai key...).
- API key chỉ nằm trong `.env` phía Python, không bao giờ nằm trong trình duyệt.

```
Bôi đen ─► content.js ──port──► background.js ──HTTP + token──► api/main.py ──► core/ ──► Gemini
                ▲                                                                        └─► Grok (dự phòng)
                └────────────────────── chữ hiện dần (SSE) ◄─────────────────────────────┘
```

## Cài đặt

### 1. Backend Python

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # Windows: copy .env.example .env
# mở .env, điền GEMINI_API_KEY (và XAI_API_KEY nếu có)

python -m scripts.list_models    # xem model Gemini key của bạn dùng được → điền GEMINI_MODEL
python -m scripts.try_core "Normalization in database" --mode explain   # thử trong terminal
```

Chưa có key? Đặt `PROVIDER=mock` trong `.env` để chạy thử với câu trả lời giả.

### 2. Chạy server

```bash
python -m api.main
```

Lần chạy đầu, server tự tạo `LOCAL_TOKEN`, ghi vào `.env` và in ra màn hình. Giữ cửa sổ này mở khi dùng extension.

### 3. Cài extension vào Chrome

1. Mở `chrome://extensions`, bật **Developer mode** (góc phải trên).
2. Bấm **Load unpacked**, chọn thư mục `extension/`.
3. Bấm icon Highlight AI trên thanh công cụ → dán token → **Kiểm tra kết nối**.

## Cách dùng

| Thao tác | Kết quả |
| --- | --- |
| Bôi đen text | Hiện nút **✦ Hỏi AI** dưới vùng chọn |
| Bấm nút / chuột phải → **Hỏi AI** | Popup trả lời, chữ hiện dần |
| Tab **Giải thích / Dịch / Tóm tắt / Trả lời** | Hỏi lại theo chế độ khác |
| Ô **Hỏi tiếp** | Hỏi thêm về cùng đoạn đó, AI nhớ các lượt trước |
| **■ Dừng**, **Copy**, **Thử lại**, phím **Esc** | Ngắt, chép, hỏi lại, đóng |
| Trang cài đặt → **Lịch sử gần đây** | Xem các câu đã hỏi (lưu trong `data/history.db`) |

Lưu ý:

- Tab đã mở từ trước khi cài extension cần tải lại trang (F5).
- **File PDF** trong Chrome: nút nổi không xuất hiện; dùng chuột phải → **Hỏi AI**, câu trả lời mở trong cửa sổ nhỏ riêng.
- Không hoạt động ở `chrome://`, Chrome Web Store, và Google Docs/Sheets (vẽ bằng canvas).
- Ô mật khẩu luôn bị bỏ qua. Thêm trang nhạy cảm (ngân hàng, email) vào ô **Không hiện nút trên các trang**.
- Free tier của Gemini có thể dùng nội dung bạn gửi để cải thiện sản phẩm; đừng gửi thông tin nhạy cảm.
- Sửa code extension xong, bấm nút tải lại (↻) ở thẻ extension trong `chrome://extensions`.

## API (cho client khác, ví dụ desktop app sau này)

| Endpoint | Token | Mô tả |
| --- | --- | --- |
| `GET /health` | không | Server có chạy không, đang dùng provider nào |
| `GET /auth-check` | có | Kiểm tra token |
| `POST /ask` | có | Trả lời một lần (JSON) |
| `POST /ask/stream` | có | Trả lời dạng stream (SSE: `meta`, chữ, `done`, `error`) |
| `GET /history?limit=20`, `DELETE /history` | có | Xem / xoá lịch sử |

Body của `/ask`: `{"selection", "context", "page_title", "mode": "explain|translate|summarize|answer", "lang": "vi|en", "followup": [{"role", "content"}]}`.
Token gửi qua header `X-Local-Token`.

```bash
curl -N -X POST http://127.0.0.1:8765/ask/stream -H "Content-Type: application/json" \
     -H "X-Local-Token: <token>" -d '{"selection": "TCP handshake", "mode": "explain"}'
```

## Kiểm thử

```bash
python -m unittest -v     # chạy với provider mock, không tốn quota
```

## Cấu trúc

```
core/          logic AI dùng chung (extension + desktop app sau này)
  llm.py         gọi Gemini / Grok / mock, tự chuyển dự phòng
  prompts.py     prompt theo mode, chống prompt injection
  context.py     làm sạch, cắt ngắn text
  history.py     lịch sử SQLite
api/           FastAPI server cho extension (token, CORS, SSE)
extension/     Chrome extension (Manifest V3)
  content.js     bắt vùng bôi đen, nút nổi, Shadow DOM
  panel.js       popup trả lời (dùng chung với answer.html)
  background.js  gọi server, đọc SSE, menu chuột phải
  options.*      cài đặt + lịch sử
scripts/       công cụ chạy thử trong terminal
tests/         kiểm thử
```
