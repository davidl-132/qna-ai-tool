"""Thử hỏi AI về một file ảnh, để kiểm tra key của bạn có đọc được ảnh không.

Chạy:  py -m scripts.try_image duong_dan_anh.png
       py -m scripts.try_image duong_dan_anh.png "câu hỏi thêm của bạn"
       py -m scripts.try_image duong_dan_anh.png --plain     (chữ thường, không màu/khung)
"""
import mimetypes
import sys
from pathlib import Path

from core import llm, prompts
from desktop.ui import make_terminal


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--plain"]
    if not args:
        sys.exit(__doc__)
    path = Path(args[0])
    question = args[1] if len(args) > 1 else ""
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    ui = make_terminal(plain="--plain" in sys.argv)
    try:
        system, messages = prompts.build_image(path.read_bytes(), mime, question)
        info: dict = {}
        ui.answer(llm.ask_stream(system, messages, info), info)
    except (llm.LLMError, ValueError, OSError) as e:
        ui.error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
