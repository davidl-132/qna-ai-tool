"""Gọi LLM. Đây là chỗ DUY NHẤT trong dự án biết đang dùng nhà cung cấp nào.

- ask_stream(): trả về từng đoạn chữ (generator)
- ask():        trả về cả câu trả lời (string)

Nếu nhà cung cấp chính lỗi TRƯỚC khi kịp trả chữ nào (hết quota 429, sai key, mất mạng...),
tự động chuyển sang nhà cung cấp dự phòng.
"""
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
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


def _short(e: Exception, limit: int = 160) -> str:
    """Rút gọn thông báo lỗi dài (JSON của Google) cho dễ đọc."""
    text = " ".join(str(e).split())
    m = re.search(r"'message': '(.*?)'", text)
    if m:
        text = f"{_error_code(e) or ''} {m.group(1)}".strip()
    return text if len(text) <= limit else text[:limit] + "…"


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
    contents = []
    for m in messages:
        parts = [types.Part.from_bytes(data=i["data"], mime_type=i["mime"]) for i in m.get("images", [])]
        parts.append(types.Part.from_text(text=m["content"]))
        contents.append(types.Content(role="model" if m["role"] == "assistant" else "user", parts=parts))
    tried: list[str] = []  # lý do lỗi của TỪNG model, để thông báo cho rõ
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
                tried.append(f"{model}: không trả về nội dung")
                break  # model này trả rỗng -> sang model kế
            except Exception as e:  # noqa: BLE001
                if started:
                    raise  # đã có chữ gửi đi, không thử lại được
                code = _error_code(e)
                reason = _short(e)
                if tried and tried[-1].startswith(f"{model}:"):
                    tried[-1] = f"{model}: {reason}"  # cùng model, ghi đè lần thử trước
                else:
                    tried.append(f"{model}: {reason}")
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
    raise LLMError("Gemini lỗi ở mọi model đã thử → " + "; ".join(tried))


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


def _has_images(messages: list[dict]) -> bool:
    return any(m.get("images") for m in messages)


def _openai_messages(system: str, messages: list[dict]) -> list[dict]:
    out = [{"role": "system", "content": system}]
    for m in messages:
        imgs = m.get("images")
        if not imgs:
            out.append({"role": m["role"], "content": m["content"]})
            continue
        content = [{"type": "text", "text": m["content"]}]
        for i in imgs:
            b64 = base64.b64encode(i["data"]).decode("ascii")
            content.append({"type": "image_url", "image_url": {"url": f"data:{i['mime']};base64,{b64}"}})
        out.append({"role": m["role"], "content": content})
    return out


def _stream_openai_compat(label: str, key: str, base_url: str, model: str,
                          system: str, messages: list[dict], used: dict) -> Iterator[str]:
    """Gọi API kiểu OpenAI (xAI, Groq...) bằng httpx, không cần gói `openai`."""
    if not key:
        raise LLMError(f"Thiếu API key của {label} trong .env")
    payload = {
        "model": model,
        "messages": _openai_messages(system, messages),
        "stream": True,
    }
    used["model"] = model
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


def _stream_ckey(system: str, messages: list[dict], used: dict) -> Iterator[str]:
    if not config.CKEY_API_KEY:
        raise LLMError("Thiếu CKEY_API_KEY trong .env")
    yield from _stream_openai_compat(
        "CKey", config.CKEY_API_KEY, config.CKEY_BASE_URL, config.CKEY_MODEL, system, messages, used
    )


def _agy_prompt(system: str, messages: list[dict], image_files: list[str]) -> str:
    """agy là một agent có prompt hệ thống riêng, nên gộp luật của mình + hội thoại vào một câu lệnh duy nhất."""
    parts = [system.strip()]
    for m in messages:
        who = "Người dùng" if m.get("role") == "user" else "Trợ lý"
        parts.append(f"{who}: {m['content']}")
    if image_files:
        names = ", ".join(image_files)
        parts.append(f"Ảnh cần xử lý nằm trong thư mục hiện tại: {names}. Hãy mở và xem ảnh đó. "
                     "Chỉ trả lời câu hỏi, không tạo/sửa/xóa file nào và không chạy lệnh nào.")
    return "\n\n".join(parts)


def _parse_agy_output(out: str) -> str:
    """`--output-format json` in một object có trường `response`; nếu không phải JSON thì lấy nguyên văn."""
    out = out.strip()
    try:
        data = json.loads(out)
    except ValueError:
        return out
    if isinstance(data, dict) and isinstance(data.get("response"), str):
        return data["response"].strip()
    return out


def _stream_agy(system: str, messages: list[dict], used: dict) -> Iterator[str]:
    """Hỏi bằng Antigravity CLI: chạy `agy -p` một lần trong thư mục tạm (ảnh được lưu thành file ở đó).

    Không stream được từng chữ: agy trả cả câu trả lời một lần khi xong.
    """
    exe = shutil.which(config.AGY_CMD)
    if not exe:
        raise LLMError(f"Không tìm thấy lệnh '{config.AGY_CMD}' (cài Antigravity CLI hoặc đặt AGY_CMD trong .env)")
    used["model"] = config.AGY_MODEL or "agy"
    with tempfile.TemporaryDirectory(prefix="highlight-ai-agy-") as tmp:
        files = []
        for m in messages:
            for img in m.get("images") or []:
                ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}.get(img["mime"], "png")
                name = f"shot{len(files) + 1}.{ext}"
                with open(os.path.join(tmp, name), "wb") as f:
                    f.write(img["data"])
                files.append(name)
        cmd = [exe, "-p", _agy_prompt(system, messages, files), "--output-format", "json",
               "--print-timeout", f"{config.AGY_TIMEOUT}s"]
        if config.AGY_MODEL:
            cmd += ["--model", config.AGY_MODEL]
        try:
            r = subprocess.run(
                cmd, cwd=tmp, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=config.AGY_TIMEOUT + 15,
                creationflags=0x08000000 if os.name == "nt" else 0,  # không bật cửa sổ console
            )
        except subprocess.TimeoutExpired as e:
            raise LLMError(f"agy không trả lời sau {config.AGY_TIMEOUT}s (đã dừng)") from e
    if r.returncode != 0:
        tail = (r.stderr or r.stdout or "").strip()[-300:]
        raise LLMError(f"agy lỗi (mã {r.returncode}): {tail}")
    text = _parse_agy_output(r.stdout)
    if text:
        yield text


def _stream_groq(system: str, messages: list[dict], used: dict) -> Iterator[str]:
    if not config.GROQ_API_KEY:
        raise LLMError("Thiếu GROQ_API_KEY trong .env")
    model = config.GROQ_MODEL
    if _has_images(messages):
        if not config.GROQ_VISION_MODEL:
            raise LLMError("Groq đang dùng model chữ, không đọc được ảnh (đặt GROQ_VISION_MODEL để bật)")
        model = config.GROQ_VISION_MODEL
    yield from _stream_openai_compat(
        "Groq", config.GROQ_API_KEY, config.GROQ_BASE_URL, model, system, messages, used
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
        f"- Số ảnh đính kèm: {sum(len(m.get('images', [])) for m in messages)}\n"
        f"- Số lượt trong hội thoại: {len(messages)}\n"
        f"- Câu cuối: `{messages[-1]['content'][-60:].strip()}`"
    )
    for word in text.split(" "):
        time.sleep(0.03)
        yield word + " "


PROVIDERS = {"gemini": _stream_gemini, "groq": _stream_groq, "grok": _stream_grok, "ckey": _stream_ckey,
             "agy": _stream_agy, "mock": _stream_mock}


def _model_name(provider: str) -> str:
    return {"gemini": config.GEMINI_MODEL, "groq": config.GROQ_MODEL, "grok": config.XAI_MODEL,
            "ckey": config.CKEY_MODEL, "agy": config.AGY_MODEL or "agy"}.get(provider, provider)


# ---------- Hàm dùng chung ----------

def provider_ready(name: str) -> bool:
    """Provider đã có đủ cấu hình (key) để gọi chưa."""
    key = {"gemini": config.GEMINI_API_KEY, "groq": config.GROQ_API_KEY, "grok": config.XAI_API_KEY,
           "ckey": config.CKEY_API_KEY}.get(name)
    if name == "agy":
        return bool(shutil.which(config.AGY_CMD))
    return name == "mock" or bool(key)


def ask_stream_one(name: str, system: str, messages: list[dict], info: dict | None = None) -> Iterator[str]:
    """Gọi đúng MỘT provider, không tự chuyển sang provider khác (dùng cho chế độ nhiều AI)."""
    fn = PROVIDERS.get(name)
    if fn is None:
        raise LLMError(f"{name}: không hỗ trợ")
    used: dict = {}
    for piece in fn(system, messages, used):
        if info is not None and "model" not in info:
            info.update(provider=name, model=used.get("model") or _model_name(name))
        yield piece


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
