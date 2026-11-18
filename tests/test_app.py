"""Test app popup: phím tắt, bộ điều khiển (lịch sử, ẩn/hiện, chụp), ghép ảnh chụp, và khung tkinter nếu có màn hình."""
import os
import struct
import unittest

os.environ.update(PROVIDER="mock", FALLBACK_PROVIDER="", LOCAL_TOKEN="test-token")  # trước khi import core.config

from core import llm
from desktop.clipboard import PNG_SIGNATURE
from desktop.controller import Controller
from unittest import mock

from desktop import hotkeys
from desktop.hotkeys import is_bare_typing_key, parse_hotkey
from desktop.screen import build_dib


class FakeView:
    def __init__(self) -> None:
        self.visible = False
        self.log: list[str] = []
        self.rendered = None
        self.msg = ""

    def show(self):
        self.visible = True
        self.log.append("show")

    def hide(self):
        self.visible = False
        self.log.append("hide")

    def render(self, entry, index, total):
        self.rendered = (entry.text, entry.status, index, total)

    def message(self, text):
        self.msg = text


def tiny_png() -> bytes:
    # PNG hợp lệ tối thiểu chỉ cần header IHDR để png_size đọc được kích thước
    return PNG_SIGNATURE + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 4, 3) + b"\x08\x02\x00\x00\x00" + b"\0" * 4


def make(view=None, answers=("Đáp án A",), capture=None, **kw):
    view = view or FakeView()
    seen = {"calls": 0}

    def ask(system, messages, info):
        seen["calls"] += 1
        info.update(provider="mock", model="m1")
        yield from answers

    ctl = Controller(view, capture or (lambda max_bytes: tiny_png()), ask_stream=ask,
                     spawn=lambda fn: fn(), sleep=lambda s: None, **kw)
    return ctl, view, seen


class HotkeyParse(unittest.TestCase):
    def test_ctrl_alt_digit(self):
        self.assertEqual(parse_hotkey("ctrl+alt+1"), (0x2 | 0x1, ord("1")))

    def test_case_and_spaces(self):
        self.assertEqual(parse_hotkey(" Ctrl + SHIFT + a "), (0x2 | 0x4, ord("A")))

    def test_function_key(self):
        self.assertEqual(parse_hotkey("win+f9"), (0x8, 0x70 + 8))

    def test_bare_key_allowed_but_flagged(self):
        self.assertEqual(parse_hotkey("1"), (0, ord("1")))
        self.assertTrue(is_bare_typing_key("1"))
        self.assertFalse(is_bare_typing_key("ctrl+alt+1"))
        self.assertFalse(is_bare_typing_key("f9"))
        self.assertFalse(is_bare_typing_key("num1"))

    def test_numpad_keys(self):
        self.assertEqual(parse_hotkey("num1"), (0, 0x61))
        self.assertEqual(parse_hotkey("ctrl+num0"), (0x2, 0x60))

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            parse_hotkey("")

    def test_bad_modifier_and_key(self):
        for spec in ("super+1", "ctrl+alt+", "ctrl+@", "ctrl+f99", "num10"):
            with self.assertRaises(ValueError, msg=spec):
                parse_hotkey(spec)


class FakeUser32:
    """Giả lập user32: ghi lại RegisterHotKey/UnregisterHotKey và phát lại các phím được bấm."""

    def __init__(self, presses, taken=()):
        self.presses = list(presses)  # danh sách id phím "được bấm"
        self.taken = set(taken)  # mã phím đã có app khác chiếm
        self.registered: dict[int, int] = {}
        self.log: list[tuple] = []

    def RegisterHotKey(self, hwnd, i, mods, vk):
        if vk in self.taken:
            return 0
        self.registered[i] = vk
        self.log.append(("reg", i))
        return 1

    def UnregisterHotKey(self, hwnd, i):
        self.registered.pop(i, None)
        self.log.append(("unreg", i))
        return 1

    def GetMessageW(self, msg, *a):
        if not self.presses:
            return 0
        msg.message, msg.wParam = hotkeys.WM_HOTKEY, self.presses.pop(0)
        return 1


class ListenerLogic(unittest.TestCase):
    def run_listener(self, presses, toggle="ctrl+alt+0", taken=()):
        got = []
        fake = FakeUser32(presses, taken)
        lis = hotkeys.HotkeyListener({"show": "1", "hide": "2", "capture": "3"}, got.append, toggle=toggle)

        class FakeKernel:
            def GetCurrentThreadId(self):
                return 7

        with mock.patch.object(hotkeys.sys, "platform", "win32"), \
                mock.patch("ctypes.WinDLL", lambda name, **kw: fake if name == "user32" else FakeKernel(), create=True), \
                mock.patch("ctypes.byref", lambda x: x):
            lis.run()
        return got, fake, lis

    def test_keys_dispatch_by_name(self):
        got, fake, _ = self.run_listener([1, 2, 3, 3])
        self.assertEqual(got, ["show", "hide", "capture", "capture"])

    def test_toggle_off_releases_keys_and_ignores_them(self):
        # bấm toggle (tắt) -> các phím 1/2/3 bị nhả; bấm 3 lúc tắt (nếu lọt qua) thì bị bỏ qua; toggle lần nữa (bật)
        got, fake, lis = self.run_listener([3, 1000, 3, 1000, 2])
        self.assertEqual(got, ["capture", "off", "on", "hide"])
        self.assertTrue(lis.enabled)
        # lúc tắt: đã nhả đúng 3 phím rồi đăng ký lại
        self.assertEqual([e for e in fake.log if e[0] == "unreg"][:3], [("unreg", 1), ("unreg", 2), ("unreg", 3)])

    def test_toggle_off_keeps_toggle_key_registered(self):
        _, fake, _ = self.run_listener([1000])
        self.assertNotIn(("unreg", 1000), fake.log[:-1])  # chỉ bị nhả khi thoát (cuối vòng lặp)
        self.assertIn(("unreg", 1000), fake.log)

    def test_no_toggle_means_no_toggle_events(self):
        got, _, _ = self.run_listener([1000, 1], toggle="")
        self.assertEqual(got, ["show"])

    def test_taken_key_reported(self):
        _, _, lis = self.run_listener([], taken={ord("2")})
        self.assertEqual(len(lis.errors), 1)
        self.assertIn("2", lis.errors[0])


class BuildDib(unittest.TestCase):
    def test_header_and_size_check(self):
        dib = build_dib(2, 1, b"\x00" * 8)
        self.assertEqual(struct.unpack("<IiiHH", dib[:16]), (40, 2, 1, 1, 32))
        with self.assertRaises(ValueError):
            build_dib(2, 2, b"\x00" * 8)


class ControllerFlow(unittest.TestCase):
    def test_show_with_empty_history_gives_hint(self):
        ctl, view, _ = make()
        ctl.handle("show")
        self.assertTrue(view.visible)
        self.assertIn("Ctrl+Alt+3", view.msg)

    def test_capture_streams_answer_but_stays_hidden_by_default(self):
        ctl, view, seen = make(answers=("Đáp ", "án B"))
        ctl.handle("capture")
        ctl.pump()
        self.assertEqual(seen["calls"], 1)
        self.assertFalse(view.visible)
        self.assertEqual(ctl.history[0].text, "Đáp án B")
        self.assertEqual(ctl.history[0].status, "done")
        self.assertEqual(ctl.history[0].size, "4×3, 0 KB")
        self.assertFalse(ctl.busy)
        ctl.handle("show")
        self.assertEqual(view.rendered, ("Đáp án B", "done", 0, 1))

    def test_auto_show_pops_up_after_capture(self):
        ctl, view, _ = make(auto_show=True)
        ctl.handle("capture")
        ctl.pump()
        self.assertTrue(view.visible)
        self.assertEqual(view.rendered[0], "Đáp án A")

    def test_hide_keeps_history(self):
        ctl, view, _ = make()
        ctl.handle("capture"); ctl.pump()
        ctl.handle("show"); ctl.handle("hide")
        self.assertFalse(view.visible)
        self.assertEqual(len(ctl.history), 1)
        ctl.handle("show")
        self.assertEqual(view.rendered[0], "Đáp án A")

    def test_popup_hidden_before_capture_and_restored_after(self):
        order = []
        view = FakeView()

        def capture(max_bytes):
            order.append(("capture", view.visible))  # lúc chụp khung phải đang ẩn
            return tiny_png()

        ctl, view, _ = make(view=view, capture=capture)
        ctl.handle("capture"); ctl.pump()
        ctl.handle("show")
        ctl.handle("capture"); ctl.pump()
        self.assertEqual(order, [("capture", False), ("capture", False)])
        self.assertTrue(view.visible)  # khung đang mở lúc bấm chụp thì được mở lại
        self.assertEqual(len(ctl.history), 2)
        self.assertEqual(view.rendered[2:], (1, 2))

    def test_second_capture_ignored_while_busy(self):
        started = []
        ctl, view, seen = make()
        ctl.spawn = started.append  # không chạy ngay: giả lập đang bận
        ctl.handle("capture"); ctl.handle("capture")
        self.assertEqual(len(started), 1)
        self.assertEqual(len(ctl.history), 1)

    def test_capture_error_is_shown_and_unlocks(self):
        def boom(max_bytes):
            raise OSError("BitBlt thất bại")

        ctl, view, _ = make(capture=boom, auto_show=True)
        ctl.handle("capture"); ctl.pump()
        self.assertEqual(ctl.history[0].status, "error")
        self.assertIn("BitBlt", ctl.history[0].error)
        self.assertFalse(ctl.busy)
        self.assertTrue(view.visible)

    def test_llm_error_reshows_popup_that_was_open(self):
        def ask(system, messages, info):
            raise llm.LLMError("Tất cả nhà cung cấp đều lỗi")
            yield  # pragma: no cover

        view = FakeView()
        ctl = Controller(view, lambda m: tiny_png(), ask_stream=ask, spawn=lambda fn: fn(), sleep=lambda s: None)
        ctl.handle("show")
        ctl.handle("capture"); ctl.pump()
        self.assertTrue(view.visible)
        self.assertEqual(view.rendered[1], "error")

    def test_prev_next_navigation(self):
        ctl, view, _ = make(answers=("x",))
        for _ in range(3):
            ctl.handle("capture"); ctl.pump()
        ctl.handle("show")
        self.assertEqual(view.rendered[2:], (2, 3))
        ctl.prev(); ctl.prev(); ctl.prev()  # không vượt quá đầu danh sách
        self.assertEqual(view.rendered[2:], (0, 3))
        ctl.next()
        self.assertEqual(view.rendered[2:], (1, 3))
        ctl.next(); ctl.next()
        self.assertEqual(view.rendered[2:], (2, 3))

    def test_new_answer_does_not_yank_user_viewing_old_entry(self):
        ctl, view, _ = make(answers=("x",))
        ctl.handle("capture"); ctl.pump()
        ctl.handle("show")
        ctl.handle("capture")  # entry 2 đang chạy; người dùng quay lại entry 1
        ctl.prev()
        ctl.pump()
        self.assertEqual(view.rendered[2], 0)


@unittest.skipUnless(os.environ.get("DISPLAY") or os.name == "nt", "cần màn hình để thử tkinter")
class PopupWidget(unittest.TestCase):
    def test_render_show_hide(self):
        try:
            import tkinter as tk
            from desktop.popup import Popup

            root = tk.Tk()
        except Exception as e:  # noqa: BLE001
            self.skipTest(f"không có tkinter/màn hình: {e}")
        root.withdraw()
        try:
            from desktop.controller import Entry

            p = Popup(root)
            self.assertFalse(p.visible)
            p.show(); self.assertTrue(p.visible)
            e = Entry(created=0, mode="answer", text="Xin chào\nđáp án", status="asking", size="4×3, 1 KB")
            e.info["model"] = "m1"
            p.render(e, 1, 3)
            body = p.text.get("1.0", "end")
            self.assertIn("đáp án", body)
            e.text = "**Đậm** thường"
            p.render(e, 1, 3)
            self.assertNotIn("**", p.text.get("1.0", "end"))
            self.assertIn("bold", p.text.tag_names("2.0"))
            self.assertIn("Đang hỏi AI", body)
            self.assertIn("2/3 · m1", p.title.cget("text"))
            e.status, e.error = "error", "hỏng"
            p.render(e, 0, 1)
            self.assertIn("⚠ hỏng", p.text.get("1.0", "end"))
            p.message("trống")
            self.assertIn("trống", p.text.get("1.0", "end"))
            p.hide(); self.assertFalse(p.visible)
            # khung nằm trong màn hình, ở góc dưới phải
            p.show(); root.update()
            self.assertGreaterEqual(p.win.winfo_x(), root.winfo_screenwidth() // 2)
            self.assertGreaterEqual(p.win.winfo_y(), root.winfo_screenheight() // 2)
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
