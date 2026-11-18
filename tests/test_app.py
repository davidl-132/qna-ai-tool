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


class ComposeText(unittest.TestCase):
    def entry(self, **kw):
        from desktop.controller import Entry

        e = Entry(created=0, mode="answer")
        for k, v in kw.items():
            setattr(e, k, v)
        return e

    def test_title_and_body_basic(self):
        from desktop.popup import compose

        e = self.entry(text="**B**", status="done", info={"model": "m1"})
        self.assertEqual(compose(e, 1, 3), ("2/3 · m1", "B"))  # dấu ** được bỏ, không kèm câu hỏi/giải thích

    def test_status_and_error_lines(self):
        from desktop.popup import compose

        self.assertEqual(compose(self.entry(status="asking"), 0, 1)[1], "⏳ Đang hỏi AI…")
        self.assertEqual(compose(self.entry(status="error", error="hỏng"), 0, 1)[1], "⚠ hỏng")

    def test_review_marks(self):
        from desktop.popup import compose

        ok = compose(self.entry(text="B", status="done", review="ok"), 0, 1)
        self.assertEqual(ok, ("1/1 · ✔", "B"))  # đã khớp thì không thêm dòng nào, chỉ dấu ✔
        fixed = compose(self.entry(text="B", status="done", review="fixed", fixed_text="**C**"), 0, 1)
        self.assertEqual(fixed, ("1/1 · đã sửa", "B\n↻ Sửa lại: C"))
        self.assertIn("không kiểm tra lại được: hết lượt".lower(),
                      compose(self.entry(text="B", review="failed", review_error="hết lượt"), 0, 1)[1].lower())


@unittest.skipUnless(os.environ.get("DISPLAY") or os.name == "nt", "cần màn hình để thử tkinter")
class PopupWidget(unittest.TestCase):
    def setUp(self):
        try:
            import tkinter as tk

            self.root = tk.Tk()
        except Exception as e:  # noqa: BLE001
            self.skipTest(f"không có tkinter/màn hình: {e}")
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def test_render_show_hide_and_corner_position(self):
        from desktop.controller import Entry
        from desktop.popup import Popup

        p = Popup(self.root)
        self.assertFalse(p.visible)
        p.show()
        self.assertTrue(p.visible)
        e = Entry(created=0, mode="answer", text="**B**", status="asking", info={"model": "m1"})
        p.render(e, 1, 3)
        self.assertEqual(p.title_text, "2/3 · m1")
        self.assertIn("Đang hỏi AI", p.body_text)
        self.assertIn("B", p.body_text)
        p.message("trống")
        self.assertEqual(p.body_text, "trống")
        p.hide()
        self.assertFalse(p.visible)
        p.show()
        self.root.update()
        right, bottom = p.win.winfo_x() + p.win.winfo_width(), p.win.winfo_y() + p.win.winfo_height()
        self.assertLessEqual(right, self.root.winfo_screenwidth())
        self.assertGreaterEqual(right, self.root.winfo_screenwidth() - 2 * p.margin)  # sát mép phải
        self.assertGreaterEqual(bottom, self.root.winfo_screenheight() - 2 * p.margin)  # sát mép dưới

    def test_grows_upward_with_long_text_and_keeps_corner(self):
        from desktop.controller import Entry
        from desktop.popup import Popup

        p = Popup(self.root)
        p.show()
        p.render(Entry(created=0, mode="answer", text="B", status="done"), 0, 1)
        self.root.update()
        h1, bottom1 = p.win.winfo_height(), p.win.winfo_y() + p.win.winfo_height()
        p.render(Entry(created=0, mode="answer", text="\n".join(f"{i}. A" for i in range(1, 9)), status="done"), 0, 1)
        self.root.update()
        self.assertGreater(p.win.winfo_height(), h1)  # nhiều dòng thì khung cao hơn
        self.assertEqual(p.win.winfo_y() + p.win.winfo_height(), bottom1)  # nhưng đáy không dịch chuyển

    def test_very_long_text_is_capped_and_scrollable(self):
        from desktop.controller import Entry
        from desktop.popup import Popup

        p = Popup(self.root, max_height_ratio=0.3)
        p.show()
        p.render(Entry(created=0, mode="answer", text="\n".join(f"dòng {i}" for i in range(200)), status="done"), 0, 1)
        self.root.update()
        self.assertLessEqual(p.win.winfo_height(), int(self.root.winfo_screenheight() * 0.3) + p.head_h + 2)
        self.assertLess(p.body.yview()[1] - p.body.yview()[0], 1.0)  # chỉ thấy một phần, còn lại cuộn

    def test_copy_puts_answer_on_clipboard(self):
        from desktop.controller import Entry
        from desktop.popup import Popup

        p = Popup(self.root)
        e = Entry(created=0, mode="answer", text="**B**", status="done", review="fixed", fixed_text="**C**")
        p.render(e, 0, 1)
        p.copy()
        self.assertEqual(self.root.clipboard_get(), "C")  # có bản sửa thì chép bản sửa
        e.review = "ok"
        p.render(e, 0, 1)
        p.copy()
        self.assertEqual(self.root.clipboard_get(), "B")  # không kèm dòng trạng thái


if __name__ == "__main__":
    unittest.main()
