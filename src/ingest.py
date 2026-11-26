"""Lấy chữ đã làm sạch cho từng trang của kho, ghi data/processed/pages.jsonl.

Nguồn chữ của một trang, theo thứ tự ưu tiên:
  1. "tesseract": cache OCR ở data/ocr/ (nếu đã chạy python -m src.ocr)
  2. "digital":   lớp chữ thật của PDF
  3. "ocr_layer": lớp OCR ẩn do phần mềm scan chèn vào (chất lượng thấp hơn Tesseract)
  4. "missing":   scan trần chưa OCR, chưa có chữ để tìm kiếm

Chạy từ gốc Du_an/:  python -m src.ingest
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from src.clean import CLEAN_VERSION, clean_page
from src.config import DATA_DIR, MANIFEST_PATH, MODELS_DIR, OCR_DIR, RAW_DIR
from src.ocr import load_cached
from src.pdf_io import PageInfo, load_pages

PROCESSED_DIR = DATA_DIR / "processed"      # gitignore: có họ tên người ký
PAGES_PATH = PROCESSED_DIR / "pages.jsonl"
# Đổi khi bản ghi trang có thêm/bớt trường (2: title_hint, 3: header_ocr, 4: sửa chữ sau OCR + text_ocr);
# cache tệp tải lên khác số này thì tính lại
INGEST_VERSION = "5"     # 5: sign_ocr (khối chữ ký OCR lại sau khi xóa mực màu)


def page_raw_text(doc_id: str, page: PageInfo, ocr_dir: Path = OCR_DIR) -> tuple[str, str]:
    """(nguồn, chữ thô) của một trang theo thứ tự ưu tiên ở đầu tệp."""
    rec = load_cached(doc_id, page.page_no, ocr_dir)
    if rec is not None:
        return "tesseract", "\n".join(line["text"] for line in rec["lines"])
    if page.layer_kind != "none":
        return page.layer_kind, page.text_layer
    return "missing", ""


def ingest_pdf(pdf_path: Path, doc_id: str | None = None, ocr_dir: Path = OCR_DIR) -> list[dict]:
    """Mọi trang của một PDF thành bản ghi {doc_id, page_no, source, text, n_changes, flags}."""
    doc_id = doc_id or pdf_path.stem
    records = []
    for page in load_pages(pdf_path):
        source, raw = page_raw_text(doc_id, page, ocr_dir)
        cleaned = clean_page(raw) if raw else None
        records.append({
            "doc_id": doc_id, "page_no": page.page_no, "source": source,
            "text": cleaned.text if cleaned else "",
            "n_changes": len(cleaned.changes) if cleaned else 0,
            "flags": [f.rule for f in cleaned.flags] if cleaned else [],
            "clean_version": CLEAN_VERSION,
            "title_hint": page.title_hint,
            "header_ocr": header_ocr_text(doc_id, page.page_no, ocr_dir) if page.page_no == 1 else "",
            "sign_ocr": header_ocr_text(doc_id, page.page_no, ocr_dir, part="sign"),
        })
    return records


def header_ocr_text(doc_id: str, page_no: int, ocr_dir: Path = OCR_DIR, part: str = "header") -> str:
    """Chữ OCR một phần trang, đã làm sạch: "header" vùng đầu trang 1 (--headers), "sign" khối họ tên người ký
    đã xóa mực màu (--signatures); rỗng nếu chưa chạy."""
    rec = load_cached(doc_id, page_no, ocr_dir, part=part)
    return clean_page("\n".join(l["text"] for l in rec["lines"])).text if rec else ""


def read_manifest(path: Path = MANIFEST_PATH) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


SPELLFIX_SOURCES = ("tesseract", "ocr_layer")      # chỉ sửa chữ lấy từ OCR, không đụng lớp chữ số
SPELLFIX_LM_PATH = MODELS_DIR / "spellfix_lm.pkl"
SPELLFIX_LOG_PATH = PROCESSED_DIR / "spellfix_log.jsonl"


def spellfix_lm(pages: list[dict] | None = None):
    """Mô hình bigram âm tiết cho bước sửa chữ (src.spellfix); học lại khi chưa có hoặc khác phiên bản.

    Học từ trang chữ số của VB train + bộ vietnamese-legal-documents (bỏ dòng trùng số ký hiệu với kho).
    """
    import csv

    from src.extract_rules import normalize_doc_number
    from src.spellfix import load_or_train

    train_ids = {r["doc_id"] for r in read_manifest() if r["split"] == "train"}
    exclude = set()
    sources = DATA_DIR / "sources.csv"
    if sources.exists():
        with open(sources, encoding="utf-8", newline="") as f:
            exclude = {normalize_doc_number(r["ref_doc_number"]) for r in csv.DictReader(f) if r["ref_doc_number"]}
    if pages is None:
        pages = read_jsonl(PAGES_PATH) if PAGES_PATH.exists() else []
    return load_or_train(pages, train_ids, exclude, SPELLFIX_LM_PATH)


def apply_spellfix(pages: list[dict], lm) -> list[dict]:
    """Sửa chữ các trang OCR tại chỗ; giữ bản gốc ở "text_ocr"; trả nhật ký [{doc_id, page_no, before, after}]."""
    from src.spellfix import SPELLFIX_VERSION, fix_text

    log = []
    for p in pages:
        if p["source"] not in SPELLFIX_SOURCES or not p["text"]:
            continue
        fixed, changes = fix_text(lm, p["text"])
        p["text_ocr"], p["text"] = p["text"], fixed
        p["n_spellfix"], p["spellfix_version"] = len(changes), SPELLFIX_VERSION
        log += [{"doc_id": p["doc_id"], "page_no": p["page_no"], "before": b, "after": a} for b, a in changes]
    return log


def build_pages(doc_ids: list[str] | None = None, spellfix: bool = True) -> list[dict]:
    """Lấy chữ mọi trang, rồi (nếu bật) sửa chữ các trang OCR bằng mô hình học từ trang chữ số train."""
    rows = read_manifest()
    if doc_ids is not None:
        wanted = set(doc_ids)
        rows = [r for r in rows if r["doc_id"] in wanted]
    pages = []
    for r in rows:
        pages.extend(ingest_pdf(RAW_DIR / f"{r['doc_id']}.pdf", r["doc_id"]))
    if spellfix:
        log = apply_spellfix(pages, spellfix_lm(pages))
        write_jsonl(log, SPELLFIX_LOG_PATH)
    return pages


def summarize(pages: list[dict]) -> None:
    by_source = Counter(p["source"] for p in pages)
    n_docs = len({p["doc_id"] for p in pages})
    print(f"{n_docs} văn bản · {len(pages)} trang · nguồn chữ: "
          + ", ".join(f"{k} {v}" for k, v in sorted(by_source.items())))
    print(f"Trang có chữ để tìm kiếm: {len(pages) - by_source['missing']} "
          f"({100 * (1 - by_source['missing'] / len(pages)):.1f}%)")
    fixed = [p for p in pages if "n_spellfix" in p]
    if fixed:
        n_syl = sum(len(p["text_ocr"].split()) for p in fixed)
        n_fix = sum(p["n_spellfix"] for p in fixed)
        print(f"Sửa chữ sau OCR: {n_fix} chỗ trên {len(fixed)} trang OCR (≈ {100 * n_fix / max(n_syl, 1):.1f}% "
              f"số từ) · nhật ký: {SPELLFIX_LOG_PATH.relative_to(DATA_DIR.parent)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    all_pages = build_pages()
    write_jsonl(all_pages, PAGES_PATH)
    summarize(all_pages)
    print(f"Đã ghi {PAGES_PATH.relative_to(DATA_DIR.parent)}")
