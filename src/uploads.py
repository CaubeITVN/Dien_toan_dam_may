"""Quản lý PDF người dùng tải lên qua web demo: mỗi lần tải là một thư mục riêng trong data/uploads/.

data/uploads/<doc_id>/
    source.pdf     PDF gốc
    meta.json      tên tệp gốc, thời điểm tải, md5, kích thước, số trang, số trang chưa OCR, đã OCR chưa
    pages.jsonl    chữ từng trang đã làm sạch (tính lại khi đổi CLEAN_VERSION hoặc vừa OCR)

Trang scan được OCR tự động (Tesseract, cùng tiền xử lý với kho chính) lúc tải lên; tệp tải lên trước khi có
bước này được OCR bù khi server khởi động (meta thiếu `ocr_done`). Cache OCR nằm ở data/ocr/<doc_id>/ như kho chính.

Tách khỏi data/raw/ (kho chính có manifest và chia train/dev/test): tệp tải lên KHÔNG thuộc tập đo nào.
Cả thư mục nằm trong .gitignore.
"""
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import pymupdf

from src.clean import CLEAN_VERSION
from src.config import DATA_DIR, OCR_DIR
from src.ingest import INGEST_VERSION, ingest_pdf, read_jsonl, write_jsonl
from src.ocr import ocr_document
from src.text import remove_diacritics

UPLOAD_DIR = DATA_DIR / "uploads"
PDF_NAME, META_NAME, PAGES_NAME = "source.pdf", "meta.json", "pages.jsonl"
_DOC_ID = re.compile(r"^up_[0-9a-f]{8}_[\w\-]{0,40}$")


def make_doc_id(body: bytes, original_name: str) -> str:
    """up_<8 ký tự md5>_<tên tệp không dấu>: cùng nội dung thì cùng mã (tải lại không sinh bản trùng)."""
    stem = re.sub(r"[^\w\-]+", "_", remove_diacritics(Path(original_name).stem)).strip("_")[:40]
    return f"up_{hashlib.md5(body).hexdigest()[:8]}_{stem}"


def _spellfix(pages: list[dict]) -> None:
    """Sửa chữ trang OCR của tệp tải lên bằng mô hình đã học cho kho chính (chỉ khi mô hình đã có sẵn)."""
    from src.ingest import SPELLFIX_LM_PATH, apply_spellfix, spellfix_lm

    if SPELLFIX_LM_PATH.exists() and any(p["source"] in ("tesseract", "ocr_layer") for p in pages):
        apply_spellfix(pages, spellfix_lm())


def run_ocr(pdf: Path, doc_id: str, ocr_dir: Path = OCR_DIR, engine=None) -> bool:
    """OCR trang scan của một tệp tải lên. Không có Tesseract hay OCR lỗi thì báo và trả False:
    tệp vẫn được nhận, trang scan để "chưa OCR" (lần khởi động sau thử lại)."""
    try:
        ocr_document(pdf, doc_id, engine, ocr_dir)
        return True
    except Exception as e:
        print(f"Không OCR được {doc_id}: {e}")
        return False


def _ingest(pdf: Path, doc_id: str, ocr_dir: Path) -> list[dict]:
    pages = ingest_pdf(pdf, doc_id, ocr_dir)
    _spellfix(pages)
    return pages


def upload_folder(doc_id: str, root: Path = UPLOAD_DIR) -> Path:
    """Đường dẫn thư mục của một tệp tải lên; chặn mã lạ (vd. "../raw") để không ra ngoài data/uploads."""
    if not _DOC_ID.match(doc_id):
        raise ValueError(f"Mã tệp tải lên không hợp lệ: {doc_id!r}")
    return root / doc_id


def _write_meta(folder: Path, meta: dict) -> None:
    with open(folder / META_NAME, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)


def save_upload(body: bytes, original_name: str, root: Path = UPLOAD_DIR, ocr_dir: Path = OCR_DIR,
                ocr_engine=None) -> tuple[str, list[dict], dict]:
    """Lưu PDF vào thư mục riêng, OCR trang scan, lấy chữ, ghi meta.json + pages.jsonl. Trả (doc_id, các trang, meta).

    PDF được mở thử trong bộ nhớ TRƯỚC khi ghi đĩa: tệp hỏng thì ném lỗi, không để lại thư mục nào
    (nếu mở trên đĩa rồi mới xóa, Windows báo tệp đang bị PyMuPDF giữ).
    """
    with pymupdf.open(stream=body, filetype="pdf") as probe:
        if probe.page_count == 0:
            raise ValueError("PDF không có trang nào")
    doc_id = make_doc_id(body, original_name)
    folder = upload_folder(doc_id, root)
    folder.mkdir(parents=True, exist_ok=True)
    pdf = folder / PDF_NAME
    pdf.write_bytes(body)
    ocr_done = run_ocr(pdf, doc_id, ocr_dir, ocr_engine)
    pages = _ingest(pdf, doc_id, ocr_dir)
    meta = {
        "doc_id": doc_id, "original_name": original_name,
        "uploaded_at": datetime.now().isoformat(timespec="seconds"),
        "md5": hashlib.md5(body).hexdigest(), "size_bytes": len(body),
        "n_pages": len(pages), "n_missing": sum(p["source"] == "missing" for p in pages),
        "clean_version": CLEAN_VERSION, "ingest_version": INGEST_VERSION, "ocr_done": ocr_done,
    }
    write_jsonl(pages, folder / PAGES_NAME)
    _write_meta(folder, meta)
    return doc_id, pages, meta


def migrate_flat_files(root: Path = UPLOAD_DIR) -> list[str]:
    """Chuyển tệp kiểu cũ data/uploads/<doc_id>.pdf vào thư mục riêng; trả các doc_id đã chuyển."""
    moved = []
    for pdf in sorted(root.glob("up_*.pdf")) if root.exists() else []:
        doc_id = pdf.stem
        folder = upload_folder(doc_id, root)
        folder.mkdir(exist_ok=True)
        stat = pdf.stat()
        shutil.move(str(pdf), folder / PDF_NAME)
        name = re.sub(r"^up_[0-9a-f]{8}_", "", doc_id) + ".pdf"
        _write_meta(folder, {"doc_id": doc_id, "original_name": name,
                             "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                             "md5": hashlib.md5((folder / PDF_NAME).read_bytes()).hexdigest(),
                             "size_bytes": stat.st_size, "migrated": True})
        moved.append(doc_id)
    return moved


def load_upload(folder: Path, ocr_dir: Path = OCR_DIR, ocr_engine=None) -> tuple[str, Path, list[dict], dict]:
    """(doc_id, đường dẫn PDF, các trang, meta) của một thư mục; OCR bù nếu chưa OCR, tính lại chữ nếu
    thiếu, vừa OCR hoặc khác CLEAN_VERSION/INGEST_VERSION."""
    with open(folder / META_NAME, encoding="utf-8") as f:
        meta = json.load(f)
    doc_id, pdf = meta["doc_id"], folder / PDF_NAME
    pages_path = folder / PAGES_NAME
    ocr_now = not meta.get("ocr_done") and run_ocr(pdf, doc_id, ocr_dir, ocr_engine)
    if (not ocr_now and pages_path.exists() and meta.get("clean_version") == CLEAN_VERSION
            and meta.get("ingest_version") == INGEST_VERSION):
        pages = read_jsonl(pages_path)
    else:
        pages = _ingest(pdf, doc_id, ocr_dir)
        write_jsonl(pages, pages_path)
        meta |= {"n_pages": len(pages), "n_missing": sum(p["source"] == "missing" for p in pages),
                 "clean_version": CLEAN_VERSION, "ingest_version": INGEST_VERSION,
                 "ocr_done": meta.get("ocr_done", False) or ocr_now}
        _write_meta(folder, meta)
    return doc_id, pdf, pages, meta


def list_uploads(root: Path = UPLOAD_DIR, ocr_dir: Path = OCR_DIR,
                 ocr_engine=None) -> list[tuple[str, Path, list[dict], dict]]:
    """Mọi tệp tải lên (đã chuyển tệp kiểu cũ), xếp theo thời điểm tải."""
    if not root.exists():
        return []
    migrate_flat_files(root)
    items = [load_upload(d, ocr_dir, ocr_engine) for d in root.iterdir() if d.is_dir() and (d / META_NAME).exists()]
    return sorted(items, key=lambda x: x[3].get("uploaded_at", ""))


def delete_upload(doc_id: str, root: Path = UPLOAD_DIR, ocr_dir: Path = OCR_DIR) -> bool:
    """Xóa cả thư mục của một tệp tải lên và cache OCR của nó. Chỉ xóa được mã dạng up_…, không đụng tới data/raw."""
    folder = upload_folder(doc_id, root)
    if not folder.is_dir():
        return False
    shutil.rmtree(folder)
    shutil.rmtree(ocr_dir / doc_id, ignore_errors=True)
    return True
