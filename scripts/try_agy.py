"""Thử gọi Antigravity CLI (agy) giống cách app sẽ gọi: có chạy được không, mất bao lâu, có đọc được ảnh không.

Chạy:  py -m scripts.try_agy                       (chỉ thử câu hỏi chữ)
       py -m scripts.try_agy duong_dan_anh.png     (thử thêm với ảnh)
Cần đã cài agy và đăng nhập trước (chạy `agy` một lần).
"""
import sys
import time
from pathlib import Path

from core import config, llm, prompts


def run(label: str, system: str, messages: list[dict]) -> bool:
    print(f"--- {label} ---")
    t = time.time()
    info: dict = {}
    try:
        text = "".join(llm.ask_stream_one("agy", system, messages, info))
    except llm.LLMError as e:
        print(f"LỖI sau {time.time() - t:.1f}s: {e}")
        return False
    print(f"Xong sau {time.time() - t:.1f}s (model: {info.get('model')}):\n{text}\n")
    return True


def main() -> None:
    print(f"Lệnh: {config.AGY_CMD}  |  model: {config.AGY_MODEL or '(mặc định)'}  |  timeout: {config.AGY_TIMEOUT}s")
    if not llm.provider_ready("agy"):
        sys.exit(f"Không tìm thấy '{config.AGY_CMD}'. Cài Antigravity CLI và mở lại terminal, hoặc đặt AGY_CMD trong .env.")
    system, messages = prompts.build("Xin chào, 2 + 3 bằng mấy?", "answer")
    ok = run("Câu hỏi chữ", system, messages)
    if ok and len(sys.argv) > 1:
        path = Path(sys.argv[1])
        system, messages = prompts.build_image(path.read_bytes(), "image/png", "")
        ok = run(f"Ảnh {path.name}", system, messages)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
