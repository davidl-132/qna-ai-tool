"""Phần Windows: hook bàn phím/chuột toàn cục để (1) nhận phím Alt/Shift bấm đơn và (2) tự tra chữ bôi đen.

Chỉ dùng ctypes (không cần thư viện ngoài). Hook CHỈ làm hai việc:
- bàn phím: biết phím bổ trợ nào được bấm đơn (không lưu, không ghi lại bạn gõ gì);
- chuột: biết bạn vừa kéo/bấm đúp để đoán có vùng bôi đen.
Vì là hook toàn cục nên một số phần mềm diệt virus có thể cảnh báo; chạy `--no-select` và để trống TAP_* để không cài hook nào.
"""
import ctypes
import os
import sys
import threading
import time
from typing import Callable

from .selection import NavKeys, SelectionDetector, TapDetector, VK_NAMES, clean_selection, grab_selection

WH_KEYBOARD_LL, WH_MOUSE_LL = 13, 14
WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x100, 0x101, 0x104, 0x105
WM_LBUTTONDOWN, WM_LBUTTONUP = 0x201, 0x202
LLKHF_INJECTED, LLMHF_INJECTED = 0x10, 0x01
KEYEVENTF_KEYUP, INPUT_KEYBOARD = 0x0002, 1
VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN, VK_C, VK_MASK = 0x11, 0x12, 0x5B, 0x5C, 0x43, 0xE8
VK_SHIFT = 0x10

# Terminal: Ctrl+C là lệnh NGẮT chương trình, tuyệt đối không bơm vào. Explorer/RDP: kéo chuột không phải bôi chữ.
DEFAULT_BLOCK_APPS = ("cmd.exe,powershell.exe,pwsh.exe,windowsterminal.exe,wt.exe,conhost.exe,openconsole.exe,"
                      "mintty.exe,putty.exe,explorer.exe,mstsc.exe")
TERMINAL_CLASSES = {"consolewindowclass", "cascadia_hosting_window_class", "virtualconsoleclass", "mintty"}


# ---------- cấu trúc Windows (dùng kiểu có kích thước cố định để kiểm tra được kích thước ở mọi nền tảng) ----------

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_int32), ("dy", ctypes.c_int32), ("mouseData", ctypes.c_uint32),
                ("dwFlags", ctypes.c_uint32), ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_uint16), ("wScan", ctypes.c_uint16), ("dwFlags", ctypes.c_uint32),
                ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_uint32), ("wParamL", ctypes.c_uint16), ("wParamH", ctypes.c_uint16)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_uint32), ("u", _INPUT_UNION)]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", ctypes.c_uint32), ("scanCode", ctypes.c_uint32), ("flags", ctypes.c_uint32),
                ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int32), ("y", ctypes.c_int32), ("mouseData", ctypes.c_uint32),
                ("flags", ctypes.c_uint32), ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t)]


def _key_input(vk: int, up: bool) -> INPUT:
    i = INPUT(type=INPUT_KEYBOARD)
    i.ki = KEYBDINPUT(wVk=vk, wScan=0, dwFlags=KEYEVENTF_KEYUP if up else 0, time=0, dwExtraInfo=0)
    return i


def parse_apps(spec: str) -> set[str]:
    return {a.strip().lower() for a in spec.split(",") if a.strip()}


class InputHooks(threading.Thread):
    """Chạy ở luồng riêng. `emit(sự_kiện)`: sự_kiện là tên phím bấm đơn (str) hoặc ("text", chữ_bôi_đen)."""

    def __init__(self, emit: Callable[[object], None], taps: dict[int, str], select: bool = True,
                 settle: float = 1.0, block_apps: str = DEFAULT_BLOCK_APPS, only_apps: str = "",
                 text_limit: int = 4000, nav: bool = False) -> None:
        super().__init__(daemon=True)
        self.emit = emit
        self.enabled = True  # app đặt False khi người dùng tắt bằng phím bật/tắt chung
        self.popup_rect: tuple[int, int, int, int] | None = None  # app cập nhật: bôi đen trong khung popup thì bỏ qua
        self.nav = NavKeys() if nav else None
        self.nav_active = False  # app đặt True khi khung đang hiện và có từ 2 câu trở lên
        self.taps = TapDetector(taps)
        self.select = SelectionDetector(settle=settle) if select else None
        self.block_apps, self.only_apps = parse_apps(block_apps), parse_apps(only_apps)
        self.text_limit = text_limit
        self.errors: list[str] = []
        self.ready = threading.Event()
        self._tid = 0
        self._last_text, self._last_time = "", 0.0
        self._hooks = []  # giữ tham chiếu tới hàm callback, nếu không bị thu gom rác thì Windows gọi vào chỗ chết

    # ---------- luồng chính: cài hook + vòng lặp thông điệp ----------

    def run(self) -> None:
        if sys.platform != "win32":
            self.errors.append("Hook bàn phím/chuột hiện chỉ chạy trên Windows.")
            self.ready.set()
            return
        from ctypes import wintypes

        user32 = self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32 = kernel32
        self._tid = kernel32.GetCurrentThreadId()
        lresult = ctypes.c_ssize_t
        hookproc = ctypes.WINFUNCTYPE(lresult, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, hookproc, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = lresult
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.SendInput.argtypes = [wintypes.UINT, ctypes.c_void_p, ctypes.c_int]
        user32.SendInput.restype = wintypes.UINT
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        module = kernel32.GetModuleHandleW(None)
        handles = []

        def next_hook(hook, n, w, l):
            return user32.CallNextHookEx(hook[0], n, w, l)

        hook_k, hook_m = [None], [None]

        def kbd(n, w, l):
            try:
                if n >= 0:
                    kb = KBDLLHOOKSTRUCT.from_address(l)
                    if not kb.flags & LLKHF_INJECTED:  # bỏ qua phím do chính app tự bơm
                        down = w in (WM_KEYDOWN, WM_SYSKEYDOWN)
                        if down or w in (WM_KEYUP, WM_SYSKEYUP):
                            if self._on_key(kb.vkCode, down):
                                return 1  # nuốt phím: app đang dùng không nhận được
            except Exception:  # noqa: BLE001 - hook tuyệt đối không được ném lỗi
                pass
            return next_hook(hook_k, n, w, l)

        def mouse(n, w, l):
            try:
                if n >= 0 and w in (WM_LBUTTONDOWN, WM_LBUTTONUP):
                    ms = MSLLHOOKSTRUCT.from_address(l)
                    if not ms.flags & LLMHF_INJECTED:
                        self._on_mouse(w == WM_LBUTTONDOWN, ms.x, ms.y)
            except Exception:  # noqa: BLE001
                pass
            return next_hook(hook_m, n, w, l)

        if self.taps.taps or self.nav is not None:
            cb = hookproc(kbd)
            hook_k[0] = user32.SetWindowsHookExW(WH_KEYBOARD_LL, cb, module, 0)
            handles.append(cb)
            if not hook_k[0]:
                self.errors.append("Không cài được hook bàn phím (phím Alt/Shift đơn sẽ không dùng được).")
        if self.select is not None:
            cb = hookproc(mouse)
            hook_m[0] = user32.SetWindowsHookExW(WH_MOUSE_LL, cb, module, 0)
            handles.append(cb)
            if not hook_m[0]:
                self.errors.append("Không cài được hook chuột (tự tra chữ bôi đen sẽ không dùng được).")
            else:
                threading.Thread(target=self._ticker, daemon=True).start()
        self._hooks = handles
        self.ready.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            pass  # hook cấp thấp chạy ngay trong vòng lặp này, không cần xử lý thông điệp
        for h in (hook_k[0], hook_m[0]):
            if h:
                user32.UnhookWindowsHookEx(h)

    def stop(self) -> None:
        if sys.platform == "win32" and self._tid:
            ctypes.WinDLL("user32").PostThreadMessageW(self._tid, 0x0012, 0, 0)  # WM_QUIT

    # ---------- xử lý sự kiện (chạy trong hook: phải thật nhanh) ----------

    def _on_key(self, vk: int, down: bool) -> bool:
        """Trả về True nếu phím này bị app nuốt (mũi tên Trái/Phải dùng để chuyển câu)."""
        now = time.monotonic()
        if down and self.select is not None and vk not in VK_NAMES:
            self.select.key()  # gõ chữ sau khi bôi đen thì hủy lượt tra
        name = self.taps.key(vk, down, now)
        if name and self.enabled:
            if vk in (0xA4, 0xA5):
                self._mask_alt()
            self.emit(name)
        if self.nav is not None and vk in self.nav.NAMES:
            mods = any(self._held(m) for m in (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN))
            nav_name, swallow = self.nav.key(vk, down, self.enabled and self.nav_active, mods)
            if nav_name:
                self.emit(nav_name)
            return swallow
        return False

    def _mask_alt(self) -> None:
        """Chèn một phím vô nghĩa giữa lúc nhấn và thả Alt để Windows KHÔNG mở menu của app (hành vi mặc định của Alt đơn)."""
        arr = (INPUT * 2)(_key_input(VK_MASK, False), _key_input(VK_MASK, True))
        self.user32.SendInput(2, ctypes.byref(arr), ctypes.sizeof(INPUT))

    def _held(self, vk: int) -> bool:
        return bool(self.user32.GetAsyncKeyState(vk) & 0x8000)

    def _on_mouse(self, down: bool, x: int, y: int) -> None:
        now = time.monotonic()
        if down:
            self.taps.mouse()
            if self.select is None:
                return
            rect = self.popup_rect
            inside = bool(rect and rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3])
            with_mod = self._held(VK_CONTROL) or self._held(VK_MENU) or self._held(VK_LWIN) or self._held(VK_RWIN)
            self.select.mouse_down(x, y, now, ignore=inside or with_mod)
        elif self.select is not None:
            self.select.mouse_up(x, y, now)

    # ---------- luồng phụ: đến hạn thì lấy chữ bôi đen ----------

    def _ticker(self) -> None:
        while True:
            time.sleep(0.05)
            try:
                if self.select.poll(time.monotonic()) and self.enabled:
                    self._lookup()
            except Exception:  # noqa: BLE001
                pass

    def _foreground(self) -> tuple[str, str]:
        """(tên file chạy của cửa sổ đang dùng, lớp cửa sổ), đều viết thường; '' nếu không đọc được."""
        from ctypes import wintypes

        u, k = self.user32, self._kernel32
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.OpenProcess.restype = wintypes.HANDLE
        k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                 ctypes.POINTER(wintypes.DWORD)]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return "", ""
        cls = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(hwnd, cls, 256)
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        exe = ""
        h = k.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if h:
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                    exe = os.path.basename(buf.value).lower()
            finally:
                k.CloseHandle(h)
        return exe, cls.value.lower()

    def _send_copy(self) -> None:
        arr = (INPUT * 4)(_key_input(VK_CONTROL, False), _key_input(VK_C, False),
                          _key_input(VK_C, True), _key_input(VK_CONTROL, True))
        self.user32.SendInput(4, ctypes.byref(arr), ctypes.sizeof(INPUT))

    def _lookup(self) -> None:
        exe, cls = self._foreground()
        if cls in TERMINAL_CLASSES or exe in self.block_apps:
            return
        if self.only_apps and exe not in self.only_apps:
            return
        # Đang giữ Ctrl/Alt/Win thì Ctrl+C bơm vào sẽ thành tổ hợp khác: bỏ qua lượt này
        if any(self._held(vk) for vk in (VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)):
            return
        from .clipboard import WinClipboard

        text = clean_selection(grab_selection(WinClipboard(), self._send_copy), self.text_limit)
        if not text:
            return
        now = time.monotonic()
        if text == self._last_text and now - self._last_time < 8:
            return  # cùng một đoạn vừa tra xong, đừng tra lại
        self._last_text, self._last_time = text, now
        self.emit(("text", text))
