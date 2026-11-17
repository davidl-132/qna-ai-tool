"""Server cục bộ cho Chrome extension.

Chạy (từ thư mục gốc dự án):
    python -m api.main

Thử bằng curl (thêm -N và đổi /ask thành /ask/stream để xem stream):
    curl -X POST http://127.0.0.1:8765/ask -H "Content-Type: application/json" \
         -H "X-Local-Token: <token>" -d "{\"selection\": \"TCP handshake\"}"
"""
import json
from typing import Literal

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import config, context, llm, prompts

from .security import ensure_token, require_token

app = FastAPI(title="Highlight AI", version="0.5.0")

# Chỉ cho phép trang của extension gọi (origin dạng chrome-extension://<id>)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^chrome-extension://[a-p]{32}$",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Local-Token"],
)


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class AskRequest(BaseModel):
    selection: str = Field(min_length=1, max_length=50_000)
    context: str = Field(default="", max_length=20_000)
    page_title: str = ""
    mode: Literal["explain", "translate", "summarize", "answer"] = "explain"
    lang: str = config.DEFAULT_LANG
    followup: list[Turn] = Field(default_factory=list, max_length=20)


def build_prompt(req: AskRequest) -> tuple[str, list[dict], bool]:
    data = context.prepare(req.selection, req.context, req.page_title)
    system, messages = prompts.build(
        data["selection"], req.mode, data["context"], data["page_title"], req.lang,
        [t.model_dump() for t in req.followup],
    )
    return system, messages, data["truncated"]


@app.get("/health")
def health():
    """Không cần token: extension dùng để kiểm tra server đang chạy."""
    return {"ok": True, "providers": llm.provider_chain()}


@app.get("/auth-check", dependencies=[Depends(require_token)])
def auth_check():
    """Trang Options dùng để kiểm tra token đúng hay sai."""
    return {"ok": True}


@app.post("/ask", dependencies=[Depends(require_token)])
def ask(req: AskRequest):
    """Trả lời một lần (không stream)."""
    system, messages, truncated = build_prompt(req)
    info: dict = {}
    try:
        answer = llm.ask(system, messages, info)
    except llm.LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"answer": answer, "truncated": truncated, **info}


def sse(data: dict, event: str | None = None) -> str:
    """Định dạng một sự kiện Server-Sent Events."""
    head = f"event: {event}\n" if event else ""
    return f"{head}data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/ask/stream", dependencies=[Depends(require_token)])
def ask_stream(req: AskRequest):
    """Trả lời dạng stream (SSE). Các sự kiện:
    meta  {provider, model, truncated}  – gửi một lần khi có chữ đầu tiên
    (mặc định) {t: "..."}             – từng đoạn chữ
    done  {}                           – xong
    error {message}                    – lỗi
    """
    system, messages, truncated = build_prompt(req)

    def events():
        info: dict = {}
        sent_meta = False
        try:
            for piece in llm.ask_stream(system, messages, info):
                if not sent_meta:
                    sent_meta = True
                    yield sse({**info, "truncated": truncated}, "meta")
                yield sse({"t": piece})
            yield sse({}, "done")
        except llm.LLMError as e:
            yield sse({"message": str(e)}, "error")

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def run() -> None:
    ensure_token()
    # Chỉ nghe trên 127.0.0.1: máy khác trong mạng không truy cập được
    uvicorn.run(app, host="127.0.0.1", port=config.PORT)


if __name__ == "__main__":
    run()
