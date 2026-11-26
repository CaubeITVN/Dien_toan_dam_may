"""Kiểm thử xác thực phi trạng thái HMAC-SHA256 (Stateless Auth across Container Restarts)."""
import time

from src.auth import AuthManager


def test_stateless_token_survives_restart():
    mgr1 = AuthManager(admin_password="CloudTestPassword!2026", announce=lambda _m: None)
    login_res = mgr1.authenticate("admin", "CloudTestPassword!2026")
    assert login_res is not None
    token = login_res["token"]
    assert token.startswith("st1.")
    assert mgr1.stateless_across_restarts is True

    # Mô phỏng Container khởi động lại với cùng mật khẩu/khóa cấu hình (active_sessions trống rỗng)
    mgr2 = AuthManager(admin_password="CloudTestPassword!2026", announce=lambda _m: None)
    assert len(mgr2.active_sessions) == 0
    verified = mgr2.verify_token(token)
    assert verified is not None
    assert verified["username"] == "admin"
    assert verified["role"] == "admin"


def test_stateless_token_rejects_tamper_and_logout_and_expiry(monkeypatch):
    mgr = AuthManager(
        environ={"APP_ADMIN_PASSWORD": "SecretAdmin#1", "APP_SECRET_KEY": "shared-cloud-hmac-key"},
        announce=lambda _m: None,
    )
    res = mgr.authenticate("admin", "SecretAdmin#1")
    assert res is not None
    token = res["token"]

    # Giả mạo chữ ký
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.{'A' * len(parts[2])}"
    assert mgr.verify_token(tampered) is None

    # Khác APP_SECRET_KEY không xác thực được
    other_mgr = AuthManager(
        environ={"APP_ADMIN_PASSWORD": "SecretAdmin#1", "APP_SECRET_KEY": "different-key"},
        announce=lambda _m: None,
    )
    assert other_mgr.verify_token(token) is None

    # Đăng xuất thu hồi token
    assert mgr.logout(token) is True
    assert mgr.verify_token(token) is None

    # Kiểm tra hết hạn TTL
    res2 = mgr.authenticate("admin", "SecretAdmin#1")
    assert res2 is not None
    tok2 = res2["token"]
    mgr.active_sessions.clear()
    future_now = time.time() + 90_000
    assert mgr._verify_stateless_token(tok2, now=future_now) is None
    assert mgr.status()["mode"] == "stateless_hmac_sha256"
