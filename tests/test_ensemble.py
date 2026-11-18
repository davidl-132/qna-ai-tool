import os
import unittest

os.environ.update(PROVIDER="mock", FALLBACK_PROVIDER="", LOCAL_TOKEN="test-token")

from core import ensemble  # noqa: E402
from tests.test_app import make  # noqa: E402


def member(name, *pieces, model=None, fail=None):
    def ask(system, messages, info):
        if fail:
            raise RuntimeError(fail)
        info.update(provider=name, model=model or f"{name}-m")
        yield from pieces
    return name, ask


def judge_factory(*pieces, fail=None, record=None):
    def judge(system, messages, info):
        if record is not None:
            record.append((system, messages))
        if fail:
            raise RuntimeError(fail)
        yield from pieces
    return judge


def collect(members, judge, system="S", messages=None):
    messages = messages or [{"role": "user", "content": "Q", "images": [{"mime": "image/png", "data": b"x"}]}]
    return list(ensemble.run(members, judge, system, messages))


class Normalize(unittest.TestCase):
    def test_markdown_punctuation_case_and_accents_ignored(self):
        self.assertEqual(ensemble.normalize("**B**"), ensemble.normalize("b."))
        self.assertEqual(ensemble.normalize("1. B\n2. D"), ensemble.normalize("1.B  2.D"))
        self.assertEqual(ensemble.normalize("Đúng"), ensemble.normalize("dung"))
        self.assertNotEqual(ensemble.normalize("B"), ensemble.normalize("C"))


class RunEnsemble(unittest.TestCase):
    def test_agreement_skips_judge(self):
        rec = []
        ev = collect([member("a", "**B**"), member("b", "B")], judge_factory("X", record=rec))
        self.assertEqual([k for k, _ in ev], ["meta", "chunk", "verdict"])
        self.assertEqual(ev[1][1], "**B**")  # lấy đáp án của AI đứng đầu
        self.assertEqual(ev[2][1], "ok")
        self.assertEqual(ev[0][1]["model"], "a-m + b-m")
        self.assertEqual(rec, [])  # không tốn lượt trọng tài

    def test_disagreement_goes_to_judge_with_image_and_both_answers(self):
        rec = []
        ev = collect([member("a", "B"), member("b", "C")], judge_factory("Chốt: ", "D", record=rec))
        kinds = [k for k, _ in ev]
        self.assertEqual(kinds, ["meta", "merging", "chunk", "chunk", "verdict"])
        self.assertEqual("".join(d for k, d in ev if k == "chunk"), "Chốt: D")
        self.assertEqual(ev[-1][1], "merged")
        system, msgs = rec[0]
        self.assertIn("TRỌNG TÀI", system)
        self.assertTrue(msgs[0]["images"])  # trọng tài vẫn thấy ảnh gốc
        self.assertIn("[AI 1] B", msgs[0]["content"])
        self.assertIn("[AI 2] C", msgs[0]["content"])

    def test_does_not_mutate_original_messages(self):
        msgs = [{"role": "user", "content": "Q"}]
        collect([member("a", "B"), member("b", "C")], judge_factory("D"), messages=msgs)
        self.assertEqual(msgs[0]["content"], "Q")

    def test_one_member_fails_uses_the_other(self):
        ev = collect([member("a", fail="503"), member("b", "C")], judge_factory("X"))
        self.assertEqual([k for k, _ in ev], ["meta", "chunk", "verdict"])
        self.assertEqual((ev[1][1], ev[2][1]), ("C", "solo"))
        self.assertEqual(ev[0][1]["model"], "b-m")

    def test_all_fail_raises_with_each_reason(self):
        with self.assertRaises(RuntimeError) as cm:
            collect([member("a", fail="503"), member("b", fail="hết quota")], judge_factory("X"))
        self.assertIn("a: 503", str(cm.exception))
        self.assertIn("b: hết quota", str(cm.exception))

    def test_judge_failure_falls_back_to_first_answer(self):
        ev = collect([member("a", "B"), member("b", "C")], judge_factory(fail="boom"))
        self.assertEqual([k for k, _ in ev][-2:], ["chunk", "verdict"])
        self.assertEqual((ev[-2][1], ev[-1][1]), ("B", "solo"))

    def test_runs_members_in_parallel(self):
        import threading
        barrier = threading.Barrier(2, timeout=3)

        def slow(name):
            def ask(system, messages, info):
                barrier.wait()  # chỉ qua được nếu cả hai AI cùng đang chạy
                info.update(model=name)
                yield "B"
            return name, ask

        ev = collect([slow("a"), slow("b")], judge_factory("X"))
        self.assertEqual(ev[-1][1], "ok")


class ControllerEnsemble(unittest.TestCase):
    def _ctl(self, members, **kw):
        ctl, view, seen = make(answers=("single",), members=members, **kw)
        return ctl, view, seen

    def test_capture_uses_ensemble_instead_of_review(self):
        ctl, view, seen = self._ctl([member("a", "B"), member("b", "B")], review=True)
        ctl.handle("capture"); ctl.pump()
        e = ctl.history[0]
        self.assertEqual((e.text, e.review, e.status), ("B", "ok", "done"))
        self.assertEqual(e.info["model"], "a-m + b-m")
        self.assertEqual(seen["calls"], 0)  # judge (ask_stream) không bị gọi, cũng không chạy vòng tự kiểm tra
        self.assertFalse(ctl.busy)

    def test_disagreement_streams_judge_answer_and_marks_merged(self):
        ctl, view, seen = self._ctl([member("a", "B"), member("b", "C")], auto_show=True)
        ctl.handle("capture"); ctl.pump()
        e = ctl.history[0]
        self.assertEqual((e.text, e.review, e.status), ("single", "merged", "done"))  # "single" = đáp án của judge giả
        self.assertEqual(seen["calls"], 1)

    def test_text_lookup_can_stay_single(self):
        ctl, view, seen = self._ctl([member("a", "x"), member("b", "y")], ensemble_text=False)
        ctl.start_text("hello"); ctl.pump()
        self.assertEqual(ctl.history[0].text, "single")
        self.assertEqual(seen["calls"], 1)

    def test_text_lookup_uses_ensemble_by_default(self):
        ctl, view, seen = self._ctl([member("a", "nghĩa"), member("b", "Nghĩa")])
        ctl.start_text("hello"); ctl.pump()
        self.assertEqual((ctl.history[0].text, ctl.history[0].review), ("nghĩa", "ok"))

    def test_error_when_all_members_fail(self):
        ctl, view, _ = self._ctl([member("a", fail="x"), member("b", fail="y")])
        ctl.handle("capture"); ctl.pump()
        self.assertEqual(ctl.history[0].status, "error")
        self.assertIn("Tất cả AI đều lỗi", ctl.history[0].error)
        self.assertFalse(ctl.busy)

    def test_single_member_means_no_ensemble(self):
        ctl, view, seen = self._ctl([member("a", "B")])
        ctl.handle("capture"); ctl.pump()
        self.assertEqual(ctl.history[0].text, "single")  # đường cũ: một AI qua ask_stream


class TitleAndLlm(unittest.TestCase):
    def test_title_markers(self):
        from desktop.controller import Entry
        from desktop.popup import compose
        for review, marker in (("ok", "✔"), ("merged", "tổng hợp"), ("solo", "1 AI")):
            e = Entry(created=0, mode="answer", text="B", status="done", review=review, info={"model": "m"})
            self.assertIn(marker, compose(e, 0, 1)[0])
        e = Entry(created=0, mode="answer", text="", status="merging")
        self.assertIn("tổng hợp", compose(e, 0, 1)[1])

    def test_ask_stream_one_has_no_fallback_and_reports_model(self):
        from unittest import mock
        from core import llm
        info = {}
        fake = lambda s, m, used: (used.update(model="zz") or iter(["a", "b"]))  # noqa: E731
        with mock.patch.dict(llm.PROVIDERS, {"fake": fake}):
            self.assertEqual("".join(llm.ask_stream_one("fake", "s", [], info)), "ab")
        self.assertEqual(info, {"provider": "fake", "model": "zz"})
        with self.assertRaises(llm.LLMError):
            list(llm.ask_stream_one("nope", "s", []))

    def test_provider_ready(self):
        from unittest import mock
        from core import config, llm
        with mock.patch.object(config, "CKEY_API_KEY", ""), mock.patch.object(config, "GEMINI_API_KEY", "k"):
            self.assertTrue(llm.provider_ready("gemini"))
            self.assertFalse(llm.provider_ready("ckey"))
            self.assertFalse(llm.provider_ready("unknown"))


if __name__ == "__main__":
    unittest.main()
