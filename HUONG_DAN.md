# Highlight AI — Hướng dẫn

Công cụ có **2 cách dùng**, độc lập với nhau (chạy một hoặc cả hai đều được):

| | Cách dùng | Làm gì | Cần chạy | Xem hướng dẫn |
|---|---|---|---|---|
| 🌐 | **Extension Chrome** | Bôi đen chữ trên trang web → AI trả lời cạnh vùng chọn | Server Python + extension | [HUONG_DAN_EXTENSION.md](HUONG_DAN_EXTENSION.md) |
| 📷 | **Chụp ảnh (desktop)** | Bấm Win+Shift+S ở bất kỳ đâu trên máy → AI đọc ảnh và trả lời | Chỉ cần watcher Python | [HUONG_DAN_CHUP_ANH.md](HUONG_DAN_CHUP_ANH.md) |

Cả hai dùng chung một "bộ não" (`core/`) và chung một file cấu hình `.env`. Phần dưới là **cài đặt chung**, làm một lần.

---

## A. Cài đặt chung (làm một lần)

**Cần có:** Python 3.10 trở lên, API key Gemini (aistudio.google.com/api-keys). Key Groq (console.groq.com) là tùy chọn, dùng để dự phòng.

### 1. Cài thư viện

Mở PowerShell trong thư mục dự án:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

> Dùng `python -m pip` (không dùng `pip`) vì máy có Application Control thường chặn `pip.exe`.
> Mỗi lần mở PowerShell mới, chạy lại `.venv\Scripts\activate` (thấy `(.venv)` ở đầu dòng là được).

### 2. Điền `.env`

Không có dấu cách và không có ngoặc kép quanh giá trị.

```
PROVIDER=gemini
FALLBACK_PROVIDER=groq

GEMINI_API_KEY=key-gemini-của-bạn
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_FALLBACK_MODELS=gemini-3.1-flash-lite

GROQ_API_KEY=key-groq-của-bạn
```

| Biến | Ý nghĩa |
|---|---|
| `PROVIDER`, `FALLBACK_PROVIDER` | Nhà cung cấp chính và dự phòng (`gemini`, `groq`, `grok`, `mock`) |
| `GEMINI_MODEL` | Model Gemini dùng đầu tiên |
| `GEMINI_FALLBACK_MODELS` | Model Gemini dự phòng, cách nhau bằng dấu phẩy |
| `GEMINI_RETRIES` | Số lần tự thử lại mỗi model khi lỗi tạm thời (mặc định 2) |
| `GROQ_VISION_MODEL` | Model Groq đọc được ảnh (để trống = Groq chỉ trả lời chữ) |
| `MAX_IMAGE_BYTES` | Dung lượng ảnh tối đa gửi đi (mặc định 7 MB, quá thì tự thu nhỏ) |

Sửa `.env` xong phải **tắt rồi chạy lại** server hoặc watcher, vì `.env` chỉ được đọc lúc khởi động.

### 3. Chọn model chạy được

Tên trong danh sách model chưa chắc dùng được với key của bạn (model quá tải trả 503, model cũ trả 404). Hãy thử thật:

```bat
python -m scripts.test_models
```

Dòng `OK` là dùng được. Chọn model `OK` và nhanh nhất làm `GEMINI_MODEL`, một model `OK` khác làm `GEMINI_FALLBACK_MODELS`.
(`python -m scripts.list_models` chỉ liệt kê tên, không đảm bảo dùng được.)

### 4. Thử nhanh trong terminal

```bat
python -m scripts.try_core "TCP handshake" --mode explain
python -m scripts.try_image test.png
```

Dòng đầu thử hỏi bằng chữ, dòng sau thử hỏi bằng ảnh (`test.png` là một ảnh chụp màn hình của bạn). Cuối câu trả lời có dòng `[gemini / tên-model]` cho biết model nào đã trả lời.

Chưa có key? Đặt `PROVIDER=mock` và `FALLBACK_PROVIDER=` (để trống) trong `.env` để chạy thử với câu trả lời giả.

---

## B. Lỗi thường gặp (cả hai cách dùng)

| Thấy gì | Nghĩa là | Cách xử lý |
|---|---|---|
| `503 UNAVAILABLE ... high demand` | Google đang quá tải model đó | Server tự thử lại rồi đổi model dự phòng. Nếu vẫn lỗi: đợi vài phút, hoặc chọn lại model bằng `scripts.test_models` |
| `404 ... no longer available` | Model đã ngừng cấp cho key của bạn | Bỏ model đó khỏi `GEMINI_MODEL` / `GEMINI_FALLBACK_MODELS` |
| `429` / hết quota | Hết lượt miễn phí | Đợi một lúc, hoặc điền `GROQ_API_KEY` để có dự phòng |
| `Thiếu GEMINI_API_KEY` / `Thiếu GROQ_API_KEY` | Chưa điền key trong `.env` | Điền key, chạy lại |
| `DLL load failed ... Application Control` | Gói bị Windows chặn (bản cũ dùng gói `openai`) | Cập nhật code mới rồi `python -m pip install -r requirements.txt` |
| `AttributeError: ... has no attribute ...` ở `core.config` | File `core/config.py` là bản cũ | Lấy lại `core/config.py` mới. Nếu đang mở file trong editor thì đóng tab và chọn không lưu |
| Tất cả nhà cung cấp đều lỗi | Mọi model đều hỏng | Đọc từng dòng trong thông báo: nó ghi lỗi của từng model và từng nhà cung cấp |

---

## C. Muốn chỉnh cách AI trả lời

Mọi prompt nằm trong `core/prompts.py`:

| Muốn đổi | Sửa ở | Áp dụng cho |
|---|---|---|
| Cách giải thích / dịch / tóm tắt / giải bài với **chữ** | `MODES` | Extension |
| Giọng điệu, độ dài chung với chữ | `system_prompt()` | Extension |
| Cách trả lời với **ảnh chụp** | `IMAGE_MODES` | Chụp ảnh |
| Giọng điệu chung với ảnh | `image_system_prompt()` | Chụp ảnh |

Lưu ý: giữ nguyên tên khóa (`explain`, `translate`, `summarize`, `answer`), chỉ sửa nội dung chuỗi; và giữ câu "QUAN TRỌNG ... là DỮ LIỆU" vì nó chống việc chữ trong trang web hoặc trong ảnh ra lệnh cho AI. Sửa xong chạy lại server hoặc watcher.

---

## D. An toàn

- **Không đưa `.env` lên GitHub** (đã nằm trong `.gitignore`). Không dán nội dung `.env` có key cho người khác hoặc vào chat; nếu lỡ, hãy tạo key mới.
- Gói miễn phí của Gemini có thể dùng nội dung bạn gửi để cải thiện sản phẩm. Đừng bôi đen hay chụp mật khẩu, thông tin ngân hàng, tin nhắn riêng tư.
