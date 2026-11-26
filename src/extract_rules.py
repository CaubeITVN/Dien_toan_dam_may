"""Trích thẻ thông tin văn bản bằng luật (đường cơ sở), theo thể thức NĐ 30/2020/NĐ-CP.

Trường: doc_type, doc_number, issue_date (dd/mm/yyyy), issuer, subject, signer, signer_title, recipients[].
Mỗi trường đi kèm (page_no, start, end) trên văn bản ĐÃ LÀM SẠCH của trang đó để dẫn nguồn.
Luật tổng quát: không có nhánh theo tên tệp hay hằng số riêng của một văn bản.
"""
import re
from dataclasses import asdict, dataclass, field

from src.text import normalize_text, remove_diacritics

# Tên loại văn bản (dòng tiêu đề in hoa ở giữa trang 1) → tên chuẩn
DOC_TYPE_TITLES = {
    "QUYẾT ĐỊNH": "Quyết định", "NGHỊ ĐỊNH": "Nghị định", "THÔNG TƯ": "Thông tư",
    "NGHỊ QUYẾT": "Nghị quyết", "CHỈ THỊ": "Chỉ thị", "THÔNG BÁO": "Thông báo",
    "BÁO CÁO": "Báo cáo", "KẾ HOẠCH": "Kế hoạch", "TỜ TRÌNH": "Tờ trình",
    "HƯỚNG DẪN": "Hướng dẫn", "QUY ĐỊNH": "Quy định", "QUY CHẾ": "Quy chế",
    "CÔNG ĐIỆN": "Công điện", "LUẬT": "Luật", "PHÁP LỆNH": "Pháp lệnh",
    "CHƯƠNG TRÌNH": "Chương trình", "ĐỀ ÁN": "Đề án", "GIẤY MỜI": "Giấy mời",
    "THÔNG TƯ LIÊN TỊCH": "Thông tư liên tịch", "LỆNH": "Lệnh",
}
# Mã loại trong số ký hiệu (phần chữ đầu tiên sau năm/số) → tên chuẩn; dùng khi không thấy dòng tiêu đề
DOC_TYPE_CODES = {
    "QĐ": "Quyết định", "NĐ": "Nghị định", "TT": "Thông tư", "NQ": "Nghị quyết", "CT": "Chỉ thị",
    "TB": "Thông báo", "BC": "Báo cáo", "KH": "Kế hoạch", "TTR": "Tờ trình", "HD": "Hướng dẫn",
    "CV": "Công văn", "CĐ": "Công điện", "QC": "Quy chế", "CTR": "Chương trình", "GM": "Giấy mời", "TTLT": "Thông tư liên tịch",
}

_TYPE_TITLE_KEYS = sorted(((remove_diacritics(k), v) for k, v in DOC_TYPE_TITLES.items()), key=lambda kv: -len(kv[0]))
# Nhãn "Số:" mà phần số nằm ở dòng sau (phần đầu ≤ 12 ký tự, có thể rỗng hoặc là rác OCR)
_NUMBER_LABEL = re.compile(r"^S[ốỐốoO]\s*[:.]?\s*(?P<head>.{0,12})$")
# Dòng tiếp theo là phần ký hiệu: có "/" và sau đó là chữ ("/BC-SGD&ĐT", "BC/SGD&ĐT-GDCN")
_NUMBER_TAIL = re.compile(r"^[\w.\-&]*/[A-Za-zĐđ][\w.\-&/]*$")
# Họ phổ biến của người Việt (dạng không dấu) để nhận họ tên bị OCR làm méo; "Y" là tiền tố tên Ê Đê
# Họ của người Việt (dạng CÓ DẤU, so nguyên dạng: "Lẽ", "Tế" do OCR đọc sai không phải họ); "Y" là tiền tố tên Ê Đê
_SURNAMES = set(normalize_text(
    "Nguyễn Trần Lê Phạm Hoàng Huỳnh Phan Vũ Võ Đặng Bùi Đỗ Hồ Ngô Dương Lý Đinh Mai Trịnh Đoàn Lương Lâm Hà "
    "Tạ Cao Chu Nông Triệu Vương Kiều Lưu Đào Tô Quách Hứa Khúc Trương La Lại Châu Mạc Ninh Lục Vi Hầu Y "
    "Thái Âu Giang Hàng Khổng Thân Diệp Đàm Văn Phùng Tăng Doãn Ông Kim Lã Viên Mông Lò Hoàng Bế Ma Đồng Quan "
    "Tống Từ Lăng Thạch Sơn Danh Lâm Đới Nghiêm Mẫn Bạch Cù Chử Tôn Thi Sầm").split())
OCR_SOURCES = ("tesseract", "ocr_layer")
MIN_VALID_RATIO = 0.8
# Quốc hiệu/tiêu ngữ dạng không dấu (chịu lỗi OCR). Chỉ nhận CẢ CỤM: "xã hội", "tự do" đứng riêng có trong
# nội dung ("kinh tế xã hội", "văn hóa - xã hội") và không được coi là quốc hiệu
_NATIONAL_ASCII = re.compile(r"CONG\s*HOA\s*XA|XA\s*H\w{0,2}\s*CH\w{0,2}\s*NGHIA|CHU\s*NGHIA\s*VI"
                             r"|DOC\s*LA\w?\s*[-–]|^DOC\s*LA\w?$|TU\s*DO\s*[-–]|[-–]\s*H\w{0,2}NH\s*PHUC")
_RULE_LINE = re.compile(r"^[_\-–—=.\s]+$")
# Dòng số ký hiệu kể cả khi OCR làm vỡ phần số ("SốC- /"): mốc kết thúc vùng tên cơ quan
_NUMBER_START = re.compile(r"^S[ốỐốoO]\s*[:.]?\s*[\w\-]*\s*[/\-:]", re.IGNORECASE)
_LEAD_NOISE = "•.,;:-–+*# "
_NAME_LEAD_NOISE = " “”\"'`‘’.,;:~^*_|/\\()[]{}"
# "Số: 385/2026/NĐ-CP", "Số 56-CV/ĐTN", "Số: /UBND-CNN&XD" (bản đăng cổng chưa điền số)
_DOC_NUMBER = re.compile(r"^S[ốỐốoO]\s*[:.]?\s*(?P<num>[\w/.\-&]*[/\-][\w/.\-&]+)", re.IGNORECASE)
_DATE_VN = re.compile(r"ngày\s+(?P<d>\d{1,2})\s+tháng\s+(?P<m>\d{1,2})\s+năm\s+(?P<y>\d{4})", re.IGNORECASE)
_PLACE_DATE = re.compile(r"^[^\d,]{2,40},\s*ngày\b", re.IGNORECASE)
_SUBJECT_VV = re.compile(r"^(V\s*[/l1|]\s*v|Về\s+việc)\s*[:.]?\s*", re.IGNORECASE)
# Dòng mở đầu phần thân: hết trích yếu. Phân biệt hoa thường: dòng tiếp của trích yếu viết thường ("năm học …")
_BODY_START = re.compile(
    r"^(Căn cứ|Kính gửi|Thực hiện|Theo đề nghị|Xét |Ngày \d|Trong |Năm |Để |Nhằm |Hiện nay"
    r"|[IVX]+[.)]|\d+[.)]|Chương|Điều|Phần|Mục )")
# Đầu dòng tên cơ quan (in hoa)
_AGENCY_HEAD = re.compile(
    r"^(BỘ|SỞ|ỦY BAN|UỶ BAN|UBND|HĐND|HỘI ĐỒNG|VĂN PHÒNG|CHÍNH PHỦ|THỦ TƯỚNG|NGÂN HÀNG|BAN|CỤC|TỔNG CỤC"
    r"|TRƯỜNG|TRUNG TÂM|PHÒNG|BẢO HIỂM|KIỂM TOÁN|TÒA ÁN|VIỆN|QUỐC HỘI|ĐẢNG|TỈNH ỦY|TỈNH UỶ|ĐOÀN|CÔNG AN"
    r"|BỘ CHỈ HUY|LIÊN ĐOÀN|HỘI|THANH TRA|KHO BẠC|CHI CỤC)\b")
# Sở/Bộ khi OCR dính hoặc sai dấu ("SỞGIÁO DUC", "SƠ GIÁO DỤC"): so trên dạng không dấu
_AGENCY_HEAD_ASCII = re.compile(r"^(SO|BO)\s*(GIAO|TAI|Y\s|NOI|KE|XAY|CONG|LAO|TU\s|NONG|VAN|KHOA|THONG|NGOAI"
                                r"|QUOC|DAN)")
# Dòng chức vụ trong khối chữ ký: "KT. GIÁM ĐỐC", "TM. CHÍNH PHỦ", "PHÓ THỦ TƯỚNG"
_SIGN_PREFIX = re.compile(r"^(KT|TM|TL|TUQ|Q|QUYỀN)\s*\.", re.IGNORECASE)
_TITLE_WORDS = re.compile(r"(GIÁM Đ[ỐÔ]C|TRƯỞNG|CHỦ TỊCH|THỦ TƯỚNG|BỘ TRƯỞNG|CHÁNH|THỐNG ĐỐC|TỔNG|BÍ THƯ"
                          r"|HIỆU TRƯỞNG|PHÓ|CỤC TRƯỞNG|VIỆN TRƯỞNG)")
_RECIPIENTS = re.compile(r"^N[ơo]i\s*nh[ậâa]n\s*:?", re.IGNORECASE)
_ADDRESSEES = re.compile(r"^Kính\s*gửi\s*:?\s*", re.IGNORECASE)
_ARCHIVE = re.compile(r"^[-–•+]?\s*L[ưu]u\s*[:.]?", re.IGNORECASE)
_BULLET = re.compile(r"^[-–•+]\s*")
# Âm tiết họ tên: viết hoa chữ đầu; cho phép một chữ cái ("Y Nhuân Byă") và dấu nháy ("H'Hen")
_NAME_WORD = re.compile(r"^[A-ZÀ-ỸĐ](?:[a-zà-ỹđ]+|'[A-ZÀ-ỸĐ]?[a-zà-ỹđ]+)?$")
# Họ tên ở đầu dòng, phía sau là chú thích bị nối dòng ("Nguyễn Danh Huy 1 Quy định …")
_NAME_PREFIX = re.compile(r"^(\S+(?:\s+\S+){1,4}?)(?=\s+\d)")
MIN_YEAR = 1945
MAX_SUBJECT_LINES = 5


@dataclass
class FieldValue:
    value: str | list[str]
    page_no: int
    start: int          # vị trí ký tự [start, end) trên văn bản đã làm sạch của trang
    end: int


@dataclass
class DocCard:
    doc_id: str
    fields: dict[str, FieldValue] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)

    def value(self, name: str):
        f = self.fields.get(name)
        return f.value if f else None

    def to_dict(self) -> dict:
        return {"doc_id": self.doc_id, "flags": self.flags,
                "fields": {k: asdict(v) for k, v in self.fields.items()}}

    @classmethod
    def from_dict(cls, d: dict) -> "DocCard":
        return cls(d["doc_id"], {k: FieldValue(**v) for k, v in d["fields"].items()}, d.get("flags", []))


def _lines_with_offsets(text: str) -> list[tuple[str, int]]:
    """Các dòng của trang kèm vị trí ký tự bắt đầu của dòng."""
    out, pos = [], 0
    for line in text.split("\n"):
        out.append((line, pos))
        pos += len(line) + 1
    return out


def _is_upper_line(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    return len(letters) >= 3 and sum(c.isupper() for c in letters) / len(letters) >= 0.8


# Chữ Kirin trông y hệt chữ Latin (gặp trong nhãn của cổng: "NĐ-СР" dùng С, Р Kirin)
_HOMOGLYPHS = str.maketrans("АВСЕНКМОРТХ", "ABCEHKMOPTX")


def normalize_doc_number(s: str) -> str:
    """Dạng so khớp của số ký hiệu: NFC, bỏ khoảng trắng, in hoa, đổi chữ Kirin giống Latin.
    KHÔNG đổi QD→QĐ hay sửa chữ số."""
    return re.sub(r"\s+", "", normalize_text(s)).upper().translate(_HOMOGLYPHS).strip("./-")


def header_end(lines: list[tuple[str, int]]) -> int:
    """Chỉ số dòng kết thúc vùng đầu trang 1 (dòng đầu tiên thuộc phần thân), tối đa 40 dòng."""
    for i, (line, _) in enumerate(lines[:40]):
        if re.match(r"^(Căn cứ|Kính gửi|Thực hiện|Điều \d|Chương [IVX\d])", line, re.IGNORECASE):
            return i
    return min(len(lines), 40)


def find_doc_number(lines, page_no, flags: list[str] | None = None) -> FieldValue | None:
    for line, off in lines[:30]:
        m = _DOC_NUMBER.match(line)
        if m:
            num = m.group("num").rstrip(".,;")
            return FieldValue(num, page_no, off + m.start("num"), off + m.start("num") + len(num))
        # OCR chèn dấu cách quanh "/": "Số: 242 /NQ-CP" → so trên dòng đã bỏ dấu cách đó; vị trí = cả dòng
        m = _DOC_NUMBER.match(re.sub(r"[ \t]*/[ \t]*", "/", line))
        if m:
            return FieldValue(m.group("num").rstrip(".,;"), page_no, off, off + len(line))
    # OCR làm vỡ số ký hiệu thành hai dòng: "Số: 3L" / "/BC-SGD&ĐT". Ghép, KHÔNG sửa chữ số, gắn cờ.
    for i, (line, off) in enumerate(lines[:min(29, len(lines) - 1)]):
        m = _NUMBER_LABEL.match(line)
        nxt, noff = lines[i + 1]
        if m and len(nxt) <= 40 and _NUMBER_TAIL.match(nxt.replace(" ", "")):
            head = m["head"] if re.search(r"\w", m["head"]) else ""
            if flags is not None:
                flags.append("doc_number_split_line")
            start = off + m.start("head") if head else noff
            return FieldValue(re.sub(r"\s+", "", head + nxt), page_no, start, noff + len(nxt))
    return None


def find_issue_date(lines, page_no, max_year: int, flags: list[str]) -> FieldValue | None:
    """Ngày ở dòng "<Địa danh>, ngày … tháng … năm …".

    Có dòng địa danh mà ngày để trống (bản đăng cổng, số và ngày đóng trên chữ ký số) thì trả None và gắn cờ,
    KHÔNG lấy ngày khác trong phần thân (đó là ngày của văn bản được nhắc tới). Không thấy dòng địa danh
    (OCR làm vỡ) mới tìm mẫu ngày trong vùng đầu trang.
    """
    place_lines = [(l, o) for l, o in lines[:30] if _PLACE_DATE.match(l)]
    if place_lines and not _DATE_VN.search(place_lines[0][0]):
        flags.append("issue_date_blank")
        return None
    candidates = place_lines[:1] or list(lines[:header_end(lines)])
    for line, off in candidates:
        m = _DATE_VN.search(line)
        if not m:
            continue
        d, mth, y = int(m["d"]), int(m["m"]), int(m["y"])
        if not (MIN_YEAR <= y <= max_year and 1 <= mth <= 12 and 1 <= d <= 31):
            flags.append("issue_date_invalid")
            return None
        return FieldValue(f"{d:02d}/{mth:02d}/{y}", page_no, off + m.start(), off + m.end())
    return None


def match_type_title(line: str) -> tuple[str, int] | None:
    """(tên loại chuẩn, độ dài phần tên loại) nếu dòng in hoa MỞ ĐẦU bằng tên loại văn bản.

    So trên dạng không dấu để chịu lỗi OCR ("BAO CAO"); tên dài thử trước ("THÔNG TƯ LIÊN TỊCH" trước
    "THÔNG TƯ"). Phần sau tên loại trên cùng dòng là trích yếu ("BÁO CÁO TÌNH HÌNH THỰC HIỆN …").
    Dòng kết thúc bằng ":" ("QUYẾT ĐỊNH:") là lời quyết định, không phải tên loại.
    """
    line = line.strip()
    if line.endswith(":"):
        return None
    ascii_line = remove_diacritics(line).upper()   # bỏ dấu giữ nguyên độ dài chuỗi NFC tiếng Việt
    for key, name in _TYPE_TITLE_KEYS:
        # Chỉ PHẦN TÊN LOẠI phải in hoa: làm sạch có thể nối "về việc …" (chữ thường) vào sau "QUYẾT ĐỊNH"
        if (ascii_line.startswith(key) and (len(ascii_line) == len(key) or not ascii_line[len(key)].isalpha())
                and _is_upper_line(line[:len(key)])):
            rest = line[len(key):].strip()
            if rest and not _is_upper_line(rest) and not _SUBJECT_VV.match(rest):
                continue    # "Quyết định này có hiệu lực…" viết thường sau tên loại: câu thân bài, không phải tiêu đề
            return name, len(key)
    return None


def find_doc_type(lines, end: int, page_no: int, doc_number: FieldValue | None) -> FieldValue | None:
    """Dòng tiêu đề tên loại → mã loại trong số ký hiệu → dấu hiệu công văn (V/v, Kính gửi)."""
    for line, off in lines[:end + 3]:
        lead = len(line) - len(line.lstrip())
        m = match_type_title(line)
        if m and not _is_national(line):
            return FieldValue(m[0], page_no, off + lead, off + lead + m[1])
    if doc_number:
        for part in re.split(r"[/\-]", doc_number.value.upper()):
            if part in DOC_TYPE_CODES:
                return FieldValue(DOC_TYPE_CODES[part], doc_number.page_no, doc_number.start, doc_number.end)
    for line, off in lines[:end + 3]:
        if _SUBJECT_VV.match(line) or _ADDRESSEES.match(line):
            return FieldValue("Công văn", page_no, off, off + len(line))
    return None


def find_issuer(lines, page_no) -> FieldValue | None:
    """Tên cơ quan ban hành: nhóm dòng in hoa đứng trước dòng "Số:", bỏ quốc hiệu; lấy cơ quan cuối cùng.

    "UBND TỈNH THÁI NGUYÊN / SỞ GIÁO DỤC VÀ ĐÀO TẠO" → cơ quan chủ quản là nhóm đầu, ban hành là nhóm sau.
    Dòng không bắt đầu bằng từ đầu tên cơ quan ("TỈNH THÁI NGUYÊN") là phần tiếp của nhóm trước.
    """
    # Tài liệu không theo thể thức (bài viết, giáo trình…): không có dòng "Số:" hay quốc hiệu → không có cơ quan
    if not any(_NUMBER_START.match(l) or _is_national(l) for l, _ in lines[:30]):
        return None
    groups: list[list[tuple[str, int]]] = []
    for line, off in lines[:30]:
        if _NUMBER_START.match(line) or _PLACE_DATE.match(line):
            break
        lead = len(line) - len(line.lstrip(_LEAD_NOISE))
        line, off = line[lead:], off + lead
        # OCR gộp hai cột đầu trang: "THỦ TƯỚNG CHÍNH PHỦ. CỘNG HÒA XÃ HỘI …" → giữ phần trước quốc hiệu
        m = _NATIONAL_ASCII.search(remove_diacritics(line).upper())
        if m and m.start() > 0:
            line = line[:m.start()].rstrip(" .,;:-–")
        if (not line or _RULE_LINE.match(line) or _is_national(line) or not _is_upper_line(line)
                or "/" in line):
            continue
        if _AGENCY_HEAD.match(line) or _AGENCY_HEAD_ASCII.match(remove_diacritics(line).upper()) or not groups:
            groups.append([(line, off)])
        else:
            groups[-1].append((line, off))
    if not groups:
        return None
    g = groups[-1]
    value = " ".join(l for l, _ in g)
    return FieldValue(value, page_no, g[0][1], g[-1][1] + len(g[-1][0]))


def _is_national(line: str) -> bool:
    """Dòng quốc hiệu/tiêu ngữ, so không dấu để chịu được lỗi OCR ("CÔNG HÒA XÃ HŨI CHÚ NGHĨA")."""
    return bool(_NATIONAL_ASCII.search(remove_diacritics(line).upper()))


def find_subject(lines, end: int, page_no: int, doc_type: FieldValue | None) -> FieldValue | None:
    """Trích yếu: khối "V/v …" (công văn), phần sau tên loại trên cùng dòng, hoặc các dòng dưới dòng tên loại.

    Trích yếu in hoa (thường gặp ở báo cáo) dừng ở dòng đầu tiên không in hoa (đó là phần thân),
    trừ dòng mở ngoặc "( Phần kinh phí … )" là chú thích của trích yếu.
    """
    start_i, skip = None, 0
    for i, (line, _) in enumerate(lines[:end + 3]):
        m = _SUBJECT_VV.match(line)
        if m:
            start_i, skip = i, m.end()
            break
    if start_i is None and doc_type is not None and doc_type.page_no == page_no:
        for i, (line, off) in enumerate(lines[:end + 3]):
            if off <= doc_type.start < off + len(line) + 1:
                rest = line[doc_type.end - off:]
                if rest.strip(" .:-"):
                    skip = doc_type.end - off + (len(rest) - len(rest.lstrip(" .:-")))
                    vv = _SUBJECT_VV.match(line[skip:])        # "QUYẾT ĐỊNH về việc …" → bỏ "về việc"
                    start_i, skip = i, skip + (vv.end() if vv else 0)
                else:
                    start_i = i + 1
                break
    if start_i is None or start_i >= len(lines):
        return None
    picked = []
    for j, (line, off) in enumerate(lines[start_i:start_i + MAX_SUBJECT_LINES]):
        text, text_off = (line[skip:], off + skip) if j == 0 else (line, off)
        if picked and (_BODY_START.match(text) or _is_national(text) or _PLACE_DATE.match(text)
                       or _RULE_LINE.match(text)
                       or (_is_upper_line(text) and _TITLE_WORDS.search(text) and not _is_upper_line(picked[0][0]))
                       or (_is_upper_line(picked[0][0]) and not _is_upper_line(text) and not text.startswith("("))):
            break
        if not picked and (_BODY_START.match(text) or _is_national(text)):
            return None
        if _RULE_LINE.match(text) or _is_national(text) or _PLACE_DATE.match(text):
            continue
        picked.append((text, text_off))
    if not picked:
        return None
    value = " ".join(t for t, _ in picked).strip()
    return FieldValue(value, page_no, picked[0][1], picked[-1][1] + len(picked[-1][0])) if value else None


def _looks_like_name(line: str) -> bool:
    words = line.split()
    return 2 <= len(words) <= 5 and all(_NAME_WORD.match(w) for w in words) and not _AGENCY_HEAD.match(line.upper())


_VOCAB: set[str] | None = None
_REGISTRY: set[str] | None = None


def _load_spellfix() -> None:
    global _VOCAB, _REGISTRY
    import pickle

    from src.config import MODELS_DIR

    path = MODELS_DIR / "spellfix_lm.pkl"
    if path.exists():
        with open(path, "rb") as f:
            saved = pickle.load(f)
        _VOCAB = set(saved["lm"].unigram)
        _REGISTRY = set(saved["info"].get("signer_names", [])) or None


def syllable_vocab() -> set[str] | None:
    """Từ điển âm tiết hợp lệ (mô hình sửa chữ src.spellfix, nếu đã học); None nếu chưa có."""
    if _VOCAB is None:
        _load_spellfix()
    return _VOCAB


def signer_registry() -> set[str] | None:
    """Danh bạ họ tên người ký từ bộ vietnamese-legal-documents (cột nguoi_ky); None nếu chưa có."""
    if _VOCAB is None:
        _load_spellfix()
    return _REGISTRY


def registry_verdict(name: str, registry: set[str] | None) -> str:
    """"match": có đúng trong danh bạ · "conflict": danh bạ có người CÙNG CHỮ KHÁC DẤU (dấu hiệu OCR đọc sai
    dấu: "Lê Tiên Châu" vs "Lê Tiến Châu") · "unknown": không có ai cùng chữ (người ký cấp Sở, xã…)."""
    if not registry:
        return "unknown"
    if name in registry:
        return "match"
    return "conflict" if _registry_by_key(registry).get(remove_diacritics(name).lower()) else "unknown"


_REG_INDEX: dict[int, tuple[set[str], dict[str, list[str]]]] = {}


def _registry_by_key(registry: set[str]) -> dict[str, list[str]]:
    """Chỉ mục danh bạ theo dạng bỏ dấu, chữ thường. Lưu kèm chính tập danh bạ: id() có thể được dùng lại
    sau khi một tập cũ bị giải phóng, nên phải so `is` trước khi dùng chỉ mục đã lưu."""
    saved = _REG_INDEX.get(id(registry))
    if saved is not None and saved[0] is registry:
        return saved[1]
    idx: dict[str, list[str]] = {}
    for r in registry:
        idx.setdefault(remove_diacritics(r).lower(), []).append(r)
    _REG_INDEX[id(registry)] = (registry, idx)
    return idx


def name_is_certain(name: str, vocab: set[str] | None) -> bool:
    """Họ tên đọc từ OCR chỉ được nhận khi CHẮC: 2–5 âm tiết viết hoa chữ đầu, âm tiết đầu là họ có thật
    (so NGUYÊN DẠNG CÓ DẤU, "Lẽ" ≠ "Lê"), mọi âm tiết có trong từ điển âm tiết tiếng Việt."""
    words = name.split()
    if not (2 <= len(words) <= 5 and all(_NAME_WORD.match(w) for w in words) and words[0] in _SURNAMES):
        return False
    return vocab is None or all(w.lower() in vocab for w in words)


def text_is_certain(text: str, vocab: set[str] | None, min_ratio: float = MIN_VALID_RATIO) -> bool:
    """Tên cơ quan/chức vụ từ OCR: ≥ min_ratio âm tiết hợp lệ (viết tắt in hoa ≤ 6 chữ như UBND, GDĐT tính là hợp lệ)."""
    words = re.findall(r"[^\W\d_]+", text)
    if not words or vocab is None:
        return bool(words)
    ok = sum(w.lower() in vocab or (w.isupper() and len(w) <= 6) for w in words)
    return ok / len(words) >= min_ratio


def number_is_certain(number: str) -> bool:
    """Số ký hiệu: phần trước dấu "/" đầu tiên phải là CHỮ SỐ (hoặc để trống); "3L/BC", "/I3t//BC" bị loại."""
    head = number.split("/", 1)[0]
    return bool(re.fullmatch(r"\d*", head)) and "//" not in number


def find_signer(lines, page_no) -> tuple[FieldValue | None, FieldValue | None]:
    """Khối chữ ký: dòng chức vụ in hoa (KT./TM./… hoặc có từ chức danh) rồi dòng HỌ TÊN IN bên dưới.

    Duyệt từ cuối trang lên; họ tên phải nằm SAU dòng chức vụ gần nhất để không lấy nhầm tên trong nơi nhận.
    Nét chữ ký tay/con dấu ở giữa (OCR ra rác) bị bỏ vì không có dạng họ tên. Không đoán họ tên méo.
    """
    def is_title(line: str) -> bool:
        return (_is_upper_line(line) and len(line) < 60 and not _BULLET.match(line)
                and bool(_SIGN_PREFIX.match(line) or _TITLE_WORDS.search(line)))

    title_idx = next((i for i in range(len(lines) - 1, -1, -1) if is_title(lines[i][0])), None)
    if title_idx is None:
        return None, None
    t0 = title_idx
    while t0 - 1 >= 0 and is_title(lines[t0 - 1][0]):
        t0 -= 1
    title_text = _clean_title(" ".join(l for l, _ in lines[t0:title_idx + 1]))
    title = FieldValue(title_text, page_no, lines[t0][1], lines[title_idx][1] + len(lines[title_idx][0]))
    for raw, raw_off in lines[title_idx + 1:]:
        # Rác do nét chữ ký/con dấu ở đầu dòng họ tên ("“Phạm Gia Túc", "` Phạm Gia Túc")
        line = raw.lstrip(_NAME_LEAD_NOISE)
        off = raw_off + len(raw) - len(line)
        if _looks_like_name(line):
            return FieldValue(line, page_no, off, off + len(line)), title
        m = _NAME_PREFIX.match(line)
        if m and _looks_like_name(m.group(1)):
            return FieldValue(m.group(1), page_no, off, off + m.end(1)), title
    return None, title


def _clean_title(s: str) -> str:
    """Bỏ phần đuôi không phải chữ in hoa do dấu chữ ký số đè lên ("PHÓ CHỦ NHIỆM [da")."""
    words = s.split()
    while words and (any(c.islower() for c in words[-1]) or not any(c.isalpha() for c in words[-1])):
        words.pop()
    return " ".join(words).rstrip("[]()|,;")


def find_recipients(lines, page_no) -> FieldValue | None:
    """Danh sách "Nơi nhận:" tới trước dòng "Lưu"; dòng không có gạch đầu là phần tiếp của mục trước."""
    start = next((i for i, (l, _) in enumerate(lines) if _RECIPIENTS.match(l)), None)
    if start is None:
        return None
    items: list[str] = []
    first_line, first_off = lines[start]
    rest = _RECIPIENTS.sub("", first_line).strip()
    if rest:
        items.append(_BULLET.sub("", rest))
    end_off = first_off + len(first_line)
    for line, off in lines[start + 1:]:
        if _ARCHIVE.match(line) or not line:
            break
        has_bullet = bool(_BULLET.match(line))
        clean_line = _BULLET.sub("", line).strip()
        if not has_bullet and (_is_upper_line(clean_line) or _looks_like_name(clean_line)):
            break
        if has_bullet or not items:
            if ";" in clean_line and has_bullet:
                items.extend(p.strip() for p in clean_line.split(";") if p.strip())
            else:
                items.append(clean_line)
        else:
            items[-1] += " " + clean_line
        end_off = off + len(line)
    items = [i.rstrip(";:,. ") for i in items if i.strip(";:,. ")]
    return FieldValue(items, page_no, first_off, end_off) if items else None


def extract_card(doc_id: str, pages: list[dict], max_year: int = 2026, vocab="auto", registry="auto") -> DocCard:
    """Thẻ thông tin của một văn bản từ các trang đã làm sạch (dict có page_no, text).

    Phần đầu (số, ngày, loại, cơ quan, trích yếu) lấy ở trang có chữ đầu tiên; khối chữ ký và nơi nhận
    lấy ở trang đầu tiên có "Nơi nhận" (sau đó thường là phụ lục), không có thì trang có chữ cuối cùng.
    """
    card = DocCard(doc_id)
    texted = [p for p in pages if p["text"]]
    if not texted:
        card.flags.append("no_text")
        return card
    if texted[0]["page_no"] != pages[0]["page_no"]:
        card.flags.append("first_page_missing")
    first = texted[0]
    lines = _lines_with_offsets(first["text"])
    end = header_end(lines)
    pno = first["page_no"]
    number = find_doc_number(lines, pno, card.flags)
    if number and not re.match(r"\w*\d", number.value):
        card.flags.append("doc_number_blank")     # "/TTg-CN": phần số để trống trong PDF
    found = {
        "doc_number": number,
        "issue_date": find_issue_date(lines, pno, max_year, card.flags),
        "issuer": find_issuer(lines, pno),
    }
    found["doc_type"] = find_doc_type(lines, end, pno, number)
    found["subject"] = find_subject(lines, end, pno, found["doc_type"])
    sign_page = next((p for p in texted if any(_RECIPIENTS.match(l) for l in p["text"].split("\n"))), texted[-1])
    sign_lines = _lines_with_offsets(sign_page["text"])
    found["signer"], found["signer_title"] = find_signer(sign_lines, sign_page["page_no"])
    found["recipients"] = find_recipients(sign_lines, sign_page["page_no"])
    found["title"] = find_title(pages[0])
    fill_from_header_ocr(found, pages[0], max_year, card.flags)
    vocab = syllable_vocab() if vocab == "auto" else vocab
    resolve_signer(found, pages, sign_page, vocab, card.flags, registry)
    keep_only_certain(found, first, vocab, card.flags)
    card.fields = {k: v for k, v in found.items() if v is not None}
    return card


def resolve_signer(found: dict, pages: list[dict], sign_page: dict, vocab, flags: list[str],
                   registry="auto") -> None:
    """Chọn họ tên người ký CHẮC CHẮN, nếu không thì để trống.

    Trang chữ số: lớp chữ chính xác, nhận như đọc được. Trang OCR: có hai nguồn đọc — (1) chữ cả trang,
    (2) khối chữ ký OCR lại sau khi xóa chữ ký tay và con dấu ("sign_ocr", python -m src.ocr --signatures).
    Chỉ nhận họ tên qua name_is_certain; hai nguồn cùng chắc mà KHÁC nhau → để trống (không chọn bừa).
    """
    if sign_page["source"] not in OCR_SOURCES:
        return
    title = found.get("signer_title")
    if title is not None and not text_is_certain(title.value, vocab):
        found["signer_title"] = None
        flags.append("signer_title_unreadable")
    cands = []
    f = found.get("signer")
    if f and name_is_certain(f.value, vocab):
        cands.append(f)
    sp = next((p for p in pages if p.get("sign_ocr")), None)
    if sp:
        sign_lines = _lines_with_offsets(sp["sign_ocr"])
        for line, _ in sign_lines:
            # Vùng cắt chỉ gồm khối chữ ký (không có danh sách nơi nhận) nên bỏ được cả "-" do nét ký để lại
            name = line.lstrip(_NAME_LEAD_NOISE + "-–").strip()
            m = _NAME_PREFIX.match(name)
            for cand in (name, m.group(1) if m else None):
                if cand and _looks_like_name(cand) and name_is_certain(cand, vocab):
                    # Vị trí (0, 0): đọc từ ảnh khối chữ ký đã xóa mực màu, không nằm trong chữ của trang
                    cands.append(FieldValue(cand, sp["page_no"], 0, 0))
                    break
    # Danh bạ người ký: tên OCR khác dấu với một người có thật cùng chữ → OCR đọc sai dấu → loại (không sửa)
    registry = registry if registry != "auto" else signer_registry()
    verdicts = {c.value: registry_verdict(c.value, registry) for c in cands}
    if any(v == "conflict" for v in verdicts.values()):
        flags.append("signer_conflicts_registry")
    cands = [c for c in cands if verdicts[c.value] != "conflict"]
    values = {c.value for c in cands}
    if len(values) == 1:
        found["signer"] = next(c for c in cands if c.end > c.start) if any(c.end > c.start for c in cands) else cands[0]
        if all(c.end <= c.start for c in cands):
            flags.append("signer_from_sign_ocr")
    else:
        had_block = f is not None or title is not None or sp is not None
        found["signer"] = None
        if had_block:
            flags.append("signer_ambiguous" if len(values) > 1 else "signer_unreadable")


def keep_only_certain(found: dict, first: dict, vocab, flags: list[str]) -> None:
    """Trang đầu là OCR: bỏ (để trống) số ký hiệu, cơ quan, chức vụ đọc không chắc; gắn cờ *_unreadable."""
    number = found.get("doc_number")
    if number is not None and (first["source"] in OCR_SOURCES or number.end <= number.start) \
            and not number_is_certain(number.value):
        found["doc_number"] = None
        flags.append("doc_number_unreadable")
    if first["source"] in OCR_SOURCES:
        for name in ("issuer",):
            f = found.get(name)
            if f is not None and not text_is_certain(f.value, vocab):
                found[name] = None
                flags.append(f"{name}_unreadable")


def fill_from_header_ocr(found: dict, page: dict, max_year: int, flags: list[str]) -> None:
    """PDF ký số của cổng: số và ngày đóng dạng ẢNH nên lớp chữ để trống ("Số: /UBND-…", "ngày tháng năm").
    Dùng chữ OCR vùng đầu trang 1 để bù HAI trường này khi lớp chữ thiếu; gắn cờ *_from_header_ocr.

    Vị trí ký tự (0, 0): giá trị không nằm trong văn bản đã làm sạch của trang (nằm trên ảnh), dẫn nguồn theo trang.
    """
    text = page.get("header_ocr") or ""
    if not text:
        return
    # OCR hay chèn dấu cách quanh "/": "12317 /UBND-CNN&XD" → "12317/UBND-CNN&XD"
    lines = _lines_with_offsets(re.sub(r"[ \t]*/[ \t]*", "/", text))
    number = found.get("doc_number")
    if number is None or not re.match(r"\w*\d", number.value):
        ocr_num = find_doc_number(lines, page["page_no"])
        if ocr_num and re.match(r"\w*\d", ocr_num.value) and (
                number is None or normalize_doc_number(ocr_num.value).endswith(normalize_doc_number(number.value))):
            found["doc_number"] = FieldValue(ocr_num.value, page["page_no"], 0, 0)
            flags.append("doc_number_from_header_ocr")
            if "doc_number_blank" in flags:
                flags.remove("doc_number_blank")
    if found.get("issue_date") is None:
        ocr_flags: list[str] = []
        date = find_issue_date(lines, page["page_no"], max_year, ocr_flags)
        if date:
            found["issue_date"] = FieldValue(date.value, page["page_no"], 0, 0)
            flags.append("issue_date_from_header_ocr")
            if "issue_date_blank" in flags:
                flags.remove("issue_date_blank")


def find_title(page: dict) -> FieldValue | None:
    """Tiêu đề theo cỡ chữ lớn nhất ở trang 1 (title_hint của pdf_io), dùng cho tài liệu không theo NĐ 30.

    Vị trí ký tự tìm trên văn bản đã làm sạch; không tìm thấy nguyên văn (khác dấu cách) thì trỏ về đầu trang.
    """
    hint = page.get("title_hint") or ""
    if not hint:
        return None
    i = page["text"].find(hint)
    return FieldValue(hint, page["page_no"], max(i, 0), i + len(hint) if i >= 0 else 0)


# ---------- Đối sánh tên cơ quan (chương 3: Levenshtein) ----------

def agency_key(name: str) -> str:
    """Khóa so khớp tên cơ quan: bỏ dấu, chữ thường, bỏ ký tự không phải chữ/số, mở rộng UBND/HĐND."""
    s = remove_diacritics(normalize_text(name)).lower()
    s = re.sub(r"\bubnd\b", "uy ban nhan dan", s)
    s = re.sub(r"\bhdnd\b", "hoi dong nhan dan", s)
    return re.sub(r"[^a-z0-9]+", "", s)


def match_agency(name: str, catalog: list[str], max_ratio: float) -> tuple[str | None, float]:
    """Cơ quan gần nhất trong danh mục theo Levenshtein trên khóa; nhận khi khoảng cách/độ dài ≤ max_ratio."""
    from src.metrics import levenshtein

    key = agency_key(name)
    best, best_ratio = None, 1.0
    for cand in catalog:
        ck = agency_key(cand)
        ratio = levenshtein(key, ck) / max(len(ck), 1)
        if ratio < best_ratio:
            best, best_ratio = cand, ratio
    return (best, best_ratio) if best_ratio <= max_ratio else (None, best_ratio)
