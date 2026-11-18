"""Chụp màn hình Windows, chỉ dùng thư viện có sẵn của Python (ctypes + zlib).

Không cần Pillow/mss vì máy có Application Control thường chặn file DLL/.pyd lạ.
Chụp màn hình chính, rồi đổi sang PNG bằng dib_to_png() (cùng code đọc ảnh clipboard).
"""
import ctypes
import struct
import sys

from .clipboard import dib_to_png


def build_dib(width: int, height: int, pixels: bytes) -> bytes:
    """Ghép header BITMAPINFOHEADER 32 bit (dòng dưới cùng trước) với dữ liệu điểm ảnh BGRA."""
    if len(pixels) != width * height * 4:
        raise ValueError("Dữ liệu ảnh không khớp kích thước")
    header = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 32, 0, len(pixels), 0, 0, 0, 0)
    return header + pixels


def enable_dpi_awareness() -> None:
    """Báo Windows rằng app tự xử lý màn hình phóng to (125%/150%).

    Phải gọi TRƯỚC khi tạo bất kỳ cửa sổ nào. Nếu bật giữa chừng (sau khi khung đã vẽ), Windows đổi cách tính
    tọa độ và khung popup bị lệch vị trí, co nhỏ. Gọi nhiều lần vô hại.
    """
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:  # noqa: BLE001
        pass


def capture_png(max_bytes: int | None = None) -> bytes:
    """Chụp toàn bộ màn hình chính và trả về PNG. Chỉ chạy trên Windows."""
    if sys.platform != "win32":
        raise OSError("Chụp màn hình hiện chỉ chạy trên Windows.")
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.BitBlt.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD,
    ]
    gdi32.BitBlt.restype = wintypes.BOOL
    gdi32.GetDIBits.argtypes = [
        wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
        ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT,
    ]
    gdi32.GetDIBits.restype = ctypes.c_int
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]

    enable_dpi_awareness()  # thường app.py đã gọi từ đầu; gọi lại ở đây để scripts khác cũng chụp đúng độ phân giải
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    if width <= 0 or height <= 0:
        raise OSError("Không đọc được kích thước màn hình.")

    screen_dc = user32.GetDC(None)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    old = gdi32.SelectObject(mem_dc, bitmap)
    try:
        # SRCCOPY | CAPTUREBLT: lấy cả cửa sổ nửa trong suốt
        if not gdi32.BitBlt(mem_dc, 0, 0, width, height, screen_dc, 0, 0, 0x00CC0020 | 0x40000000):
            raise OSError("BitBlt thất bại (không chụp được màn hình).")
        info = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 32, 0, 0, 0, 0, 0, 0)
        info_buf = ctypes.create_string_buffer(info, 40)
        pixels = ctypes.create_string_buffer(width * height * 4)
        if not gdi32.GetDIBits(mem_dc, bitmap, 0, height, pixels, info_buf, 0):
            raise OSError("GetDIBits thất bại (không đọc được ảnh).")
        data = pixels.raw
    finally:
        gdi32.SelectObject(mem_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)
    return dib_to_png(build_dib(width, height, data), max_bytes)
