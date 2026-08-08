"""轻量的本地登录会话。适合单用户工作台，不依赖第三方身份服务。"""
import base64
import hashlib
import hmac
import os
import time

from fastapi import HTTPException

COOKIE_NAME = "workbench_session"


def secret() -> bytes:
    value = os.getenv("WORKBENCH_SESSION_SECRET", "")
    if not value:
        raise HTTPException(503, "服务器尚未设置 WORKBENCH_SESSION_SECRET")
    return value.encode()


def create_session() -> str:
    """签发 30 天有效、不可篡改的会话令牌。"""
    expires = str(int(time.time()) + 30 * 24 * 60 * 60)
    signature = hmac.new(secret(), expires.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(f"{expires}.".encode() + signature).decode()


def valid_session(token: str | None) -> bool:
    try:
        raw = base64.urlsafe_b64decode((token or "").encode())
        expires, signature = raw.split(b".", 1)
        expected = hmac.new(secret(), expires, hashlib.sha256).digest()
        return hmac.compare_digest(signature, expected) and int(expires) > time.time()
    except (ValueError, TypeError):
        return False
