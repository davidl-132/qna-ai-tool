"""Vòng tự kiểm tra: AI viết nháp xong thì xem lại ảnh một lượt nữa để xác nhận hoặc sửa.

Tổng cộng 2 lượt gọi AI: (1) nháp, (2) kiểm tra. Lượt 2 chỉ trả về dòng kết luận ĐÚNG/SAI và, nếu SAI, bản đã sửa.
Dùng riêng file này (không sửa prompts.py) để không đè lên phần prompt bạn tự chỉnh.
"""
import unicodedata
from typing import Callable, Iterator

from . import prompts

REVIEW_RULES = (
    "\n\nVAI TRÒ KIỂM TRA: Bạn đang kiểm tra lại một câu trả lời nháp ở lượt trước. "
    "Hãy tự giải lại từ ảnh một cách độc lập rồi so với nháp. "
    "Dòng ĐẦU TIÊN chỉ được ghi đúng một từ: ĐÚNG (nháp chính xác) hoặc SAI (nháp có lỗi). "
    "Nếu ĐÚNG: dừng ngay, không viết thêm gì. "
    "Nếu SAI: từ dòng thứ hai, nêu lỗi trong một câu rồi viết lại câu trả lời đã sửa hoàn chỉnh, "
    "cùng định dạng và độ ngắn gọn như một câu trả lời bình thường. "
    "Dòng đầu luôn ghi ĐÚNG hoặc SAI dù trả lời bằng ngôn ngữ nào."
)
CHECK_REQUEST = "Hãy kiểm tra câu trả lời nháp ở trên theo đúng quy tắc: dòng đầu chỉ ghi ĐÚNG hoặc SAI."

_OK = ("DUNG", "CORRECT", "RIGHT", "OK")
_BAD = ("SAI", "WRONG", "INCORRECT")


def build_review(image: bytes, mime: str, question: str, mode: str, lang: str, draft: str,
                 max_bytes: int | None = None) -> tuple[str, list[dict]]:
    """Giống build_image nhưng thêm nháp (lượt assistant) và yêu cầu kiểm tra (lượt user)."""
    system, messages = prompts.build_image(
        image, mime, question, mode, lang,
        followup=[{"role": "assistant", "content": draft}, {"role": "user", "content": CHECK_REQUEST}],
        max_bytes=max_bytes,
    )
    return system + REVIEW_RULES, messages


def parse_verdict(line: str) -> str | None:
    """'ĐÚNG' -> 'ok', 'SAI' -> 'fixed', còn lại None. Chịu được in đậm, dấu chấm, chữ hoa/thường, bỏ dấu."""
    text = unicodedata.normalize("NFD", line.upper().replace("Đ", "D"))
    text = "".join(c for c in text if not unicodedata.combining(c)).strip(" \t*#_`>-:.!\"'")
    if text.startswith(_BAD):
        return "fixed"
    if text.startswith(_OK):
        return "ok"
    return None


def run_review(ask_stream: Callable[..., Iterator[str]], image: bytes, mime: str, question: str, mode: str,
               lang: str, draft: str, max_bytes: int | None = None) -> Iterator[tuple[str, str]]:
    """Phát ra ("verdict", "ok"|"fixed"|"unknown") đúng một lần, rồi ("fix", đoạn chữ) nếu có bản sửa."""
    system, messages = build_review(image, mime, question, mode, lang, draft, max_bytes)
    buf, verdict = "", None
    for piece in ask_stream(system, messages, {}):
        if verdict is None:
            buf += piece
            if "\n" not in buf:
                continue
            first, rest = buf.split("\n", 1)
            verdict = parse_verdict(first) or "unknown"
            yield "verdict", verdict
            if verdict == "fixed" and rest:
                yield "fix", rest
        elif verdict == "fixed":
            yield "fix", piece
    if verdict is None:  # AI chỉ trả đúng một dòng, không xuống dòng
        verdict = parse_verdict(buf) or "unknown"
        yield "verdict", verdict
