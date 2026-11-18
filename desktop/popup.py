"""Khung popup nhỏ (tkinter) ở góc dưới bên phải màn hình để hiện câu trả lời.

- Không viền, luôn nằm trên cùng, không cướp focus của app bạn đang dùng (Windows).
- Kéo thanh tiêu đề để dời chỗ; nút ◀ ▶ xem lại các câu trước; ✕ chỉ ẩn khung, lịch sử vẫn còn.
- Chữ chọn được bằng chuột để copy.
"""
import re
import sys
import tkinter as tk
import tkinter.font as tkfont

BG, BAR, FG, DIM = "#1e1e2e", "#2a2a3e", "#e8e8f0", "#9a9ab0"
ACCENT, ERR = "#7aa2f7", "#f7768e"
STATUS_TEXT = {"capturing": "📸 Đang chụp màn hình…", "asking": "⏳ Đang hỏi AI…"}


class Popup:
    def __init__(self, root: tk.Tk, width: int = 460, height: int = 300, margin: int = 16, alpha: float = 0.96) -> None:
        self.root = root
        # Màn hình phóng to 150% thì 460 điểm ảnh trông rất nhỏ: nhân theo tỉ lệ DPI (96 DPI = 100%)
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96)
        self.w, self.h, self.margin = int(width * self.scale), int(height * self.scale), int(margin * self.scale)
        self.on_prev = self.on_next = self.on_hide = lambda: None
        self.visible = False

        self.win = tk.Toplevel(root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-alpha", alpha)
        except tk.TclError:
            pass
        self.win.configure(bg=BG, highlightbackground=ACCENT, highlightthickness=1)

        bar = tk.Frame(self.win, bg=BAR)
        bar.pack(fill="x")
        self.title = tk.Label(bar, text="Highlight AI", bg=BAR, fg=ACCENT, anchor="w", padx=8, pady=4,
                              font=("Segoe UI", 9, "bold"))
        self.title.pack(side="left", fill="x", expand=True)
        for text, cmd in (("×", lambda: self.on_hide()), ("›", lambda: self.on_next()), ("‹", lambda: self.on_prev())):
            b = tk.Label(bar, text=text, bg=BAR, fg=FG, padx=8, pady=4, cursor="hand2", font=("Segoe UI", 12, "bold"))
            b.pack(side="right")
            b.bind("<Button-1>", lambda _e, c=cmd: c())
        for widget in (bar, self.title):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_move)

        body = tk.Frame(self.win, bg=BG)
        body.pack(fill="both", expand=True)
        self.scroll = tk.Scrollbar(body, orient="vertical")
        self.scroll.pack(side="right", fill="y")
        family = "Segoe UI" if "Segoe UI" in tkfont.families(root) else "TkDefaultFont"
        self.text = tk.Text(body, wrap="word", bg=BG, fg=FG, insertbackground=FG, relief="flat", padx=10, pady=8,
                            font=(family, 11), yscrollcommand=self.scroll.set, cursor="arrow", spacing3=3)
        self.text.pack(side="left", fill="both", expand=True)
        self.scroll.config(command=self.text.yview)
        self.text.tag_configure("dim", foreground=DIM, font=(family, 9))
        self.text.tag_configure("bold", font=(family, 11, "bold"))
        self.text.tag_configure("err", foreground=ERR)
        self.text.tag_configure("status", foreground=ACCENT)
        # Chỉ cho chọn/copy, không cho gõ vào
        self.text.bind("<Key>", lambda e: None if (e.state & 0x4 and e.keysym.lower() in "ca") else "break")

        self._x = self._y = 0
        self._place()

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

    def _place(self) -> None:
        left, top, right, bottom = self._work_area()
        x = max(left, right - self.w - self.margin)
        y = max(top, bottom - self.h - self.margin)
        self.win.geometry(f"{self.w}x{self.h}+{x}+{y}")

    def _drag_start(self, e) -> None:
        self._x, self._y = e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y()

    def _drag_move(self, e) -> None:
        self.win.geometry(f"+{e.x_root - self._x}+{e.y_root - self._y}")

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

    # ---------- nội dung ----------

    def _set(self, title: str, parts: list[tuple[str, str]], keep_scroll: bool = False) -> None:
        y = self.text.yview()
        at_bottom = y[1] >= 0.999
        self.title.config(text=title)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        for chunk, tag in parts:
            if tag:
                self.text.insert("end", chunk, tag)
                continue
            for i, piece in enumerate(re.split(r"\*\*(.+?)\*\*", chunk, flags=re.S)):  # **đậm** -> chữ đậm
                if piece:
                    self.text.insert("end", piece, "bold" if i % 2 else ())
        if keep_scroll and not at_bottom:
            self.text.yview_moveto(y[0])
        else:
            self.text.see("end")  # đang stream thì tự cuộn xuống cuối
        # giữ state normal để còn chọn/copy; việc chặn gõ do bind <Key>

    def message(self, text: str) -> None:
        self._set("Highlight AI", [(text, "dim")])

    def render(self, entry, index: int, total: int) -> None:
        model = entry.info.get("model", "")
        title = f"Highlight AI · {index + 1}/{total}" + (f" · {model}" if model else "")
        parts: list[tuple[str, str]] = []
        if entry.size:
            parts.append((f"Ảnh {entry.size}\n", "dim"))
        if entry.text:
            parts.append((entry.text, ""))
        if entry.status in STATUS_TEXT:
            parts.append((("\n" if entry.text else "") + STATUS_TEXT[entry.status], "status"))
        if entry.status == "error":
            parts.append((("\n\n" if entry.text else "") + "⚠ " + entry.error, "err"))
        self._set(title, parts, keep_scroll=True)
