"""Quản lý tệp tải lên: thư mục riêng, meta, chuyển tệp kiểu cũ, chặn đường dẫn lạ."""
import json

import pymupdf
import pytest

from src import uploads
from src.ocr import OcrLine, cache_path


class FakeEngine:
    """Thay Tesseract trong test: trả một dòng chữ cố định, đếm số lần được gọi."""
    name, version = "fake", "1"

    def __init__(self):
        self.calls = 0

    def __call__(self, image):
        self.calls += 1
        return [OcrLine("Thông báo về việc nghỉ lễ của cơ quan", (10, 10, 400, 40), 0.9)]


def scan_pdf_bytes(n_pages=2) -> bytes:
    """PDF chỉ có hình vẽ, không có lớp chữ: giống trang scan."""
    doc = pymupdf.open()
    for _ in range(n_pages):
        doc.new_page().draw_rect(pymupdf.Rect(50, 50, 300, 100), fill=(0, 0, 0))
    data = doc.tobytes()
    doc.close()
    return data


def pdf_bytes(text="noi dung mau " * 40) -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 60), text, fontsize=9)
    data = doc.tobytes()
    doc.close()
    return data


def test_save_creates_folder_with_meta_and_pages(tmp_path):
    doc_id, pages, meta = uploads.save_upload(pdf_bytes(), "Báo cáo tháng 9.pdf", tmp_path, tmp_path / "ocr", FakeEngine())
    folder = tmp_path / doc_id
    assert doc_id.startswith("up_") and doc_id.endswith("_Bao_cao_thang_9")
    assert {p.name for p in folder.iterdir()} == {"source.pdf", "meta.json", "pages.jsonl"}
    saved = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    assert saved["original_name"] == "Báo cáo tháng 9.pdf" and saved["n_pages"] == len(pages) == 1
    assert saved["size_bytes"] > 0 and len(saved["md5"]) == 32


def test_same_content_same_id_and_list_delete(tmp_path):
    body = pdf_bytes()
    a, _, _ = uploads.save_upload(body, "x.pdf", tmp_path, tmp_path / "ocr", FakeEngine())
    b, _, _ = uploads.save_upload(body, "x.pdf", tmp_path, tmp_path / "ocr", FakeEngine())
    assert a == b and len(uploads.list_uploads(tmp_path, tmp_path / "ocr", FakeEngine())) == 1
    assert uploads.delete_upload(a, tmp_path, tmp_path / "ocr") and uploads.list_uploads(tmp_path, tmp_path / "ocr", FakeEngine()) == []


def test_migrate_flat_legacy_file(tmp_path):
    (tmp_path / "up_1234abcd_cu.pdf").write_bytes(pdf_bytes())
    items = uploads.list_uploads(tmp_path, tmp_path / "ocr", FakeEngine())
    assert [i[0] for i in items] == ["up_1234abcd_cu"]
    assert (tmp_path / "up_1234abcd_cu" / "source.pdf").exists()
    assert not (tmp_path / "up_1234abcd_cu.pdf").exists()
    assert items[0][3]["migrated"] is True and items[0][3]["n_pages"] == 1


def test_broken_pdf_leaves_nothing(tmp_path):
    with pytest.raises(Exception):
        uploads.save_upload(b"%PDF-1.4 hong", "hong.pdf", tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_reject_path_like_ids(tmp_path):
    for bad in ["../raw", "cp_219922", "up_1234abcd_../../x"]:
        with pytest.raises(ValueError):
            uploads.upload_folder(bad, tmp_path)


def test_scan_upload_is_ocred_and_ocr_cache_deleted(tmp_path):
    ocr_dir, engine, body = tmp_path / "ocr", FakeEngine(), scan_pdf_bytes(2)
    doc_id, pages, meta = uploads.save_upload(body, "scan.pdf", tmp_path, ocr_dir, engine)
    assert engine.calls == 2, "mỗi trang scan OCR một lần"
    assert [p["source"] for p in pages] == ["tesseract", "tesseract"]
    assert "nghỉ lễ" in pages[0]["text"]
    assert meta["n_missing"] == 0 and meta["ocr_done"] is True
    assert cache_path(doc_id, 1, ocr_dir).exists()
    uploads.save_upload(body, "scan.pdf", tmp_path, ocr_dir, engine)
    assert engine.calls == 2, "tải lại cùng tệp thì đọc cache OCR"
    assert uploads.delete_upload(doc_id, tmp_path, ocr_dir)
    assert not (ocr_dir / doc_id).exists()


def test_old_upload_without_ocr_is_ocred_on_load(tmp_path):
    ocr_dir = tmp_path / "ocr"
    failing = lambda image: (_ for _ in ()).throw(RuntimeError("không có Tesseract"))
    failing.name, failing.version = "x", "1"
    doc_id, pages, meta = uploads.save_upload(scan_pdf_bytes(1), "cu.pdf", tmp_path, ocr_dir, failing)
    assert meta["ocr_done"] is False and meta["n_missing"] == 1, "OCR lỗi vẫn nhận tệp, trang để chưa OCR"
    items = uploads.list_uploads(tmp_path, ocr_dir, FakeEngine())
    assert items[0][3]["ocr_done"] is True and items[0][3]["n_missing"] == 0
    assert items[0][2][0]["source"] == "tesseract"
