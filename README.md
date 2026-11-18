# Highlight AI

AI trả lời cho thứ bạn đang đọc, theo 2 cách:

| | Cách dùng | Mô tả | Hướng dẫn từng bước |
|---|---|---|---|
| 🌐 | **Extension Chrome** | Bôi đen chữ trên web → AI giải thích / dịch / tóm tắt / giải bài cạnh vùng chọn | [HUONG_DAN_EXTENSION.md](HUONG_DAN_EXTENSION.md) |
| 📷 | **Chụp ảnh (desktop)** | Win+Shift+S ở bất kỳ đâu trên máy → AI đọc ảnh và trả lời | [HUONG_DAN_CHUP_ANH.md](HUONG_DAN_CHUP_ANH.md) |
| 🪟 | **App popup (desktop)** | Ctrl+Alt+3 chụp màn hình, Ctrl+Alt+1/2 hiện/ẩn khung đáp án nhỏ, có lịch sử | [HUONG_DAN_POPUP.md](HUONG_DAN_POPUP.md) |

**Đọc [HUONG_DAN.md](HUONG_DAN.md) trước** (cài Python, lấy key, cài thư viện, điền `.env`), rồi đọc hướng dẫn của cách dùng bạn chọn.

- **`core/`** chứa toàn bộ logic AI, dùng chung cho cả hai cách.
- **Gemini** là nhà cung cấp mặc định. **Groq** (hoặc Grok của xAI) tự động dự phòng khi Gemini lỗi (quá tải, hết quota, sai key...). Gemini cũng tự thử lại và đổi model dự phòng khi gặp lỗi tạm thời.
- API key chỉ nằm trong `.env` phía Python, không bao giờ nằm trong trình duyệt.
- Chạy được trên máy có Application Control: chỉ dùng thư viện thuần Python (`httpx`, `ctypes`, `zlib`), không cần file DLL lạ.

```
🌐 Bôi đen ─► content.js ──► background.js ──HTTP + token──► api/main.py ──┐
                                                                            ├──► core/ ──► Gemini
📷 Win+Shift+S ─► clipboard ─► desktop/watcher.py ─────────────────────────┘        └──► Groq (dự phòng)
```

## Bắt đầu nhanh

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env      :: điền GEMINI_API_KEY (và GROQ_API_KEY nếu có)
python -m scripts.test_models      :: xem model nào dùng được → điền GEMINI_MODEL

python -m api.main                 :: 🌐 extension (cần thêm bước nạp extension, xem hướng dẫn)
python -m desktop.watcher          :: 📷 chụp ảnh
python -m desktop.app              :: 🪟 app popup (phím tắt)
```

Chưa có key? Đặt `PROVIDER=mock` và `FALLBACK_PROVIDER=` trong `.env` để chạy thử với câu trả lời giả.

## API (cho client khác)

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
core/          logic AI dùng chung (extension + chụp ảnh)
  llm.py         gọi Gemini / Groq / Grok / mock, retry, đổi model, tự chuyển dự phòng, nhận ảnh
  prompts.py     prompt cho chữ (MODES) và cho ảnh (IMAGE_MODES), chống prompt injection
  review.py      vòng tự kiểm tra: nháp rồi xem lại ảnh để xác nhận/sửa (dùng bởi app popup)
  context.py     làm sạch, cắt ngắn text
  history.py     lịch sử SQLite
api/           FastAPI server cho extension (token, CORS, SSE)
extension/     Chrome extension (Manifest V3)
  content.js     bắt vùng bôi đen, nút nổi, Shadow DOM
  panel.js       popup trả lời (dùng chung với answer.html)
  background.js  gọi server, đọc SSE, menu chuột phải
  options.*      cài đặt + lịch sử
desktop/       app chụp ảnh (Windows)
  clipboard.py   đọc ảnh từ clipboard bằng ctypes, đổi sang PNG bằng zlib
  watcher.py     theo dõi clipboard, gọi AI
  app.py         app popup: phím tắt + khung đáp án (python -m desktop.app)
  controller.py  điều khiển app popup (kèm vòng tự kiểm tra lại đáp án): lịch sử, ẩn/hiện, chụp + hỏi AI
  popup.py       khung đáp án tkinter ở góc màn hình
  hotkeys.py     phím tắt toàn cục (RegisterHotKey)
  screen.py      chụp màn hình bằng ctypes
  ui.py          giao diện terminal: khung màu bằng thư viện rich (hoặc chữ thường với --plain)
scripts/       công cụ chạy thử trong terminal
  list_models.py   liệt kê model Gemini
  test_models.py   thử gọi từng model xem cái nào dùng được
  try_core.py      hỏi bằng chữ  |  try_image.py   hỏi bằng ảnh
tests/         kiểm thử
```
