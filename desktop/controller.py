"""Bộ điều khiển của app popup: nhận lệnh từ phím tắt, chụp màn hình, hỏi AI, giữ lịch sử.

Không phụ thuộc tkinter hay Windows nên test được. `view` là thứ có các hàm:
    visible (thuộc tính), show(), hide(), render(entry, index, total), message(text)
Luồng làm việc (chụp + hỏi AI) chỉ đẩy sự kiện vào hàng đợi; hàm pump() chạy ở luồng giao diện
mới là nơi sửa lịch sử và gọi view, nên không có chuyện hai luồng cùng sửa một thứ.
"""
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Iterator

from core import config, llm, prompts


@dataclass
class Entry:
    created: float
    mode: str
    question: str = ""
    status: str = "capturing"  # capturing -> asking -> done | error
    text: str = ""
    error: str = ""
    size: str = ""  # ví dụ "1920×1080, 312 KB"
    reshow: bool = False  # khung đang mở lúc bấm chụp (đã ẩn tạm) -> mở lại khi có kết quả
    info: dict = field(default_factory=dict)


class Controller:
    def __init__(
        self,
        view,
        capture: Callable[[int | None], bytes],
        ask_stream: Callable[..., Iterator[str]] = llm.ask_stream,
        mode: str = "answer",
        question: str = "",
        lang: str = "vi",
        auto_show: bool = False,
        hide_delay: float = 0.25,
        capture_key: str = "Ctrl+Alt+3",
        spawn: Callable[[Callable[[], None]], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.view = view
        self.capture = capture
        self.ask_stream = ask_stream
        self.mode, self.question, self.lang = mode, question, lang
        self.auto_show = auto_show
        self.hide_delay = hide_delay
        self.capture_key = capture_key
        self.spawn = spawn or (lambda fn: threading.Thread(target=fn, daemon=True).start())
        self.sleep = sleep
        self.clock = clock
        self.history: list[Entry] = []
        self.index = -1  # câu đang hiển thị
        self.busy = False
        self._events: queue.Queue = queue.Queue()

    # ---------- lệnh từ phím tắt (gọi ở luồng giao diện) ----------

    def handle(self, name: str) -> None:
        {"show": self.show, "hide": self.hide, "capture": self.start_capture}[name]()

    def show(self) -> None:
        self.view.show()
        self._render()

    def hide(self) -> None:
        self.view.hide()  # chỉ ẩn khung, lịch sử vẫn giữ nguyên

    def prev(self) -> None:
        if self.index > 0:
            self.index -= 1
            self._render()

    def next(self) -> None:
        if self.index < len(self.history) - 1:
            self.index += 1
            self._render()

    def start_capture(self) -> None:
        if self.busy:
            return  # đang xử lý ảnh trước, bỏ qua lần bấm này
        self.busy = True
        was_visible = self.view.visible
        if was_visible:
            self.view.hide()  # để khung popup không lọt vào ảnh chụp
        entry = Entry(created=self.clock(), mode=self.mode, question=self.question, reshow=was_visible)
        self.history.append(entry)
        self.index = len(self.history) - 1
        self.spawn(lambda: self._work(entry))

    # ---------- luồng nền: chỉ đẩy sự kiện, không đụng view/lịch sử ----------

    def _work(self, entry: Entry) -> None:
        put = self._events.put
        try:
            if entry.reshow:
                self.sleep(self.hide_delay)  # chờ Windows vẽ lại màn hình sau khi khung đã ẩn
            png = self.capture(config.MAX_IMAGE_BYTES)
            put(("captured", entry, png_info(png)))
            system, messages = prompts.build_image(png, "image/png", self.question, self.mode, self.lang)
            for piece in self.ask_stream(system, messages, entry.info):
                put(("chunk", entry, piece))
            put(("done", entry, None))
        except Exception as e:  # noqa: BLE001 - luồng nền không được chết im lặng
            put(("error", entry, str(e) or e.__class__.__name__))

    # ---------- luồng giao diện: gọi định kỳ ----------

    def pump(self) -> None:
        while True:
            try:
                kind, entry, data = self._events.get_nowait()
            except queue.Empty:
                return
            if kind == "captured":
                entry.size = data
                entry.status = "asking"
                if entry.reshow or self.auto_show:
                    self.view.show()
            elif kind == "chunk":
                entry.text += data
            elif kind == "done":
                entry.status = "done"
                self.busy = False
            elif kind == "error":
                entry.status = "error"
                entry.error = data
                self.busy = False
                if entry.reshow or self.auto_show:
                    self.view.show()
            if self.history and entry is self.history[self.index]:
                self._render()

    def _render(self) -> None:
        if not self.view.visible:
            return
        if not self.history:
            self.view.message(f"Chưa có câu trả lời nào.\nBấm {self.capture_key} để chụp màn hình và hỏi AI.")
            return
        self.view.render(self.history[self.index], self.index, len(self.history))


def png_info(png: bytes) -> str:
    from .clipboard import png_size

    w, h = png_size(png)
    return f"{w}×{h}, {len(png) // 1024} KB"
