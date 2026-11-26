"""Kiểm thử lớp Lưu trữ Bền vững Đám mây (CloudStorageManager): Local Volume & Mock HF Dataset."""
import json
from pathlib import Path
import shutil

import pymupdf

from src.archive import ArchiveManager
from src.cloud_store import CloudStorageManager
from src.uploads import save_upload


def _make_pdf_bytes(text: str = "Cong hoa xa hoi chu nghia Viet Nam") -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 60), text, fontsize=11)
    raw = doc.tobytes()
    doc.close()
    return raw


def test_local_volume_persists_dossier_and_upload_across_container_wipe(tmp_path):
    volume_dir = tmp_path / "cloud_volume"
    data_dir = tmp_path / "container_a" / "data"
    models_dir = tmp_path / "container_a" / "models"
    (data_dir / "uploads").mkdir(parents=True)
    (data_dir / "ocr").mkdir(parents=True)
    (data_dir / "raw").mkdir(parents=True)
    models_dir.mkdir(parents=True)

    struct_path = data_dir / "archive_structure.json"
    struct_path.write_text(
        json.dumps({"portal_name": "Test Portal", "fonds": []}, ensure_ascii=False),
        encoding="utf-8",
    )

    store_a = CloudStorageManager(volume_dir=volume_dir)
    assert store_a.backend == "local_volume" and store_a.durable is True

    mgr = ArchiveManager(structure_path=struct_path, auto_save=True)
    mgr.create_dossier({"file_code": "CLOUD.2026.001", "title": "Hồ sơ Đám mây thử nghiệm"})
    store_a.sync_archive_structure(struct_path, background=False)

    doc_id, _pages, _meta = save_upload(
        _make_pdf_bytes("Tai lieu cloud ben vung"),
        "cloud_demo.pdf",
        root=data_dir / "uploads",
        ocr_dir=data_dir / "ocr",
    )
    store_a.sync_upload(doc_id, data_dir / "uploads", data_dir / "ocr", background=False)

    # Đặt một tệp PDF gốc vào kho bền vững để kiểm tra tải lười
    (volume_dir / "raw").mkdir(parents=True, exist_ok=True)
    (volume_dir / "raw" / "vanban_nguon_01.pdf").write_bytes(_make_pdf_bytes("Noi dung goc"))

    # Mô phỏng Container A bị hủy hoàn toàn, Container B khởi tạo mới tinh từ Image
    data_dir_b = tmp_path / "container_b" / "data"
    models_dir_b = tmp_path / "container_b" / "models"
    data_dir_b.mkdir(parents=True)
    models_dir_b.mkdir(parents=True)

    store_b = CloudStorageManager(volume_dir=volume_dir)
    boot = store_b.bootstrap_on_startup(data_dir_b, models_dir_b)
    assert boot["durable"] is True
    assert boot["restored"]["archive_structure"] is True
    assert boot["restored"]["uploads_files"] >= 2

    mgr_b = ArchiveManager(structure_path=data_dir_b / "archive_structure.json")
    assert "CLOUD.2026.001" in mgr_b.dossiers
    assert (data_dir_b / "uploads" / doc_id / "source.pdf").is_file()

    # Tải lười PDF gốc và chặn path traversal
    fetched = store_b.ensure_raw_pdf("vanban_nguon_01", data_dir_b / "raw")
    assert fetched is not None and fetched.is_file()
    assert store_b.ensure_raw_pdf("../secret", data_dir_b / "raw") is None

    # Kiểm tra xóa đồng bộ
    store_b.delete_remote_upload(doc_id, background=False)
    assert not (volume_dir / "uploads" / doc_id).exists()


def test_hf_dataset_mode_with_mocked_hub(tmp_path):
    remote_repo_dir = tmp_path / "mock_hf_dataset"
    calls = []

    class FakeHfApi:
        def __init__(self, token=None):
            self.token = token

        def create_repo(self, **kwargs):
            calls.append(("create_repo", kwargs))
            assert kwargs.get("private") is True

        def upload_file(self, **kwargs):
            calls.append(("upload_file", kwargs))
            dst = remote_repo_dir / kwargs["path_in_repo"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(kwargs["path_or_fileobj"], dst)

        def upload_folder(self, **kwargs):
            calls.append(("upload_folder", kwargs))
            src = Path(kwargs["folder_path"])
            for p in src.rglob("*"):
                if p.is_file():
                    dst = remote_repo_dir / p.relative_to(src)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p, dst)

        def delete_folder(self, **kwargs):
            calls.append(("delete_folder", kwargs))
            shutil.rmtree(remote_repo_dir / kwargs["path_in_repo"], ignore_errors=True)

    def fake_snapshot_download(**kwargs):
        return str(remote_repo_dir)

    def fake_hf_hub_download(**kwargs):
        return str(remote_repo_dir / kwargs["filename"])

    data_dir = tmp_path / "app" / "data"
    data_dir.mkdir(parents=True)
    struct_path = data_dir / "archive_structure.json"
    struct_path.write_text('{"portal_name": "HF Cloud", "fonds": []}', encoding="utf-8")

    store = CloudStorageManager(
        hf_repo="tester/tra-cuu-luu-tru-so-storage",
        hf_token="hf_dummy_token",
        hf_api_factory=FakeHfApi,
        snapshot_download_fn=fake_snapshot_download,
        hf_hub_download_fn=fake_hf_hub_download,
    )
    assert store.backend == "hf_dataset" and store.durable is True
    store.sync_archive_structure(struct_path, background=False)
    assert (remote_repo_dir / "state" / "archive_structure.json").is_file()

    (remote_repo_dir / "raw").mkdir(parents=True, exist_ok=True)
    (remote_repo_dir / "raw" / "doc_remote.pdf").write_bytes(_make_pdf_bytes("Remote HF"))
    fetched = store.ensure_raw_pdf("doc_remote", data_dir / "raw")
    assert fetched is not None and fetched.is_file()
    assert store.status()["lazy_fetches"] == 1
    assert any(c[0] == "create_repo" and c[1]["private"] is True for c in calls)
