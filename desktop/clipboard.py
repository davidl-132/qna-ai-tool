"""Đọc ảnh từ clipboard Windows, chỉ dùng thư viện có sẵn của Python (ctypes + zlib).

Không cần Pillow hay PowerShell, vì máy có Application Control thường chặn file DLL/.pyd lạ.

- dib_to_png(): đổi ảnh dạng DIB (định dạng Windows dùng cho ảnh trong clipboard) sang PNG. Thuần Python.
- WinClipboard: gọi API Windows để biết clipboard có ảnh mới không và lấy ảnh ra.
"""
import struct
import sys
import time
import zlib

CF_UNICODETEXT = 13
# Các định dạng không phải khối nhớ HGLOBAL (là handle GDI): không sao lưu được
_NON_HGLOBAL = {2, 3, 9, 14, 0x80, 0x82, 0x83, 0x8E}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CF_DIB = 8


# ---------- Thuần Python (test được trên mọi hệ điều hành) ----------

def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _encode_png(width: int, height: int, rows: list[bytes]) -> bytes:
    raw = b"".join(b"\x00" + r for r in rows)  # filter 0 cho mỗi dòng
    return (
        PNG_SIGNATURE
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, 3))
        + _chunk(b"IEND", b"")
    )


def parse_dib(dib: bytes) -> tuple[int, int, list[bytes]]:
    """Trả về (rộng, cao, các dòng RGB từ trên xuống). Hỗ trợ 24 và 32 bit."""
    if len(dib) < 40:
        raise ValueError("DIB quá ngắn")
    (size, width, height, _planes, bpp, comp, _img, _xp, _yp, clr_used, _imp) = struct.unpack(
        "<IiiHHIIiiII", dib[:40]
    )
    if size < 40 or width <= 0 or height == 0:
        raise ValueError("DIB không hợp lệ")
    if bpp not in (24, 32):
        raise ValueError(f"Chưa hỗ trợ ảnh {bpp} bit")
    if comp not in (0, 3):  # BI_RGB hoặc BI_BITFIELDS
        raise ValueError(f"Chưa hỗ trợ nén kiểu {comp}")
    offset = size
    if comp == 3 and size == 40:
        masks = struct.unpack("<III", dib[40:52])
        if bpp == 32 and masks != (0x00FF0000, 0x0000FF00, 0x000000FF):
            raise ValueError("Mặt nạ màu lạ")
        offset += 12
    offset += clr_used * 4
    h = abs(height)
    bytes_pp = bpp // 8
    stride = ((width * bpp + 31) // 32) * 4
    if len(dib) < offset + stride * h:
        raise ValueError("DIB bị cụt")
    rows: list[bytes] = []
    for y in range(h):
        row = dib[offset + y * stride: offset + y * stride + width * bytes_pp]
        out = bytearray(width * 3)
        out[0::3] = row[2::bytes_pp]  # R
        out[1::3] = row[1::bytes_pp]  # G
        out[2::3] = row[0::bytes_pp]  # B
        rows.append(bytes(out))
    if height > 0:  # bottom-up: dòng đầu tiên trong dữ liệu là dòng dưới cùng
        rows.reverse()
    return width, h, rows


def _decimate(width: int, rows: list[bytes], k: int) -> tuple[int, list[bytes]]:
    new_w = (width + k - 1) // k
    out = []
    for row in rows[::k]:
        o = bytearray(new_w * 3)
        for c in range(3):
            o[c::3] = row[c::3][::k]
        out.append(bytes(o))
    return new_w, out


def dib_to_png(dib: bytes, max_bytes: int | None = None) -> bytes:
    """DIB -> PNG. Nếu PNG vượt `max_bytes` thì thu nhỏ ảnh (bỏ bớt điểm ảnh) cho đến khi vừa."""
    width, height, rows = parse_dib(dib)
    png = _encode_png(width, height, rows)
    k = 1
    while max_bytes and len(png) > max_bytes and k < 8:
        k += 1
        w2, r2 = _decimate(width, rows, k)
        png = _encode_png(w2, len(r2), r2)
    return png


def png_size(png: bytes) -> tuple[int, int]:
    return struct.unpack(">II", png[16:24])


# ---------- Phần gọi API Windows ----------

class WinClipboard:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Chỉ chạy trên Windows")
        import ctypes
        from ctypes import wintypes

        self._ct = ctypes
        u = self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        k = self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        u.GetClipboardSequenceNumber.restype = wintypes.DWORD
        u.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        u.IsClipboardFormatAvailable.restype = wintypes.BOOL
        u.OpenClipboard.argtypes = [wintypes.HWND]
        u.OpenClipboard.restype = wintypes.BOOL
        u.CloseClipboard.restype = wintypes.BOOL
        u.GetClipboardData.argtypes = [wintypes.UINT]
        u.GetClipboardData.restype = wintypes.HANDLE
        u.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
        u.RegisterClipboardFormatW.restype = wintypes.UINT
        k.GlobalLock.argtypes = [wintypes.HGLOBAL]
        k.GlobalLock.restype = wintypes.LPVOID
        k.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        k.GlobalUnlock.restype = wintypes.BOOL
        k.GlobalSize.argtypes = [wintypes.HGLOBAL]
        k.GlobalSize.restype = ctypes.c_size_t
        k.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        k.GlobalAlloc.restype = wintypes.HGLOBAL
        k.GlobalFree.argtypes = [wintypes.HGLOBAL]
        k.GlobalFree.restype = wintypes.HGLOBAL
        u.EnumClipboardFormats.argtypes = [wintypes.UINT]
        u.EnumClipboardFormats.restype = wintypes.UINT
        u.EmptyClipboard.restype = wintypes.BOOL
        u.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        u.SetClipboardData.restype = wintypes.HANDLE
        u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                      ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                      wintypes.HANDLE, wintypes.HANDLE, wintypes.LPVOID]
        u.CreateWindowExW.restype = wintypes.HWND
        u.DestroyWindow.argtypes = [wintypes.HWND]
        u.DestroyWindow.restype = wintypes.BOOL
        self.cf_png = u.RegisterClipboardFormatW("PNG")

    def sequence(self) -> int:
        """Số này tăng mỗi khi nội dung clipboard thay đổi."""
        return int(self.user32.GetClipboardSequenceNumber())

    def has_image(self) -> bool:
        return bool(self.user32.IsClipboardFormatAvailable(CF_DIB)) or bool(
            self.cf_png and self.user32.IsClipboardFormatAvailable(self.cf_png)
        )

    def _read_format(self, fmt: int) -> bytes | None:
        h = self.user32.GetClipboardData(fmt)
        if not h:
            return None
        ptr = self.kernel32.GlobalLock(h)
        if not ptr:
            return None
        try:
            return self._ct.string_at(ptr, self.kernel32.GlobalSize(h))
        finally:
            self.kernel32.GlobalUnlock(h)

    def read_png(self, max_bytes: int | None = None) -> bytes | None:
        """Lấy ảnh trong clipboard dưới dạng PNG; None nếu không có ảnh hoặc không mở được clipboard."""
        for _ in range(20):  # app khác có thể đang giữ clipboard, thử lại vài lần
            if self.user32.OpenClipboard(None):
                break
            time.sleep(0.05)
        else:
            return None
        try:
            if self.cf_png and self.user32.IsClipboardFormatAvailable(self.cf_png):
                data = self._read_format(self.cf_png)
                if data and data.startswith(PNG_SIGNATURE):
                    # Windows có thể đệm thêm byte 0 ở cuối: cắt đến hết chunk IEND
                    end = data.rfind(b"IEND")
                    if end != -1:
                        data = data[: end + 8]
                    if not max_bytes or len(data) <= max_bytes:
                        return data
            if self.user32.IsClipboardFormatAvailable(CF_DIB):
                dib = self._read_format(CF_DIB)
                if dib:
                    return dib_to_png(dib, max_bytes)
            return None
        finally:
            self.user32.CloseClipboard()

    # ---------- chữ + sao lưu/khôi phục (dùng khi tự copy chữ bôi đen) ----------

    def _open(self, hwnd=None) -> bool:
        for _ in range(20):  # app khác có thể đang giữ clipboard, thử lại vài lần
            if self.user32.OpenClipboard(hwnd):
                return True
            time.sleep(0.05)
        return False

    def read_text(self) -> str | None:
        """Chữ (Unicode) trong clipboard; None nếu không có chữ hoặc không mở được."""
        if not self._open():
            return None
        try:
            if not self.user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                return None
            data = self._read_format(CF_UNICODETEXT)
            if data is None:
                return None
            return data.decode("utf-16-le", errors="replace").split("\x00", 1)[0]
        finally:
            self.user32.CloseClipboard()

    def snapshot(self, max_bytes: int = 32_000_000) -> list[tuple[int, bytes]] | None:
        """Sao lưu MỌI định dạng của clipboard (để trả lại y nguyên sau khi tự copy).

        Trả về None nếu không sao lưu trọn vẹn được (có ảnh bitmap dạng handle, quá lớn, không mở được...);
        khi đó phía gọi sẽ KHÔNG đụng vào clipboard.
        """
        if not self._open():
            return None
        try:
            items: list[tuple[int, bytes]] = []
            total, fmt = 0, 0
            while True:
                fmt = self.user32.EnumClipboardFormats(fmt)
                if not fmt:
                    break
                if fmt in _NON_HGLOBAL or 0x300 <= fmt <= 0x3FF:
                    return None
                data = self._read_format(fmt)
                if data is None:
                    continue  # định dạng không đọc được (vd. chỉ có trong OLE): bỏ qua
                total += len(data)
                if total > max_bytes:
                    return None
                items.append((fmt, data))
            return items
        finally:
            self.user32.CloseClipboard()

    def restore(self, items: list[tuple[int, bytes]]) -> None:
        """Trả clipboard về đúng như lúc sao lưu (danh sách rỗng = xóa sạch)."""
        ct = self._ct
        # Phải mở clipboard bằng một cửa sổ thật: với NULL thì SetClipboardData sau EmptyClipboard bị từ chối
        hwnd = self.user32.CreateWindowExW(0, "STATIC", None, 0, 0, 0, 0, 0, None, None, None, None)
        try:
            if not self._open(hwnd):
                return
            try:
                self.user32.EmptyClipboard()
                for fmt, data in items:
                    h = self.kernel32.GlobalAlloc(0x0002, max(len(data), 1))  # GMEM_MOVEABLE
                    if not h:
                        continue
                    ptr = self.kernel32.GlobalLock(h)
                    if not ptr:
                        self.kernel32.GlobalFree(h)
                        continue
                    ct.memmove(ptr, data, len(data))
                    self.kernel32.GlobalUnlock(h)
                    if not self.user32.SetClipboardData(fmt, h):
                        self.kernel32.GlobalFree(h)  # không được nhận thì mình phải tự giải phóng
            finally:
                self.user32.CloseClipboard()
        finally:
            if hwnd:
                self.user32.DestroyWindow(hwnd)
