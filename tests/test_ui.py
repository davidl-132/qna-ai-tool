"""Test giao diện terminal (rich và chữ thường). Không cần Windows."""
import io
import re
import unittest
from contextlib import redirect_stdout
from unittest import mock

from rich.console import Console

from core import llm
from desktop import clipboard, ui, watcher
from tests.test_desktop import GRID, make_dib


def strip(text):
    return re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", text)


def rich_term(height=12):
    buf = io.StringIO()
    con = Console(file=buf, force_terminal=True, width=70, height=height, color_system="standard",
                  legacy_windows=False)
    return ui.RichTerminal(con), buf


class Hints(unittest.TestCase):
    def test_known_errors_have_hints(self):
        self.assertIn("quá tải", ui.hint_for("503 UNAVAILABLE ... high demand"))
        self.assertIn(".env", ui.hint_for("Thiếu GEMINI_API_KEY trong .env"))
        self.assertIn("Groq", ui.hint_for("Groq đang dùng model chữ, không đọc được ảnh"))

    def test_unknown_error_has_no_hint(self):
        self.assertIsNone(ui.hint_for("lỗi lạ chưa gặp"))


class RichOutput(unittest.TestCase):
    def test_answer_is_framed_and_complete(self):
        term, buf = rich_term()
        info = {"provider": "gemini", "model": "gemini-x"}
        text = "**Đáp án: C**\n\n" + "\n".join(f"- ý số {i}" for i in range(30))  # dài hơn màn hình
        out = term.answer(iter([text[i:i + 25] for i in range(0, len(text), 25)]), info)
        self.assertEqual(out, text)
        screen = strip(buf.getvalue())
        self.assertIn("Trả lời", screen)
        self.assertIn("gemini · gemini-x", screen)
        self.assertIn("ý số 29", screen)  # không bị cắt mất phần cuối

    def test_final_panel_contains_whole_answer(self):
        term, buf = rich_term(height=10)
        info = {"provider": "p", "model": "m"}
        text = "\n\n".join(f"đoạn {i}" for i in range(40))
        term.answer(iter([text]), info)
        final = strip(buf.getvalue()).rsplit("Trả lời", 1)[-1]
        self.assertIn("đoạn 0", final)
        self.assertIn("đoạn 39", final)

    def test_empty_stream_prints_no_panel(self):
        term, buf = rich_term()
        self.assertEqual(term.answer(iter([]), {}), "")
        self.assertNotIn("Trả lời", strip(buf.getvalue()))

    def test_error_stops_live_and_propagates(self):
        term, buf = rich_term()

        def gen():
            yield "một phần "
            raise llm.LLMError("đứt giữa chừng")

        with self.assertRaises(llm.LLMError):
            term.answer(gen(), {})
        term.error("503 hết")  # console vẫn dùng bình thường được sau đó
        self.assertIn("Lỗi", strip(buf.getvalue()))

    def test_error_panel_shows_hint(self):
        term, buf = rich_term()
        term.error("503 UNAVAILABLE high demand")
        screen = strip(buf.getvalue())
        self.assertIn("Lỗi", screen)
        self.assertIn("quá tải", screen)

    def test_banner_and_image_header(self):
        term, buf = rich_term()
        term.banner("translate", ["gemini", "groq"], "vi")
        term.image_received(1280, 720, 85)
        screen = strip(buf.getvalue())
        for s in ("Win+Shift+S", "translate", "gemini", "groq", "1280×720", "85 KB"):
            self.assertIn(s, screen)


class PlainOutput(unittest.TestCase):
    def test_plain_answer(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            out = ui.PlainTerminal().answer(iter(["xin ", "chào"]), {"provider": "g", "model": "m"})
        self.assertEqual(out, "xin chào")
        self.assertIn("xin chào", buf.getvalue())
        self.assertIn("g / m", buf.getvalue())

    def test_plain_error_has_hint(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            ui.PlainTerminal().error("429 quota")
        self.assertIn("Hết lượt", buf.getvalue())


class Factory(unittest.TestCase):
    def test_plain_flag(self):
        self.assertIsInstance(ui.make_terminal(plain=True), ui.PlainTerminal)
        self.assertNotIsInstance(ui.make_terminal(plain=True), ui.RichTerminal)

    def test_default_is_rich(self):
        self.assertIsInstance(ui.make_terminal(), ui.RichTerminal)

    def test_falls_back_when_rich_missing(self):
        with mock.patch.object(ui.RichTerminal, "__init__", side_effect=ImportError):
            t = ui.make_terminal()
        self.assertNotIsInstance(t, ui.RichTerminal)


class FakeUI:
    def __init__(self):
        self.calls = []

    def image_received(self, w, h, kb):
        self.calls.append(("image", w, h))

    def answer(self, pieces, info):
        self.calls.append(("answer", "".join(pieces)))

    def error(self, msg):
        self.calls.append(("error", msg))

    def separator(self):
        self.calls.append(("sep",))


class WatcherUsesUI(unittest.TestCase):
    PNG = clipboard.dib_to_png(make_dib(GRID))

    def test_success_flow(self):
        fake = FakeUI()
        with mock.patch.object(watcher.llm, "ask_stream", lambda s, m, i: iter(["ok"])):
            watcher.make_asker("answer", "", "vi", fake)(self.PNG)
        self.assertEqual([c[0] for c in fake.calls], ["image", "answer", "sep"])
        self.assertEqual(fake.calls[1], ("answer", "ok"))

    def test_error_flow(self):
        fake = FakeUI()
        with mock.patch.object(watcher.llm, "ask_stream", side_effect=llm.LLMError("503 hỏng")):
            watcher.make_asker("answer", "", "vi", fake)(self.PNG)
        self.assertIn(("error", "503 hỏng"), fake.calls)

    def test_error_raised_during_stream_is_reported(self):
        fake = FakeUI()

        def bad(s, m, i):
            def g():
                raise llm.LLMError("đứt")
                yield  # noqa

            return g()

        with mock.patch.object(watcher.llm, "ask_stream", bad):
            watcher.make_asker("answer", "", "vi", fake)(self.PNG)
        self.assertIn(("error", "đứt"), fake.calls)


if __name__ == "__main__":
    unittest.main()
