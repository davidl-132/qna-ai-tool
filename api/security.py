"""Bảo vệ server cục bộ: chỉ ai có LOCAL_TOKEN mới gọi được.

Lý do: mọi trang web bạn mở đều có thể thử gửi request tới http://127.0.0.1:8765.
Token bí mật (chỉ extension biết) chặn được việc đó.
"""
import secrets

from fastapi import Header, HTTPException

from core import config

ENV_FILE = config.ROOT / ".env"


def ensure_token() -> str:
    """Lấy LOCAL_TOKEN; nếu chưa có thì tạo mới và ghi vào .env."""
    if config.LOCAL_TOKEN:
        return config.LOCAL_TOKEN
    token = secrets.token_urlsafe(32)
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    lines = [ln for ln in lines if not ln.strip().startswith("LOCAL_TOKEN=")]
    lines.append(f"LOCAL_TOKEN={token}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    config.LOCAL_TOKEN = token
    print("\n" + "=" * 60)
    print("Đã tạo LOCAL_TOKEN mới và lưu vào .env:")
    print(f"  {token}")
    print("Dán token này vào trang Options của extension.")
    print("=" * 60 + "\n")
    return token


def require_token(x_local_token: str = Header(default="")) -> None:
    """Dependency của FastAPI: từ chối request thiếu/sai token."""
    if not config.LOCAL_TOKEN or not secrets.compare_digest(x_local_token, config.LOCAL_TOKEN):
        raise HTTPException(status_code=401, detail="Sai hoặc thiếu X-Local-Token")
