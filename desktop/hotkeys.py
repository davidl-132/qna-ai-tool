"""Phím tắt toàn cục trên Windows (RegisterHotKey qua ctypes, không cần thư viện ngoài).

Cú pháp: "ctrl+alt+1", "ctrl+shift+f9", "win+z", "1" (phím trần), "num1" (phím số bên phải bàn phím)...
Phím trần như "1", "2", "3" chặn luôn việc gõ số ở mọi app trong lúc app popup chạy; mặc định dùng Ctrl+Alt+số.
"""
import sys
import threading
from typing import Callable

MODIFIERS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
NAMED_KEYS = {"space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "left": 0x25, "up": 0x26,
              "right": 0x27, "down": 0x28, "home": 0x24, "end": 0x23, "pageup": 0x21, "pagedown": 0x22}


def is_bare_typing_key(spec: str) -> bool:
    """True nếu phím tắt là một chữ/số trần (không phím bổ trợ): bật nó sẽ chặn việc gõ phím đó ở mọi app."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    return len(parts) == 1 and len(parts[0]) == 1


def parse_hotkey(spec: str) -> tuple[int, int]:
    """'ctrl+alt+1' -> (modifiers, virtual-key). Ném ValueError nếu sai cú pháp."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if not parts:
        raise ValueError("Phím tắt đang để trống.")
    *mods, key = parts
    mask = 0
    for m in mods:
        if m not in MODIFIERS:
            raise ValueError(f"Phím bổ trợ '{m}' không hợp lệ trong '{spec}' (chỉ ctrl/alt/shift/win).")
        mask |= MODIFIERS[m]
    if key in NAMED_KEYS:
        vk = NAMED_KEYS[key]
    elif len(key) == 1 and (key.isalpha() or key.isdigit()) and key.isascii():
        vk = ord(key.upper())
    elif key.startswith("num") and key[3:].isdigit() and 0 <= int(key[3:]) <= 9:  # bàn phím số bên phải
        vk = 0x60 + int(key[3:])
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError(f"Phím '{key}' không hợp lệ trong '{spec}'.")
    return mask, vk


class HotkeyListener(threading.Thread):
    """Chạy vòng lặp thông điệp ở luồng riêng, gọi callback(tên) mỗi khi bấm phím tắt.

    Nếu có `toggle`, phím đó bật/tắt toàn bộ các phím còn lại (tắt = trả phím về cho các app khác dùng bình thường,
    chỉ riêng phím toggle vẫn nghe). Mỗi lần đổi trạng thái gọi callback("on") hoặc callback("off").
    """

    TOGGLE_ID = 1000

    def __init__(self, bindings: dict[str, str], callback: Callable[[str], None], toggle: str = "") -> None:
        super().__init__(daemon=True)
        self.bindings = bindings
        self.callback = callback
        self.toggle = toggle
        self.enabled = True
        self.errors: list[str] = []
        self.registered: list[str] = []  # cú pháp các phím đã đăng ký được (để app báo cho người dùng)
        self.ready = threading.Event()
        self._tid = 0

    def run(self) -> None:
        if sys.platform != "win32":
            self.errors.append("Phím tắt toàn cục hiện chỉ chạy trên Windows.")
            self.ready.set()
            return
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._tid = kernel32.GetCurrentThreadId()

        parsed: dict[int, tuple[str, str, int, int]] = {}  # id -> (tên, cú pháp, phím bổ trợ, mã phím)
        for i, (name, spec) in enumerate(self.bindings.items(), start=1):
            try:
                mods, vk = parse_hotkey(spec)
                parsed[i] = (name, spec, mods, vk)
            except ValueError as e:
                self.errors.append(str(e))
        active: set[int] = set()

        def apply(enabled: bool, report: bool) -> None:
            for i, (_name, spec, mods, vk) in parsed.items():
                if enabled and i not in active:
                    if user32.RegisterHotKey(None, i, mods | MOD_NOREPEAT, vk):
                        active.add(i)
                        if report:
                            self.registered.append(spec)
                    elif report:
                        self.errors.append(f"Không đăng ký được {spec} (đã có app khác dùng phím này?).")
                elif not enabled and i in active:
                    user32.UnregisterHotKey(None, i)
                    active.discard(i)

        apply(True, report=True)
        toggle_on = False
        if self.toggle:
            try:
                mods, vk = parse_hotkey(self.toggle)
                if user32.RegisterHotKey(None, self.TOGGLE_ID, mods | MOD_NOREPEAT, vk):
                    toggle_on = True
                    self.registered.append(self.toggle)
                else:
                    self.errors.append(f"Không đăng ký được {self.toggle} (đã có app khác dùng phím này?).")
            except ValueError as e:
                self.errors.append(str(e))
        self.ready.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message != WM_HOTKEY:
                continue
            try:
                if toggle_on and msg.wParam == self.TOGGLE_ID:
                    self.enabled = not self.enabled
                    apply(self.enabled, report=False)
                    self.callback("on" if self.enabled else "off")
                elif msg.wParam in active:
                    self.callback(parsed[msg.wParam][0])
            except Exception:  # noqa: BLE001 - không để lỗi callback giết vòng lặp phím tắt
                pass
        for i in list(active):
            user32.UnregisterHotKey(None, i)
        if toggle_on:
            user32.UnregisterHotKey(None, self.TOGGLE_ID)

    def stop(self) -> None:
        if sys.platform == "win32" and self._tid:
            import ctypes

            ctypes.WinDLL("user32").PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
