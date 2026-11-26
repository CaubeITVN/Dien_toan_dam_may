"""Kiểm tra src/clean.py trên văn bản tự tạo, mô phỏng các lỗi OCR đã gặp trên kho thật."""
from src.clean import clean_page, junk_rule, should_join


def test_signature_stamp_lines_from_ocr_removed():
    assert junk_rule("“2 Người ký: CỤC THÔNG TIN VÀ TRUYỀN THÔNG CHÍNH PHỦ ù ò Email: a@b.vn") == "signature_stamp"
    assert junk_rule("V7 Cơ quan: VĂN PHÒNG CHÍNH PHỦ") == "signature_stamp"
    assert junk_rule("Z Thời gian ký: 09.10.2026 15:52:30 +07:00") == "signature_stamp"
    assert junk_rule("s Cơ quan phát hành: VĂN PHÒNG CHÍNH PHỦ") == "signature_stamp"
    assert junk_rule("Cơ quan, đơn vị phải báo cáo kết quả thực hiện trước ngày 30/6/2026.") is None
    assert junk_rule("Giao cơ quan: các bộ, ngành chủ trì thực hiện nhiệm vụ được giao tại Nghị quyết này") is None

RAW = "\n".join([
    "Ký bởi: SỞ GIÁO DỤC VÀ ĐÀO TẠO",
    "Kỳ bở 52001222000 200 Thoi Thai Nguyên",
    "is",
    "sper",                     # 4 chữ cái: luật "short" cố ý không bỏ (hạn chế đã biết)
    "UBND TỈNH THÁI NGUYÊN",
    "SỞ GIÁO DỤC VÀ ĐẠO TẠO",
    "Số: 3L/BC-SGD&ĐT",
    "Thái Nguyên, ngày 16 tháng Jnăm 2015",
    "Căn cứ công văn số 677/SGDĐT-GDTrH ngày 23/6/2014 của Sở Giáo dục và Đạo",
    "tạo về việc tổ chức thi khảo sát cho học sinh lớp 6, 10 năm học",
    "2015-2016;",
    "Điều 2, Hội đồng có trách nhiệm thực hiện đúng quy trình.",
    "001000000119",
    "THU THU THU THU THU",
    "19",
    "Nơi nhân:",
    "- Như Điều 3;",
    "1.",
])


def test_clean_page_end_to_end():
    res = clean_page(RAW, max_year=2026)
    lines = res.text.split("\n")
    assert lines == [
        "sper",
        "UBND TỈNH THÁI NGUYÊN",
        "SỞ GIÁO DỤC VÀ ĐÀO TẠO",
        "Số: 3L/BC-SGD&ĐT",                                   # số ký hiệu sai vẫn giữ nguyên, không đoán
        "Thái Nguyên, ngày 16 tháng Jnăm 2015",               # không bịa ra số tháng
        "Căn cứ công văn số 677/SGDĐT-GDTrH ngày 23/6/2014 của Sở Giáo dục và Đào tạo về việc tổ chức "
        "thi khảo sát cho học sinh lớp 6, 10 năm học 2015-2016;",
        "Điều 2. Hội đồng có trách nhiệm thực hiện đúng quy trình.",
        "Nơi nhận:",
        "- Như Điều 3;",
        "1.",
    ]
    dropped = {c.rule: c.before for c in res.changes if c.after == ""}
    assert dropped["digit_noise"] == "001000000119" and dropped["repeat"].startswith("THU")
    assert {c.rule for c in res.changes} >= {"signature", "short", "phrase", "article_comma", "join_lines"}
    assert [f.rule for f in res.flags] == ["glued_date_word"]


def test_junk_rule_keeps_real_content():
    assert junk_rule("Kỳ bở 52001222.000 Thoi Thoi Nguyên") == "signature"
    assert junk_rule("Giờ ký: 02.06.2026 22:03:59+07:00") == "signature"
    assert junk_rule("Kỳ báo cáo: 6 tháng đầu năm") is None
    assert junk_rule("0 0 0 0 0") is None, "hàng số trong bảng là nội dung"
    assert junk_rule("Tổng kinh phí: 1.250.000 đồng") is None
    assert junk_rule("a)") is None and junk_rule("I.") is None
    assert junk_rule("is") == "short"


def test_should_join_rules():
    assert should_join("của Sở Giáo dục và", "tạo về việc")
    assert should_join("từ ngày 17 tháng 7 năm", "2015 đến ngày 21")
    assert not should_join("QUYẾT ĐỊNH:", "Điều 1. Thành lập")
    assert not should_join("đơn vị thuộc tỉnh", "a) Thực hiện")
    assert not should_join("Chủ tịch hội đồng", "1. Ông A")
    assert not should_join("UBND TỈNH THÁI NGUYÊN", "SỞ GIÁO DỤC VÀ ĐÀO TẠO")


def test_normalize_is_logged():
    res = clean_page("Việt  Nam mới")       # NFD + khoảng trắng thừa + dấu cách không ngắt
    assert res.text == "Việt Nam mới"
    assert [(c.rule, c.after) for c in res.changes] == [("normalize", "Việt Nam mới")]


def test_year_out_of_range_flagged_not_fixed():
    res = clean_page("Ngày 03/06/0009 và ngày 01 tháng 01 năm 2015.", max_year=2026)
    assert "03/06/0009" in res.text
    assert [(f.rule, f.text) for f in res.flags] == [("year_out_of_range", "03/06/0009")]
