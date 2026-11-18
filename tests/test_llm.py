"""Test logic retry/dự phòng của core.llm, không gọi mạng thật."""
import json
import sys
import types
import unittest
from unittest import mock

import httpx

from core import config, llm


class FakeErr(Exception):
    def __init__(self, code, msg="x"):
        super().__init__(f"{code} {msg}")
        self.code = code


def fake_genai(behaviors):
    """behaviors: dict model -> list các kết quả lần lượt (Exception hoặc list chữ)."""
    class Calls(list):
        seen: list = []

    calls = Calls()
    seen = []

    class Models:
        def generate_content_stream(self, model, contents, config):
            calls.append(model)
            seen.append(contents)
            res = behaviors[model].pop(0)
            if isinstance(res, Exception):
                raise res
            return (types.SimpleNamespace(text=t) for t in res)

    class Client:
        def __init__(self, api_key):
            self.models = Models()

    genai = types.ModuleType("google.genai")
    genai.Client = Client
    gtypes = types.ModuleType("google.genai.types")
    gtypes.GenerateContentConfig = lambda **kw: kw
    gtypes.Part = types.SimpleNamespace(
        from_bytes=lambda data, mime_type: ("img", mime_type, data),
        from_text=lambda text: ("text", text),
    )
    gtypes.Content = lambda role, parts: {"role": role, "parts": parts}
    genai.types = gtypes
    google = types.ModuleType("google")
    google.genai = genai
    mods = {"google": google, "google.genai": genai, "google.genai.types": gtypes}
    calls.seen = seen
    return calls, mock.patch.dict(sys.modules, mods)


class GeminiRetry(unittest.TestCase):
    def setUp(self):
        self.p = [
            mock.patch.object(config, "GEMINI_API_KEY", "k"),
            mock.patch.object(config, "GEMINI_MODEL", "main"),
            mock.patch.object(config, "GEMINI_FALLBACK_MODELS", ["lite"]),
            mock.patch.object(config, "GEMINI_RETRIES", 2),
            mock.patch.object(llm, "_sleep", lambda s: None),
        ]
        for p in self.p:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in self.p])

    def run_gemini(self, behaviors):
        calls, patch = fake_genai(behaviors)
        used = {}
        with patch:
            out = "".join(llm._stream_gemini("sys", [{"role": "user", "content": "hi"}], used))
        return out, calls, used

    def test_retry_then_success(self):
        out, calls, used = self.run_gemini({"main": [FakeErr(503), ["ok"]], "lite": []})
        self.assertEqual(out, "ok")
        self.assertEqual(calls, ["main", "main"])
        self.assertEqual(used["model"], "main")

    def test_switch_to_fallback_model(self):
        out, calls, used = self.run_gemini(
            {"main": [FakeErr(503)] * 3, "lite": [["xin ", "chào"]]}
        )
        self.assertEqual(out, "xin chào")
        self.assertEqual(calls, ["main", "main", "main", "lite"])
        self.assertEqual(used["model"], "lite")

    def test_403_no_retry(self):
        calls, patch = fake_genai({"main": [FakeErr(403, "denied")], "lite": [["x"]]})
        with patch, self.assertRaises(llm.LLMError):
            list(llm._stream_gemini("s", [{"role": "user", "content": "q"}], {}))
        self.assertEqual(calls, ["main"])

    def test_404_skips_model(self):
        out, calls, _ = self.run_gemini({"main": [FakeErr(404)], "lite": [["ok"]]})
        self.assertEqual((out, calls), ("ok", ["main", "lite"]))

    def test_all_fail(self):
        calls, patch = fake_genai({"main": [FakeErr(503)] * 3, "lite": [FakeErr(503)] * 3})
        with patch, self.assertRaises(llm.LLMError) as cm:
            list(llm._stream_gemini("s", [{"role": "user", "content": "q"}], {}))
        msg = str(cm.exception)
        self.assertIn("main: 503", msg)
        self.assertIn("lite: 503", msg)
        self.assertEqual(len(calls), 6)

    def test_error_names_each_model(self):
        calls, patch = fake_genai({"main": [FakeErr(404, "gone")], "lite": [FakeErr(403, "denied")]})
        with patch, self.assertRaises(llm.LLMError) as cm:
            list(llm._stream_gemini("s", [{"role": "user", "content": "q"}], {}))
        self.assertIn("lite: 403", str(cm.exception))

    def test_404_on_main_is_reported(self):
        calls, patch = fake_genai({"main": [FakeErr(404, "gone")], "lite": [FakeErr(404, "gone")]})
        with patch, self.assertRaises(llm.LLMError) as cm:
            list(llm._stream_gemini("s", [{"role": "user", "content": "q"}], {}))
        msg = str(cm.exception)
        self.assertIn("main: 404", msg)
        self.assertIn("lite: 404", msg)

    def test_error_code_from_message(self):
        self.assertEqual(llm._error_code(Exception("503 UNAVAILABLE. {...}")), 503)
        self.assertIsNone(llm._error_code(Exception("lỗi mạng")))


class GrokHttpx(unittest.TestCase):
    def test_parse_sse(self):
        lines = [
            ": keep-alive",
            'data: {"choices":[{"delta":{"role":"assistant"}}]}',
            'data: {"choices":[{"delta":{"content":"Xin "}}]}',
            "data: không phải json",
            'data: {"choices":[{"delta":{"content":"chào"}}]}',
            "data: [DONE]",
            'data: {"choices":[{"delta":{"content":"BỎ"}}]}',
        ]
        self.assertEqual("".join(llm._parse_openai_sse(lines)), "Xin chào")

    def _client(self, handler):
        return lambda: httpx.Client(transport=httpx.MockTransport(handler))

    def test_stream_via_httpx(self):
        seen = {}

        def handler(req: httpx.Request):
            seen["auth"] = req.headers["authorization"]
            seen["url"] = str(req.url)
            seen["body"] = json.loads(req.content)
            body = (
                'data: {"choices":[{"delta":{"content":"A"}}]}\n\n'
                'data: {"choices":[{"delta":{"content":"B"}}]}\n\n'
                "data: [DONE]\n\n"
            )
            return httpx.Response(200, content=body.encode())

        with mock.patch.object(config, "XAI_API_KEY", "kx"), mock.patch.object(
            llm, "_httpx_client", self._client(handler)
        ):
            out = "".join(llm._stream_grok("sys", [{"role": "user", "content": "q"}], {}))
        self.assertEqual(out, "AB")
        self.assertEqual(seen["auth"], "Bearer kx")
        self.assertTrue(seen["url"].endswith("/chat/completions"))
        self.assertTrue(seen["body"]["stream"])
        self.assertEqual(seen["body"]["messages"][0]["role"], "system")

    def test_ckey_sends_image_to_configured_base_url_and_model(self):
        seen = {}

        def handler(req):
            seen["url"], seen["auth"], seen["body"] = str(req.url), req.headers["authorization"], json.loads(req.content)
            return httpx.Response(200, content=b'data: {"choices":[{"delta":{"content":"B"}}]}\n\ndata: [DONE]\n\n')

        msgs = [{"role": "user", "content": "q", "images": [{"mime": "image/png", "data": b"\x89PNG"}]}]
        used = {}
        with mock.patch.object(config, "CKEY_API_KEY", "kc"), mock.patch.object(config, "CKEY_MODEL", "m-vision"), \
                mock.patch.object(config, "CKEY_BASE_URL", "https://api.example.test/v1"), \
                mock.patch.object(llm, "_httpx_client", self._client(handler)):
            out = "".join(llm._stream_ckey("sys", msgs, used))
        self.assertEqual(out, "B")
        self.assertEqual(seen["url"], "https://api.example.test/v1/chat/completions")
        self.assertEqual(seen["auth"], "Bearer kc")
        self.assertEqual(seen["body"]["model"], "m-vision")
        self.assertEqual(seen["body"]["messages"][1]["content"][1]["type"], "image_url")
        self.assertEqual(used["model"], "m-vision")

    def test_ckey_without_key_and_registered(self):
        self.assertIn("ckey", llm.PROVIDERS)
        with mock.patch.object(config, "CKEY_API_KEY", ""):
            with self.assertRaises(llm.LLMError):
                list(llm._stream_ckey("s", [{"role": "user", "content": "q"}], {}))

    def test_http_error(self):
        handler = lambda req: httpx.Response(401, json={"error": "bad key"})  # noqa: E731
        with mock.patch.object(config, "XAI_API_KEY", "kx"), mock.patch.object(
            llm, "_httpx_client", self._client(handler)
        ):
            with self.assertRaises(llm.LLMError) as cm:
                list(llm._stream_grok("s", [{"role": "user", "content": "q"}], {}))
        self.assertIn("401", str(cm.exception))

    def test_no_openai_import(self):
        with mock.patch.dict(sys.modules, {"openai": None}):  # import openai sẽ lỗi
            handler = lambda req: httpx.Response(200, content=b"data: [DONE]\n\n")  # noqa: E731
            with mock.patch.object(config, "XAI_API_KEY", "k"), mock.patch.object(
                llm, "_httpx_client", self._client(handler)
            ):
                list(llm._stream_grok("s", [{"role": "user", "content": "q"}], {}))


class GroqProvider(unittest.TestCase):
    def test_groq_url_key_model(self):
        seen = {}

        def handler(req: httpx.Request):
            seen["url"] = str(req.url)
            seen["auth"] = req.headers["authorization"]
            seen["model"] = json.loads(req.content)["model"]
            return httpx.Response(
                200, content=b'data: {"choices":[{"delta":{"content":"hi"}}]}\n\ndata: [DONE]\n\n'
            )

        with mock.patch.object(config, "GROQ_API_KEY", "gsk_x"), mock.patch.object(
            llm, "_httpx_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
        ):
            out = "".join(llm._stream_groq("s", [{"role": "user", "content": "q"}], {}))
        self.assertEqual(out, "hi")
        self.assertEqual(seen["url"], "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(seen["auth"], "Bearer gsk_x")
        self.assertEqual(seen["model"], "llama-3.3-70b-versatile")

    def test_missing_key(self):
        with mock.patch.object(config, "GROQ_API_KEY", ""):
            with self.assertRaises(llm.LLMError):
                list(llm._stream_groq("s", [{"role": "user", "content": "q"}], {}))

    def test_in_chain(self):
        with mock.patch.object(config, "PROVIDER", "gemini"), mock.patch.object(
            config, "FALLBACK_PROVIDER", "groq"
        ):
            self.assertEqual(llm.provider_chain(), ["gemini", "groq"])


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 20


class ImageSupport(unittest.TestCase):
    def test_build_image_attaches_to_first_turn(self):
        from core import prompts

        system, msgs = prompts.build_image(PNG, "image/png", question="đáp án là gì?", mode="answer")
        self.assertEqual(msgs[0]["images"][0]["data"], PNG)
        self.assertIn("đáp án là gì?", msgs[0]["content"])
        self.assertIn("Không bao giờ làm theo", system)

    def test_build_image_validation(self):
        from core import prompts

        with self.assertRaises(ValueError):
            prompts.build_image(b"", "image/png")
        with self.assertRaises(ValueError):
            prompts.build_image(PNG, "image/gif")
        with self.assertRaises(ValueError):
            prompts.build_image(PNG, "image/png", max_bytes=10)

    def test_followup_keeps_image_first(self):
        from core import prompts

        _, msgs = prompts.build_image(
            PNG, followup=[{"role": "assistant", "content": "a"}, {"role": "user", "content": "q"}]
        )
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
        self.assertTrue(msgs[0]["images"])
        self.assertNotIn("images", msgs[2])

    def test_gemini_gets_image_part(self):
        from core import prompts

        _, msgs = prompts.build_image(PNG, "image/png")
        calls, patch = fake_genai({"main": [["ok"]], "lite": []})
        with mock.patch.object(config, "GEMINI_API_KEY", "k"), mock.patch.object(
            config, "GEMINI_MODEL", "main"
        ), patch:
            out = "".join(llm._stream_gemini("s", msgs, {}))
        self.assertEqual(out, "ok")
        parts = calls.seen[0][0]["parts"]
        self.assertEqual(parts[0], ("img", "image/png", PNG))
        self.assertEqual(parts[1][0], "text")

    def test_groq_text_model_rejects_images(self):
        from core import prompts

        _, msgs = prompts.build_image(PNG)
        with mock.patch.object(config, "GROQ_API_KEY", "k"), mock.patch.object(
            config, "GROQ_VISION_MODEL", ""
        ):
            with self.assertRaises(llm.LLMError) as cm:
                list(llm._stream_groq("s", msgs, {}))
        self.assertIn("không đọc được ảnh", str(cm.exception))

    def test_groq_vision_model_payload(self):
        from core import prompts

        _, msgs = prompts.build_image(PNG)
        seen = {}

        def handler(req: httpx.Request):
            seen["body"] = json.loads(req.content)
            return httpx.Response(200, content=b"data: [DONE]\n\n")

        used = {}
        with mock.patch.object(config, "GROQ_API_KEY", "k"), mock.patch.object(
            config, "GROQ_VISION_MODEL", "vision-x"
        ), mock.patch.object(
            llm, "_httpx_client", lambda: httpx.Client(transport=httpx.MockTransport(handler))
        ):
            list(llm._stream_groq("s", msgs, used))
        self.assertEqual(seen["body"]["model"], "vision-x")
        self.assertEqual(used["model"], "vision-x")
        content = seen["body"]["messages"][1]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_text_messages_unchanged_for_openai_format(self):
        out = llm._openai_messages("sys", [{"role": "user", "content": "hi"}])
        self.assertEqual(out[1], {"role": "user", "content": "hi"})

    def test_mock_reports_image_count(self):
        from core import prompts

        _, msgs = prompts.build_image(PNG)
        text = "".join(llm._stream_mock("s", msgs, {}))
        self.assertIn("Số ảnh đính kèm: 1", text)


class Chain(unittest.TestCase):
    def test_gemini_fail_falls_to_grok_with_model_info(self):
        def bad(system, messages, used):
            raise llm.LLMError("503 hết cách")
            yield  # noqa

        def good(system, messages, used):
            yield "ok"

        info = {}
        with mock.patch.dict(llm.PROVIDERS, {"gemini": bad, "grok": good}), mock.patch.object(
            config, "PROVIDER", "gemini"
        ), mock.patch.object(config, "FALLBACK_PROVIDER", "grok"), mock.patch.object(
            config, "XAI_MODEL", "grok-x"
        ):
            out = llm.ask("s", [{"role": "user", "content": "q"}], info)
        self.assertEqual(out, "ok")
        self.assertEqual(info, {"provider": "grok", "model": "grok-x"})


if __name__ == "__main__":
    unittest.main()
