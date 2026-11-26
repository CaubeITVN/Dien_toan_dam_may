"""Xử lý chuỗi tiếng Việt dùng chung: chuẩn hóa Unicode, bỏ dấu, tách token."""
import re
import unicodedata

# Khoảng trắng "lạ" hay gặp khi trích chữ từ PDF: không ngắt, rộng hẹp khác nhau, độ rộng 0
_ODD_SPACES = re.compile(r"[  -   　]")
_ZERO_WIDTH = re.compile(r"[​-‍﻿]")
_MULTI_SPACE = re.compile(r"[ \t]+")

# Thứ tự nhánh quan trọng: số ký hiệu/ngày trước, rồi từ (cho phép V/v, SGD&ĐT), cuối cùng là dấu câu
_TOKEN_RE = re.compile(
    r"\d+(?:[/.\-]\d+)*(?:/[\w&\-]+)*"   # 1425/QĐ-SGDĐT, 02/06/2025, 3.1
    r"|\w+(?:[/&\-]\w+)*"                 # Số, V/v, SGD&ĐT, Covid-19
    r"|[^\w\s]"                           # dấu câu đứng riêng
)


def normalize_text(s: str) -> str:
    """Đưa về NFC, thay khoảng trắng lạ bằng dấu cách, gộp dấu cách thừa trong từng dòng.

    Giữ nguyên xuống dòng vì bố cục dòng có ý nghĩa với văn bản hành chính.
    """
    s = unicodedata.normalize("NFC", s)
    s = _ZERO_WIDTH.sub("", s)
    s = _ODD_SPACES.sub(" ", s)
    lines = [_MULTI_SPACE.sub(" ", line).strip() for line in s.split("\n")]
    return "\n".join(lines)


def remove_diacritics(s: str) -> str:
    """Bỏ dấu tiếng Việt: tách dấu (NFD), xóa ký tự dấu (loại Mn), đổi đ/Đ thành d/D."""
    decomposed = unicodedata.normalize("NFD", s)
    no_marks = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", no_marks.replace("đ", "d").replace("Đ", "D"))


def tokenize(s: str) -> list[str]:
    """Tách token mức âm tiết/ký hiệu, giữ nguyên số ký hiệu văn bản và ngày thành một token."""
    return _TOKEN_RE.findall(normalize_text(s))


# Từ điển từ viết tắt và từ đồng nghĩa hành chính chuẩn
ADMIN_SYNONYMS = {
    "ubnd": "ủy ban nhân dân",
    "hđnd": "hội đồng nhân dân",
    "hdnd": "hội đồng nhân dân",
    "bgdđt": "bộ giáo dục và đào tạo",
    "bgddt": "bộ giáo dục và đào tạo",
    "sgdđt": "sở giáo dục và đào tạo",
    "sgddt": "sở giáo dục và đào tạo",
    "btc": "bộ tài chính",
    "bct": "bộ công thương",
    "bnv": "bộ nội vụ",
    "bxd": "bộ xây dựng",
    "bgtvt": "bộ giao thông vận tải",
    "nhnn": "ngân hàng nhà nước",
    "ttg": "thủ tướng chính phủ",
    "vpcp": "văn phòng chính phủ",
    "thcs": "trung học cơ sở",
    "thpt": "trung học phổ thông",
    "gdtx": "giáo dục thường xuyên",
    "tnhh": "trách nhiệm hữu hạn",
    "bhxh": "bảo hiểm xã hội",
    "tthc": "thủ tục hành chính",
    "cbcc": "cán bộ công chức",
    "ccvc": "công chức viên chức",
    "clv": "campuchia lào việt nam",
}


def expand_admin_terms(text: str) -> list[str]:
    """Mở rộng câu truy vấn bằng cách thay các từ viết tắt hành chính thành dạng đầy đủ."""
    words = text.split()
    expanded = []
    has_match = False
    for w in words:
        w_lower = remove_diacritics(w).lower().strip(".,;:?!()")
        if w_lower in ADMIN_SYNONYMS:
            expanded.append(ADMIN_SYNONYMS[w_lower])
            has_match = True
        else:
            expanded.append(w)
    return [" ".join(expanded)] if has_match else []

