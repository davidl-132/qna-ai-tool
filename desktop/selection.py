"""Logic thuần (không gọi Windows) cho: bấm phím đơn (Alt/Shift), nhận biết bôi đen, lấy chữ đã bôi đen.

Phần gọi Windows thật (hook bàn phím/chuột, SendInput, clipboard) nằm ở inputhooks.py và clipboard.py; tách ra như
vậy để test được logic bằng sự kiện giả.
"""
import math
import threading
import time
from typing import Callable

# Mã phím ảo của các phím bổ trợ hay dùng làm "phím bấm đơn"
TAP_KEYS = {"lalt": 0xA4, "ralt": 0xA5, "lshift": 0xA0, "rshift": 0xA1, "lctrl": 0xA2, "rctrl": 0xA3}
VK_NAMES = {v: k for k, v in TAP_KEYS.items()}


def parse_tap(spec: str) -> int | None:
    """'lalt' -> 0xA4; để trống -> None (không dùng). Sai tên thì ném ValueError."""
    spec = spec.strip().lower()
    if not spec:
        return None
    if spec not in TAP_KEYS:
        raise ValueError(f"Phím '{spec}' không hợp lệ (chọn: {', '.join(TAP_KEYS)}, hoặc để trống để tắt).")
    return TAP_KEYS[spec]


class TapDetector:
    """Nhận ra "bấm đơn" một phím bổ trợ: nhấn rồi thả nhanh, KHÔNG có phím/chuột nào khác xen vào.

    Nhờ vậy Alt+Tab, Shift+chữ, Alt+Shift (đổi bàn phím)... không bị tính là bấm đơn.
    """

    def __init__(self, taps: dict[int, str], max_hold: float = 0.4) -> None:
        self.taps = taps  # mã phím -> tên sự kiện
        self.max_hold = max_hold
        self._down: set[int] = set()  # mọi phím đang giữ (kể cả phím không theo dõi)
        self._started: dict[int, float] = {}  # phím theo dõi -> lúc nhấn
        self._dirty: set[int] = set()  # phím theo dõi đã bị "làm bẩn" bởi phím/chuột khác

    def key(self, vk: int, down: bool, t: float) -> str | None:
        """Gọi với mỗi sự kiện phím thật (đã bỏ sự kiện do chương trình tự bơm). Trả về tên sự kiện nếu vừa có bấm đơn."""
        if down:
            if vk in self._down:
                return None  # giữ phím nên lặp sự kiện: bỏ qua
            others_down = bool(self._down)
            self._down.add(vk)
            self._dirty.update(self._started)  # phím theo dõi khác đang giữ thì không còn là bấm đơn
            if vk in self.taps:
                self._started[vk] = t
                if others_down:
                    self._dirty.add(vk)
            return None
        self._down.discard(vk)
        if vk not in self._started:
            return None
        began = self._started.pop(vk)
        dirty = vk in self._dirty
        self._dirty.discard(vk)
        if not dirty and t - began <= self.max_hold:
            return self.taps[vk]
        return None

    def mouse(self) -> None:
        """Có bấm chuột khi đang giữ phím (Shift+click, Alt+click...): không phải bấm đơn."""
        self._dirty.update(self._started)


VK_LEFT, VK_RIGHT = 0x25, 0x27


class NavKeys:
    """Phím mũi tên Trái/Phải trần: xem câu trước/sau khi khung đang hiện. Logic thuần để test.

    `key()` trả về (tên_sự_kiện | None, có_nuốt_phím_không). Chỉ nuốt khi khung đang hiện và không giữ
    Ctrl/Alt/Shift/Win (Shift+mũi tên để chọn chữ, Ctrl+mũi tên nhảy từ... vẫn chạy bình thường).
    Nuốt cả lúc thả phím để app đằng sau không thấy một cú "thả" lẻ loi; giữ phím không lặp lại việc chuyển câu.
    """

    NAMES = {VK_LEFT: "prev", VK_RIGHT: "next"}

    def __init__(self) -> None:
        self._held: set[int] = set()

    def key(self, vk: int, down: bool, active: bool, mods_held: bool) -> tuple[str | None, bool]:
        if vk not in self.NAMES:
            return None, False
        if not down:
            if vk in self._held:
                self._held.discard(vk)
                return None, True
            return None, False
        if vk in self._held:  # giữ phím -> lặp lại: nuốt nhưng không chuyển câu nữa
            return None, True
        if not active or mods_held:
            return None, False
        self._held.add(vk)
        return self.NAMES[vk], True


class SelectionDetector:
    """Đoán người dùng vừa bôi đen chữ: kéo chuột, hoặc bấm đúp/ba, rồi đứng yên `settle` giây thì báo "đến hạn"."""

    def __init__(self, settle: float = 1.0, min_drag: float = 6.0, multi_click: float = 0.5) -> None:
        self.settle = settle
        self.min_drag = min_drag
        self.multi_click = multi_click
        self._down: tuple[float, float] | None = None
        self._last_up: tuple[float, float, float] | None = None  # x, y, lúc thả
        self._clicks = 0
        self._due: float | None = None
        self._lock = threading.Lock()

    def mouse_down(self, x: float, y: float, t: float, ignore: bool = False) -> None:
        with self._lock:
            self._due = None  # bấm chuột mới: hủy lượt chờ
            self._down = None if ignore else (x, y)

    def mouse_up(self, x: float, y: float, t: float) -> None:
        with self._lock:
            if self._down is None:
                return
            dx, dy = x - self._down[0], y - self._down[1]
            dragged = math.hypot(dx, dy) >= self.min_drag
            if (self._last_up and t - self._last_up[2] <= self.multi_click
                    and math.hypot(x - self._last_up[0], y - self._last_up[1]) <= self.min_drag):
                self._clicks += 1
            else:
                self._clicks = 1
            self._last_up = (x, y, t)
            self._down = None
            if dragged or self._clicks >= 2:
                self._due = t + self.settle

    def key(self) -> None:
        """Gõ phím sau khi bôi đen (người dùng đang làm việc khác): hủy."""
        with self._lock:
            self._due = None

    def poll(self, now: float) -> bool:
        """True đúng một lần khi vùng chọn đã đứng yên đủ lâu."""
        with self._lock:
            if self._due is not None and now >= self._due:
                self._due = None
                return True
            return False


def clean_selection(text: str | None, limit: int = 4000) -> str | None:
    """Chữ bôi đen hợp lệ để tra: bỏ khoảng trắng thừa, cần ít nhất 2 ký tự, cắt bớt nếu quá dài."""
    if not text:
        return None
    text = text.replace("\r\n", "\n").strip()
    if len(text.replace(" ", "").replace("\n", "")) < 2:
        return None
    return text[:limit]


def grab_selection(clip, send_copy: Callable[[], None], sleep: Callable[[float], None] = time.sleep,
                   timeout: float = 0.5, step: float = 0.02) -> str | None:
    """Lấy chữ đang bôi đen bằng cách bơm Ctrl+C, rồi trả clipboard về như cũ.

    `clip` cần có: snapshot() (None = không sao lưu được, thì KHÔNG đụng vào), sequence(), read_text(), restore(snap).
    Trả về None nếu không có chữ nào được copy (app không có vùng chọn, hoặc copy không ra chữ).
    """
    snap = clip.snapshot()
    if snap is None:
        return None
    before = clip.sequence()
    send_copy()
    waited = 0.0
    while clip.sequence() == before:
        if waited >= timeout:
            return None  # clipboard không đổi: không có gì được copy, cũng không có gì cần khôi phục
        sleep(step)
        waited += step
    try:
        return clip.read_text()
    finally:
        clip.restore(snap)
