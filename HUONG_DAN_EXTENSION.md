# 🌐 Hướng dẫn: Extension Chrome (bôi đen chữ)

Bôi đen chữ trên trang web → AI giải thích / dịch / tóm tắt / giải bài ngay cạnh vùng chọn.

Phần này gồm 2 thứ chạy cùng lúc: **server Python** (xử lý AI) và **extension Chrome** (giao diện).
Làm [phần A trong HUONG_DAN.md](HUONG_DAN.md) (cài đặt chung) trước.

## 1. Chạy server (mỗi lần dùng)

```bat
cd /d <thư-mục-dự-án>
.venv\Scripts\activate
python -m api.main
```

- Lần đầu, server tự tạo một **token** và in ra màn hình. Token cũng được lưu trong `.env` (dòng `LOCAL_TOKEN=`).
- **Giữ cửa sổ này mở** trong lúc dùng extension. Tắt cửa sổ là extension ngừng hoạt động.

## 2. Nạp extension vào Chrome (làm một lần)

1. Mở `chrome://extensions`, bật **Developer mode** (góc trên phải).
2. Bấm **Load unpacked**, chọn thư mục **`extension`** bên trong dự án (không chọn thư mục gốc của dự án).
3. Bấm icon Highlight AI → dán **token** → **Lưu** → **Kiểm tra kết nối**. Thấy dòng xanh `Kết nối OK` là xong.

## 3. Cách dùng

| Thao tác | Kết quả |
|---|---|
| Mở trang web, bấm **F5** một lần | Để extension nạp vào trang |
| Bôi đen một đoạn chữ | Hiện nút **✦ Hỏi AI** dưới vùng chọn |
| Bấm nút, hoặc chuột phải → **Hỏi AI** | Popup trả lời, chữ hiện dần |
| Tab **Giải thích / Dịch / Tóm tắt / Trả lời** | Hỏi lại theo chế độ khác |
| Ô **Hỏi tiếp** | Hỏi thêm về cùng đoạn đó, AI nhớ các lượt trước |
| **■ Dừng**, **Copy**, **Thử lại**, phím **Esc** | Ngắt, chép câu trả lời, hỏi lại, đóng popup |
| Trang cài đặt → **Lịch sử gần đây** | Xem các câu đã hỏi (lưu trong `data/history.db`) |

**File PDF** mở trong Chrome: nút nổi không hiện. Hãy bôi đen → **chuột phải → Hỏi AI**; câu trả lời mở trong một cửa sổ nhỏ riêng.

## 4. Giới hạn

- Không hoạt động ở `chrome://`, Chrome Web Store, và Google Docs/Sheets (các trang này vẽ chữ bằng canvas).
- Ô mật khẩu luôn bị bỏ qua. Thêm trang nhạy cảm (ngân hàng, email) vào ô **Không hiện nút trên các trang** ở trang cài đặt.
- Tab đã mở từ trước khi cài extension cần bấm F5.

## 5. Lỗi riêng của extension

| Thấy gì | Cách xử lý |
|---|---|
| `Failed to load extension ... Manifest file is missing` | Bạn chọn nhầm thư mục. Phải chọn thư mục `extension` (bên trong có `manifest.json`) |
| `Không kết nối được server` | Chưa chạy bước 1, hoặc đã lỡ đóng cửa sổ server |
| `token SAI` | Dán lại đúng token từ `.env` vào trang cài đặt extension |
| Bôi đen không hiện nút | Bấm F5 trang; kiểm tra trang không thuộc danh sách bị loại trừ |
| Sửa code extension mà không thấy đổi | Ở `chrome://extensions` bấm ↻ ở thẻ extension, rồi F5 trang |
| Sửa `.env` hoặc code Python mà không thấy đổi | Tắt server (Ctrl+C) rồi chạy lại `python -m api.main` |

Lỗi về AI (503, 404, 429, thiếu key...): xem [mục B trong HUONG_DAN.md](HUONG_DAN.md).
