# 📷 Hướng dẫn: Chụp ảnh rồi hỏi AI (desktop)

Bấm **Win+Shift+S**, kéo chọn một vùng màn hình (web, PDF, game, app nào cũng được) → ảnh vào clipboard → AI đọc ảnh và trả lời ngay trong terminal.

Cách này **không cần Chrome, không cần server, không cần token**. Chỉ cần một cửa sổ PowerShell chạy watcher.
Làm [phần A trong HUONG_DAN.md](HUONG_DAN.md) (cài đặt chung) trước, rồi thử `python -m scripts.try_image test.png` để chắc key của bạn đọc được ảnh.

## 1. Chạy

```bat
cd /d <thư-mục-dự-án>
.venv\Scripts\activate
python -m desktop.watcher
```

Thấy dòng `Đang theo dõi clipboard...` là sẵn sàng. **Giữ cửa sổ này mở**; dừng bằng **Ctrl+C**.

## 2. Cách dùng

1. Bấm **Win+Shift+S**.
2. Kéo chọn vùng cần hỏi (bài tập, đoạn chữ tiếng Anh, biểu đồ, lỗi trên màn hình...).
3. Khoảng 1 giây sau, terminal hiện `📷 Nhận ảnh ...` rồi câu trả lời chạy ra từng đoạn. Cuối cùng là `[gemini / tên-model]` cho biết model nào trả lời.

## 3. Tùy chọn khi chạy

| Lệnh | Tác dụng |
|---|---|
| `python -m desktop.watcher` | Chế độ mặc định `answer`: giải bài, hoặc giải thích ảnh nếu không có câu hỏi |
| `python -m desktop.watcher --mode explain` | Giải thích nội dung trong ảnh |
| `python -m desktop.watcher --mode translate` | Đọc chữ trong ảnh và dịch |
| `python -m desktop.watcher --mode summarize` | Tóm tắt thành 3–5 ý |
| `python -m desktop.watcher --question "đáp án đúng là gì?"` | Gửi kèm một câu hỏi cho mọi ảnh |
| `python -m desktop.watcher --lang en` | Trả lời bằng tiếng Anh |

Có thể kết hợp, ví dụ: `python -m desktop.watcher --mode translate --lang vi`.

## 4. Watcher xử lý thế nào

| Tình huống | Kết quả |
|---|---|
| Ảnh đã có sẵn trong clipboard lúc khởi động | Bỏ qua, chỉ hỏi ảnh mới |
| Copy chữ (Ctrl+C) | Bỏ qua |
| Chụp hoặc copy lại đúng ảnh vừa hỏi | Không hỏi lại |
| Ảnh lớn hơn 7 MB | Tự thu nhỏ trước khi gửi |
| **Mọi ảnh mới vào clipboard**, kể cả ảnh copy từ web | Đều được hỏi AI |

## 5. Giới hạn

- Chỉ chạy trên **Windows**.
- Gemini đọc được ảnh. **Groq** mặc định dùng model chữ nên không đọc được ảnh; nếu Gemini lỗi thì phần ảnh sẽ không có dự phòng, trừ khi bạn điền `GROQ_VISION_MODEL` (tên model ảnh xem ở console.groq.com/docs/models).
- Câu trả lời hiện trong terminal dạng chữ thường (chưa có cửa sổ riêng, chưa hỏi tiếp được).
- Đừng chụp mật khẩu, thông tin ngân hàng, tin nhắn riêng tư (ảnh được gửi lên Google).

## 6. Lỗi riêng của chụp ảnh

| Thấy gì | Cách xử lý |
|---|---|
| Chụp xong mà không thấy gì | Đợi vài giây. Chắc chắn đã kéo chọn xong vùng (không chỉ bấm Win+Shift+S). Xem watcher còn chạy không |
| `Groq đang dùng model chữ, không đọc được ảnh` | Gemini đã lỗi nên chuyển sang Groq. Chọn lại model Gemini chạy được (`python -m scripts.test_models`) |
| `Ảnh quá lớn` | Chụp vùng nhỏ hơn, hoặc tăng `MAX_IMAGE_BYTES` trong `.env` |
| `Chỉ chạy trên Windows` | Watcher cần Windows |
| `AttributeError: ... MAX_IMAGE_BYTES` | File `core/config.py` là bản cũ. Lấy lại bản mới |
| Sửa `.env` hoặc code mà không thấy đổi | Ctrl+C rồi chạy lại `python -m desktop.watcher` |

Lỗi về AI (503, 404, 429, thiếu key...): xem [mục B trong HUONG_DAN.md](HUONG_DAN.md).
