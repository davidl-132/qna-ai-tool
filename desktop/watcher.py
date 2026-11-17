"""Theo dõi clipboard: hễ có ảnh mới (ví dụ vừa bấm Win+Shift+S) thì hỏi AI và in câu trả lời.

Chạy (Windows):
    py -m desktop.watcher
    py -m desktop.watcher --mode translate
    py -m desktop.watcher --question "đáp án đúng là gì?"

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


def make_asker(mode: str, question: str, lang: str) -> Callable[[bytes], None]:
    def ask(png: bytes) -> None:
        from .clipboard import png_size

        w, h = png_size(png)
        print(f"\n📷 [{time.strftime('%H:%M:%S')}] Nhận ảnh {w}x{h} ({len(png) // 1024} KB), đang hỏi AI…\n")
        info: dict = {}
        try:
            system, messages = prompts.build_image(png, "image/png", question, mode, lang)
            for piece in llm.ask_stream(system, messages, info):
                print(piece, end="", flush=True)
            print(f"\n\n[{info.get('provider')} / {info.get('model')}]")
        except (llm.LLMError, ValueError) as e:
            print(f"⚠ {e}")
        print("-" * 60)

    return ask


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", default="answer", choices=sorted(prompts.IMAGE_MODES))
    ap.add_argument("--question", default="", help="câu hỏi thêm gửi kèm mỗi ảnh")
    ap.add_argument("--lang", default=config.DEFAULT_LANG)
    args = ap.parse_args()

    if sys.platform != "win32":
        sys.exit("Công cụ theo dõi clipboard hiện chỉ chạy trên Windows.")
    from .clipboard import WinClipboard

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # để hiện tiếng Việt/emoji trong PowerShell
    print("Đang theo dõi clipboard. Bấm Win+Shift+S để chụp, Ctrl+C để dừng.")
    print(f"Chế độ: {args.mode} | Nhà cung cấp: {' → '.join(llm.provider_chain())}")
    try:
        Watcher(WinClipboard(), make_asker(args.mode, args.question, args.lang)).run()
    except KeyboardInterrupt:
        print("\nĐã dừng.")


if __name__ == "__main__":
    main()
