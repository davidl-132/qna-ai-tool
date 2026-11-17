"""Thử hỏi AI về một file ảnh, để kiểm tra key của bạn có đọc được ảnh không.

Chạy:  py -m scripts.try_image duong_dan_anh.png
       py -m scripts.try_image duong_dan_anh.png "câu hỏi thêm của bạn"
"""
import mimetypes
import sys
from pathlib import Path

from core import llm, prompts


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1])
    question = sys.argv[2] if len(sys.argv) > 2 else ""
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    system, messages = prompts.build_image(path.read_bytes(), mime, question)
    info: dict = {}
    try:
        for piece in llm.ask_stream(system, messages, info):
            print(piece, end="", flush=True)
    except llm.LLMError as e:
        sys.exit(f"\n⚠ {e}")
    print(f"\n\n[{info.get('provider')} / {info.get('model')}]")


if __name__ == "__main__":
    main()
