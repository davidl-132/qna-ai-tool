# 📷 Hướng dẫn: Chụp ảnh rồi hỏi AI (desktop)

Bấm **Win+Shift+S**, kéo chọn một vùng màn hình (web, PDF, game, app nào cũng được) → ảnh vào clipboard → AI đọc ảnh và trả lời ngay trong terminal.

Cách này **không cần Chrome, không cần server, không cần token**. Chỉ cần một cửa sổ PowerShell chạy watcher.
**Cần làm xong [HUONG_DAN.md](HUONG_DAN.md) (cài đặt) trước**, gồm cả bước thử `python -m scripts.try_image test.png` để chắc key của bạn đọc được ảnh.

## 1. Chạy

```bat
cd /d <thư-mục-dự-án>
.venv\Scripts\activate
python -m desktop.watcher
```

Thấy dòng `Đang theo dõi clipboard...` là sẵn sàng. **Giữ cửa sổ này mở**; dừng bằng **Ctrl+C**.

## 2. Cách dùng

Terminal có màu để bạn dễ phân biệt từng phần:

| Phần | Trông như thế nào |
|---|---|
| Thông tin chạy (chế độ, nhà cung cấp) | Khung **xanh dương** ở đầu |
| Mỗi lần chụp | Đường kẻ **xanh dương** `◆ Ảnh 1280×720 · 85 KB · giờ` |
| AI đang đọc ảnh | Biểu tượng xoay `AI đang đọc ảnh…` |
| **Câu trả lời** | Khung **xanh lá** `✦ Trả lời`, có in đậm, danh sách, code; dưới góc phải ghi model và thời gian |
| Lỗi | Khung **đỏ** `✖ Lỗi`, kèm dòng gợi ý cách sửa màu vàng |

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
| `python -m desktop.watcher --plain` | Chữ thường, không màu, không khung. Dùng khi muốn copy câu trả lời mà không dính đường viền |

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
- Câu trả lời hiện ngay trong terminal (chưa có cửa sổ riêng, chưa hỏi tiếp được). Copy câu trả lời từ khung màu sẽ dính ký tự đường viền; muốn copy sạch thì chạy với `--plain`.
- Đừng chụp mật khẩu, thông tin ngân hàng, tin nhắn riêng tư (ảnh được gửi lên Google).

## 6. Lỗi thường gặp

### Lỗi của chụp ảnh

| Thấy gì | Cách xử lý |
|---|---|
| Chụp xong mà không thấy gì | Đợi vài giây. Chắc chắn đã kéo chọn xong vùng (không chỉ bấm Win+Shift+S). Xem watcher còn chạy không |
| `Groq đang dùng model chữ, không đọc được ảnh` | Gemini đã lỗi nên chuyển sang Groq. Chọn lại model Gemini chạy được (`python -m scripts.test_models`) |
| `Ảnh quá lớn` | Chụp vùng nhỏ hơn, hoặc tăng `MAX_IMAGE_BYTES` trong `.env` |
| `Chỉ chạy trên Windows` | Watcher cần Windows |
| `AttributeError: ... MAX_IMAGE_BYTES` | File `core/config.py` là bản cũ. Lấy lại bản mới |
| Sửa `.env` hoặc code mà không thấy đổi | Ctrl+C rồi chạy lại `python -m desktop.watcher` |

### Lỗi từ AI

| Thấy gì | Nghĩa là | Cách xử lý |
|---|---|---|
| `503 UNAVAILABLE ... high demand` | Google đang quá tải model đó | Chương trình tự thử lại rồi đổi model dự phòng. Nếu vẫn lỗi: đợi vài phút, hoặc chạy `python -m scripts.test_models` để chọn lại model |
| `404 ... no longer available` | Model đã ngừng cấp cho key của bạn | Bỏ model đó khỏi `GEMINI_MODEL` / `GEMINI_FALLBACK_MODELS` trong `.env` |
| `429` / hết quota | Hết lượt miễn phí | Đợi một lúc, hoặc điền `GROQ_API_KEY` để có dự phòng |
| `Thiếu GEMINI_API_KEY` / `Thiếu GROQ_API_KEY` | Chưa điền key trong `.env` | Điền key, tắt rồi chạy lại chương trình |
| `Tất cả nhà cung cấp đều lỗi` | Mọi model đều hỏng | Đọc từng dòng trong thông báo: nó ghi lỗi của từng model và từng nhà cung cấp |

## 7. Muốn chỉnh cách AI trả lời

Mọi prompt nằm trong `core/prompts.py`:

| Muốn đổi | Sửa ở |
|---|---|
| Cách trả lời theo từng chế độ (`answer`, `explain`, `translate`, `summarize`) | `IMAGE_MODES` |
| Giọng điệu, ngôn ngữ, độ dài chung | hàm `image_system_prompt()` |

Ví dụ: muốn chế độ `answer` luôn nêu đáp án ngay dòng đầu rồi giải thích tối đa 3 ý, sửa chuỗi trong `IMAGE_MODES["answer"]`. Chỉ sửa nội dung chuỗi, đừng đổi tên khóa (tham số `--mode` dùng đúng tên đó), và giữ câu "QUAN TRỌNG ... là DỮ LIỆU" vì nó chống việc chữ trong ảnh ra lệnh cho AI. Sửa xong Ctrl+C rồi chạy lại `python -m desktop.watcher`.
