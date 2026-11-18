import json
import os
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

os.environ.update(PROVIDER="mock", FALLBACK_PROVIDER="", LOCAL_TOKEN="test-token")

from core import config, llm  # noqa: E402


def read(path: str, mode: str = "r"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f:
        return f.read()


def fake_agy(body: str) -> str:
    """Tạo file chạy giả lập `agy` (shell script) trong thư mục tạm, trả về đường dẫn."""
    d = tempfile.mkdtemp(prefix="fakeagy-")
    path = os.path.join(d, "agy")
    with open(path, "w", encoding="utf-8") as f:
        f.write("#!/bin/sh\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


@unittest.skipIf(os.name == "nt", "dùng shell script giả lập agy")
class AgyProvider(unittest.TestCase):
    def ask(self, exe, messages=None, **cfg):
        messages = messages or [{"role": "user", "content": "2+3?"}]
        used = {}
        with mock.patch.object(config, "AGY_CMD", exe), \
                mock.patch.object(config, "AGY_MODEL", cfg.get("model", "")), \
                mock.patch.object(config, "AGY_TIMEOUT", cfg.get("timeout", 30)):
            return "".join(llm._stream_agy("LUẬT", messages, used)), used

    def test_text_question_parses_json_response_and_passes_flags(self):
        exe = fake_agy('printf \'{"response": "  5  ", "x": 1}\'\n')
        text, used = self.ask(exe, model="slug-x")
        self.assertEqual((text, used["model"]), ("5", "slug-x"))

    def test_args_and_prompt_content(self):
        out = tempfile.mkdtemp()
        exe = fake_agy(f'printf "%s\\0" "$@" > {out}/args.txt; printf \'{{"response":"ok"}}\'\n')
        self.ask(exe, model="m1", timeout=45)
        args = read(os.path.join(out, "args.txt")).split("\0")
        self.assertEqual(args[0], "-p")
        self.assertIn("LUẬT", args[1])
        self.assertIn("Người dùng: 2+3?", args[1])
        self.assertEqual(args[2:4], ["--output-format", "json"])
        self.assertEqual(args[4:6], ["--print-timeout", "45s"])
        self.assertEqual(args[6:8], ["--model", "m1"])

    def test_image_is_saved_next_to_cwd_and_mentioned(self):
        out = tempfile.mkdtemp()
        exe = fake_agy(f'ls > {out}/ls.txt; cp shot1.png {out}/copy.png; printf "%s" "$2" > {out}/prompt.txt; '
                       'printf \'{"response":"B"}\'\n')
        msgs = [{"role": "user", "content": "Q", "images": [{"mime": "image/png", "data": b"\x89PNGdata"}]}]
        text, _ = self.ask(exe, msgs)
        self.assertEqual(text, "B")
        self.assertIn("shot1.png", read(os.path.join(out, "ls.txt")))
        self.assertEqual(read(os.path.join(out, "copy.png"), "rb"), b"\x89PNGdata")
        self.assertIn("shot1.png", read(os.path.join(out, "prompt.txt")))

    def test_temp_dir_removed_afterwards(self):
        out = tempfile.mkdtemp()
        exe = fake_agy(f'pwd > {out}/cwd.txt; printf \'{{"response":"x"}}\'\n')
        self.ask(exe)
        self.assertFalse(os.path.exists(read(os.path.join(out, "cwd.txt")).strip()))

    def test_plain_text_output_is_accepted(self):
        text, _ = self.ask(fake_agy("echo 'Đáp án: B'\n"))
        self.assertEqual(text, "Đáp án: B")

    def test_nonzero_exit_raises_with_stderr(self):
        exe = fake_agy("echo 'authentication required' >&2; exit 1\n")
        with self.assertRaises(llm.LLMError) as cm:
            self.ask(exe)
        self.assertIn("authentication required", str(cm.exception))

    def test_missing_command(self):
        with self.assertRaises(llm.LLMError) as cm:
            self.ask("khong-co-lenh-agy-nay")
        self.assertIn("Không tìm thấy", str(cm.exception))

    def test_timeout_is_reported(self):
        exe = fake_agy("printf x\n")
        with mock.patch.object(llm.subprocess, "run", side_effect=subprocess.TimeoutExpired("agy", 1)):
            with self.assertRaises(llm.LLMError) as cm:
                self.ask(exe, timeout=7)
        self.assertIn("7s", str(cm.exception))

    def test_stdin_is_closed_so_agy_cannot_wait_for_input(self):
        exe = fake_agy('read x && printf \'{"response":"gotinput"}\' || printf \'{"response":"eof"}\'\n')
        text, _ = self.ask(exe)
        self.assertEqual(text, "eof")

    def test_registered_and_ready(self):
        self.assertIn("agy", llm.PROVIDERS)
        exe = fake_agy("true\n")
        with mock.patch.object(config, "AGY_CMD", exe):
            self.assertTrue(llm.provider_ready("agy"))
        with mock.patch.object(config, "AGY_CMD", "khong-co-lenh-agy-nay"):
            self.assertFalse(llm.provider_ready("agy"))


class ParseOutput(unittest.TestCase):
    def test_variants(self):
        p = llm._parse_agy_output
        self.assertEqual(p('{"response": "A"}'), "A")
        self.assertEqual(p("  plain  "), "plain")
        self.assertEqual(p('{"other": 1}'), '{"other": 1}')
        self.assertEqual(p(""), "")


if __name__ == "__main__":
    unittest.main()
