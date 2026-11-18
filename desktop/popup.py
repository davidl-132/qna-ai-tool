"""Khung popup nhỏ (tkinter) ở góc dưới bên phải màn hình để hiện câu trả lời.

Kiểu "phụ đề": chữ TRẮNG ĐẬM có viền ĐEN, nền trong suốt (chế độ ghost, Windows) nên đọc được trên mọi nền.
- Nhỏ gọn, tự co giãn theo độ dài câu trả lời (mọc lên phía trên, góc dưới phải giữ nguyên).
- Hàng đầu: số thứ tự/model, rồi các nút: Copy (chép đáp án), ‹ › (xem câu trước/sau), ◐ (đổi độ mờ), × (ẩn).
- Kéo hàng đầu để dời chỗ. Không cướp focus của app đang dùng (Windows).
- Quá dài thì cuộn bằng con lăn chuột.
"""
import sys
import tkinter as tk
import tkinter.font as tkfont

WHITE, BLACK = "#ffffff", "#000000"
GHOST_KEY = "#010101"  # màu "đục lỗ": mọi điểm ảnh màu này trở nên trong suốt (Windows -transparentcolor)
OPACITY_STEPS = (1.0, 0.85, 0.7, 0.55, 0.4, 0.25)
# Chỉ dùng ký tự trong BMP: Tk 8.6 trên Windows hiển thị emoji ngoài BMP (📸, 🔍...) thành ô vuông hoặc báo lỗi
STATUS_TEXT = {"capturing": "⏳ Đang chụp màn hình…", "asking": "⏳ Đang hỏi AI…", "reviewing": "⏳ Đang kiểm tra lại…",
               "merging": "⏳ Các AI khác nhau, đang tổng hợp…"}


def compose(entry, index: int, total: int) -> tuple[str, str]:
    """(tiêu đề, nội dung) của một câu trả lời. Chỉ là chữ thuần nên test được không cần màn hình."""
    model = entry.info.get("model", "")
    title = f"{index + 1}/{total}" + (f" · {model}" if model else "")
    title += {"ok": " · ✔", "fixed": " · đã sửa", "merged": " · tổng hợp", "solo": " · 1 AI"}.get(entry.review, "")
    lines: list[str] = []
    if entry.text:
        lines.append(entry.text.replace("**", "").strip("\n"))
    if entry.review == "fixed":
        lines.append("↻ Sửa lại: " + entry.fixed_text.replace("**", "").strip("\n"))
    elif entry.review == "unknown":
        lines.append("(Kiểm tra lại: không rõ kết quả)")
    elif entry.review == "failed":
        lines.append(f"(Không kiểm tra lại được: {entry.review_error})")
    if entry.status in STATUS_TEXT and not (entry.status == "reviewing" and entry.review == "fixed"):
        lines.append(STATUS_TEXT[entry.status])
    if entry.status == "error":
        lines.append("⚠ " + entry.error)
    return title, "\n".join(lines)


class Popup:
    def __init__(self, root: tk.Tk, width: int = 340, margin: int = 12, alpha: float = 0.96,
                 ghost: bool = False, max_height_ratio: float = 0.45) -> None:
        self.root = root
        self.opacity = min(1.0, max(0.2, alpha))
        # Màn hình phóng to 150% thì 340 điểm ảnh trông rất nhỏ: nhân theo tỉ lệ DPI (96 DPI = 100%)
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96)
        self.w, self.margin = int(width * self.scale), int(margin * self.scale)
        self.pad = int(8 * self.scale)
        self.head_h = int(24 * self.scale)
        self.outline = 2  # viền đen dày cho dễ đọc trên mọi nền
        self.on_prev = self.on_next = self.on_hide = lambda: None
        self.visible = False
        self.title_text = ""
        self.body_text = ""
        self._full_text = ""

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self._apply_opacity()
        self.ghost = False
        if ghost:
            try:
                self.win.attributes("-transparentcolor", GHOST_KEY)
                self.ghost = True
            except tk.TclError:  # hệ điều hành không hỗ trợ (chỉ Windows có): dùng nền đen đặc
                pass
        self.bg = GHOST_KEY if self.ghost else BLACK
        self.win.configure(bg=self.bg)

        family = "Segoe UI" if "Segoe UI" in tkfont.families(root) else "TkDefaultFont"
        self.f_body = tkfont.Font(root=root, family=family, size=10, weight="bold")
        self.f_head = tkfont.Font(root=root, family=family, size=9, weight="bold")
        self.f_btn = tkfont.Font(root=root, family=family, size=12, weight="bold")
        self.f_nav = tkfont.Font(root=root, family=family, size=14, weight="bold")

        self.head = tk.Canvas(self.win, width=self.w, height=self.head_h, bg=self.bg, highlightthickness=0)
        self.head.pack(side="top", fill="x")
        self.body = tk.Canvas(self.win, width=self.w, height=self.head_h, bg=self.bg, highlightthickness=0)
        self.body.pack(side="top", fill="both", expand=True)
        self.body.bind("<MouseWheel>", lambda e: self.body.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self.body.bind("<Button-4>", lambda e: self.body.yview_scroll(-1, "units"))  # X11
        self.body.bind("<Button-5>", lambda e: self.body.yview_scroll(1, "units"))

        work = self._work_area()
        self.max_h = int((work[3] - work[1]) * max_height_ratio)
        self._x = self._y = 0
        self._right = max(work[0], work[2] - self.margin)
        self._bottom = max(work[1], work[3] - self.margin)
        self.message("")  # dựng khung rỗng + đặt vị trí lần đầu

    # ---------- vẽ chữ có viền ----------

    def _text(self, canvas, x, y, text, font, anchor="nw", width=0, tags=(), bold=False):
        """Chữ trắng đậm viền đen: vẽ chữ đen lệch quanh 8 hướng rồi chữ trắng lên trên."""
        r = self.outline
        kw = {"font": font, "anchor": anchor, "text": text, "tags": tags}
        if width:
            kw["width"] = width
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                if (dx or dy) and dx * dx + dy * dy <= r * r + 1:
                    canvas.create_text(x + dx, y + dy, fill=BLACK, **kw)
        item = canvas.create_text(x, y, fill=WHITE, **kw)
        if bold:  # chữ trắng vẽ chồng lệch 1 điểm ảnh -> nét dày hơn
            canvas.create_text(x + 1, y, fill=WHITE, **kw)
        return item

    @staticmethod
    def _fit(font, text: str, max_px: int) -> str:
        if font.measure(text) <= max_px:
            return text
        while len(text) > 1 and font.measure(text + "…") > max_px:
            text = text[:-1]
        return text + "…"

    def _button(self, name: str, label: str, right_edge: int, cmd) -> int:
        """Vẽ một nút ở mép phải `right_edge`, trả về mép trái của nó."""
        tag = f"btn_{name}"
        font = self.f_head if len(label) > 1 else self.f_btn
        self._text(self.head, right_edge, self.head_h // 2, label, font, anchor="e", tags=(tag,))
        self.head.tag_bind(tag, "<Button-1>", lambda _e: cmd())
        self.head.tag_bind(tag, "<Enter>", lambda _e: self.head.config(cursor="hand2"))
        self.head.tag_bind(tag, "<Leave>", lambda _e: self.head.config(cursor=""))
        return right_edge - font.measure(label) - int(8 * self.scale)

    def _nav_button(self, name: str, label: str, right_edge: int, cmd, enabled: bool) -> int:
        """Nút ‹ › to, có khung: bấm trúng dễ hơn nhiều so với một ký tự mảnh. Nền #000000 (khác màu khóa
        trong suốt) nên ở chế độ ghost vẫn nhận được cú bấm."""
        bw, bh = int(26 * self.scale), self.head_h - 2
        x0, y0 = right_edge - bw, 1
        tag = f"btn_{name}"
        edge = WHITE if enabled else "#707070"
        self.head.create_rectangle(x0, y0, right_edge, y0 + bh, fill=BLACK, outline=edge, width=2, tags=(tag,))
        cx, cy = x0 + bw // 2, y0 + bh // 2
        if enabled:
            self._text(self.head, cx, cy, label, self.f_nav, anchor="center", tags=(tag,), bold=True)
            self.head.tag_bind(tag, "<Button-1>", lambda _e: cmd())
            self.head.tag_bind(tag, "<Enter>", lambda _e: self.head.config(cursor="hand2"))
            self.head.tag_bind(tag, "<Leave>", lambda _e: self.head.config(cursor=""))
        else:  # hết câu để xem thì nút mờ đi, bấm không làm gì (gỡ cả lệnh bấm cũ: tag giữ binding sau khi xóa hình)
            for seq in ("<Button-1>", "<Enter>", "<Leave>"):
                self.head.tag_unbind(tag, seq)
            self.head.create_text(cx, cy, text=label, font=self.f_nav, fill="#707070", tags=(tag,))
        return x0 - int(4 * self.scale)

    def _draw_head(self, title: str, index: int = 0, total: int = 0) -> None:
        self.head.delete("all")
        self.title_text = title
        x = self.w - self.pad
        for name, label, cmd in (("hide", "×", lambda: self.on_hide()), ("fade", "◐", lambda: self.cycle_opacity())):
            x = self._button(name, label, x, cmd)
        x = self._nav_button("next", "›", x, lambda: self.on_next(), enabled=index < total - 1)
        x = self._nav_button("prev", "‹", x, lambda: self.on_prev(), enabled=index > 0)
        x = self._button("copy", "Copy", x - int(4 * self.scale), lambda: self.copy())
        shown = self._fit(self.f_head, title, max(x - self.pad, 20))
        self._text(self.head, self.pad, self.head_h // 2, shown, self.f_head, anchor="w", tags=("drag",))
        self.head.tag_bind("drag", "<ButtonPress-1>", self._drag_start)
        self.head.tag_bind("drag", "<B1-Motion>", self._drag_move)

    def _draw_body(self, text: str) -> None:
        at_bottom = self.body.yview()[1] >= 0.999
        self.body_text = text
        self.body.delete("all")
        inner = self.w - 2 * self.pad
        self._text(self.body, self.pad, 2, text, self.f_body, width=inner, bold=True)
        content_h = (self.body.bbox("all") or (0, 0, 0, 0))[3] + self.pad
        view_h = min(max(content_h, int(20 * self.scale)), self.max_h)
        self.body.config(height=view_h, scrollregion=(0, 0, self.w, content_h))
        self._resize(self.head_h + view_h)
        self.win.update_idletasks()  # để yview tính theo kích thước mới
        if content_h <= view_h:
            self.body.yview_moveto(0.0)
        elif at_bottom:
            self.body.yview_moveto(1.0)  # đang stream thì tự cuộn xuống cuối; đang cuộn lên đọc thì giữ nguyên

    def _resize(self, height: int) -> None:
        """Giữ nguyên góc dưới phải, khung mọc lên phía trên khi chữ dài ra."""
        self.win.geometry(f"{self.w}x{height}+{self._right - self.w}+{self._bottom - height}")

    # ---------- nội dung ----------

    def message(self, text: str) -> None:
        self._draw_head("Highlight AI")
        self._full_text = text
        self._draw_body(text)

    def render(self, entry, index: int, total: int) -> None:
        title, body = compose(entry, index, total)
        self._draw_head(title, index, total)
        self._full_text = entry.text.replace("**", "")  # nút Copy chép đáp án, không kèm dòng trạng thái
        if entry.review == "fixed" and entry.fixed_text:
            self._full_text = entry.fixed_text.replace("**", "")  # bản đã sửa mới là đáp án cuối
        self._draw_body(body)

    def copy(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self._full_text.strip())

    # ---------- độ trong suốt ----------

    def _apply_opacity(self) -> None:
        try:
            self.win.attributes("-alpha", self.opacity)
        except tk.TclError:
            pass

    def set_opacity(self, value: float) -> None:
        self.opacity = min(1.0, max(0.2, value))
        self._apply_opacity()

    def cycle_opacity(self) -> None:
        """Bấm nút ◐: đậm hơn -> mờ dần qua từng mức, hết mức mờ nhất thì quay về đậm nhất."""
        lower = [v for v in OPACITY_STEPS if v < self.opacity - 0.01]
        self.set_opacity(lower[0] if lower else OPACITY_STEPS[0])

    # ---------- vị trí / hiện ẩn ----------

    def _work_area(self) -> tuple[int, int, int, int]:
        """(trái, trên, phải, dưới) của vùng làm việc, tức màn hình trừ thanh taskbar."""
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                rect = wintypes.RECT()
                if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
                    return rect.left, rect.top, rect.right, rect.bottom
            except Exception:  # noqa: BLE001
                pass
        return 0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight()

    def rect(self) -> tuple[int, int, int, int] | None:
        """Vị trí khung trên màn hình (trái, trên, phải, dưới) khi đang hiện; dùng để bỏ qua bôi đen ngay trong khung."""
        if not self.visible:
            return None
        x, y = self.win.winfo_x(), self.win.winfo_y()
        return x, y, x + self.win.winfo_width(), y + self.win.winfo_height()

    def _drag_start(self, e) -> None:
        self._x, self._y = e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y()

    def _drag_move(self, e) -> None:
        x, y = e.x_root - self._x, e.y_root - self._y
        self.win.geometry(f"+{x}+{y}")
        self._right, self._bottom = x + self.w, y + self.win.winfo_height()

    def _no_activate(self) -> None:
        """Windows: khung hiện ra không cướp focus bàn phím của app đang dùng."""
        if sys.platform != "win32":
            return
        try:
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(self.win.winfo_id()) or self.win.winfo_id()
            style = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            user32.SetWindowLongW(hwnd, -20, style | 0x08000000 | 0x00000080)  # NOACTIVATE | TOOLWINDOW
        except Exception:  # noqa: BLE001
            pass

    def show(self) -> None:
        if not self.visible:
            self.win.deiconify()
            self.win.update_idletasks()
            self._no_activate()
            self.win.attributes("-topmost", True)
            self.win.lift()
            self.visible = True

    def hide(self) -> None:
        if self.visible:
            self.win.withdraw()
            self.win.update_idletasks()  # xóa khung khỏi màn hình ngay (để chụp màn hình không dính khung)
            self.visible = False
