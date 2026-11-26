"""Làm sạch văn bản OCR của một trang; mọi thay đổi đều ghi nhật ký (rule, before, after).

Nguyên tắc: chỉ bỏ dòng rác và sửa lỗi chắc chắn. KHÔNG đoán chữ số trong số ký hiệu, ngày, số tiền:
chỗ đáng ngờ thì giữ nguyên và gắn cờ. Luật phải tổng quát, không có nhánh theo tên văn bản.
"""
import re
from dataclasses import dataclass, field
from datetime import date

from src.pdf_io import SIGNATURE_LINE
from src.text import normalize_text

# Vị trí ký tự trong bộ vàng trường thông tin tính trên văn bản đã làm sạch: đổi luật thì tăng số này
CLEAN_VERSION = "2"     # 2: thêm luật signature_stamp (khối chữ ký số in trên ảnh, Tesseract đọc ra)

# Dấu chữ ký số bị OCR đọc lệch: "Kỳ bở 52001222.000 …", "Giờ kỷ …"; khớp lỏng phần nhãn ở đầu dòng
_FUZZY_SIGNATURE = re.compile(r"^(K[ýỳỷỹy]\s*b[ởơờớo]\w?|Gi[ờơớo]\s*k[ýỳỷy])\b", re.IGNORECASE)
# Khối chữ ký số của cổng in trên ẢNH trang scan; OCR đọc ra kèm rác đầu dòng ("“2 Người ký: CỤC …"):
# nhãn riêng của khối chữ ký ở BẤT KỲ đâu trong dòng, thư điện tử, hoặc "Cơ quan: <TÊN IN HOA>" trên dòng ngắn
_SIGNATURE_STAMP = re.compile(
    r"(Người ký|Ký bởi|Giờ ký|Thời gian ký|Cơ quan phát hành)\s*:|Email\s*:\s*\S+@\S+", re.IGNORECASE)
_STAMP_AGENCY = re.compile(r"Cơ quan\s*:\s*[A-ZĐÀ-Ỹ]{2,}")
MAX_STAMP_AGENCY_CHARS = 70
# Dòng chỉ gồm số, có một dãy từ 9 chữ số liền trở lên (mã chứng thư, nhiễu con dấu)
_DIGIT_NOISE = re.compile(r"^[\d\s.]*\d{9,}[\d\s.]*$")
# Một từ (≥ 2 chữ cái) lặp từ 4 lần liền trở lên: ảo giác của bộ nhận dạng ("THU THU THU THU").
# Không tính số: hàng bảng "0 0 0 0" là nội dung thật
_REPEAT = re.compile(r"\b([^\W\d_]{2,})(?:\s+\1\b){3,}")
# Dòng ngắn nhưng có nghĩa: đề mục "I.", "1.", "a)"
_HEADING_MARK = re.compile(r"^([IVXLC]+\.|\d+\.|[a-zđ]\))$")
MAX_SHORT_CHARS = 2

# Lỗi OCR của cụm từ cố định trong văn bản hành chính; cụm đủ dài để không sửa nhầm chữ đúng
PHRASE_FIXES = {
    "Đạo tạo": "Đào tạo",
    "ĐẠO TẠO": "ĐÀO TẠO",
    "Nơi nhân:": "Nơi nhận:",
    "cống cụ": "công cụ",
    "ông (bả)": "ông (bà)",
}
# "Điều 2, Hội đồng…" → "Điều 2. Hội đồng…" (chỉ ở đầu dòng)
_ARTICLE_COMMA = re.compile(r"^(Điều \d+),\s")

# Nối dòng: dòng trước chưa hết câu và dòng sau không mở đầu một thành phần cấu trúc
_SENTENCE_END = re.compile(r"[.;:!?]$")
_STRUCT_START = re.compile(r"^(Điều|Chương|Mục|Phần|Căn cứ|Nơi nhận|[-–•+*]|\d+[.)]|[a-zđ]\))")

# Cờ (không sửa): chữ cái dính trước "năm"/"tháng" ("tháng Jnăm"), năm ngoài khoảng hợp lệ
_GLUED_DATE_WORD = re.compile(r"[^\W\d_](năm|tháng)\b", re.IGNORECASE)
_YEAR_IN_DATE = re.compile(r"\b\d{1,2}/\d{1,2}/(\d{1,4})\b|\btháng \d{1,2} năm (\d{1,4})\b", re.IGNORECASE)
MIN_YEAR = 1945


@dataclass
class Change:
    rule: str
    before: str
    after: str          # "" khi bỏ cả dòng


@dataclass
class Flag:
    rule: str
    text: str           # đoạn đáng ngờ, giữ nguyên trong văn bản


@dataclass
class CleanResult:
    text: str
    changes: list[Change] = field(default_factory=list)
    flags: list[Flag] = field(default_factory=list)


def junk_rule(line: str) -> str | None:
    """Tên luật nếu cả dòng là rác, ngược lại None."""
    if SIGNATURE_LINE.match(line) or _FUZZY_SIGNATURE.match(line):
        return "signature"
    if _SIGNATURE_STAMP.search(line) or (len(line) <= MAX_STAMP_AGENCY_CHARS and _STAMP_AGENCY.search(line)):
        return "signature_stamp"
    if _DIGIT_NOISE.match(line):
        return "digit_noise"
    if _REPEAT.search(line):
        return "repeat"
    if len(line.replace(" ", "")) <= MAX_SHORT_CHARS and not _HEADING_MARK.match(line):
        return "short"
    return None


def fix_line(line: str, changes: list[Change]) -> str:
    """Sửa lỗi chắc chắn trong một dòng, ghi từng lần sửa vào `changes`."""
    for wrong, right in PHRASE_FIXES.items():
        if wrong in line:
            fixed = line.replace(wrong, right)
            changes.append(Change("phrase", line, fixed))
            line = fixed
    fixed = _ARTICLE_COMMA.sub(r"\1. ", line)
    if fixed != line:
        changes.append(Change("article_comma", line, fixed))
    return fixed


def should_join(cur: str, nxt: str) -> bool:
    """Dòng sau là phần tiếp của câu đang dở: bắt đầu bằng chữ thường hoặc chữ số (không phải số mục)."""
    if _SENTENCE_END.search(cur) or _STRUCT_START.match(nxt):
        return False
    return nxt[0].islower() or nxt[0].isdigit()


def find_flags(text: str, max_year: int) -> list[Flag]:
    flags = [Flag("glued_date_word", m.group(0)) for m in _GLUED_DATE_WORD.finditer(text)]
    for m in _YEAR_IN_DATE.finditer(text):
        year = int(m.group(1) or m.group(2))
        if not MIN_YEAR <= year <= max_year:
            flags.append(Flag("year_out_of_range", m.group(0)))
    return flags


def clean_page(text: str, max_year: int | None = None) -> CleanResult:
    """Làm sạch một trang: bỏ dòng rác → nối dòng bị ngắt → sửa lỗi chắc chắn → gắn cờ chỗ đáng ngờ.

    Sửa sau khi nối để bắt được cụm bị ngắt dòng ("Đạo⏎tạo").
    """
    max_year = max_year or date.today().year
    changes: list[Change] = []
    joined: list[str] = []
    for raw_line in text.split("\n"):
        line = normalize_text(raw_line)
        if not line:
            continue
        if line != raw_line:
            changes.append(Change("normalize", raw_line, line))
        rule = junk_rule(line)
        if rule:
            changes.append(Change(rule, line, ""))
        elif joined and should_join(joined[-1], line):
            changes.append(Change("join_lines", joined[-1] + "\n" + line, joined[-1] + " " + line))
            joined[-1] = joined[-1] + " " + line
        else:
            joined.append(line)
    cleaned = "\n".join(fix_line(line, changes) for line in joined)
    return CleanResult(cleaned, changes, find_flags(cleaned, max_year))
