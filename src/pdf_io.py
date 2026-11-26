"""Đọc PDF theo trang: lấy lớp chữ, phân loại trang có chữ thật hay scan, render ảnh."""
import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pymupdf

from src.text import normalize_text

# Dòng do chữ ký số sinh ra, không phải nội dung văn bản
# Chỉ khớp nhãn riêng của khối chữ ký số; "Cơ quan:", "Email:" có thể là nội dung thật nên không lọc
SIGNATURE_LINE = re.compile(r"^(Ký bởi|Giờ ký|Thời gian ký|Signed by)\s*:", re.IGNORECASE)
# Ít hơn ngưỡng này (sau khi bỏ dòng chữ ký) thì coi trang là scan
MIN_TEXT_CHARS = 200
RENDER_DPI = int(os.environ.get("OCR_RENDER_DPI", "300"))
TITLE_SIZE_RATIO = 1.3      # dòng tiêu đề phải to hơn cỡ chữ trung vị ít nhất 30%
MAX_TITLE_CHARS = 200


@dataclass
class PageInfo:
    page_no: int          # đánh số từ 1, đúng như số trang khi dẫn nguồn
    text_layer: str       # lớp chữ đã bỏ dòng chữ ký số
    n_images: int
    layer_kind: str       # "digital": chữ thật · "ocr_layer": scan có lớp OCR ẩn · "none": scan trần
    title_hint: str = ""  # dòng chữ to nhất của trang (chỉ trang có chữ thật), dùng làm tiêu đề dự phòng

    @property
    def is_scan(self) -> bool:
        """Trang scan = không có chữ thật (kể cả khi có lớp OCR ẩn do phần mềm scan chèn vào)."""
        return self.layer_kind != "digital"


def strip_signature_lines(text: str) -> str:
    """Bỏ các dòng do chữ ký số chèn vào lớp chữ."""
    lines = normalize_text(text).split("\n")
    return "\n".join(l for l in lines if l and not SIGNATURE_LINE.match(l))


def classify_page(text_layer: str, invisible_ratio: float = 0.0) -> str:
    """Phân loại trang theo lớp chữ.

    - Ít hơn MIN_TEXT_CHARS ký tự (sau khi bỏ dòng chữ ký) → "none" (scan trần).
    - Đủ chữ nhưng phần lớn là chữ ẩn (chế độ vẽ 3, kiểu "PDF sandwich" của phần mềm scan) → "ocr_layer".
    - Còn lại → "digital".
    """
    if len(re.sub(r"\s", "", text_layer)) < MIN_TEXT_CHARS:
        return "none"
    return "ocr_layer" if invisible_ratio >= 0.5 else "digital"


def invisible_text_ratio(page: pymupdf.Page) -> float:
    """Tỉ lệ ký tự được vẽ ở chế độ ẩn (type 3) hoặc bằng GlyphLessFont trên trang."""
    total = hidden = 0
    for span in page.get_texttrace():
        n = len(span["chars"])
        total += n
        if span["type"] == 3 or "GlyphLess" in span["font"]:
            hidden += n
    return hidden / total if total else 0.0


def largest_text(page: pymupdf.Page) -> str:
    """Các dòng có cỡ chữ lớn nhất trang (≥ TITLE_SIZE_RATIO × cỡ chữ trung vị), ví dụ tiêu đề bài viết.

    Trả chuỗi rỗng nếu trang không có dòng nào nổi bật về cỡ chữ (văn bản hành chính thường như vậy).
    """
    lines = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if spans:
                lines.append((max(s["size"] for s in spans), pymupdf.Rect(line["bbox"])))
    if not lines:
        return ""
    sizes = sorted(size for size, _ in lines)
    median, biggest = sizes[len(sizes) // 2], sizes[-1]
    if biggest < TITLE_SIZE_RATIO * median:
        return ""
    # Nhóm dòng chữ to LIỀN NHAU đầu tiên (đề mục "I. Giới thiệu" cùng cỡ ở dưới không phải tiêu đề)
    first = next(i for i, (size, _) in enumerate(lines) if size >= 0.95 * biggest)
    group = []
    for size, rect in lines[first:]:
        if size < 0.95 * biggest:
            break
        group.append(rect)
    # Đọc lại chữ theo khung dòng: span trong "dict" có thể thiếu dấu cách giữa các từ
    title = " ".join(page.get_text("text", clip=r).strip() for r in group)
    return normalize_text(re.sub(r"\s+", " ", title))[:MAX_TITLE_CHARS]


def load_pages(pdf_path: Path) -> list[PageInfo]:
    """Đọc mọi trang của một PDF, chưa render ảnh (render tốn bộ nhớ, làm sau khi cần OCR)."""
    pages = []
    with pymupdf.open(pdf_path) as doc:
        for i, page in enumerate(doc, start=1):
            text = strip_signature_lines(page.get_text("text"))
            kind = classify_page(text, invisible_text_ratio(page))
            hint = largest_text(page) if kind == "digital" and i == 1 else ""
            pages.append(PageInfo(i, text, len(page.get_images()), kind, hint))
    return pages


def render_page(pdf_path: Path, page_no: int, dpi: int | None = None) -> np.ndarray:
    """Render một trang thành mảng RGB (cao, rộng, 3)."""
    use_dpi = int(os.environ.get("OCR_RENDER_DPI", str(RENDER_DPI))) if dpi is None else dpi
    with pymupdf.open(pdf_path) as doc:
        pix = doc[page_no - 1].get_pixmap(dpi=use_dpi, alpha=False)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3).copy()
    try:
        pymupdf.TOOLS.store_shrink(100)
    except Exception:
        pass
    return arr
