"""Kiểm thử tính năng Quản lý Lưu trữ số hóa, Tra cứu đa tiêu chí và Chatbot RAG.

Tuân thủ Thông tư 02/2019/TT-BNV, Nghị định 30/2020/NĐ-CP và mô hình Cổng Thái Nguyên.
"""
import pytest

from src.archive import ArchiveManager, get_archive_manager
from src.archive_qa import get_session_manager, handle_archive_query
from src.archive_search import SearchFilter, faceted_search
from src.qa import Assistant
from tests.fixtures import sample_pages
from web import app as web_app


@pytest.fixture
def test_assistant():
    return Assistant(sample_pages())


def test_archive_structure_loading():
    mgr = get_archive_manager()
    assert len(mgr.fonds) >= 3
    assert len(mgr.dossiers) >= 10
    assert "P_UBND_TN" in mgr.fonds
    assert "P_SGD_TN" in mgr.fonds
    assert "P_TW_APPLY" in mgr.fonds

    # Kiểm tra hồ sơ cụ thể của Thái Nguyên
    dos = mgr.dossiers.get("UBNDTN.2026.P01.01.001")
    assert dos is not None
    assert "Chuyển đổi số" in dos.title
    assert dos.retention_period == "Vĩnh viễn"
    assert dos.fond_id == "P_UBND_TN"


def test_doc_archive_info_mapping():
    mgr = get_archive_manager()
    info = mgr.get_doc_archive_info("tn_297093")
    assert info["fond_id"] == "P_UBND_TN"
    assert info["file_code"] == "UBNDTN.2026.P01.01.001"
    assert info["retention_period"] == "Vĩnh viễn"

    # Kiểm tra văn bản Sở GD&ĐT scan
    sgd_info = mgr.get_doc_archive_info("Bao_cao_TTTN_07")
    assert sgd_info["fond_id"] == "P_SGD_TN"
    assert sgd_info["retention_period"] == "20 năm"


def test_faceted_search(test_assistant):
    mgr = get_archive_manager()

    # 1. Lọc theo Phông
    f1 = SearchFilter(fond_id="P_SGD_TN")
    r1 = faceted_search(test_assistant, f1, mgr)
    assert r1["total"] >= 0

    # 2. Lọc theo từ khóa toàn văn
    f2 = SearchFilter(query="học sinh giỏi")
    r2 = faceted_search(test_assistant, f2, mgr)
    assert r2["total"] >= 1
    assert any("qd_125" in item["doc_id"] for item in r2["items"])

    # 3. Facets được tổng hợp đầy đủ
    assert "doc_types" in r2["facets"]
    assert "fonds" in r2["facets"]


def test_content_passage_search(test_assistant):
    mgr = get_archive_manager()
    f = SearchFilter(query="học sinh giỏi", search_mode="content")
    res = faceted_search(test_assistant, f, mgr)
    assert res["total"] >= 1
    assert "items" in res
    first_item = res["items"][0]
    assert first_item["page_no"] >= 1
    assert "snippet_html" in first_item
    assert "kw-highlight" in first_item["snippet_html"]


def test_archive_qa_intents(test_assistant):
    mgr = get_archive_manager()
    session = get_session_manager().get_or_create("test_session_123")

    # Intent 1: Thủ tục trích lục lưu trữ Thái Nguyên
    r_proc = handle_archive_query(
        "Thủ tục xin cấp bản sao trích lục hồ sơ lưu trữ tại Thái Nguyên?",
        session=session,
        assistant=test_assistant,
        archive_mgr=mgr,
    )
    assert r_proc["status"] == "answered"
    assert r_proc["kind"] == "procedure"
    assert "Trung tâm Lưu trữ Lịch sử" in r_proc["text"]

    # Intent 2: Danh mục Phông lưu trữ
    r_fonds = handle_archive_query(
        "Có những phông lưu trữ nào đang được quản lý?",
        session=session,
        assistant=test_assistant,
        archive_mgr=mgr,
    )
    assert r_fonds["status"] == "answered"
    assert r_fonds["kind"] == "archive_catalog"
    assert "P_UBND_TN" in r_fonds["text"]

    # Intent 3: Hỏi nội dung văn bản cụ thể kèm liên kết đa vòng
    r_doc = handle_archive_query(
        "Ai ký Quyết định 125/QĐ-SGDĐT?",
        session=session,
        assistant=test_assistant,
        archive_mgr=mgr,
    )
    assert r_doc["status"] == "answered"
    assert "Trần Văn Bình" in r_doc["text"]
    assert session.active_doc_id == "qd_125"

    # Multi-turn: Hỏi tiếp về ngày ban hành mà không nhắc lại số hiệu
    r_next = handle_archive_query(
        "Văn bản này ban hành khi nào?",
        session=session,
        assistant=test_assistant,
        archive_mgr=mgr,
    )
    assert r_next["status"] == "answered"
    assert "05/03/2024" in r_next["text"]


def test_web_app_archive_integration():
    web_app.state.clear()
    web_app.state.update(
        assistant=Assistant(sample_pages()),
        paths={},
        meta={"qd_125": {"group": "test", "split": "dev"}},
    )

    tree = web_app.archive_tree()
    assert len(tree) >= 3

    # Tra cứu hồ sơ
    dos = web_app.get_dossier("UBNDTN.2026.P01.01.001")
    assert dos["file_code"] == "UBNDTN.2026.P01.01.001"
    assert "documents" in dos

    # API Tra cứu đa tiêu chí
    search_req = web_app.FacetedSearchRequest(query="thành lập Hội đồng", doc_type="Quyết định")
    res = web_app.search_archive(search_req)
    assert res["total"] >= 1

    # API Hỏi đáp
    ask_req = web_app.AskRequest(question="Quy trình nộp lưu tài liệu theo Thông tư 02/2019/TT-BNV?")
    ans = web_app.ask_post(ask_req)
    assert ans["status"] == "answered"
    assert ans["kind"] == "procedure"
