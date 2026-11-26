"""Bộ kiểm câu trả lời của LLM (không cần mô hình thật)."""
from src.llm import build_messages, verify_answer

SOURCES = [
    {"label": "Quyết định 125, trang 1", "text": "Hội đồng chấm thi gồm 25 thành viên, hoàn thành trước ngày 30/3/2024."},
    {"label": "Công văn 4521, trang 1", "text": "Phun hóa chất diệt muỗi trong vòng 48 giờ kể từ khi phát hiện ca bệnh."},
]


def test_build_messages_numbers_sources():
    msgs = build_messages("Hỏi gì?", SOURCES)
    assert msgs[0]["role"] == "system" and "[1] (Quyết định 125, trang 1)" in msgs[1]["content"]
    assert "[2] (Công văn 4521, trang 1)" in msgs[1]["content"]


def test_marked_sentence_checked_against_its_own_source():
    out = verify_answer("Phun hóa chất diệt muỗi trong vòng 48 giờ [1].", SOURCES, set())
    assert not out[0].kept, "câu đúng nội dung nhưng dẫn sai nguồn [1] phải bị cắt"
    out = verify_answer("Phun hóa chất diệt muỗi trong vòng 48 giờ [2].", SOURCES, set())
    assert out[0].kept and out[0].sources == [2]


def test_unmarked_sentence_auto_cited_to_best_source():
    out = verify_answer("Hội đồng chấm thi gồm 25 thành viên.", SOURCES, set())
    assert out[0].kept and out[0].auto_cited and out[0].sources == [1]


def test_invented_number_and_unsupported_sentence_dropped():
    out = verify_answer("Hội đồng gồm 30 thành viên [1]. Ngân sách tỉnh cấp đủ kinh phí cho năm sau [1].", SOURCES, set())
    assert [s.kept for s in out] == [False, False]
    assert "con số" in out[0].reason and "từ khóa" in out[1].reason


def test_markdown_headings_and_numbering_are_not_points():
    out = verify_answer("**Nội dung chính:**\n1. Hội đồng chấm thi gồm 25 thành viên [1].\n2.", SOURCES, set())
    kept = [s for s in out if s.kept]
    assert [s.text for s in kept] == ["Hội đồng chấm thi gồm 25 thành viên."]


def test_year_range_matches_spaced_source():
    src = [{"label": "x", "text": "Kế hoạch năm học 2009 - 2010 của Sở Giáo dục và Đào tạo."}]
    assert verify_answer("Kế hoạch năm học 2009-2010 của Sở [1].", src, set())[0].kept


def test_out_of_range_marker_treated_as_unmarked():
    out = verify_answer("Hội đồng chấm thi gồm 25 thành viên [7].", SOURCES, set())
    assert out[0].kept and out[0].auto_cited


def test_openrouter_error_falls_back_to_local_llm(monkeypatch):
    from src.llm import LocalLLM

    llm = LocalLLM(provider="openrouter", model_id="nvidia/nemotron-3-ultra-550b-a55b:free")
    monkeypatch.setattr(llm, "_call_openrouter", lambda msgs, max_new_tokens=280: (_ for _ in ()).throw(RuntimeError("OpenRouter HTTP 400")))
    monkeypatch.setattr(llm, "is_local_downloaded", lambda: True)
    monkeypatch.setattr(llm, "_call_local", lambda msgs, max_new_tokens=280: {"text": "Trả lời cục bộ [1].", "provider": "local", "model": llm.local_model})

    out = llm([{"role": "user", "content": "test"}])
    assert out["provider"] == "local"
    assert out["model"] == llm.local_model
    assert out["fallback_from"] == "openrouter"
    assert "400" in out["fallback_reason"]


def test_openrouter_error_reraises_when_no_local_model(monkeypatch):
    import pytest
    from src.llm import LocalLLM

    llm = LocalLLM(provider="openrouter", model_id="nvidia/nemotron-3-ultra-550b-a55b:free")
    monkeypatch.setattr(llm, "_call_openrouter", lambda msgs, max_new_tokens=280: (_ for _ in ()).throw(RuntimeError("OpenRouter HTTP 503")))
    monkeypatch.setattr(llm, "is_local_downloaded", lambda: False)

    with pytest.raises(RuntimeError, match="503"):
        llm([{"role": "user", "content": "test"}])
