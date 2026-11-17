"""Gọi LLM. Đây là chỗ DUY NHẤT trong dự án biết đang dùng nhà cung cấp nào.

- ask_stream(): trả về từng đoạn chữ (generator)
- ask():        trả về cả câu trả lời (string)

Nếu nhà cung cấp chính lỗi TRƯỚC khi kịp trả chữ nào (hết quota 429, sai key, mất mạng...),
tự động chuyển sang nhà cung cấp dự phòng.
"""
import logging
from typing import Iterator

from . import config

log = logging.getLogger("highlight-ai.llm")


class LLMError(RuntimeError):
    pass


# ---------- Từng nhà cung cấp ----------

def _stream_gemini(system: str, messages: list[dict]) -> Iterator[str]:
    if not config.GEMINI_API_KEY:
        raise LLMError("Thiếu GEMINI_API_KEY trong .env")
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    stream = client.models.generate_content_stream(
        model=config.GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system),
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


def _stream_grok(system: str, messages: list[dict]) -> Iterator[str]:
    if not config.XAI_API_KEY:
        raise LLMError("Thiếu XAI_API_KEY trong .env")
    from openai import OpenAI  # xAI dùng API tương thích OpenAI

    client = OpenAI(api_key=config.XAI_API_KEY, base_url=config.XAI_BASE_URL)
    stream = client.chat.completions.create(
        model=config.XAI_MODEL,
        messages=[{"role": "system", "content": system}, *messages],
        stream=True,
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def _stream_mock(system: str, messages: list[dict]) -> Iterator[str]:
    """Nhà cung cấp giả: dùng để test khi chưa có mạng/key."""
    import time

    last = messages[-1]["content"]
    text = f"[mock] Đã nhận {len(last)} ký tự. Đây là câu trả lời thử nghiệm."
    for word in text.split(" "):
        time.sleep(0.03)
        yield word + " "


PROVIDERS = {"gemini": _stream_gemini, "grok": _stream_grok, "mock": _stream_mock}


def _model_name(provider: str) -> str:
    return {"gemini": config.GEMINI_MODEL, "grok": config.XAI_MODEL}.get(provider, provider)


# ---------- Hàm dùng chung ----------

def provider_chain() -> list[str]:
    chain = [config.PROVIDER]
    fb = config.FALLBACK_PROVIDER
    if fb and fb != config.PROVIDER and fb in PROVIDERS:
        chain.append(fb)
    return chain


def ask_stream(system: str, messages: list[dict], info: dict | None = None) -> Iterator[str]:
    """Stream câu trả lời. Nếu truyền `info` (dict), hàm sẽ ghi provider/model đã dùng vào đó."""
    errors = []
    for name in provider_chain():
        fn = PROVIDERS.get(name)
        if fn is None:
            errors.append(f"{name}: không hỗ trợ")
            continue
        started = False
        try:
            for piece in fn(system, messages):
                if not started:
                    started = True
                    if info is not None:
                        info.update(provider=name, model=_model_name(name))
                yield piece
            if started:
                return
            errors.append(f"{name}: không trả về nội dung")
        except Exception as e:  # noqa: BLE001 - muốn bắt mọi lỗi để chuyển dự phòng
            if started:
                # Đã gửi chữ cho người dùng rồi thì không thể đổi provider giữa chừng
                raise LLMError(f"{name} bị ngắt giữa chừng: {e}") from e
            log.warning("Provider %s lỗi, thử provider tiếp theo: %s", name, e)
            errors.append(f"{name}: {e}")
    raise LLMError("Tất cả nhà cung cấp đều lỗi → " + " | ".join(errors))


def ask(system: str, messages: list[dict], info: dict | None = None) -> str:
    return "".join(ask_stream(system, messages, info))
