"""Server cục bộ cho Chrome extension.

Chạy (từ thư mục gốc dự án):
    python -m api.main

Thử bằng curl:
    curl -X POST http://127.0.0.1:8765/ask -H "Content-Type: application/json" \
         -H "X-Local-Token: <token>" -d "{\"selection\": \"TCP handshake\"}"
"""
from typing import Literal

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core import config, context, llm, prompts

from .security import ensure_token, require_token

app = FastAPI(title="Highlight AI", version="0.2.0")

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


def run() -> None:
    ensure_token()
    # Chỉ nghe trên 127.0.0.1: máy khác trong mạng không truy cập được
    uvicorn.run(app, host="127.0.0.1", port=config.PORT)


if __name__ == "__main__":
    run()
