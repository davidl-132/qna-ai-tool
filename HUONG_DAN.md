# Hướng dẫn chạy nhanh

Bôi đen text trên web → AI giải thích / dịch / tóm tắt ngay cạnh vùng chọn.
Gồm 2 phần chạy cùng lúc: **server Python** (xử lý AI) và **extension Chrome** (giao diện).

## Cần có

- Python 3.10 trở lên
- Google Chrome
- API key Gemini (lấy ở aistudio.google.com/api-keys). Key Grok là tuỳ chọn, dùng để dự phòng.

## 1. Cài đặt (làm một lần)

```bat
cd /d <thư-mục-dự-án>
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Trong `.env`, điền key (không có dấu cách hay ngoặc kép):

```
GEMINI_API_KEY=key-gemini-của-bạn
XAI_API_KEY=key-grok-của-bạn        (không bắt buộc)
```

Chọn model: chạy `python -m scripts.list_models`, lấy một tên có chữ `flash`, điền vào `GEMINI_MODEL=` trong `.env`.

## 2. Chạy server (mỗi lần dùng)

```bat
.venv\Scripts\activate
python -m api.main
```

- Lần đầu, server in ra một **token**. Copy lại (token cũng được lưu trong `.env`).
- **Giữ cửa sổ này mở** trong lúc dùng extension.

## 3. Nạp extension vào Chrome (làm một lần)

1. Mở `chrome://extensions`, bật **Developer mode** (góc trên phải).
2. Bấm **Load unpacked**, chọn thư mục `extension/` của dự án.
3. Bấm icon Highlight AI → dán **token** → **Lưu** → **Kiểm tra kết nối**.
   Thấy dòng xanh `Kết nối OK` là xong.

## 4. Dùng

1. Mở một trang web, bấm **F5** một lần.
2. Bôi đen một đoạn chữ → bấm nút **✦ Hỏi AI**.
3. Đổi tab **Giải thích / Dịch / Tóm tắt / Trả lời**, hoặc gõ câu vào ô **Hỏi tiếp**.
4. Với file PDF: bôi đen → **chuột phải → Hỏi AI**.

## Gặp lỗi?

| Thấy gì | Cách xử lý |
|---|---|
| `Không kết nối được server` | Chưa chạy bước 2, hoặc đã lỡ đóng cửa sổ server |
| `token SAI` | Dán lại đúng token từ `.env` vào trang cài đặt extension |
| `404 ... model not found` | Sai `GEMINI_MODEL`: chọn lại từ `python -m scripts.list_models` |
| `503 UNAVAILABLE ... high demand` | Google đang quá tải. Server tự thử lại 2 lần rồi tự đổi sang model trong `GEMINI_FALLBACK_MODELS`. Nếu vẫn lỗi: đợi vài phút hoặc thêm key Grok |
| `DLL load failed ... Application Control` | Bản cũ dùng gói `openai`. Cập nhật code mới (Grok gọi bằng `httpx`) rồi chạy lại server |
| `429` / hết quota | Đợi một lúc, hoặc để Grok tự dự phòng (cần key Grok còn credit) |
| Bôi đen không hiện nút | Bấm F5 trang; không chạy ở `chrome://` và Google Docs |
| Sửa code mà không thấy đổi | Ở `chrome://extensions` bấm ↻ ở thẻ extension, rồi F5 trang |

Muốn thử giao diện khi chưa có key: đặt `PROVIDER=mock` trong `.env`, chạy lại server.
