"""Thử core/ ngay trong terminal, chưa cần web.

Cách chạy (từ thư mục gốc dự án):
    python -m scripts.try_core "Normalization in database" --mode explain
    python -m scripts.try_core "The quick brown fox" --mode translate
"""
import argparse
import sys

from core import context, llm, prompts


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Hỏi AI về một đoạn text")
    p.add_argument("selection", help="Đoạn text giả lập phần bôi đen")
    p.add_argument("--mode", default="explain", choices=list(prompts.MODES))
    p.add_argument("--context", default="", help="Đoạn văn xung quanh (tuỳ chọn)")
    p.add_argument("--title", default="", help="Tiêu đề trang (tuỳ chọn)")
    args = p.parse_args()

    data = context.prepare(args.selection, args.context, args.title)
    system, messages = prompts.build(data["selection"], args.mode, data["context"], data["page_title"])

    info: dict = {}
    try:
        for piece in llm.ask_stream(system, messages, info):
            print(piece, end="", flush=True)
    except llm.LLMError as e:
        print(f"\n[LỖI] {e}")
        sys.exit(1)
    print(f"\n\n--- trả lời bởi {info.get('provider')} ({info.get('model')})")


if __name__ == "__main__":
    main()
