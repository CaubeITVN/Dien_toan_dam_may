"""Kiểm thử WP-B2: Lớp hồ sơ lưu trữ, đánh dấu mô phỏng và kiểm soát mức tiếp cận."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.archive import ArchiveManager, Dossier, is_access_allowed
from src.archive_qa import ChatSession, handle_archive_query
from src.qa import Assistant
from tests.fixtures import sample_pages
from web import app as web_app


def _build_temp_archive_manager(tmp_path: Path) -> ArchiveManager:
    """Tạo ArchiveManager giả lập gồm 1 hồ sơ Công khai (qd_125) và 1 hồ sơ Nội bộ (cv_4521)."""
    structure = {
        "portal_name": "Cổng Lưu trữ Mô phỏng",
        "fonds": [
            {
                "fond_id": "P_TEST",
                "fond_name": "Phông Kiểm thử",
                "agency_name": "Sở An Bình",
                "time_range": "2024",
                "description": "Phông dùng cho kiểm thử WP-B2.",
                "dossiers": [
                    {
                        "file_code": "AB.2024.P01.01.001",
                        "catalog_no": "01",
                        "title": "Hồ sơ thi học sinh giỏi cấp tỉnh năm 2024",
                        "retention_period": "20 năm",
                        "usage_mode": "Công khai",
                        "start_date": "01/01/2024",
                        "end_date": "31/12/2024",
                        "creator_unit": "Sở GD&ĐT An Bình",
                        "doc_ids": ["qd_125"],
                    },
                    {
                        "file_code": "AB.2024.P01.01.002",
                        "catalog_no": "01",
                        "title": "Hồ sơ phòng chống dịch nội bộ năm 2024",
                        "retention_period": "Vĩnh viễn",
                        "usage_mode": "Nội bộ",
                        "start_date": "01/08/2024",
                        "end_date": "31/12/2024",
                        "creator_unit": "UBND tỉnh An Bình",
                        "doc_ids": ["cv_4521"],
                    },
                ],
            }
        ],
    }
    path = tmp_path / "archive_structure.json"
    path.write_text(json.dumps(structure, ensure_ascii=False), encoding="utf-8")
    return ArchiveManager(structure_path=path)


def test_dossier_simulated_markers(tmp_path: Path):
    mgr = _build_temp_archive_manager(tmp_path)
    dos = mgr.dossiers["AB.2024.P01.01.001"]
    d = dos.to_dict()

    assert d["ho_so_id"] == "AB.2024.P01.01.001"
    assert d["simulated"] is True
    for field_name in ("file_code", "title", "retention_period", "usage_mode", "start_date", "end_date", "doc_ids"):
        assert field_name in d["simulated_fields"]

    info = mgr.get_doc_archive_info("qd_125")
    assert info["ho_so_id"] == "AB.2024.P01.01.001"
    assert info["simulated"] is True
    assert "usage_mode" in info["simulated_fields"]

    fallback_info = mgr.get_doc_archive_info("khong_ton_tai")
    assert fallback_info["ho_so_id"] == "CHUA_LAP_HO_SO"
    assert fallback_info["simulated"] is True


def test_is_access_allowed():
    assert is_access_allowed("Công khai", "public") is True
    assert is_access_allowed("Công khai", "internal") is True
    assert is_access_allowed("Công khai", "admin") is True

    for restricted_mode in ("Nội bộ", "Hạn chế", "Mật"):
        assert is_access_allowed(restricted_mode, "public") is False
        assert is_access_allowed(restricted_mode, "internal") is True
        assert is_access_allowed(restricted_mode, "admin") is True


def test_archive_qa_access_control(tmp_path: Path):
    mgr = _build_temp_archive_manager(tmp_path)
    assistant = Assistant(sample_pages())
    session = ChatSession(session_id="b2_qa")

    # Hỏi về văn bản thuộc hồ sơ Nội bộ với vai trò public -> bị từ chối
    res_denied = handle_archive_query(
        "Ai ký văn bản 4521/UBND-KGVX?",
        session=session,
        assistant=assistant,
        archive_mgr=mgr,
        file_code="AB.2024.P01.01.002",
        user_role="public",
    )
    assert res_denied["status"] == "refused"
    assert res_denied["kind"] == "access_denied"
    assert res_denied["access_denied"] is True
    assert "Nội bộ" in res_denied["text"]

    # Cùng truy vấn với vai trò internal -> được trả lời
    res_allowed = handle_archive_query(
        "Ai ký văn bản 4521/UBND-KGVX?",
        session=session,
        assistant=assistant,
        archive_mgr=mgr,
        file_code="AB.2024.P01.01.002",
        user_role="internal",
    )
    assert res_allowed["status"] == "answered"
    assert "Lê Thị Hoa" in res_allowed["text"]

    # Hỏi chi tiết hồ sơ Nội bộ với vai trò public -> bị từ chối
    res_dos_denied = handle_archive_query(
        "Hồ sơ AB.2024.P01.01.002 gồm những văn bản nào?",
        session=session,
        assistant=assistant,
        archive_mgr=mgr,
        user_role="public",
    )
    assert res_dos_denied["status"] == "refused"
    assert res_dos_denied["kind"] == "access_denied"


def test_web_endpoints_with_testclient(tmp_path: Path):
    import secrets
    import time
    from src.auth import PRESET_USERS, UserSession, get_auth_manager

    mgr = _build_temp_archive_manager(tmp_path)
    assistant = Assistant(sample_pages())
    auth_mgr = get_auth_manager()
    tok_internal = secrets.token_hex(16)
    tok_admin = secrets.token_hex(16)
    auth_mgr.active_sessions[tok_internal] = UserSession(
        token=tok_internal,
        username="internal_test",
        created_at=time.time(),
        user_info={"username": "internal_test", "role": "internal"},
    )
    auth_mgr.active_sessions[tok_admin] = UserSession(
        token=tok_admin,
        username="admin",
        created_at=time.time(),
        user_info=dict(PRESET_USERS["admin"]),
    )

    old_state = dict(web_app.state)
    web_app.state.clear()
    web_app.state.update(
        assistant=assistant,
        paths={},
        meta={"qd_125": {"group": "test", "split": "dev"}, "cv_4521": {"group": "test", "split": "dev"}},
        archive_mgr=mgr,
    )
    try:
        with TestClient(web_app.app) as client:
            # 1. Endpoint chi tiết hồ sơ có đánh dấu simulated và ho_so_id
            r_dos = client.get("/api/archive/dossiers/AB.2024.P01.01.001")
            assert r_dos.status_code == 200
            dos_data = r_dos.json()
            assert dos_data["ho_so_id"] == "AB.2024.P01.01.001"
            assert dos_data["simulated"] is True
            assert "usage_mode" in dos_data["simulated_fields"]

            # 1b. Văn bản nội bộ không lộ qua GET /api/docs hoặc /api/docs/{doc_id} nếu chưa đăng nhập
            assert [d["doc_id"] for d in client.get("/api/docs").json()] == ["qd_125"]
            assert client.get("/api/docs/cv_4521").status_code == 403

            # 2. Tìm kiếm lọc vào hồ sơ Nội bộ khi chưa có token (dù tự khai user_role=internal) -> vẫn ép public & bị chặn
            r_search_spoof = client.post(
                "/api/archive/search",
                json={"file_code": "AB.2024.P01.01.002", "user_role": "internal"},
            )
            assert r_search_spoof.status_code == 200
            s_denied = r_search_spoof.json()
            assert s_denied["status"] == "access_denied"
            assert s_denied["access_denied"] is True
            assert s_denied["total"] == 0
            assert s_denied["items"] == []

            # 3. Tìm kiếm hồ sơ Nội bộ có Bearer token internal -> thành công
            r_search_ok = client.post(
                "/api/archive/search",
                headers={"Authorization": f"Bearer {tok_internal}"},
                json={"file_code": "AB.2024.P01.01.002"},
            )
            assert r_search_ok.status_code == 200
            s_ok = r_search_ok.json()
            assert s_ok["total"] >= 1
            assert s_ok["items"][0]["doc_id"] == "cv_4521"

            # 4. Hỏi đáp lọc theo hồ sơ Nội bộ + năm 2024 với user_role=public (hoặc giả mạo không token) -> từ chối
            r_ask_denied = client.post(
                "/api/ask",
                json={
                    "question": "Ai ký văn bản phòng chống dịch?",
                    "file_code": "AB.2024.P01.01.002",
                    "year": "2024",
                    "user_role": "admin",
                },
            )
            assert r_ask_denied.status_code == 200
            a_denied = r_ask_denied.json()
            assert a_denied["status"] == "refused"
            assert a_denied["kind"] == "access_denied"

            # 5. Hỏi đáp có Bearer token admin -> trả lời được
            r_ask_ok = client.post(
                "/api/ask",
                headers={"Authorization": f"Bearer {tok_admin}"},
                json={
                    "question": "Ai ký văn bản phòng chống dịch?",
                    "file_code": "AB.2024.P01.01.002",
                    "year": "2024",
                },
            )
            assert r_ask_ok.status_code == 200
            a_ok = r_ask_ok.json()
            assert a_ok["status"] == "answered"
            assert "Lê Thị Hoa" in a_ok["text"]
    finally:
        auth_mgr.active_sessions.pop(tok_internal, None)
        auth_mgr.active_sessions.pop(tok_admin, None)
        web_app.state.clear()
        web_app.state.update(old_state)
