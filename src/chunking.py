"""Chia văn bản đã làm sạch thành đoạn để tìm kiếm, mỗi đoạn nằm TRỌN trong một trang.

Đơn vị dẫn nguồn là (doc_id, page_no). Đoạn không vắt qua trang: Điều 2 bắt đầu ở trang 1 và tiếp ở
trang 2 sinh hai đoạn, mỗi đoạn mang đúng trang của mình, cùng nhãn mục "Điều 2" (mục kế thừa qua trang).
"""
import re
import unicodedata
from dataclasses import asdict, dataclass

# Dòng mở một mục mới: Chương, Mục, Điều, đề mục số La Mã, "Nơi nhận"
_SECTION = re.compile(r"^(Chương\s+[IVXLC\d]+|Mục\s+\d+|Điều\s+\d+[a-z]?|Phần\s+[IVXLC\d]+|[IVX]+[.)]\s|PHỤ LỤC|Nơi nhận)",
                      re.IGNORECASE)
# Dòng có thể ngắt đoạn khi đoạn đã đủ dài: khoản "1.", điểm "a)", gạch đầu dòng
_SOFT_BREAK = re.compile(r"^(\d+(\.\d+)*[.)]\s|[a-zđ]\)\s|[-–•+]\s)")
# Dòng mở Khoản trong văn bản hành chính ("1. ...", "2. ...")
_CLAUSE = re.compile(r"^(\d+[.)])\s+")
# Trích loại văn bản và số ký hiệu từ đầu trang khi không có metadata ngoài
_DOC_TYPE_RE = re.compile(
    r"\b(QUYẾT ĐỊNH|NGHỊ ĐỊNH|THÔNG TƯ|CÔNG VĂN|BÁO CÁO|KẾ HOẠCH|TỜ TRÌNH|CHỈ THỊ|HƯỚNG DẪN)\b",
    re.IGNORECASE,
)
_DOC_NUMBER_RE = re.compile(r"Số\s*[:.]?\s*([0-9A-Za-zĐđ/._-]{2,40})")
MAX_CHARS = 900
MIN_CHARS = 200


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    page_no: int
    section: str        # mục đang mở ("Điều 2", "II.", "" nếu chưa có)
    start: int          # [start, end) trên văn bản đã làm sạch của trang
    end: int
    text: str
    parent_id: str = ""
    parent_text: str = ""
    search_text: str = ""

    @property
    def index_text(self) -> str:
        """Văn bản dùng để lập chỉ mục/truy hồi (kèm tiền tố metadata nếu có)."""
        return self.search_text or self.text

    def to_dict(self) -> dict:
        return asdict(self)


def section_label(line: str) -> str | None:
    m = _SECTION.match(line)
    return m.group(1).strip().rstrip(".)") if m else None


def chunk_page(doc_id: str, page_no: int, text: str, section: str = "",
               max_chars: int = MAX_CHARS, min_chars: int = MIN_CHARS) -> tuple[list[Chunk], str]:
    """Chia một trang; trả (các đoạn, mục còn mở ở cuối trang) để trang sau kế thừa nhãn mục.

    Ngắt khi gặp mục mới; khi đoạn đã ≥ min_chars thì ngắt thêm ở khoản/điểm; không bao giờ vượt max_chars
    (dòng quá dài thì cắt tại dấu cách gần nhất).
    """
    chunks: list[Chunk] = []
    cur_start, cur_end, cur_section = None, None, section

    def flush():
        nonlocal cur_start
        if cur_start is not None and text[cur_start:cur_end].strip():
            idx = len(chunks)
            chunks.append(Chunk(f"{doc_id}#p{page_no}#{idx}", doc_id, page_no, cur_section,
                                cur_start, cur_end, text[cur_start:cur_end]))
        cur_start = None

    pos = 0
    for line in text.split("\n"):
        start, end = pos, pos + len(line)
        pos = end + 1
        if not line.strip():
            continue
        label = section_label(line)
        size = 0 if cur_start is None else cur_end - cur_start
        if label or (size >= min_chars and _SOFT_BREAK.match(line)) or size + len(line) + 1 > max_chars:
            flush()
            if label:
                cur_section = label
        while end - start > max_chars:          # dòng quá dài: cắt thành nhiều đoạn
            cut = text.rfind(" ", start, start + max_chars)
            cut = cut if cut > start else start + max_chars
            cur_start, cur_end = start, cut
            flush()
            start = cut + 1
        if cur_start is None:
            cur_start = start
        cur_end = end
    flush()
    return chunks, cur_section


def extract_doc_metadata(text: str, doc_id: str = "") -> dict[str, str]:
    """Trích loại văn bản và số ký hiệu từ nội dung trang (hoặc suy ra từ `doc_id`)."""
    norm = unicodedata.normalize("NFC", text or "")
    doc_type = ""
    m_type = _DOC_TYPE_RE.search(norm[:800])
    if m_type:
        doc_type = m_type.group(1).title()
    elif doc_id.startswith("qd_"):
        doc_type = "Quyết Định"
    elif doc_id.startswith("cv_"):
        doc_type = "Công Văn"
    elif doc_id.startswith("bc_"):
        doc_type = "Báo Cáo"

    doc_number = ""
    m_num = _DOC_NUMBER_RE.search(norm[:800])
    if m_num:
        doc_number = m_num.group(1).strip(".,;:")
    return {"doc_type": doc_type, "doc_number": doc_number}


def format_metadata_prefix(
    doc_id: str,
    page_no: int,
    doc_type: str = "",
    doc_number: str = "",
    section: str = "",
) -> str:
    """Tạo chuỗi tiền tố metadata chuẩn NFC để gắn vào ngữ cảnh lập chỉ mục."""
    parts = [
        f"doc_type={doc_type or 'N/A'}",
        f"doc_number={doc_number or 'N/A'}",
        f"doc_id={doc_id}",
        f"page_no={page_no}",
    ]
    if section:
        parts.append(f"section={section}")
    return unicodedata.normalize("NFC", "[" + " | ".join(parts) + "]")


def chunk_page_dieu_khoan(
    doc_id: str,
    page_no: int,
    text: str,
    section: str = "",
    max_chars: int = MAX_CHARS,
    min_chars: int = 40,
) -> tuple[list[Chunk], str]:
    """Chia một trang theo cấu trúc văn bản hành chính: ngắt tại mỗi Điều/Mục và mỗi Khoản (`1.`, `2.`)."""
    chunks: list[Chunk] = []
    cur_start, cur_end = None, None
    cur_article = section.split(" · ")[0] if section else ""
    cur_section = section

    def flush():
        nonlocal cur_start
        if cur_start is not None and text[cur_start:cur_end].strip():
            idx = len(chunks)
            chunks.append(
                Chunk(
                    f"{doc_id}#p{page_no}#{idx}",
                    doc_id,
                    page_no,
                    cur_section,
                    cur_start,
                    cur_end,
                    text[cur_start:cur_end],
                )
            )
        cur_start = None

    pos = 0
    for line in text.split("\n"):
        start, end = pos, pos + len(line)
        pos = end + 1
        stripped = line.strip()
        if not stripped:
            continue
        label = section_label(stripped)
        clause_m = _CLAUSE.match(stripped)
        size = 0 if cur_start is None else cur_end - cur_start

        if label:
            flush()
            cur_article = label
            cur_section = label
        elif clause_m and (size >= min_chars or cur_start is not None):
            flush()
            clause_tag = f"Khoản {clause_m.group(1).rstrip('.)')}"
            cur_section = f"{cur_article} · {clause_tag}" if cur_article else clause_tag
        elif (size >= max(min_chars, MIN_CHARS) and _SOFT_BREAK.match(stripped)) or size + len(line) + 1 > max_chars:
            flush()

        while end - start > max_chars:
            cut = text.rfind(" ", start, start + max_chars)
            cut = cut if cut > start else start + max_chars
            cur_start, cur_end = start, cut
            flush()
            start = cut + 1
        if cur_start is None:
            cur_start = start
        cur_end = end
    flush()
    return chunks, cur_section


def build_parent_child_chunks(
    parents: list[Chunk],
    child_max_chars: int = 350,
    child_min_chars: int = 80,
) -> list[Chunk]:
    """Tách mỗi chunk cha thành các chunk con nhỏ để truy hồi chính xác, giữ `parent_id` và `parent_text`."""
    children: list[Chunk] = []
    for p in parents:
        text = p.text
        if len(text) <= child_max_chars:
            children.append(
                Chunk(
                    chunk_id=f"{p.chunk_id}#c0",
                    doc_id=p.doc_id,
                    page_no=p.page_no,
                    section=p.section,
                    start=p.start,
                    end=p.end,
                    text=text,
                    parent_id=p.chunk_id,
                    parent_text=p.text,
                    search_text=p.search_text,
                )
            )
            continue

        # Tách theo dòng trước, nếu dòng vẫn dài hơn child_max_chars thì cắt theo dấu cách
        sub_spans: list[tuple[int, int]] = []
        cur_s: int | None = None
        cur_e = 0
        pos = 0
        for line in text.split("\n"):
            l_start, l_end = pos, pos + len(line)
            pos = l_end + 1
            if not line.strip():
                continue
            cur_len = 0 if cur_s is None else cur_e - cur_s
            if cur_s is not None and (cur_len + len(line) + 1 > child_max_chars and cur_len >= child_min_chars or cur_len + len(line) + 1 > child_max_chars):
                sub_spans.append((cur_s, cur_e))
                cur_s = None
            while l_end - l_start > child_max_chars:
                cut = text.rfind(" ", l_start, l_start + child_max_chars)
                cut = cut if cut > l_start else l_start + child_max_chars
                sub_spans.append((l_start, cut))
                l_start = cut + 1
            if cur_s is None:
                cur_s = l_start
            cur_e = l_end
        if cur_s is not None and text[cur_s:cur_e].strip():
            sub_spans.append((cur_s, cur_e))

        for c_idx, (s_rel, e_rel) in enumerate(sub_spans):
            c_text = text[s_rel:e_rel]
            if not c_text.strip():
                continue
            children.append(
                Chunk(
                    chunk_id=f"{p.chunk_id}#c{c_idx}",
                    doc_id=p.doc_id,
                    page_no=p.page_no,
                    section=p.section,
                    start=p.start + s_rel,
                    end=p.start + e_rel,
                    text=c_text,
                    parent_id=p.chunk_id,
                    parent_text=p.text,
                )
            )
    return children


def chunk_document(
    pages: list[dict],
    strategy: str = "default",
    include_metadata_prefix: bool = False,
    doc_meta: dict[str, str] | None = None,
    max_chars: int = MAX_CHARS,
    min_chars: int = MIN_CHARS,
    child_max_chars: int = 350,
    child_min_chars: int = 80,
) -> list[Chunk]:
    """Chia mọi trang có chữ của một văn bản (dict có doc_id, page_no, text), giữ nhãn mục qua trang.

    strategy:
    - "default": chia theo quy tắc mặc định hiện tại (không đổi hành vi cũ).
    - "dieu_khoan": chia theo cấu trúc Điều / Khoản văn bản hành chính.
    - "parent_child": chia cha theo Điều/Khoản (tối đa `max_chars`), rồi tách con nhỏ (`child_max_chars`)
      mang `parent_id` và `parent_text`.
    """
    sorted_pages = sorted(pages, key=lambda p: p["page_no"])
    meta_inferred: dict[str, str] = {"doc_type": "", "doc_number": ""}
    for p in sorted_pages:
        if p.get("text"):
            meta_inferred = extract_doc_metadata(p["text"], p["doc_id"])
            if meta_inferred["doc_type"] or meta_inferred["doc_number"]:
                break
    if doc_meta:
        meta = {
            "doc_type": doc_meta.get("doc_type") or meta_inferred["doc_type"],
            "doc_number": doc_meta.get("doc_number") or meta_inferred["doc_number"],
        }
    else:
        meta = meta_inferred

    chunks: list[Chunk] = []
    section = ""
    for p in sorted_pages:
        if not p.get("text"):
            continue
        if strategy == "dieu_khoan":
            page_chunks, section = chunk_page_dieu_khoan(
                p["doc_id"], p["page_no"], p["text"], section, max_chars=max_chars, min_chars=min_chars
            )
        elif strategy == "parent_child":
            # Cha giữ trọn cả Điều/mục lớn (tối đa max_chars) để con tách nhỏ hơn làm ngữ cảnh truy hồi
            page_chunks, section = chunk_page(
                p["doc_id"], p["page_no"], p["text"], section, max_chars=max_chars, min_chars=max(min_chars, 500)
            )
        else:
            page_chunks, section = chunk_page(
                p["doc_id"], p["page_no"], p["text"], section, max_chars=max_chars, min_chars=min_chars
            )
        chunks.extend(page_chunks)

    if strategy == "parent_child":
        chunks = build_parent_child_chunks(
            chunks, child_max_chars=child_max_chars, child_min_chars=child_min_chars
        )

    if include_metadata_prefix:
        for c in chunks:
            prefix = format_metadata_prefix(
                c.doc_id,
                c.page_no,
                doc_type=meta.get("doc_type", ""),
                doc_number=meta.get("doc_number", ""),
                section=c.section,
            )
            c.search_text = f"{prefix}\n{c.text}"

    return chunks
