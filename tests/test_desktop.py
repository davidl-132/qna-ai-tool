"""Test phần desktop (chuyển DIB -> PNG, logic theo dõi clipboard). Không cần Windows."""
import struct
import unittest
import zlib
from unittest import mock

from desktop import clipboard, watcher


def make_dib(pixels, bpp=24, top_down=False, bitfields=False):
    """pixels: danh sách dòng (từ trên xuống), mỗi dòng là list (r,g,b)."""
    h, w = len(pixels), len(pixels[0])
    stride = ((w * bpp + 31) // 32) * 4
    rows = []
    for line in pixels:
        data = b"".join(bytes((b, g, r)) + (b"\x00" if bpp == 32 else b"") for r, g, b in line)
        rows.append(data + b"\x00" * (stride - len(data)))
    if not top_down:
        rows.reverse()
    comp = 3 if bitfields else 0
    head = struct.pack("<IiiHHIIiiII", 40, w, -h if top_down else h, 1, bpp, comp, 0, 0, 0, 0, 0)
    if bitfields:
        head += struct.pack("<III", 0x00FF0000, 0x0000FF00, 0x000000FF)
    return head + b"".join(rows)


def decode_png(png):
    """Bộ giải mã PNG tối giản (RGB 8 bit, filter 0) để kiểm tra điểm ảnh."""
    assert png.startswith(clipboard.PNG_SIGNATURE)
    pos, idat, w, h = 8, b"", 0, 0
    while pos < len(png):
        n = struct.unpack(">I", png[pos:pos + 4])[0]
        kind, body = png[pos + 4:pos + 8], png[pos + 8:pos + 8 + n]
        assert struct.unpack(">I", png[pos + 8 + n:pos + 12 + n])[0] == zlib.crc32(kind + body) & 0xFFFFFFFF
        if kind == b"IHDR":
            w, h = struct.unpack(">II", body[:8])
        elif kind == b"IDAT":
            idat += body
        pos += 12 + n
    raw = zlib.decompress(idat)
    stride = w * 3 + 1
    rows = []
    for y in range(h):
        line = raw[y * stride:(y + 1) * stride]
        assert line[0] == 0
        rows.append([tuple(line[1 + x * 3:4 + x * 3]) for x in range(w)])
    return w, h, rows


RED, GREEN, BLUE, WHITE = (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)
GRID = [[RED, GREEN, BLUE], [WHITE, RED, GREEN]]  # 3 rộng x 2 cao


class DibToPng(unittest.TestCase):
    def check(self, dib):
        w, h, rows = decode_png(clipboard.dib_to_png(dib))
        self.assertEqual((w, h), (3, 2))
        self.assertEqual(rows, GRID)

    def test_24bit_bottom_up_with_padding(self):
        self.check(make_dib(GRID, 24))

    def test_24bit_top_down(self):
        self.check(make_dib(GRID, 24, top_down=True))

    def test_32bit(self):
        self.check(make_dib(GRID, 32))

    def test_32bit_bitfields(self):
        self.check(make_dib(GRID, 32, bitfields=True))

    def test_png_size_helper(self):
        self.assertEqual(clipboard.png_size(clipboard.dib_to_png(make_dib(GRID))), (3, 2))

    def test_shrinks_when_too_big(self):
        big = [[((x * 7) % 256, (y * 13) % 256, (x * y) % 256) for x in range(60)] for y in range(40)]
        dib = make_dib(big, 24)
        full = clipboard.dib_to_png(dib)
        small = clipboard.dib_to_png(dib, max_bytes=len(full) // 2)
        self.assertLess(len(small), len(full))
        w, h = clipboard.png_size(small)
        self.assertLess(w, 60)
        self.assertLess(h, 40)
        decode_png(small)  # vẫn là PNG hợp lệ

    def test_bad_input(self):
        with self.assertRaises(ValueError):
            clipboard.dib_to_png(b"abc")
        with self.assertRaises(ValueError):
            clipboard.dib_to_png(make_dib(GRID, 24)[:50])  # bị cụt
        bad = struct.pack("<IiiHHIIiiII", 40, 3, 2, 1, 8, 0, 0, 0, 0, 0, 0) + b"\x00" * 100
        with self.assertRaises(ValueError):
            clipboard.dib_to_png(bad)  # 8 bit chưa hỗ trợ


class FakeClip:
    def __init__(self):
        self.seq, self.image = 1, None
        self.reads = 0

    def sequence(self):
        return self.seq

    def has_image(self):
        return self.image is not None

    def read_png(self, max_bytes=None):
        self.reads += 1
        return self.image

    def copy(self, image):
        self.seq += 1
        self.image = image


class WatcherLogic(unittest.TestCase):
    def setUp(self):
        self.clip, self.got = FakeClip(), []
        self.w = watcher.Watcher(self.clip, self.got.append, settle=0)

    def test_ignores_image_present_at_start(self):
        clip = FakeClip()
        clip.copy(b"old")
        got = []
        w = watcher.Watcher(clip, got.append, settle=0)
        self.assertFalse(w.poll_once())
        self.assertEqual(got, [])

    def test_asks_once_per_new_image(self):
        self.clip.copy(b"img1")
        self.assertTrue(self.w.poll_once())
        self.assertFalse(self.w.poll_once())  # seq không đổi
        self.assertEqual(self.got, [b"img1"])

    def test_same_image_copied_again_is_skipped(self):
        self.clip.copy(b"img1")
        self.w.poll_once()
        self.clip.copy(b"img1")
        self.assertFalse(self.w.poll_once())
        self.assertEqual(len(self.got), 1)

    def test_new_different_image_is_asked(self):
        self.clip.copy(b"img1")
        self.w.poll_once()
        self.clip.copy(b"img2")
        self.assertTrue(self.w.poll_once())
        self.assertEqual(self.got, [b"img1", b"img2"])

    def test_text_copy_is_ignored(self):
        self.clip.seq += 1  # copy chữ: seq đổi nhưng không có ảnh
        self.assertFalse(self.w.poll_once())
        self.assertEqual(self.clip.reads, 0)

    def test_unreadable_clipboard_is_skipped(self):
        self.clip.seq += 1
        self.clip.has_image = lambda: True
        self.clip.read_png = lambda max_bytes=None: None
        self.assertFalse(self.w.poll_once())

    def test_asker_prints_answer_and_survives_errors(self):
        png = clipboard.dib_to_png(make_dib(GRID))
        with mock.patch.object(watcher.llm, "ask_stream", side_effect=watcher.llm.LLMError("hỏng")):
            watcher.make_asker("answer", "", "vi")(png)  # không được ném lỗi ra ngoài

    def test_winclipboard_refuses_non_windows(self):
        import sys

        if sys.platform != "win32":
            with self.assertRaises(RuntimeError):
                clipboard.WinClipboard()


if __name__ == "__main__":
    unittest.main()
