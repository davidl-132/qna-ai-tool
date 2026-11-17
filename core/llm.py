"""Gọi LLM. Đây là chỗ DUY NHẤT trong dự án biết đang dùng nhà cung cấp nào.

- ask_stream(): trả về từng đoạn chữ (generator)
- ask():        trả về cả câu trả lời (string)

Nếu nhà cung cấp chính lỗi TRƯỚC khi kịp trả chữ nào (hết quota 429, sai key, mất mạng...),
tự động chuyển sang nhà cung cấp dự phòng.
"""
import json
import logging
import re
from typing import Iterable, Iterator

from . import config

log = logging.getLogger("highlight-ai.llm")


class LLMError(RuntimeError):
    pass


# ---------- Từng nhà cung cấp ----------

# Mã lỗi tạm thời: đáng thử lại. 400/401/403 là lỗi cấu hình: thử lại vô ích.
_TRANSIENT = {429, 500, 502, 503, 504}


def _sleep(seconds: float) -> None:  # tách riêng để test không phải chờ thật
    import time

    time.sleep(seconds)


def _error_code(e: Exception) -> int | None:
    code = getattr(e, "code", None)
    if isinstance(code, int):
        return code
    m = re.match(r"\s*(\d{3})\b", str(e))
    return int(m.group(1)) if m else None


def _gemini_models() -> list[str]:
    models = [config.GEMINI_MODEL]
    models += [m for m in config.GEMINI_FALLBACK_MODELS if m not in models]
    return models


def _stream_gemini(system: str, messages: list[dict], used: dict) -> Iterator[str]:
    if not config.GEMINI_API_KEY:
        raise LLMError("Thiếu GEMINI_API_KEY trong .env")
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    contents = [
        {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    last: Exception | None = None
    for model in _gemini_models():
        for attempt in range(config.GEMINI_RETRIES + 1):
            started = False
            try:
                stream = client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(system_instruction=system),
                )
                for chunk in stream:
                    if chunk.text:
                        if not started:
                            started = True
                            used["model"] = model
                        yield chunk.text
                if started:
                    return
                last = LLMError(f"{model} không trả về nội dung")
                break  # model này trả rỗng -> sang model kế
            except Exception as e:  # noqa: BLE001
                if started:
                    raise  # đã có chữ gửi đi, không thử lại được
                last = e
                code = _error_code(e)
                if code in (400, 401, 403):
                    raise LLMError(f"{model}: {e}") from e  # sai key/quyền: dừng luôn
                if code == 404:
                    log.warning("Model %s không tồn tại, thử model khác", model)
                    break
                if attempt < config.GEMINI_RETRIES:
                    delay = 1.5 * (attempt + 1)
                    log.warning("Gemini %s lỗi %s, thử lại sau %.1fs", model, code, delay)
                    _sleep(delay)
                else:
                    log.warning("Gemini %s vẫn lỗi %s, đổi model", model, code)
    raise LLMError(f"Gemini quá tải/lỗi sau khi thử {', '.join(_gemini_models())}: {last}")


def _httpx_client():
    import httpx  # thuần Python, không cần file DLL

    return httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0))


def _parse_openai_sse(lines: Iterable[str]) -> Iterator[str]:
    """Đọc luồng SSE kiểu OpenAI, trả về từng đoạn chữ."""
    for line in lines:
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            return
        try:
            obj = json.loads(data)
        except ValueError:
            continue
        choices = obj.get("choices") or []
        if choices:
            text = (choices[0].get("delta") or {}).get("content")
            if text:
                yield text


def _stream_openai_compat(label: str, key: str, base_url: str, model: str,
                          system: str, messages: list[dict], used: dict) -> Iterator[str]:
    """Gọi API kiểu OpenAI (xAI, Groq...) bằng httpx, không cần gói `openai`."""
    if not key:
        raise LLMError(f"Thiếu API key của {label} trong .env")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "stream": True,
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    url = base_url.rstrip("/") + "/chat/completions"
    with _httpx_client() as client:
        with client.stream("POST", url, json=payload, headers=headers) as r:
            if r.status_code != 200:
                body = r.read().decode("utf-8", "replace")[:300]
                raise LLMError(f"{r.status_code} từ {label}: {body}")
            yield from _parse_openai_sse(r.iter_lines())


def _stream_grok(system: str, messages: list[dict], used: dict) -> Iterator[str]:
    if not config.XAI_API_KEY:
        raise LLMError("Thiếu XAI_API_KEY trong .env")
    yield from _stream_openai_compat(
        "xAI Grok", config.XAI_API_KEY, config.XAI_BASE_URL, config.XAI_MODEL, system, messages, used
    )


def _stream_groq(system: str, messages: list[dict], used: dict) -> Iterator[str]:
    if not config.GROQ_API_KEY:
        raise LLMError("Thiếu GROQ_API_KEY trong .env")
    yield from _stream_openai_compat(
        "Groq", config.GROQ_API_KEY, config.GROQ_BASE_URL, config.GROQ_MODEL, system, messages, used
    )


def _stream_mock(system: str, messages: list[dict], used: dict) -> Iterator[str]:
    """Nhà cung cấp giả: dùng để test khi chưa có mạng/key."""
    import time

    first = messages[0]["content"]
    task = first.rsplit("Yêu cầu:", 1)[-1].strip()[:40]
    text = (
        "**[mock]** Câu trả lời thử nghiệm, không gọi AI thật.\n\n"
        f"- Yêu cầu: {task}…\n"
        f"- Có context xung quanh: {'có' if '<context>' in first else 'không'}\n"
        f"- Số lượt trong hội thoại: {len(messages)}\n"
        f"- Câu cuối: `{messages[-1]['content'][-60:].strip()}`"
    )
    for word in text.split(" "):
        time.sleep(0.03)
        yield word + " "


PROVIDERS = {"gemini": _stream_gemini, "groq": _stream_groq, "grok": _stream_grok, "mock": _stream_mock}


def _model_name(provider: str) -> str:
    return {"gemini": config.GEMINI_MODEL, "groq": config.GROQ_MODEL, "grok": config.XAI_MODEL}.get(provider, provider)


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
        used: dict = {}
        try:
            for piece in fn(system, messages, used):
                if not started:
                    started = True
                    if info is not None:
                        info.update(provider=name, model=used.get("model") or _model_name(name))
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
