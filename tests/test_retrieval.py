"""BM25, RRF (ví dụ tính tay k = 60) và tìm kiếm không dấu."""
import math

import pytest

from src.chunking import chunk_document
from src.retrieval import BM25, HybridIndex, rrf
from tests.fixtures import sample_pages


def test_rrf_hand_example():
    # Hệ 1 xếp [A, B, C], hệ 2 xếp [B, C, A] (A=0, B=1, C=2)
    fused = rrf([[0, 1, 2], [1, 2, 0]], k=60)
    assert fused[1] == pytest.approx(1 / 62 + 1 / 61)    # B: hạng 2 và hạng 1 → 0,032522
    assert fused[0] == pytest.approx(1 / 61 + 1 / 63)    # A: hạng 1 và hạng 3 → 0,032266
    assert fused[1] > fused[0] > fused[2]


def test_bm25_hand_example():
    docs = [["mèo", "đen"], ["chó", "vàng", "chó"], ["mèo", "vàng"]]
    bm = BM25(docs, k1=1.5, b=0.75)
    idf_meo = math.log(1 + (3 - 2 + 0.5) / (2 + 0.5))          # df = 2 → ln(1,6) = 0,4700
    avgdl = 7 / 3
    expected0 = idf_meo * 1 * 2.5 / (1 + 1.5 * (1 - 0.75 + 0.75 * 2 / avgdl))
    s = bm.scores(["mèo"])
    assert s[0] == pytest.approx(expected0) and s[1] == 0.0


def test_hybrid_search_finds_right_page_and_accentless():
    idx = HybridIndex([c for d in ("qd_125", "cv_4521")
                       for c in chunk_document([p for p in sample_pages() if p["doc_id"] == d])])
    top = idx.search("phun hóa chất diệt muỗi", k=3)[0]["chunk"]
    assert (top.doc_id, top.page_no) == ("cv_4521", 1)
    top = idx.search("phun hoa chat diet muoi", k=3)[0]["chunk"]
    assert top.doc_id == "cv_4521", "truy vấn không dấu dùng chỉ mục bỏ dấu"
    hits = idx.search("hội đồng tự giải thể", k=3, doc_ids={"cv_4521"})
    assert all(h["chunk"].doc_id == "cv_4521" for h in hits)


def test_unseen_token_gets_max_idf():
    idx = HybridIndex(chunk_document(sample_pages()[:1]))
    n = len(idx.chunks)
    assert idx.idf("xyzzy", False) == pytest.approx(math.log(1 + (n + 0.5) / 0.5))
