"""Nhiều AI cùng trả lời rồi tổng hợp (kiểu multi-agent): mỗi AI giải độc lập, đồng ý thì lấy luôn, khác nhau thì
một lượt "trọng tài" xem lại đề, so các đáp án rồi chốt đáp án cuối.

Chạy song song nên thời gian chờ ≈ AI chậm nhất (cộng thêm một lượt trọng tài nếu các AI không đồng ý).
Không phụ thuộc giao diện nên test được bằng AI giả. Dùng riêng file này để không đè lên prompts.py của bạn.
"""
import re
import threading
import unicodedata
from dataclasses import dataclass
from typing import Callable, Iterator

JUDGE_RULES = (
    "\n\nVAI TRÒ TRỌNG TÀI: Có nhiều AI đã trả lời độc lập cùng một câu hỏi và đáp án của chúng KHÁC nhau. "
    "Hãy tự giải lại từ đầu bằng nội dung gốc, dùng các đáp án kia chỉ làm tham khảo (chúng có thể đều sai), "
    "rồi chỉ viết ĐÁP ÁN CUỐI CÙNG đúng định dạng và độ ngắn gọn của yêu cầu ban đầu. "
    "Không nhắc tới các AI, không so sánh, không nêu lý do."
)


@dataclass
class Answer:
    name: str
    model: str = ""
    text: str = ""
    error: str = ""


def normalize(text: str) -> str:
    """Bỏ in đậm/dấu câu/khoảng trắng/dấu tiếng Việt, chữ thường: '**B**', 'b.' và 'B' coi là một."""
    t = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", "", t)


def judge_messages(messages: list[dict], answers: list[Answer]) -> list[dict]:
    """Chép messages (giữ nguyên ảnh) rồi nối các đáp án vào cuối lượt user cuối cùng."""
    out = [dict(m) for m in messages]
    lines = [f"[AI {i}] {a.text.strip()}" for i, a in enumerate(answers, start=1)]
    note = ("Các AI khác đã trả lời độc lập, đáp án khác nhau:\n" + "\n\n".join(lines) +
            "\n\nHãy chốt đáp án cuối cùng đúng nhất.")
    for m in reversed(out):
        if m.get("role") == "user":
            m["content"] = f"{m['content']}\n\n{note}"
            return out
    out.append({"role": "user", "content": note})
    return out


def ask_all(members: list[tuple[str, Callable[..., Iterator[str]]]], system: str, messages: list[dict]) -> list[Answer]:
    """Gọi mọi AI cùng lúc, chờ hết. Lỗi của AI nào ghi vào Answer.error của AI đó (không làm hỏng cả nhóm)."""
    results = [Answer(name) for name, _ in members]

    def call(i: int, fn: Callable[..., Iterator[str]]) -> None:
        info: dict = {}
        try:
            results[i].text = "".join(fn(system, messages, info)).strip()
            results[i].model = info.get("model", "")
            if not results[i].text:
                results[i].error = "không trả về nội dung"
        except Exception as e:  # noqa: BLE001
            results[i].error = str(e) or e.__class__.__name__

    threads = [threading.Thread(target=call, args=(i, fn), daemon=True) for i, (_, fn) in enumerate(members)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def run(members: list[tuple[str, Callable[..., Iterator[str]]]], judge_ask: Callable[..., Iterator[str]],
        system: str, messages: list[dict]) -> Iterator[tuple[str, object]]:
    """Phát ra các sự kiện:
    ("meta", {"model": ...})            AI nào đã trả lời
    ("merging", None)                   bắt đầu lượt trọng tài (các AI khác nhau)
    ("chunk", chữ)                      nội dung đáp án cuối
    ("verdict", "ok"|"merged"|"solo")   ok = các AI đồng ý; merged = trọng tài chốt; solo = chỉ một AI trả lời được
    """
    answers = ask_all(members, system, messages)
    good = [a for a in answers if a.text]
    if not good:
        raise RuntimeError("Tất cả AI đều lỗi → " + " | ".join(f"{a.name}: {a.error}" for a in answers))
    yield "meta", {"model": " + ".join(a.model or a.name for a in good)}
    if len(good) == 1:
        yield "chunk", good[0].text
        yield "verdict", "solo"
        return
    if len({normalize(a.text) for a in good}) == 1:
        yield "chunk", good[0].text
        yield "verdict", "ok"
        return
    yield "merging", None
    started = False
    try:
        for piece in judge_ask(system + JUDGE_RULES, judge_messages(messages, good), {}):
            started = True
            yield "chunk", piece
    except Exception:  # noqa: BLE001
        if started:
            raise
        yield "chunk", good[0].text  # trọng tài lỗi: dùng đáp án của AI đầu tiên (AI chính) thay vì mất hết
        yield "verdict", "solo"
        return
    if not started:
        yield "chunk", good[0].text
        yield "verdict", "solo"
        return
    yield "verdict", "merged"
