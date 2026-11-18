"""Test vòng tự kiểm tra: phân tích kết luận, stream bản sửa, nối vào controller và hiển thị trong popup."""
import os
import unittest

os.environ.update(PROVIDER="mock", FALLBACK_PROVIDER="", LOCAL_TOKEN="test-token")  # trước khi import core.config

from core import llm, review
from desktop.controller import Controller
from tests.test_app import FakeView, tiny_png


class ParseVerdict(unittest.TestCase):
    def test_variants(self):
        for text, want in [("ĐÚNG", "ok"), ("**ĐÚNG**", "ok"), ("Đúng.", "ok"), ("dung", "ok"), ("CORRECT", "ok"),
                           ("SAI", "fixed"), ("Sai:", "fixed"), ("**SAI**", "fixed"), ("WRONG", "fixed"),
                           ("", None), ("Lời giải: ĐÚNG", None), ("không biết", None)]:
            self.assertEqual(review.parse_verdict(text), want, text)


class BuildReview(unittest.TestCase):
    def test_structure(self):
        system, messages = review.build_review(tiny_png(), "image/png", "câu 3?", "answer", "vi", "Đáp án: B")
        self.assertIn("VAI TRÒ KIỂM TRA", system)
        self.assertEqual([m["role"] for m in messages], ["user", "assistant", "user"])
        self.assertEqual(len(messages[0]["images"]), 1)  # ảnh gốc đi kèm để AI tự giải lại
        self.assertEqual(messages[1]["content"], "Đáp án: B")
        self.assertIn("câu 3?", messages[0]["content"])


def stream(*pieces):
    def ask(system, messages, info):
        yield from pieces
    return ask


def run(*pieces):
    return list(review.run_review(stream(*pieces), tiny_png(), "image/png", "", "answer", "vi", "nháp"))


class RunReview(unittest.TestCase):
    def test_ok_stops_after_verdict(self):
        self.assertEqual(run("ĐÚNG\n", "bla bla không hiện"), [("verdict", "ok")])

    def test_ok_single_line_without_newline(self):
        self.assertEqual(run("ĐÚ", "NG"), [("verdict", "ok")])

    def test_fixed_streams_correction(self):
        out = run("SA", "I\nLỗi ở bước 2.", " Đáp án đúng: **C**")
        self.assertEqual(out[0], ("verdict", "fixed"))
        self.assertEqual("".join(d for k, d in out if k == "fix"), "Lỗi ở bước 2. Đáp án đúng: **C**")

    def test_unknown_when_first_line_is_not_verdict(self):
        self.assertEqual(run("Mình nghĩ là ổn nhé\nvì...")[0], ("verdict", "unknown"))

    def test_empty_stream_is_unknown(self):
        self.assertEqual(run(), [("verdict", "unknown")])


def make(review_pieces, review_on=True, draft=("Đáp án: B",), review_exc=None):
    calls = []

    def ask(system, messages, info):
        is_review = "VAI TRÒ KIỂM TRA" in system
        calls.append("review" if is_review else "draft")
        if is_review:
            if review_exc:
                raise review_exc
            yield from review_pieces
        else:
            info.update(provider="mock", model="m1")
            yield from draft

    view = FakeView()
    ctl = Controller(view, lambda m: tiny_png(), ask_stream=ask, review=review_on,
                     spawn=lambda fn: fn(), sleep=lambda s: None)
    return ctl, view, calls


class ControllerReview(unittest.TestCase):
    def go(self, *a, **kw):
        ctl, view, calls = make(*a, **kw)
        ctl.handle("capture"); ctl.pump()
        return ctl.history[0], view, calls, ctl

    def test_review_confirms(self):
        e, _, calls, ctl = self.go(["ĐÚNG\n"])
        self.assertEqual(calls, ["draft", "review"])
        self.assertEqual((e.status, e.review, e.text, e.fixed_text), ("done", "ok", "Đáp án: B", ""))
        self.assertFalse(ctl.busy)

    def test_review_fixes(self):
        e, *_ = self.go(["SAI\n", "Đúng ra là **C**."])
        self.assertEqual((e.status, e.review), ("done", "fixed"))
        self.assertEqual(e.text, "Đáp án: B")  # nháp vẫn giữ để người dùng đối chiếu
        self.assertEqual(e.fixed_text, "Đúng ra là **C**.")

    def test_review_off_makes_single_call(self):
        e, _, calls, _ = self.go([], review_on=False)
        self.assertEqual(calls, ["draft"])
        self.assertEqual((e.status, e.review), ("done", ""))

    def test_review_failure_keeps_draft(self):
        e, _, calls, ctl = self.go([], review_exc=llm.LLMError("429 hết lượt"))
        self.assertEqual((e.status, e.review, e.text), ("done", "failed", "Đáp án: B"))
        self.assertIn("429", e.review_error)
        self.assertFalse(ctl.busy)

    def test_status_is_reviewing_between_passes(self):
        ctl, view, _ = make(["ĐÚNG\n"])
        ctl.spawn = lambda fn: None  # chưa chạy luồng nền: tự đẩy từng bước
        ctl.handle("capture")
        e = ctl.history[0]
        ctl._events.put(("captured", e, "4×3, 0 KB")); ctl._events.put(("chunk", e, "Đáp án: B"))
        ctl._events.put(("reviewing", e, None)); ctl.pump()
        self.assertEqual((e.status, e.text), ("reviewing", "Đáp án: B"))


@unittest.skipUnless(os.environ.get("DISPLAY") or os.name == "nt", "cần màn hình để thử tkinter")
class PopupReviewRender(unittest.TestCase):
    def test_states(self):
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
            e = Entry(created=0, mode="answer", text="Đáp án: B", status="reviewing")
            p.render(e, 0, 1)
            self.assertIn("Đang kiểm tra lại", p.text.get("1.0", "end"))
            e.status, e.review = "done", "ok"
            p.render(e, 0, 1)
            self.assertIn("đáp án khớp", p.text.get("1.0", "end"))
            self.assertTrue(p.title.cget("text").endswith("✔"))
            e.review, e.fixed_text = "fixed", "Đúng ra là **C**"
            p.render(e, 0, 1)
            body = p.text.get("1.0", "end")
            self.assertIn("Đáp án: B", body)  # vẫn thấy nháp
            self.assertIn("Bản đã sửa", body)
            self.assertIn("Đúng ra là C", body)
            self.assertNotIn("**", body)
            self.assertIn("đã sửa", p.title.cget("text"))
            e.review, e.review_error = "failed", "hết lượt"
            p.render(e, 0, 1)
            self.assertIn("Không kiểm tra lại được: hết lượt", p.text.get("1.0", "end"))
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
