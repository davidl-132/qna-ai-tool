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

| Phím | Việc |
|---|---|
| **Left Alt** (bấm đơn) | **Chụp màn hình** rồi hỏi AI |
| **Left Shift** (bấm đơn) | **Ẩn/hiện** khung (lịch sử vẫn giữ) |
| **Ctrl+Alt+0** | **BẬT/TẮT toàn bộ app** (phím bấm đơn và tự tra chữ bôi đen) |
| **Bôi đen chữ** | Giữ nguyên vùng chọn ~1 giây: **tự tra**, khung tự hiện đáp án |
| **← / →** (mũi tên Trái/Phải) | Xem câu **trước / sau**, chỉ khi khung đang hiện và có từ 2 câu trở lên |
| Nút **‹ ›** trên khung | Giống ← →, bấm bằng chuột |

Chỉ còn đúng các phím này. **Ctrl+Alt+1/2/3 và `HOTKEY_SHOW/HIDE/CAPTURE` đã bỏ**: nếu `.env` của bạn còn các dòng đó (ví dụ `=1`, `=2`, `=3`) thì app bỏ qua, các phím số gõ bình thường trở lại; bạn có thể xóa các dòng ấy.

**Mũi tên Trái/Phải:** trong lúc khung đang hiện, app **nuốt** hai phím này (app bạn đang dùng không nhận được) để chuyển câu. Giữ Shift/Ctrl/Alt thì không nuốt, nên Shift+← → chọn chữ và Ctrl+← → nhảy từ vẫn bình thường. Cần dùng mũi tên bình thường thì bấm đơn **Left Shift** để ẩn khung, hoặc tắt hẳn bằng `--no-nav-keys` (`NAV_KEYS=0` trong `.env`).

**"Bấm đơn"** nghĩa là nhấn rồi thả nhanh (dưới 0,4 giây), không kèm phím hay chuột nào khác. Nên Alt+Tab, Shift+chữ hoa, Alt+Shift đổi bàn phím... **không** bị tính. Khi bấm đơn Alt, app tự chèn một phím "đệm" để thanh menu của app không bật lên. Đổi phím bằng `TAP_CAPTURE` / `TAP_POPUP` trong `.env` (chọn `lalt`, `ralt`, `lshift`, `rshift`, `lctrl`, `rctrl`; để trống = không dùng).

**Bật/tắt:** bấm Ctrl+Alt+0 để tắt: Left Alt, Left Shift và tự tra chữ bôi đen ngừng hoạt động; khung đáp án tự ẩn (lịch sử vẫn giữ). Bấm Ctrl+Alt+0 lần nữa để bật lại. Mỗi lần đổi có tiếng bíp và một dòng 🟢/🔴 trong terminal. Đổi phím này bằng `HOTKEY_TOGGLE` trong `.env` (dạng `ctrl+alt+0`, `ctrl+shift+f9`...; để trống = không dùng).

## 3. Cách dùng

1. Mở nội dung cần hỏi trên màn hình (câu hỏi, bài tập, trang web...).
2. Bôi đen chữ cần hỏi (tự tra sau ~1 giây), hoặc bấm đơn **Left Alt** để chụp toàn màn hình chính và hỏi AI.
3. Khung đáp án hiện ở góc dưới phải (nếu đang ẩn mà muốn xem lại: bấm đơn **Left Shift**). Câu trả lời chạy dần từng chữ.
4. Xem câu cũ bằng mũi tên **←**, câu mới bằng **→** (hoặc nút ‹ ›). Xong thì bấm đơn **Left Shift** để ẩn.

Khung kiểu **phụ đề**: chữ **trắng đậm, viền đen**, nhỏ gọn, tự cao lên theo độ dài câu trả lời (đáy khung đứng yên ở góc dưới phải). Hàng đầu khung ghi `2/5 · tên-model · ✔` và các nút:

| Thao tác | Tác dụng |
|---|---|
| Nút **Copy** | Chép đáp án vào clipboard (có bản đã sửa thì chép bản sửa; không kèm dòng trạng thái) |
| Nút **‹ ›** (to, có khung) | Xem câu trước / sau trong lịch sử; mờ đi khi đã tới câu đầu / câu cuối |
| Nút **◐** | Đổi độ mờ: mỗi lần bấm mờ thêm một mức (100% → 85% → 70% → 55% → 40% → 25%), hết mức thì quay lại 100% |
| Nút **×** | Ẩn khung (giống Left Shift, không xóa lịch sử) |
| Kéo hàng đầu | Dời khung sang chỗ khác |
| Con lăn chuột trên chữ | Cuộn khi câu trả lời dài quá 45% chiều cao màn hình |

Khung **không cướp focus**: bàn phím vẫn gõ vào app bạn đang dùng. Nếu khung đang mở lúc chụp (Left Alt), app tự ẩn khung đi để không lọt vào ảnh chụp, xong thì mở lại.

**Chế độ `answer` (mặc định) chỉ in đáp án**, ví dụ `B` hoặc `1. B` / `2. D`: không chép lại đề, không giải thích. Đổi cách trả lời: sửa hàm `_answer_only()` trong `core/prompts.py`.

### Tự tra chữ bôi đen (mọi app)

Bôi đen chữ ở Chrome, Word, PDF, Zalo... rồi **giữ yên khoảng 1 giây**, app tự lấy chữ đó và hỏi AI: một từ/cụm từ thì ra nghĩa ngắn, đoạn văn có câu hỏi thì ra đáp án. Khung tự hiện (vì chính bạn vừa chủ động bôi), và không chạy vòng tự kiểm tra cho nhanh.

Cách lấy chữ: app gửi Ctrl+C ngầm. Để không mất thứ bạn đang copy, app **chụp lại toàn bộ clipboard trước, trả lại y nguyên sau** (chữ, ảnh, file...). Nếu clipboard có thứ không lưu lại được thì app **bỏ qua lần tra đó** chứ không đụng vào clipboard.

Chỗ **không** tra (cố ý): terminal/cmd/PowerShell (Ctrl+C ở đó là ngắt lệnh), File Explorer, Remote Desktop; bôi đen khi đang giữ Ctrl/Alt/Win; bôi đen ngay trong khung popup; cùng một đoạn chữ vừa tra trong 8 giây. Đổi bằng `SELECT_BLOCK_APPS` (danh sách .exe cách nhau dấu phẩy) hoặc `SELECT_ONLY_APPS` (chỉ tra trong các app này, ví dụ `chrome.exe,msedge.exe`).

## 4. Tự kiểm tra lại đáp án (agent loop)

Mỗi lần chụp, app gọi AI **2 lượt**: (1) viết câu trả lời nháp, hiện ngay cho bạn xem; (2) AI xem lại ảnh, tự giải lại và so với nháp.

| Kết quả lượt 2 | Khung hiện |
|---|---|
| Nháp đúng | Dòng xanh `✔ Đã kiểm tra lại: đáp án khớp.`, tiêu đề có dấu ✔ |
| Nháp sai | Giữ nguyên nháp, bên dưới thêm `↻ Bản đã sửa:` kèm đáp án mới; tiêu đề ghi `đã sửa` |
| Không rõ / lượt 2 lỗi | Dòng xám báo không kiểm tra được; nháp vẫn còn, không mất |

Lúc đang kiểm tra khung ghi `⏳ Đang kiểm tra lại…`, và phải đợi xong mới chụp tiếp được. Đổi lại thì mỗi lần chụp tốn thêm 1 lượt gọi AI và chậm thêm vài giây. Key miễn phí dễ báo 429/503 hơn; khi đó chỉ lượt kiểm tra bị lỗi, nháp vẫn hiện.

Tắt vòng này: `AGENT_REVIEW=0` trong `.env`, hoặc chạy `python -m desktop.app --no-review`.

## 5. Khung trong suốt

| Kiểu | Cách bật | Kết quả |
|---|---|---|
| **Mờ** | Bấm nút ◐ trên khung, hoặc đặt `POPUP_OPACITY=0.5` trong `.env` | Cả khung mờ đi, nhìn xuyên qua thấy cửa sổ phía sau. Thấp nhất 0.2 |
| **Ghost (chỉ còn chữ), mặc định** | Luôn bật sẵn. Muốn khung đặc: `python -m desktop.app --solid` hoặc `POPUP_GHOST=0` | Nền khung biến mất hẳn, chỉ chữ nổi trên màn hình. Click vào chỗ trống thì xuyên xuống cửa sổ bên dưới |

Lưu ý khi dùng ghost:
- Chỉ chạy trên Windows. Máy khác tự dùng khung thường.
- Chữ trắng có viền đen nên đọc được trên cả nền sáng lẫn tối. Nếu vẫn thấy khó, dùng `--solid` (nền đen đặc).
- Các nút chỉ bấm được đúng trên nét chữ của nút (phần trong suốt thì click xuyên xuống). Nút nhỏ nên bấm hơi lệch là trượt.
- Chữ không chọn/bôi được như ô văn bản; muốn lấy đáp án thì bấm **Copy**.

## 6. Tùy chọn

| Cách | Ý nghĩa |
|---|---|
| `python -m desktop.app --auto-show` (hoặc `POPUP_AUTO_SHOW=1` trong `.env`) | Chụp xong tự hiện khung (mặc định chụp xong khung vẫn ẩn, bấm Left Shift để xem) |
| `--no-review` (hoặc `AGENT_REVIEW=0`) | Tắt tự kiểm tra lại, chỉ 1 lượt gọi AI (nhanh hơn) |
| `--no-nav-keys` (hoặc `NAV_KEYS=0`) | Không dùng mũi tên Trái/Phải để chuyển câu (chỉ còn nút ‹ ›) |
| `--no-select` (hoặc `SELECT_AUTO=0`) | Tắt tự tra chữ bôi đen, vẫn giữ Left Alt / Left Shift |
| `SELECT_SETTLE=1.5` | Phải giữ yên vùng chọn bao nhiêu giây mới tra (mặc định 1,0) |
| `--mode explain` / `translate` / `summarize` | Đổi kiểu trả lời (mặc định `answer`) |
| `--question "đáp án đúng là gì?"` | Câu hỏi thêm gửi kèm mỗi ảnh |

## 7. Giới hạn

- Chỉ chạy trên **Windows**. Chỉ chụp **màn hình chính** (không chụp màn hình thứ hai).
- Lịch sử nằm trong bộ nhớ, **tắt app là mất**.
- Mỗi lần chỉ xử lý một ảnh (gồm cả lượt kiểm tra lại); bấm phím chụp khi đang xử lý thì bị bỏ qua.
- AI kiểm tra vẫn có thể sai: ✔ nghĩa là hai lượt đồng ý với nhau, không phải bảo đảm đúng. Việc nào quan trọng thì bạn tự xem lại.
- Tự tra chữ bôi đen và phím bấm đơn dùng **hook bàn phím/chuột toàn cục**. Một số phần mềm diệt virus hoặc anti-cheat có thể cảnh báo/chặn; game có anti-cheat thì nên tắt app (hoặc Ctrl+Alt+0).
- Mỗi lần bôi đen giữ yên đủ lâu là tốn một lượt gọi AI; lỡ tay bấm đơn Left Alt cũng chụp và hỏi. Thấy phiền thì đặt `--no-select` hoặc để trống `TAP_CAPTURE`.
- App đang chạy quyền Administrator (vd. Task Manager) thì hook của app thường không thấy phím/chuột trong đó, trừ khi chạy app bằng quyền Administrator.
- Khung chỉ hiện trên màn hình thường; game/video toàn màn hình độc quyền có thể che khung.

## 8. Lỗi thường gặp

| Thấy gì | Cách xử lý |
|---|---|
| `Không đăng ký được Ctrl+Alt+0 (đã có app khác dùng phím này?)` | Phím trùng với app khác: đổi `HOTKEY_TOGGLE` trong `.env` |
| `Phím ... không hợp lệ` | Sửa `HOTKEY_TOGGLE` theo dạng `ctrl+alt+0`; sửa `TAP_CAPTURE`/`TAP_POPUP` thành `lalt`, `lshift`... |
| Bôi đen không tự tra | Kiểm tra app đang bôi có nằm trong danh sách chặn không (terminal/Explorer), có giữ yên đủ 1 giây không, terminal có dòng `⚠ ...hook...` không; thử `SELECT_SETTLE` dài hơn |
| Chụp xong không thấy gì | Khung mặc định ẩn: bấm đơn Left Shift để hiện; hoặc chạy với `--auto-show` |
| Khung báo `⚠ ...` | Lỗi AI/ảnh: xem bảng lỗi trong [HUONG_DAN_CHUP_ANH.md](HUONG_DAN_CHUP_ANH.md#6-lỗi-thường-gặp) (cùng nguyên nhân) |
| `ModuleNotFoundError: tkinter` | Cài lại Python từ python.org (bản đầy đủ có tkinter) |
| Ảnh đen/thiếu một phần | Nội dung được bảo vệ (một số app/phim chặn chụp màn hình) |
