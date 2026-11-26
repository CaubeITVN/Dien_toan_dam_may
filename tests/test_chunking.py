"""T10: đoạn không vắt qua trang; mục kế thừa qua trang; vị trí ký tự đúng."""
from src.chunking import chunk_document, chunk_page
from tests.fixtures import DECISION_P1, DECISION_P2, pages_of


def test_article_spanning_two_pages_gives_two_chunks():
    chunks = chunk_document(pages_of("qd", [DECISION_P1, DECISION_P2]))
    art2 = [c for c in chunks if c.section == "Điều 2"]
    assert [c.page_no for c in art2] == [1, 2], "Điều 2 vắt trang → 2 đoạn, trang 1 và trang 2"
    assert art2[1].text.startswith("Hội đồng tự giải thể")


def test_chunk_spans_match_page_text():
    pages = pages_of("qd", [DECISION_P1, DECISION_P2])
    for c in chunk_document(pages):
        assert pages[c.page_no - 1]["text"][c.start:c.end] == c.text


def test_max_chars_respected_for_long_line():
    text = "Điều 1. " + "chữ " * 600
    chunks, _ = chunk_page("x", 1, text, max_chars=300)
    assert len(chunks) >= 7 and all(len(c.text) <= 300 for c in chunks)
    assert all(c.section == "Điều 1" for c in chunks)


def test_missing_pages_are_skipped():
    pages = pages_of("qd", [DECISION_P1, ""])
    assert {c.page_no for c in chunk_document(pages)} == {1}


def test_dieu_khoan_chunking_with_metadata_prefix():
    text = (
        "QUYẾT ĐỊNH\nSố: 99/QĐ-UBND\n"
        "Điều 1. Quy định chung.\n"
        "1. Phạm vi điều chỉnh của văn bản này.\n"
        "2. Đối tượng áp dụng gồm các đơn vị trực thuộc.\n"
        "Điều 2. Tổ chức thực hiện."
    )
    pages = [{"doc_id": "qd_99", "page_no": 1, "text": text}]
    chunks = chunk_document(pages, strategy="dieu_khoan", include_metadata_prefix=True)
    sections = [c.section for c in chunks]
    assert "Điều 1 · Khoản 1" in sections
    assert "Điều 1 · Khoản 2" in sections
    assert "Điều 2" in sections
    for c in chunks:
        assert "doc_type=Quyết Định" in c.index_text
        assert "doc_number=99/QĐ-UBND" in c.index_text
        assert "doc_id=qd_99" in c.index_text
        assert "page_no=1" in c.index_text
        assert text[c.start:c.end] == c.text


def test_parent_child_chunking_keeps_parent_context():
    long_art = "Điều 1. " + "\n".join(f"{i}. Nội dung khoản số {i} rất dài để tách thành nhiều đoạn con." for i in range(1, 12))
    pages = [{"doc_id": "cv_10", "page_no": 1, "text": long_art}]
    children = chunk_document(
        pages,
        strategy="parent_child",
        include_metadata_prefix=True,
        doc_meta={"doc_type": "Công Văn", "doc_number": "10/SYT"},
        max_chars=900,
        child_max_chars=160,
        child_min_chars=40,
    )
    assert len(children) >= 2
    for c in children:
        assert len(c.text) <= 160
        assert c.parent_id != ""
        assert c.text in c.parent_text
        assert "doc_type=Công Văn" in c.index_text
        assert "doc_number=10/SYT" in c.index_text
