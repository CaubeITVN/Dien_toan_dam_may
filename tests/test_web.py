"""Web demo qua TestClient: văn bản tự tạo, không cần dữ liệu thật hay engine OCR.

Trợ lý dựng từ trang mẫu có dấu; PDF tự tạo chỉ để render ảnh trang (phông Helvetica không có chữ có dấu).
"""
import pymupdf
import pytest
from fastapi.testclient import TestClient

from src.qa import Assistant
from tests.fixtures import pages_of, sample_pages
from web import app as web_app


def make_pdf(path, n_pages, filler="noi dung van ban mau "):
    doc = pymupdf.open()
    for i in range(n_pages):
        doc.new_page().insert_text((50, 60), f"Trang {i + 1}\n" + filler * 30, fontsize=9)
    doc.save(path)
    doc.close()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    pdf = tmp_path / "qd_125.pdf"
    make_pdf(pdf, 2)
    monkeypatch.setattr(web_app, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(web_app, "OCR_DIR", tmp_path / "ocr")
    web_app.state.clear()
    web_app.state.update(assistant=Assistant([p for p in sample_pages() if p["doc_id"] == "qd_125"]),
                         paths={"qd_125": pdf}, meta={"qd_125": {"group": "test", "split": "dev"}})
    web_app.render_png.cache_clear()
    with TestClient(web_app.app) as c:
        yield c
    web_app.state.clear()


@pytest.fixture()
def admin_headers(monkeypatch):
    import secrets
    import time
    from src.auth import PRESET_USERS, UserSession, get_auth_manager

    tok = secrets.token_hex(16)
    mgr = get_auth_manager()
    sess = UserSession(token=tok, username="admin", created_at=time.time(), user_info=dict(PRESET_USERS["admin"]))
    monkeypatch.setitem(mgr.active_sessions, tok, sess)
    return {"Authorization": f"Bearer {tok}"}


def test_docs_and_card(client):
    docs = client.get("/api/docs").json()
    assert [d["doc_id"] for d in docs] == ["qd_125"]
    card = client.get("/api/docs/qd_125").json()
    assert {f["name"] for f in card["fields"]} >= {"doc_number", "issue_date", "signer"}
    assert client.get("/api/docs/khong_co").status_code == 404


def test_ask_returns_citations(client):
    a = client.get("/api/ask", params={"q": "Ai ký Quyết định 125/QĐ-SGDĐT?"}).json()
    assert a["status"] == "answered" and a["citations"][0]["doc_id"] == "qd_125"
    assert client.get("/api/ask", params={"q": "  "}).status_code == 400


def test_post_ask_with_selected_sources(client):
    r = client.post("/api/ask", json={"question": "Ai ký Quyết định 125/QĐ-SGDĐT?", "doc_ids": ["qd_125"]})
    a = r.json()
    assert r.status_code == 200 and a["status"] == "answered" and a["citations"][0]["label"]
    assert client.post("/api/ask", json={"question": "Ai ký?", "doc_ids": []}).json()["status"] == "refused"
    card = client.get("/api/docs/qd_125").json()
    assert card["suggestions"] and card["label"]


def test_summary_endpoint(client, tmp_path, monkeypatch):
    from src import summarize
    monkeypatch.setattr(summarize, "SUMMARY_DIR", tmp_path / "summaries")
    assert client.get("/api/docs/qd_125/summary", params={"cached_only": True}).json()["points"] == []
    s = client.get("/api/docs/qd_125/summary").json()
    assert s["kind"] == "extractive" and s["points"] and s["citations"][0]["label"]
    assert client.get("/api/docs/qd_125/summary", params={"cached_only": True}).json()["points"]
    assert client.get("/api/docs/khong_co/summary").status_code == 404


def test_page_png_with_highlight(client):
    r = client.get("/api/page/qd_125/1.png", params={"start": 0, "end": 40})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"
    assert client.get("/api/page/qd_125/9.png").status_code == 404


def test_upload_pdf_and_reject_non_pdf(client, admin_headers, tmp_path):
    pdf = tmp_path / "moi.pdf"
    make_pdf(pdf, 1)
    assert client.post(
        "/api/upload",
        content=pdf.read_bytes(),
        headers={"Content-Type": "application/pdf", "X-Filename": "moi.pdf"},
    ).status_code == 401

    r = client.post(
        "/api/upload",
        content=pdf.read_bytes(),
        headers={**admin_headers, "Content-Type": "application/pdf", "X-Filename": "m%E1%BB%9Bi.pdf"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["doc_id"].startswith("up_") and body["doc_id"].endswith("_moi") and body["n_pages"] == 1
    assert len(client.get("/api/docs").json()) == 2
    assert body["upload"]["original_name"] == "mới.pdf"
    assert (tmp_path / "uploads" / body["doc_id"] / "source.pdf").exists()
    assert [u["doc_id"] for u in client.get("/api/uploads").json()] == [body["doc_id"]]
    assert client.post("/api/upload", content=b"hello", headers=admin_headers).status_code == 400
    assert client.delete(f"/api/uploads/{body['doc_id']}").status_code == 401

    assert client.delete(f"/api/uploads/{body['doc_id']}", headers=admin_headers).status_code == 200
    assert not (tmp_path / "uploads" / body["doc_id"]).exists()
    assert len(client.get("/api/docs").json()) == 1
    assert client.delete("/api/uploads/qd_125", headers=admin_headers).status_code == 404, "không xóa được văn bản kho chính"


def test_login_uses_env_password_and_no_default(monkeypatch):
    from src.auth import AuthManager
    msgs = []
    m = AuthManager(environ={"APP_ADMIN_PASSWORD": "mat-khau-thu-nghiem"}, announce=msgs.append)
    assert not m.password_generated and msgs == []
    assert m.authenticate("admin", "abc@123") is None, "không còn mật khẩu cố định"
    assert m.authenticate("admin", "") is None
    res = m.authenticate("admin", "mat-khau-thu-nghiem")
    assert res and "password_hash" not in res["user"] and m.verify_token(res["token"])["username"] == "admin"


def test_login_random_password_printed_once_when_env_missing():
    from src.auth import AuthManager
    msgs = []
    m = AuthManager(environ={}, announce=msgs.append)
    assert m.password_generated and len(msgs) == 1
    pw = msgs[0].rsplit(": ", 1)[1]
    assert len(pw) >= 12 and m.authenticate("admin", pw) is not None
    assert m.authenticate("admin", "abc@123") is None
    other = AuthManager(environ={}, announce=lambda s: None)
    assert other.password_generated and other.authenticate("admin", pw) is None, "mỗi lần khởi động một mật khẩu khác"


def test_login_endpoint_rejects_old_default_password(client):
    assert client.post("/api/auth/login", json={"username": "admin", "password": "abc@123"}).status_code == 401
    from src.auth import get_auth_manager
    assert "abc@123" not in repr(get_auth_manager()._password_hashes)


def test_no_hardcoded_password_in_sources():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    for rel in ("src/auth.py", "web/app.py", "README.md", "HUONG_DAN_CHAY.txt"):
        assert "abc@123" not in (root / rel).read_text(encoding="utf-8"), rel


def test_conversational_chatbot_endpoints(client):
    r_hi = client.post("/api/ask", json={"question": "Xin chào!"})
    assert r_hi.status_code == 200
    d_hi = r_hi.json()
    assert d_hi["status"] == "answered"
    assert d_hi["kind"] == "conversation"
    assert d_hi["suggestions"]

    r_help = client.post("/api/ask", json={"question": "Bạn làm được gì?"})
    assert r_help.status_code == 200
    assert r_help.json()["status"] == "answered"
    assert r_help.json()["kind"] == "conversation"

    r_stats = client.post("/api/ask", json={"question": "Thống kê kho lưu trữ"})
    assert r_stats.status_code == 200
    d_stats = r_stats.json()
    assert d_stats["status"] == "answered"
    assert d_stats["kind"] == "archive_stats"
    assert "Phông" in d_stats["text"]


def test_dossier_crud_import_and_excel_csv_export(client, admin_headers):
    from src.archive import ArchiveManager
    # Cô lập ArchiveManager mới cho test CRUD
    web_app.state["archive_mgr"] = ArchiveManager()

    # Chưa đăng nhập không thể ghi cấu hình LLM hay tạo hồ sơ
    assert client.post("/api/llm/config", json={"provider": "openrouter"}).status_code == 401
    assert client.post(
        "/api/archive/dossiers",
        json={"file_code": "TN.2026.UNAUTH.001", "title": "Không hợp lệ"},
    ).status_code == 401

    r_create = client.post(
        "/api/archive/dossiers",
        headers=admin_headers,
        json={
            "file_code": "TN.2026.TEST.001",
            "title": "Hồ sơ kiểm thử tạo mới từ giao diện",
            "fond_id": "P_UBND_TN",
            "retention_period": "50 năm",
            "usage_mode": "Công khai",
            "status": "Tạo mới",
        },
    )
    assert r_create.status_code == 200
    created = r_create.json()
    assert created["file_code"] == "TN.2026.TEST.001"
    assert created["simulated"] is True

    r_upd = client.put(
        "/api/archive/dossiers/TN.2026.TEST.001",
        headers=admin_headers,
        json={"status": "Đã duyệt", "location": "Kho số 2 / Kệ A"},
    )
    assert r_upd.status_code == 200
    assert r_upd.json()["status"] == "Đã duyệt"
    assert r_upd.json()["location"] == "Kho số 2 / Kệ A"

    r_tpl = client.get("/api/archive/dossiers-template")
    assert r_tpl.status_code == 200
    assert r_tpl.content.startswith(b"\xef\xbb\xbf")
    assert "Mã hồ sơ" in r_tpl.content.decode("utf-8-sig")

    r_exp = client.get("/api/archive/dossiers-export", params={"file_codes": "TN.2026.TEST.001"})
    assert r_exp.status_code == 200
    assert r_exp.content.startswith(b"\xef\xbb\xbf")
    csv_text = r_exp.content.decode("utf-8-sig")
    assert "TN.2026.TEST.001" in csv_text
    assert "Đã duyệt" in csv_text

    r_imp = client.post(
        "/api/archive/dossiers/import",
        headers=admin_headers,
        json={
            "rows": [
                {
                    "Mã hồ sơ": "TN.2026.IMP.002",
                    "Tiêu đề hồ sơ": "Hồ sơ nhập từ Excel CSV mẫu",
                    "Phông lưu trữ": "P_SGD_TN",
                    "Trạng thái": "Chờ hiệu chỉnh",
                }
            ]
        },
    )
    assert r_imp.status_code == 200
    assert r_imp.json()["imported"] == 1

    r_del = client.delete("/api/archive/dossiers/TN.2026.TEST.001", headers=admin_headers)
    assert r_del.status_code == 200
    assert r_del.json()["deleted"] == "TN.2026.TEST.001"
    assert client.get("/api/archive/dossiers/TN.2026.TEST.001").status_code == 404
