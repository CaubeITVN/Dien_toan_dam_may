"""Tóm tắt có trích dẫn: chọn đoạn MMR, LLM giả, kiểm từng ý, quay về tóm tắt trích."""
import pytest

from src import summarize
from src.qa import Assistant
from tests.fixtures import sample_pages


@pytest.fixture()
def assistant(tmp_path, monkeypatch):
    monkeypatch.setattr(summarize, "SUMMARY_DIR", tmp_path / "summaries")
    return Assistant(sample_pages())


class FakeLLM:
    model_id = "fake/llm"

    def __init__(self, text):
        self.text, self.calls = text, 0

    def __call__(self, messages, max_new_tokens=None):
        self.calls += 1
        assert "thẻ thông tin văn bản" in messages[-1]["content"], "thẻ thông tin là một nguồn đánh số"
        return {"text": self.text, "seconds": 0.1, "new_tokens": 10}


def test_extractive_summary_has_page_citations(assistant):
    s = summarize.summarize_doc(assistant, "qd_125")
    assert s["kind"] == "extractive" and s["points"]
    for p in s["points"]:
        assert p["sources"] and all(1 <= n <= len(s["citations"]) for n in p["sources"])
    assert {c["doc_id"] for c in s["citations"]} == {"qd_125"}


def test_llm_summary_keeps_grounded_points_only(assistant):
    # Câu không ghi [n]: bộ kiểm tự gán nguồn khớp nhất; câu có số 40 không có trong nguồn nào phải bị cắt
    fake = FakeLLM("**Tóm tắt:**\n1. Thành lập Hội đồng chấm thi học sinh giỏi cấp tỉnh gồm 25 thành viên.\n"
                   "2. Hội đồng chấm thi gồm 40 thành viên.\n- Quyết định do Sở Giáo dục và Đào tạo ban hành [1].\n"
                   "- Nội dung chính:")
    s = summarize.summarize_doc(assistant, "qd_125", fake)
    texts = [p["text"] for p in s["points"]]
    assert s["kind"] == "llm" and len(texts) == 2
    assert any("25 thành viên" in t for t in texts) and not any("40" in t for t in texts)
    reasons = " | ".join(d["reason"] for d in s["meta"]["dropped"])
    assert "con số" in reasons and ("quá ngắn" in reasons or "dẫn nhập" in reasons)
    assert "**" not in " ".join(texts)


def test_summary_cached_and_falls_back(assistant):
    bad = FakeLLM("Bịa hoàn toàn chuyện khác [1].")
    s = summarize.summarize_doc(assistant, "qd_125", bad)
    assert s["kind"] == "extractive" and s["meta"]["fallback"]
    s2 = summarize.summarize_doc(assistant, "qd_125", bad)
    assert bad.calls == 1 and s2["key"] == s["key"], "lần hai đọc cache, không gọi lại LLM"


def test_chat_summary_intent(assistant):
    ans = assistant.ask("Tóm tắt Quyết định 125/QĐ-SGDĐT")
    assert ans.status == "answered" and ans.kind == "summary"
    assert ans.text.startswith("Tóm tắt Quyết định 125/QĐ-SGDĐT") and "[1]" in ans.text
    assert assistant.ask("tóm tắt giúp tôi", doc_ids={"cv_4521"}).citations[0]["doc_id"] == "cv_4521"
