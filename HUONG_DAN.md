# Highlight AI — Cài đặt (đọc file này trước)

Highlight AI là công cụ hỏi AI nhanh về thứ bạn đang đọc. Có **2 cách dùng**:

| | Cách dùng | Làm gì |
|---|---|---|
| 🌐 | **Extension Chrome** | Bôi đen chữ trên trang web → AI trả lời ngay cạnh |
| 📷 | **Chụp ảnh** | Bấm Win+Shift+S ở bất kỳ đâu trên máy → AI đọc ảnh và trả lời |

**Cách làm:** cài đặt xong file này (một lần), rồi chọn cách dùng bạn cần ở [Bước cuối](#xong-chọn-cách-dùng) và đọc hướng dẫn riêng của cách đó.

> Hướng dẫn viết cho **Windows 10/11** và **PowerShell**.

---

## Máy bạn cần có

| Cần | Bắt buộc? | Ghi chú |
|---|---|---|
| Windows 10/11, có internet | Có | |
| Python 3.10 trở lên | Có | Bước 1 |
| API key Gemini | Có | Bước 2 (miễn phí) |
| API key Groq | Không | Dự phòng khi Gemini lỗi, cũng miễn phí |
| Google Chrome | Chỉ khi dùng 🌐 extension | |

---

## Bước 1. Cài Python

Mở PowerShell, gõ:

```bat
python --version
```

- Thấy `Python 3.10` trở lên (ví dụ `Python 3.11.9`): xong, sang Bước 2.
- Báo lỗi hoặc số nhỏ hơn: tải Python ở python.org/downloads, chạy file cài và **tích ô "Add python.exe to PATH"** ở màn hình đầu tiên. Cài xong, đóng PowerShell, mở lại, gõ lại lệnh trên.

## Bước 2. Lấy API key

**Gemini (bắt buộc):**
1. Vào aistudio.google.com/api-keys, đăng nhập tài khoản Google.
2. Bấm **Create API key**, rồi copy key (một chuỗi dài).

**Groq (tùy chọn, nên có):**
1. Vào console.groq.com, đăng nhập, mở mục **API Keys**.
2. Bấm **Create API Key**, copy key (bắt đầu bằng `gsk_`).

Key giống mật khẩu: không gửi cho người khác, không đăng lên mạng.

## Bước 3. Tải dự án

Cách 1, có Git:

```bat
git clone https://github.com/davidl-132/qna-ai-tool.git
cd qna-ai-tool
```

Cách 2, không có Git: vào trang GitHub của dự án, bấm **Code → Download ZIP**, giải nén, rồi mở PowerShell trong thư mục vừa giải nén:

```bat
cd /d D:\duong-dan-toi-thu-muc-du-an
```

## Bước 4. Cài thư viện

Chạy lần lượt trong thư mục dự án:

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

Thấy `(.venv)` ở đầu dòng lệnh là đã vào môi trường của dự án.

> Luôn gõ `python -m pip` (không gõ `pip`), vì máy có Application Control thường chặn `pip.exe`.
> **Mỗi lần mở PowerShell mới**, bạn phải chạy lại `.venv\Scripts\activate` trước khi dùng.

## Bước 5. Điền key vào `.env`

```bat
copy .env.example .env
notepad .env
```

Sửa các dòng sau (không có dấu cách, không có ngoặc kép quanh giá trị), rồi lưu file:

```
PROVIDER=gemini
FALLBACK_PROVIDER=groq

GEMINI_API_KEY=dán-key-gemini-vào-đây
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_FALLBACK_MODELS=gemini-3.1-flash-lite

GROQ_API_KEY=dán-key-groq-vào-đây
```

Không có key Groq thì để trống dòng `GROQ_API_KEY=` và đặt `FALLBACK_PROVIDER=` (để trống).

| Biến | Ý nghĩa |
|---|---|
| `PROVIDER` / `FALLBACK_PROVIDER` | Nhà cung cấp chính / dự phòng (`gemini`, `groq`, `mock`) |
| `GEMINI_MODEL` | Model Gemini dùng đầu tiên |
| `GEMINI_FALLBACK_MODELS` | Model Gemini dự phòng, cách nhau bằng dấu phẩy |
| `GEMINI_RETRIES` | Số lần tự thử lại mỗi model khi Google báo quá tải (mặc định 2) |
| `GROQ_VISION_MODEL` | Model Groq đọc được ảnh (để trống = Groq chỉ trả lời chữ) |
| `MAX_IMAGE_BYTES` | Dung lượng ảnh tối đa gửi đi (mặc định 7 MB, quá thì tự thu nhỏ) |

Sau này sửa `.env` xong, phải **tắt rồi chạy lại** chương trình, vì `.env` chỉ được đọc lúc khởi động.

## Bước 6. Chọn model dùng được

Tên model trong tài liệu chưa chắc dùng được với key của bạn (có model đang quá tải, có model đã ngừng cấp). Hãy thử thật:

```bat
python -m scripts.test_models
```

Mỗi dòng báo `OK` hoặc `LỖI`. Chọn model `OK` và nhanh nhất làm `GEMINI_MODEL`, một model `OK` khác làm `GEMINI_FALLBACK_MODELS`, rồi lưu `.env`. Danh sách model thay đổi theo thời gian và theo từng key; model quá tải (503) thì thử lại sau.

## Bước 7. Kiểm tra cài đặt

```bat
python -m scripts.try_core "TCP handshake" --mode explain
```

Thấy AI trả lời một đoạn giải thích, cuối câu có dòng `[gemini / tên-model]` là cài đặt thành công.

Muốn thử cả đọc ảnh (cần cho cách 📷): chụp một ảnh màn hình, lưu thành `test.png` trong thư mục dự án, chạy:

```bat
python -m scripts.try_image test.png
```

Chưa có key mà muốn xem thử? Đặt `PROVIDER=mock` và `FALLBACK_PROVIDER=` trong `.env`; AI sẽ trả lời giả để bạn thấy giao diện.

---

## Xong! Chọn cách dùng

| Bạn muốn | Đọc hướng dẫn |
|---|---|
| 🌐 Bôi đen chữ trên web rồi hỏi AI | [HUONG_DAN_EXTENSION.md](HUONG_DAN_EXTENSION.md) |
| 📷 Chụp màn hình (Win+Shift+S) rồi AI trả lời đáp án | [HUONG_DAN_CHUP_ANH.md](HUONG_DAN_CHUP_ANH.md) |

Hai cách độc lập với nhau; bạn có thể dùng một hoặc cả hai.

---

## Lỗi khi cài đặt

| Thấy gì | Cách xử lý |
|---|---|
| `python` không được nhận ra | Chưa cài Python hoặc quên tích **Add to PATH**: cài lại (Bước 1). Có thể thử `py --version` |
| `.venv\Scripts\activate` báo "running scripts is disabled" | Chạy `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` rồi chạy lại lệnh activate (chỉ có tác dụng trong cửa sổ này) |
| `pip.exe` bị chặn bởi Application Control | Dùng `python -m pip install -r requirements.txt` |
| `DLL load failed ... Application Control` | Một gói bị Windows chặn. Dùng đúng bản code mới nhất (không dùng gói `openai`) rồi cài lại: `python -m pip install -r requirements.txt` |
| `No module named ...` | Chưa kích hoạt môi trường: chạy `.venv\Scripts\activate`, hoặc chưa chạy Bước 4 |
| `Thiếu GEMINI_API_KEY` | `.env` chưa có key, hoặc đặt sai thư mục. `.env` phải nằm cạnh `README.md` |
| `AttributeError: ... has no attribute ...` ở `core.config` | File `core/config.py` là bản cũ. Tải lại dự án hoặc lấy lại file đó |

Lỗi khi đang dùng (Google quá tải, hết lượt miễn phí...) nằm ở cuối hướng dẫn của từng cách dùng.

## An toàn

- **Không đưa file `.env` lên GitHub** (đã được `.gitignore` chặn) và không dán nội dung `.env` có key cho người khác hoặc vào chat. Nếu lỡ, vào trang quản lý key xóa key đó và tạo key mới.
- Gói miễn phí của Gemini có thể dùng nội dung bạn gửi để cải thiện sản phẩm. Đừng bôi đen hay chụp mật khẩu, thông tin ngân hàng, tin nhắn riêng tư.
