"""Kiểm thử điểm cuối giám sát đám mây (/healthz, /readyz, /api/cloud/*, /cloud) và CloudTelemetry."""
import secrets
import time

from fastapi.testclient import TestClient
import pymupdf
import pytest

from src.auth import PRESET_USERS, UserSession, get_auth_manager
from src.cloud_store import CloudStorageManager, reset_cloud_store
from src.qa import Assistant
from src.telemetry import reset_telemetry
from tests.fixtures import sample_pages
from web import app as web_app


def _make_pdf(path):
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 60), "Trang 1 mau", fontsize=10)
    doc.save(path)
    doc.close()


@pytest.fixture()
def cloud_client(tmp_path, monkeypatch):
    vol_dir = tmp_path / "vol"
    data_dir = tmp_path / "data"
    raw_dir = data_dir / "raw"
    data_dir.mkdir(parents=True)
    raw_dir.mkdir(parents=True)
    (data_dir / "archive_structure.json").write_text('{"portal_name": "Cloud", "fonds": []}', encoding="utf-8")

    # Đặt PDF chỉ trong Cloud Volume để test lazy-fetch qua endpoint ảnh/PDF
    (vol_dir / "raw").mkdir(parents=True)
    _make_pdf(vol_dir / "raw" / "qd_125.pdf")

    monkeypatch.setattr(web_app, "DATA_DIR", data_dir)
    monkeypatch.setattr(web_app, "RAW_DIR", raw_dir)
    monkeypatch.setattr(web_app, "UPLOAD_DIR", data_dir / "uploads")
    monkeypatch.setattr(web_app, "OCR_DIR", data_dir / "ocr")

    reset_telemetry()
    reset_cloud_store(CloudStorageManager(volume_dir=vol_dir))

    web_app.state.clear()
    web_app.state.update(
        assistant=Assistant([p for p in sample_pages() if p["doc_id"] == "qd_125"]),
        paths={},
        meta={"qd_125": {"group": "test", "split": "dev"}},
    )
    web_app.render_png.cache_clear()
    with TestClient(web_app.app) as c:
        yield c
    web_app.state.clear()
    reset_cloud_store(CloudStorageManager())


def test_healthz_readyz_and_cloud_dashboard(cloud_client):
    hz = cloud_client.get("/healthz")
    assert hz.status_code == 200 and hz.json()["status"] == "ok"

    rz = cloud_client.get("/readyz")
    assert rz.status_code == 200
    assert rz.json()["ready"] is True
    assert rz.json()["storage_backend"] == "local_volume"
    assert rz.json()["storage_durable"] is True

    page = cloud_client.get("/cloud")
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert "Hạ tầng" in page.text

    st = cloud_client.get("/api/cloud/status")
    assert st.status_code == 200
    body = st.json()
    assert body["storage"]["backend"] == "local_volume"
    assert body["telemetry"]["http"]["total_requests"] >= 3
    assert body["corpus"]["n_docs"] == 1


def test_cloud_sync_requires_admin_and_lazy_fetch_pdf(cloud_client, monkeypatch):
    # Chưa đăng nhập bị chặn 401
    unauth = cloud_client.post("/api/cloud/sync", json={"action": "push"})
    assert unauth.status_code == 401

    tok = secrets.token_hex(16)
    mgr = get_auth_manager()
    monkeypatch.setitem(
        mgr.active_sessions,
        tok,
        UserSession(token=tok, username="admin", created_at=time.time(), user_info=dict(PRESET_USERS["admin"])),
    )
    ok = cloud_client.post(
        "/api/cloud/sync",
        json={"action": "push"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert ok.status_code == 200
    assert ok.json()["result"]["durable"] is True

    # Kiểm chứng lazy-fetch PDF từ Cloud Volume khi chưa có trong container local
    pdf_resp = cloud_client.get("/api/docs/qd_125/pdf")
    assert pdf_resp.status_code == 200 and pdf_resp.content.startswith(b"%PDF")
    img_resp = cloud_client.get("/api/page/qd_125/1.png")
    assert img_resp.status_code == 200 and img_resp.content.startswith(b"\x89PNG")
