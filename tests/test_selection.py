"""Test logic thuần của bấm phím đơn, nhận biết bôi đen và lấy chữ bôi đen (không cần Windows)."""
import unittest

from desktop.selection import (SelectionDetector, TapDetector, clean_selection, grab_selection, parse_tap)

LALT, LSHIFT, LCTRL, KEY_A = 0xA4, 0xA0, 0xA2, 0x41


def taps():
    return TapDetector({LALT: "capture", LSHIFT: "popup"})


class ParseTap(unittest.TestCase):
    def test_names(self):
        self.assertEqual(parse_tap("lalt"), LALT)
        self.assertEqual(parse_tap(" LShift "), LSHIFT)
        self.assertIsNone(parse_tap(""))
        with self.assertRaises(ValueError):
            parse_tap("alt")


class TapLogic(unittest.TestCase):
    def test_plain_tap(self):
        d = taps()
        self.assertIsNone(d.key(LALT, True, 0.0))
        self.assertEqual(d.key(LALT, False, 0.1), "capture")

    def test_key_repeat_while_holding_is_ignored_but_slow_hold_is_not_a_tap(self):
        d = taps()
        d.key(LSHIFT, True, 0.0)
        d.key(LSHIFT, True, 0.5)  # lặp phím
        self.assertIsNone(d.key(LSHIFT, False, 0.9))  # giữ quá lâu

    def test_other_key_in_between_cancels(self):
        d = taps()
        d.key(LSHIFT, True, 0.0)
        d.key(KEY_A, True, 0.05)  # Shift+A (viết hoa)
        d.key(KEY_A, False, 0.08)
        self.assertIsNone(d.key(LSHIFT, False, 0.1))

    def test_alt_tab_not_a_tap(self):
        d = taps()
        d.key(LALT, True, 0.0)
        d.key(0x09, True, 0.05)  # Tab
        d.key(0x09, False, 0.08)
        self.assertIsNone(d.key(LALT, False, 0.12))

    def test_alt_shift_layout_switch_is_not_a_tap_for_either(self):
        d = taps()
        d.key(LALT, True, 0.0)
        d.key(LSHIFT, True, 0.05)
        self.assertIsNone(d.key(LSHIFT, False, 0.1))
        self.assertIsNone(d.key(LALT, False, 0.12))

    def test_modifier_already_held_before_tap_key(self):
        d = taps()
        d.key(LCTRL, True, 0.0)  # Ctrl giữ sẵn rồi bấm Alt = Ctrl+Alt
        d.key(LALT, True, 0.05)
        self.assertIsNone(d.key(LALT, False, 0.1))

    def test_mouse_click_while_holding_cancels(self):
        d = taps()
        d.key(LSHIFT, True, 0.0)
        d.mouse()  # Shift+click
        self.assertIsNone(d.key(LSHIFT, False, 0.1))

    def test_two_taps_in_a_row(self):
        d = taps()
        out = []
        for t in (0.0, 1.0):
            d.key(LSHIFT, True, t)
            out.append(d.key(LSHIFT, False, t + 0.1))
        self.assertEqual(out, ["popup", "popup"])

    def test_untracked_key_alone_does_nothing(self):
        d = taps()
        d.key(KEY_A, True, 0.0)
        self.assertIsNone(d.key(KEY_A, False, 0.1))


class SelectionLogic(unittest.TestCase):
    def test_drag_then_settle(self):
        s = SelectionDetector(settle=1.0)
        s.mouse_down(100, 100, 0.0)
        s.mouse_up(300, 100, 0.5)
        self.assertFalse(s.poll(1.4))  # chưa đủ 1 giây
        self.assertTrue(s.poll(1.6))
        self.assertFalse(s.poll(2.0))  # chỉ báo một lần

    def test_plain_click_is_not_a_selection(self):
        s = SelectionDetector()
        s.mouse_down(100, 100, 0.0)
        s.mouse_up(102, 101, 0.1)
        self.assertFalse(s.poll(5.0))

    def test_double_click_selects_a_word(self):
        s = SelectionDetector(settle=1.0)
        for t in (0.0, 0.3):
            s.mouse_down(100, 100, t)
            s.mouse_up(100, 100, t + 0.05)
        self.assertTrue(s.poll(2.0))

    def test_two_slow_clicks_are_not_double(self):
        s = SelectionDetector(settle=1.0)
        for t in (0.0, 2.0):
            s.mouse_down(100, 100, t)
            s.mouse_up(100, 100, t + 0.05)
        self.assertFalse(s.poll(9.0))

    def test_new_click_or_key_cancels_pending(self):
        s = SelectionDetector(settle=1.0)
        s.mouse_down(0, 0, 0.0)
        s.mouse_up(200, 0, 0.1)
        s.mouse_down(500, 500, 0.5)  # bấm chỗ khác trước khi đủ 1 giây
        s.mouse_up(500, 500, 0.55)
        self.assertFalse(s.poll(3.0))
        s.mouse_down(0, 0, 4.0)
        s.mouse_up(200, 0, 4.1)
        s.key()  # gõ phím
        self.assertFalse(s.poll(9.0))

    def test_ignored_gesture_inside_popup(self):
        s = SelectionDetector()
        s.mouse_down(0, 0, 0.0, ignore=True)
        s.mouse_up(300, 0, 0.1)
        self.assertFalse(s.poll(9.0))


class FakeClip:
    def __init__(self, content="cũ", copy_result="chữ bôi đen", snapshot_ok=True, changes=True):
        self.content, self.copy_result, self.snapshot_ok, self.changes = content, copy_result, snapshot_ok, changes
        self.seq = 1
        self.restored = []

    def snapshot(self):
        return ("snap", self.content) if self.snapshot_ok else None

    def sequence(self):
        return self.seq

    def read_text(self):
        return self.content

    def restore(self, snap):
        self.restored.append(snap)
        self.content = snap[1]
        self.seq += 1

    def send_copy(self):
        if self.changes:
            self.content, self.seq = self.copy_result, self.seq + 1


class GrabSelection(unittest.TestCase):
    def test_grabs_text_and_restores_clipboard(self):
        clip = FakeClip()
        text = grab_selection(clip, clip.send_copy, sleep=lambda s: None)
        self.assertEqual(text, "chữ bôi đen")
        self.assertEqual(clip.content, "cũ")  # clipboard trả về như cũ
        self.assertEqual(clip.restored, [("snap", "cũ")])

    def test_nothing_selected_means_no_copy_and_no_restore(self):
        clip = FakeClip(changes=False)
        waited = []
        self.assertIsNone(grab_selection(clip, clip.send_copy, sleep=waited.append, timeout=0.1))
        self.assertEqual(clip.restored, [])
        self.assertTrue(waited)  # có chờ rồi mới bỏ cuộc

    def test_cannot_snapshot_means_do_not_touch_clipboard(self):
        clip = FakeClip(snapshot_ok=False)
        called = []
        self.assertIsNone(grab_selection(clip, lambda: called.append(1), sleep=lambda s: None))
        self.assertEqual(called, [])  # không bơm Ctrl+C khi không sao lưu được

    def test_restore_happens_even_if_read_fails(self):
        clip = FakeClip()

        def boom():
            raise OSError("không đọc được")

        clip.read_text = boom
        with self.assertRaises(OSError):
            grab_selection(clip, clip.send_copy, sleep=lambda s: None)
        self.assertEqual(clip.restored, [("snap", "cũ")])


class CleanSelection(unittest.TestCase):
    def test_rules(self):
        self.assertIsNone(clean_selection(None))
        self.assertIsNone(clean_selection("   \n "))
        self.assertIsNone(clean_selection("a"))
        self.assertEqual(clean_selection("  ephemeral \r\n"), "ephemeral")
        self.assertEqual(len(clean_selection("x" * 9000, limit=4000)), 4000)


if __name__ == "__main__":
    unittest.main()


class StructSizes(unittest.TestCase):
    def test_input_structs_match_win64_layout(self):
        import ctypes
        if ctypes.sizeof(ctypes.c_void_p) != 8:
            self.skipTest("chỉ kiểm tra bố cục 64-bit")
        from desktop import inputhooks as ih
        self.assertEqual(ctypes.sizeof(ih.INPUT), 40)
        self.assertEqual(ctypes.sizeof(ih.KBDLLHOOKSTRUCT), 24)
        self.assertEqual(ctypes.sizeof(ih.MSLLHOOKSTRUCT), 32)


class NavKeysLogic(unittest.TestCase):
    def setUp(self):
        from desktop.selection import NavKeys, VK_LEFT, VK_RIGHT
        self.nav, self.L, self.R = NavKeys(), VK_LEFT, VK_RIGHT

    def test_arrows_switch_entries_and_are_swallowed_while_active(self):
        self.assertEqual(self.nav.key(self.L, True, True, False), ("prev", True))
        self.assertEqual(self.nav.key(self.L, False, True, False), (None, True))  # thả phím cũng bị nuốt
        self.assertEqual(self.nav.key(self.R, True, True, False), ("next", True))
        self.assertEqual(self.nav.key(self.R, False, True, False), (None, True))

    def test_key_repeat_does_not_skip_through_history(self):
        self.assertEqual(self.nav.key(self.L, True, True, False), ("prev", True))
        self.assertEqual(self.nav.key(self.L, True, True, False), (None, True))
        self.assertEqual(self.nav.key(self.L, True, True, False), (None, True))
        self.nav.key(self.L, False, True, False)
        self.assertEqual(self.nav.key(self.L, True, True, False), ("prev", True))

    def test_passthrough_when_popup_hidden_or_modifier_held(self):
        self.assertEqual(self.nav.key(self.L, True, False, False), (None, False))  # khung ẩn: mũi tên chạy bình thường
        self.assertEqual(self.nav.key(self.L, False, False, False), (None, False))
        self.assertEqual(self.nav.key(self.R, True, True, True), (None, False))  # Shift/Ctrl+mũi tên: không đụng
        self.assertEqual(self.nav.key(self.R, False, True, True), (None, False))

    def test_other_keys_ignored(self):
        self.assertEqual(self.nav.key(0x41, True, True, False), (None, False))
