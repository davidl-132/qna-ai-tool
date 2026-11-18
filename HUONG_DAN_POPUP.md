# 🪟 Hướng dẫn: App popup (phím tắt + khung đáp án nhỏ)

Một app chạy nền: bấm phím tắt để **chụp màn hình** hỏi AI, rồi bấm phím khác để **hiện/ẩn** khung đáp án nhỏ ở góc dưới bên phải. Dùng được ở mọi nơi trên máy.

**Cần làm xong [HUONG_DAN.md](HUONG_DAN.md) (cài đặt) trước.** Không cần Chrome, server hay token.

## 1. Chạy

```bat
cd /d <thư-mục-dự-án>
.venv\Scripts\activate
python -m desktop.app
```

Thấy danh sách phím tắt hiện ra là sẵn sàng. **Giữ cửa sổ này mở** (có thể thu nhỏ); dừng bằng **Ctrl+C**.

## 2. Phím tắt

| Phím mặc định | Việc |
|---|---|
| **Ctrl+Alt+1** | **Hiện** khung đáp án (xem câu mới nhất) |
| **Ctrl+Alt+2** | **Ẩn** khung. Lịch sử vẫn còn, bấm Ctrl+Alt+1 là thấy lại |
| **Ctrl+Alt+3** | **Chụp màn hình lúc đó** rồi hỏi AI |
| **Ctrl+Alt+0** | **BẬT/TẮT** cả bộ phím trên |

**Bật/tắt:** bấm Ctrl+Alt+0 để tắt, lúc này 1/2/3 (hay mọi phím bạn đã đặt) trả về cho các app khác, gõ bình thường; khung đáp án cũng tự ẩn (lịch sử vẫn giữ). Bấm Ctrl+Alt+0 lần nữa để bật lại. Mỗi lần đổi có tiếng bíp và một dòng 🟢/🔴 trong terminal. Đổi phím này bằng `HOTKEY_TOGGLE` trong `.env` (để trống = không dùng).

Đổi phím trong `.env`. Bạn có thể dùng:

| Kiểu | Ví dụ | Ghi chú |
|---|---|---|
| Có phím bổ trợ (khuyên dùng) | `ctrl+alt+1`, `ctrl+shift+f9` | An toàn, không ảnh hưởng việc gõ |
| Phím số bên phải bàn phím | `num1`, `num2`, `num3` | Không đụng hàng số phía trên; cần bàn phím có numpad |
| Phím trần | `1`, `2`, `3` | Làm được, nhưng **mọi app sẽ không gõ ra số 1/2/3 nữa** khi app popup đang chạy |

Muốn dùng đúng `1`, `2`, `3`: đặt `HOTKEY_SHOW=1`, `HOTKEY_HIDE=2`, `HOTKEY_CAPTURE=3`. Cần gõ số thì bấm **Ctrl+Alt+0** để tắt tạm (hoặc tắt app bằng Ctrl+C).

## 3. Cách dùng

1. Mở nội dung cần hỏi trên màn hình (câu hỏi, bài tập, trang web...).
2. Bấm **Ctrl+Alt+3**. App chụp **toàn màn hình chính** và gửi cho AI.
3. Bấm **Ctrl+Alt+1** để hiện khung. Câu trả lời chạy dần từng chữ trong khung.
4. Xong thì bấm **Ctrl+Alt+2** để ẩn.

Trong khung:

| Thao tác | Tác dụng |
|---|---|
| Nút **‹ ›** trên thanh tiêu đề | Xem câu trước / sau trong lịch sử (tiêu đề ghi `2/5` và tên model) |
| Nút **×** | Ẩn khung (giống Ctrl+Alt+2, không xóa lịch sử) |
| Kéo thanh tiêu đề | Dời khung sang chỗ khác |
| Bôi chữ + Ctrl+C | Copy câu trả lời |

Khung **không cướp focus**: bàn phím vẫn gõ vào app bạn đang dùng. Nếu khung đang mở lúc bấm Ctrl+Alt+3, app tự ẩn khung đi để không lọt vào ảnh chụp, xong thì mở lại.

## 4. Tự kiểm tra lại đáp án (agent loop)

Mỗi lần chụp, app gọi AI **2 lượt**: (1) viết câu trả lời nháp, hiện ngay cho bạn xem; (2) AI xem lại ảnh, tự giải lại và so với nháp.

| Kết quả lượt 2 | Khung hiện |
|---|---|
| Nháp đúng | Dòng xanh `✔ Đã kiểm tra lại: đáp án khớp.`, tiêu đề có dấu ✔ |
| Nháp sai | Giữ nguyên nháp, bên dưới thêm `↻ Bản đã sửa:` kèm đáp án mới; tiêu đề ghi `đã sửa` |
| Không rõ / lượt 2 lỗi | Dòng xám báo không kiểm tra được; nháp vẫn còn, không mất |

Lúc đang kiểm tra khung ghi `⏳ Đang kiểm tra lại…`, và phải đợi xong mới chụp tiếp được. Đổi lại thì mỗi lần chụp tốn thêm 1 lượt gọi AI và chậm thêm vài giây. Key miễn phí dễ báo 429/503 hơn; khi đó chỉ lượt kiểm tra bị lỗi, nháp vẫn hiện.

Tắt vòng này: `AGENT_REVIEW=0` trong `.env`, hoặc chạy `python -m desktop.app --no-review`.

## 5. Tùy chọn

| Cách | Ý nghĩa |
|---|---|
| `python -m desktop.app --auto-show` (hoặc `POPUP_AUTO_SHOW=1` trong `.env`) | Chụp xong tự hiện khung, khỏi bấm Ctrl+Alt+1 |
| `--no-review` (hoặc `AGENT_REVIEW=0`) | Tắt tự kiểm tra lại, chỉ 1 lượt gọi AI (nhanh hơn) |
| `--mode explain` / `translate` / `summarize` | Đổi kiểu trả lời (mặc định `answer`) |
| `--question "đáp án đúng là gì?"` | Câu hỏi thêm gửi kèm mỗi ảnh |

## 6. Giới hạn

- Chỉ chạy trên **Windows**. Chỉ chụp **màn hình chính** (không chụp màn hình thứ hai).
- Lịch sử nằm trong bộ nhớ, **tắt app là mất**.
- Mỗi lần chỉ xử lý một ảnh (gồm cả lượt kiểm tra lại); bấm phím chụp khi đang xử lý thì bị bỏ qua.
- AI kiểm tra vẫn có thể sai: ✔ nghĩa là hai lượt đồng ý với nhau, không phải bảo đảm đúng. Việc nào quan trọng thì bạn tự xem lại.
- Khung chỉ hiện trên màn hình thường; game/video toàn màn hình độc quyền có thể che khung.

## 7. Lỗi thường gặp

| Thấy gì | Cách xử lý |
|---|---|
| `Không đăng ký được Ctrl+Alt+1 (đã có app khác dùng phím này?)` | Phím trùng với app khác: đổi `HOTKEY_*` trong `.env` |
| `Phím ... không hợp lệ` | Sửa `HOTKEY_*` theo dạng `ctrl+alt+1`, `num1` hoặc `1` |
| Bấm phím tắt không thấy gì | Bấm Ctrl+Alt+1 sau khi chụp; hoặc chạy với `--auto-show` |
| Khung báo `⚠ ...` | Lỗi AI/ảnh: xem bảng lỗi trong [HUONG_DAN_CHUP_ANH.md](HUONG_DAN_CHUP_ANH.md#6-lỗi-thường-gặp) (cùng nguyên nhân) |
| `ModuleNotFoundError: tkinter` | Cài lại Python từ python.org (bản đầy đủ có tkinter) |
| Ảnh đen/thiếu một phần | Nội dung được bảo vệ (một số app/phim chặn chụp màn hình) |
