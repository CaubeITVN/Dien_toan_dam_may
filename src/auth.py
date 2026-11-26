"""Quản lý xác thực người dùng và phân quyền (RBAC) theo tiêu chuẩn cơ quan nhà nước.

Phục vụ Cổng Quản lý và Khai thác Tài liệu Lưu trữ Số hóa tỉnh Thái Nguyên.
"""
from __future__ import annotations

import base64
from collections import OrderedDict
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

ADMIN_PASSWORD_ENV = "APP_ADMIN_PASSWORD"
APP_SECRET_ENV = "APP_SECRET_KEY"
PBKDF2_ITERATIONS = 600_000
STATELESS_KEY_ITERATIONS = 100_000
SESSION_TTL_SECONDS = 86_400
MAX_SESSIONS = 500
MAX_FAILED_ATTEMPTS = 5
FAILED_WINDOW_SECONDS = 300
LOCKOUT_SECONDS = 300
TOKEN_PREFIX = "st1"


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(txt: str) -> bytes:
    pad = "=" * ((4 - len(txt) % 4) % 4)
    return base64.urlsafe_b64decode(txt + pad)

# Danh mục tài khoản người dùng được cấp phép (KHÔNG chứa mật khẩu; mật khẩu admin lấy từ biến môi trường)
PRESET_USERS = {
    "admin": {
        "username": "admin",
        "full_name": "Quản trị viên Hệ thống",
        "role": "admin",
        "role_title": "Quản trị viên Hệ thống",
        "agency": "Sở Giáo dục và Đào tạo",
        "avatar": "👤",
        "permissions": ["all", "manage_fonds", "upload", "view_internal", "view_public", "delete_docs", "audit_logs"],
    },
}


@dataclass
class UserSession:
    token: str
    username: str
    created_at: float
    user_info: dict[str, Any] = field(default_factory=dict)


class AuthManager:
    """Quản lý phiên đăng nhập và phân quyền an toàn luồng."""

    def __init__(
        self,
        admin_password: str | None = None,
        environ=None,
        announce=print,
        max_sessions: int = MAX_SESSIONS,
        max_failed_attempts: int = MAX_FAILED_ATTEMPTS,
        failed_window_seconds: int = FAILED_WINDOW_SECONDS,
        lockout_seconds: int = LOCKOUT_SECONDS,
    ):
        """Mật khẩu admin: tham số > biến môi trường APP_ADMIN_PASSWORD > sinh ngẫu nhiên (in ra một lần)."""
        self._lock = threading.RLock()
        self.active_sessions: OrderedDict[str, UserSession] = OrderedDict()
        self.max_sessions = max(1, int(max_sessions))
        self.max_failed_attempts = max(1, int(max_failed_attempts))
        self.failed_window_seconds = max(1, int(failed_window_seconds))
        self.lockout_seconds = max(1, int(lockout_seconds))

        environ = os.environ if environ is None else environ
        if admin_password is not None and admin_password != "":
            password = admin_password
        else:
            env_val = environ.get(ADMIN_PASSWORD_ENV, "")
            password = env_val.strip() if env_val.strip() else ""
        self.password_generated = not password
        if self.password_generated:
            password = secrets.token_urlsafe(12)
            announce(f"[AUTH] Chưa đặt {ADMIN_PASSWORD_ENV}. Mật khẩu tạm của tài khoản 'admin' cho lần chạy này: {password}")

        self._dummy_salt = secrets.token_bytes(16)
        self._dummy_hash = self._hash(secrets.token_urlsafe(16), self._dummy_salt)
        admin_salt = secrets.token_bytes(16)
        self._salts: dict[str, bytes] = {"admin": admin_salt}
        self._password_hashes: dict[str, bytes] = {"admin": self._hash(password, admin_salt)}
        self._failed_attempts: dict[str, list[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._revoked_tokens: OrderedDict[str, float] = OrderedDict()

        secret_env = (environ.get(APP_SECRET_ENV, "") or "").strip()
        if secret_env:
            self._signing_key = hashlib.sha256(secret_env.encode("utf-8")).digest()
            self.stateless_across_restarts = True
        elif not self.password_generated:
            self._signing_key = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                b"cloud-archive-stateless-v1",
                STATELESS_KEY_ITERATIONS,
            )
            self.stateless_across_restarts = True
        else:
            self._signing_key = secrets.token_bytes(32)
            self.stateless_across_restarts = False

    def _hash(self, password: str, salt: bytes | None = None) -> bytes:
        use_salt = salt if salt is not None else self._dummy_salt
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), use_salt, PBKDF2_ITERATIONS)

    def _cleanup_expired_unlocked(self, now: float | None = None) -> None:
        ts = time.time() if now is None else now
        expired = [tok for tok, sess in self.active_sessions.items() if ts - sess.created_at > SESSION_TTL_SECONDS]
        for tok in expired:
            self.active_sessions.pop(tok, None)

    def is_locked(self, username: str) -> int:
        """Trả số giây còn lại nếu tài khoản đang bị khóa tạm do nhập sai nhiều lần; 0 nếu không khóa."""
        uname = (username or "").strip()
        with self._lock:
            now = time.time()
            until = self._locked_until.get(uname, 0.0)
            if until > now:
                return int(until - now) + 1
            if uname in self._locked_until:
                self._locked_until.pop(uname, None)
            return 0

    def authenticate(self, username: str, password: str) -> dict[str, Any] | None:
        uname = (username or "").strip()
        raw_pw = password if isinstance(password, str) else ""
        with self._lock:
            now = time.time()
            until = self._locked_until.get(uname, 0.0)
            if until > now:
                # Thực hiện băm giả để giảm chênh lệch thời gian phản hồi
                self._hash(raw_pw, self._dummy_salt)
                return None

            user = PRESET_USERS.get(uname)
            salt = self._salts.get(uname)
            expected_hash = self._password_hashes.get(uname)
            if not user or salt is None or expected_hash is None:
                hmac.compare_digest(self._dummy_hash, self._hash(raw_pw, self._dummy_salt))
                return None

            candidate_hash = self._hash(raw_pw, salt)
            if not raw_pw or not hmac.compare_digest(expected_hash, candidate_hash):
                recent = [t for t in self._failed_attempts.get(uname, []) if now - t <= self.failed_window_seconds]
                recent.append(now)
                self._failed_attempts[uname] = recent
                if len(recent) >= self.max_failed_attempts:
                    self._locked_until[uname] = now + self.lockout_seconds
                    self._failed_attempts.pop(uname, None)
                return None

            self._failed_attempts.pop(uname, None)
            self._locked_until.pop(uname, None)
            self._cleanup_expired_unlocked(now)
            while len(self.active_sessions) >= self.max_sessions:
                self.active_sessions.popitem(last=False)

            token = self._issue_stateless_token(uname, str(user.get("role") or "public"), now)
            user_info = dict(user)
            session = UserSession(token=token, username=uname, created_at=now, user_info=user_info)
            self.active_sessions[token] = session
            return {"token": token, "user": user_info}

    def _issue_stateless_token(self, username: str, role: str, now: float) -> str:
        payload = {
            "u": username,
            "role": role,
            "iat": int(now),
            "exp": int(now) + SESSION_TTL_SECONDS,
            "jti": secrets.token_hex(8),
        }
        payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
        sig = hmac.new(self._signing_key, f"{TOKEN_PREFIX}.{payload_b64}".encode("ascii"), hashlib.sha256).digest()
        return f"{TOKEN_PREFIX}.{payload_b64}.{_b64url_encode(sig)}"

    def _verify_stateless_token(self, token: str, now: float | None = None) -> dict[str, Any] | None:
        parts = (token or "").split(".")
        if len(parts) != 3 or parts[0] != TOKEN_PREFIX:
            return None
        _, payload_b64, sig_b64 = parts
        try:
            expected_sig = hmac.new(
                self._signing_key, f"{TOKEN_PREFIX}.{payload_b64}".encode("ascii"), hashlib.sha256
            ).digest()
            provided_sig = _b64url_decode(sig_b64)
            if not hmac.compare_digest(expected_sig, provided_sig):
                return None
            payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        ts = time.time() if now is None else now
        exp = float(payload.get("exp") or 0)
        if exp <= ts:
            return None
        uname = str(payload.get("u") or "")
        preset = PRESET_USERS.get(uname)
        if not preset:
            return None
        return dict(preset)

    def _cleanup_revoked_unlocked(self, now: float | None = None) -> None:
        ts = time.time() if now is None else now
        expired = [tok for tok, exp_at in self._revoked_tokens.items() if exp_at <= ts]
        for tok in expired:
            self._revoked_tokens.pop(tok, None)

    def verify_token(self, token: str) -> dict[str, Any] | None:
        with self._lock:
            now = time.time()
            self._cleanup_expired_unlocked(now)
            self._cleanup_revoked_unlocked(now)
            if token in self._revoked_tokens:
                return None
            session = self.active_sessions.get(token)
            if session:
                self.active_sessions.move_to_end(token)
                return session.user_info
            stateless_user = self._verify_stateless_token(token, now=now)
            if stateless_user is not None:
                return stateless_user
            return None

    def logout(self, token: str) -> bool:
        with self._lock:
            removed = False
            if token in self.active_sessions:
                del self.active_sessions[token]
                removed = True
            if (token or "").startswith(f"{TOKEN_PREFIX}.") and self._verify_stateless_token(token) is not None:
                while len(self._revoked_tokens) >= self.max_sessions * 2:
                    self._revoked_tokens.popitem(last=False)
                self._revoked_tokens[token] = time.time() + SESSION_TTL_SECONDS
                removed = True
            return removed

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._cleanup_expired_unlocked()
            return {
                "mode": "stateless_hmac_sha256",
                "stateless_across_restarts": self.stateless_across_restarts,
                "token_ttl_seconds": SESSION_TTL_SECONDS,
                "active_sessions_count": len(self.active_sessions),
                "revoked_tokens_count": len(self._revoked_tokens),
            }

    def list_preset_accounts(self) -> list[dict]:
        """Danh sách tài khoản mẫu cung cấp cho người kiểm thử."""
        out = []
        for u, data in PRESET_USERS.items():
            out.append({
                "username": u,
                "full_name": data["full_name"],
                "role": data["role"],
                "role_title": data["role_title"],
                "agency": data["agency"],
                "avatar": data["avatar"],
            })
        return out


_auth_manager = AuthManager()


def get_auth_manager() -> AuthManager:
    return _auth_manager
