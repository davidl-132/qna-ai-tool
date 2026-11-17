"""Làm sạch và cắt ngắn đoạn text trước khi gửi cho AI."""
import re

from . import config


def clean(text: str) -> str:
    """Gộp khoảng trắng thừa, bỏ ký tự điều khiển."""
    text = text or ""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate(text: str, limit: int) -> tuple[str, bool]:
    """Cắt text về tối đa `limit` ký tự. Trả về (text, có_bị_cắt_không)."""
    if len(text) <= limit:
        return text, False
    return text[:limit].rstrip() + " …", True


def prepare(selection: str, context: str = "", page_title: str = "") -> dict:
    """Chuẩn hoá đầu vào. Trả về dict đã làm sạch + cờ `truncated`."""
    sel, cut = truncate(clean(selection), config.MAX_SELECTION_CHARS)
    ctx, _ = truncate(clean(context), config.MAX_CONTEXT_CHARS)
    title, _ = truncate(clean(page_title), 200)
    return {"selection": sel, "context": ctx, "page_title": title, "truncated": cut}
