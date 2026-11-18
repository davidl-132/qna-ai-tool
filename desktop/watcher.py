"""Theo dõi clipboard: hễ có ảnh mới (ví dụ vừa bấm Win+Shift+S) thì hỏi AI và in câu trả lời.

Chạy (Windows):
    py -m desktop.watcher
    py -m desktop.watcher --mode translate
    py -m desktop.watcher --question "đáp án đúng là gì?"
    py -m desktop.watcher --plain        (chữ thường, không màu/khung)

Dừng bằng Ctrl+C. Ảnh đang có sẵn trong clipboard lúc khởi động sẽ bị bỏ qua.
"""
import argparse
import hashlib
import sys
import time
from typing import Callable

from core import config, llm, prompts


class Watcher:
    def __init__(self, clipboard, ask: Callable[[bytes], None], settle: float = 0.4) -> None:
        self.clip = clipboard
        self.ask = ask
        self.settle = settle  # chờ app chụp ghi xong ảnh vào clipboard
        self.last_seq = clipboard.sequence()  # bỏ qua nội dung có sẵn lúc khởi động
        self.last_hash = ""

    def poll_once(self) -> bool:
        """Kiểm tra clipboard một lần. Trả về True nếu vừa xử lý một ảnh mới."""
        seq = self.clip.sequence()
        if seq == self.last_seq:
            return False
        self.last_seq = seq
        if not self.clip.has_image():
            return False
        time.sleep(self.settle)
        self.last_seq = self.clip.sequence()  # nếu ảnh ghi xong thì seq có thể đã nhảy thêm
        png = self.clip.read_png(config.MAX_IMAGE_BYTES)
        if not png:
            return False
        digest = hashlib.sha1(png).hexdigest()
        if digest == self.last_hash:
            return False
        self.last_hash = digest
        self.ask(png)
        return True

    def run(self, interval: float = 0.3) -> None:
        while True:
            self.poll_once()
            time.sleep(interval)


def make_asker(mode: str, question: str, lang: str, ui=None) -> Callable[[bytes], None]:
    from .ui import make_terminal

    ui = ui or make_terminal()

    def ask(png: bytes) -> None:
        from .clipboard import png_size

        w, h = png_size(png)
        ui.image_received(w, h, len(png) // 1024)
        info: dict = {}
        try:
            system, messages = prompts.build_image(png, "image/png", question, mode, lang)
            ui.answer(llm.ask_stream(system, messages, info), info)
        except (llm.LLMError, ValueError) as e:
            ui.error(str(e))
        ui.separator()

    return ask


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", default="answer", choices=sorted(prompts.IMAGE_MODES))
    ap.add_argument("--question", default="", help="câu hỏi thêm gửi kèm mỗi ảnh")
    ap.add_argument("--lang", default=config.DEFAULT_LANG)
    ap.add_argument("--plain", action="store_true", help="chữ thường, không màu/khung (dễ copy câu trả lời)")
    args = ap.parse_args()

    if sys.platform != "win32":
        sys.exit("Công cụ theo dõi clipboard hiện chỉ chạy trên Windows.")
    from .clipboard import WinClipboard

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # để hiện tiếng Việt/emoji trong PowerShell
    from .ui import make_terminal

    ui = make_terminal(args.plain)
    ui.banner(args.mode, llm.provider_chain(), args.lang)
    try:
        Watcher(WinClipboard(), make_asker(args.mode, args.question, args.lang, ui)).run()
    except KeyboardInterrupt:
        ui.stopped()


if __name__ == "__main__":
    main()
