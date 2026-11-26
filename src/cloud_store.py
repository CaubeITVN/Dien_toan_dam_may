"""Lớp trừu tượng Lưu trữ Bền vững Đám mây (Cloud Object & State Storage).

Tách biệt tầng tính toán phi trạng thái (Stateless Compute Container) khỏi tầng
lưu trữ dữ liệu bền vững. Hỗ trợ 3 chế độ tự động qua biến môi trường:
  - ``hf_dataset``   : Hugging Face Hub Dataset riêng tư (``HF_STORAGE_REPO`` + ``HF_TOKEN``).
  - ``local_volume`` : Ổ đĩa gắn ngoài Docker Volume / Persistent Disk (``CLOUD_VOLUME_DIR``).
  - ``ephemeral``    : Chế độ cục bộ tạm thời khi chưa gắn kho lưu trữ ngoài.
"""
from __future__ import annotations

from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import tempfile
import threading
from typing import Any

_SAFE_DOC_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,120}$")
_SAFE_UPLOAD_ID = re.compile(r"^up_[0-9a-f]{8}_[\w\-]{0,40}$")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _atomic_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(dst.parent), prefix=f".{dst.name}.tmp.")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as out_f, open(src, "rb") as in_f:
            shutil.copyfileobj(in_f, out_f)
            out_f.flush()
            os.fsync(out_f.fileno())
        os.replace(tmp_path, dst)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _copy_tree_merge(src_dir: Path, dst_dir: Path, *, overwrite: bool = True) -> int:
    if not src_dir.is_dir():
        return 0
    copied = 0
    for item in sorted(src_dir.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(src_dir)
        target = dst_dir / rel
        if not overwrite and target.exists():
            continue
        _atomic_copy(item, target)
        copied += 1
    return copied


class CloudStorageManager:
    """Quản lý đồng bộ và khôi phục trạng thái hệ thống với tầng lưu trữ bền vững."""

    def __init__(
        self,
        *,
        hf_repo: str | None = None,
        hf_token: str | None = None,
        volume_dir: str | Path | None = None,
        hf_api_factory: Any = None,
        snapshot_download_fn: Any = None,
        hf_hub_download_fn: Any = None,
    ):
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cloud-sync")
        self._pending_futures: list[Future] = []

        env_repo = (os.environ.get("HF_STORAGE_REPO") or "").strip()
        env_token = (os.environ.get("HF_TOKEN") or "").strip()
        env_vol = (os.environ.get("CLOUD_VOLUME_DIR") or "").strip()

        self.hf_repo = (hf_repo if hf_repo is not None else env_repo).strip()
        self.hf_token = (hf_token if hf_token is not None else env_token).strip()
        vol_raw = volume_dir if volume_dir is not None else env_vol
        self.volume_dir: Path | None = Path(vol_raw).resolve() if str(vol_raw or "").strip() else None

        if self.hf_repo:
            self.backend = "hf_dataset"
        elif self.volume_dir is not None:
            self.backend = "local_volume"
            self.volume_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.backend = "ephemeral"

        self.durable = self.backend in ("hf_dataset", "local_volume")
        self._hf_api_factory = hf_api_factory
        self._snapshot_download_fn = snapshot_download_fn
        self._hf_hub_download_fn = hf_hub_download_fn

        self.bootstrapped = False
        self.last_sync_at: str | None = None
        self.sync_ok_count = 0
        self.sync_err_count = 0
        self.lazy_fetches = 0
        self._events: deque[dict[str, Any]] = deque(maxlen=20)

    def _record_event(self, action: str, target: str, status: str, detail: str = "") -> None:
        with self._lock:
            ts = _utc_now_iso()
            self._events.appendleft({
                "timestamp": ts,
                "action": action,
                "target": target,
                "status": status,
                "detail": detail[:240],
            })
            if status == "ok":
                self.sync_ok_count += 1
                self.last_sync_at = ts
            elif status == "error":
                self.sync_err_count += 1

    def _get_hf_api(self):
        if self._hf_api_factory is not None:
            return self._hf_api_factory(token=self.hf_token or None)
        from huggingface_hub import HfApi

        return HfApi(token=self.hf_token or None)

    def _snapshot_download(self, **kwargs) -> str:
        if self._snapshot_download_fn is not None:
            return self._snapshot_download_fn(**kwargs)
        from huggingface_hub import snapshot_download

        return snapshot_download(**kwargs)

    def _hf_hub_download(self, **kwargs) -> str:
        if self._hf_hub_download_fn is not None:
            return self._hf_hub_download_fn(**kwargs)
        from huggingface_hub import hf_hub_download

        return hf_hub_download(**kwargs)

    def _submit(self, fn, *args, background: bool = True, **kwargs):
        if not background or self.backend == "local_volume":
            return fn(*args, **kwargs)
        fut = self._executor.submit(fn, *args, **kwargs)
        with self._lock:
            self._pending_futures = [f for f in self._pending_futures if not f.done()]
            self._pending_futures.append(fut)
        return fut

    def wait_pending(self, timeout: float = 10.0) -> None:
        with self._lock:
            futs = list(self._pending_futures)
        for f in futs:
            try:
                f.result(timeout=timeout)
            except Exception:
                pass

    def _ensure_hf_repo(self) -> None:
        if self.backend != "hf_dataset" or not self.hf_repo:
            return
        api = self._get_hf_api()
        api.create_repo(repo_id=self.hf_repo, repo_type="dataset", private=True, exist_ok=True)

    def bootstrap_on_startup(self, data_dir: Path, models_dir: Path | None = None) -> dict[str, Any]:
        """Khôi phục trạng thái bền vững từ Cloud Storage về thư mục làm việc khi khởi động."""
        data_dir = Path(data_dir)
        models_dir = Path(models_dir) if models_dir is not None else (data_dir.parent / "models")
        restored = {"archive_structure": False, "uploads_files": 0, "ocr_files": 0, "data_files": 0, "model_files": 0}

        if self.backend == "ephemeral":
            with self._lock:
                self.bootstrapped = True
            return {"backend": self.backend, "durable": False, "restored": restored}

        try:
            if self.backend == "local_volume":
                assert self.volume_dir is not None
                vol_state = self.volume_dir / "state" / "archive_structure.json"
                if vol_state.is_file():
                    _atomic_copy(vol_state, data_dir / "archive_structure.json")
                    restored["archive_structure"] = True
                vol_manifest = self.volume_dir / "data" / "manifest.csv"
                if vol_manifest.is_file() and not (data_dir / "manifest.csv").is_file():
                    _atomic_copy(vol_manifest, data_dir / "manifest.csv")
                    restored["data_files"] += 1
                restored["data_files"] += _copy_tree_merge(
                    self.volume_dir / "data" / "processed", data_dir / "processed", overwrite=False
                )
                restored["model_files"] += _copy_tree_merge(
                    self.volume_dir / "models", models_dir, overwrite=False
                )
                restored["uploads_files"] += _copy_tree_merge(
                    self.volume_dir / "uploads", data_dir / "uploads", overwrite=True
                )
                restored["ocr_files"] += _copy_tree_merge(
                    self.volume_dir / "ocr", data_dir / "ocr", overwrite=True
                )
                self._record_event("bootstrap", str(self.volume_dir), "ok", f"Khôi phục {restored['uploads_files']} tệp tải lên")
            elif self.backend == "hf_dataset":
                has_base_data = (data_dir / "manifest.csv").is_file() and any((data_dir / "processed").glob("*.jsonl"))
                has_base_models = models_dir.is_dir() and any(models_dir.iterdir())
                patterns = ["state/*", "uploads/*", "ocr/up_*"]
                if not has_base_data:
                    patterns.extend(["data/manifest.csv", "data/processed/*", "ocr/*"])
                if not has_base_models:
                    patterns.append("models/*")
                snap_dir = Path(
                    self._snapshot_download(
                        repo_id=self.hf_repo,
                        repo_type="dataset",
                        token=self.hf_token or None,
                        allow_patterns=patterns,
                    )
                )
                snap_state = snap_dir / "state" / "archive_structure.json"
                if snap_state.is_file():
                    _atomic_copy(snap_state, data_dir / "archive_structure.json")
                    restored["archive_structure"] = True
                snap_manifest = snap_dir / "data" / "manifest.csv"
                if snap_manifest.is_file() and not (data_dir / "manifest.csv").is_file():
                    _atomic_copy(snap_manifest, data_dir / "manifest.csv")
                    restored["data_files"] += 1
                restored["data_files"] += _copy_tree_merge(
                    snap_dir / "data" / "processed", data_dir / "processed", overwrite=False
                )
                restored["model_files"] += _copy_tree_merge(
                    snap_dir / "models", models_dir, overwrite=False
                )
                restored["uploads_files"] += _copy_tree_merge(
                    snap_dir / "uploads", data_dir / "uploads", overwrite=True
                )
                restored["ocr_files"] += _copy_tree_merge(
                    snap_dir / "ocr", data_dir / "ocr", overwrite=True
                )
                self._record_event("bootstrap", self.hf_repo, "ok", f"Khôi phục {restored['uploads_files']} tệp tải lên")
        except Exception as exc:
            self._record_event("bootstrap", self.target_label, "error", str(exc))
        finally:
            with self._lock:
                self.bootstrapped = True

        return {"backend": self.backend, "durable": self.durable, "restored": restored}

    def _do_sync_archive_structure(self, structure_path: Path) -> None:
        if not structure_path.is_file():
            return
        if self.backend == "local_volume" and self.volume_dir is not None:
            _atomic_copy(structure_path, self.volume_dir / "state" / "archive_structure.json")
            self._record_event("sync_state", "state/archive_structure.json", "ok", "Đồng bộ danh mục hồ sơ")
            return
        if self.backend == "hf_dataset":
            self._ensure_hf_repo()
            api = self._get_hf_api()
            api.upload_file(
                path_or_fileobj=str(structure_path),
                path_in_repo="state/archive_structure.json",
                repo_id=self.hf_repo,
                repo_type="dataset",
                commit_message="Sync archive_structure.json from Cloud Runtime",
            )
            self._record_event("sync_state", "state/archive_structure.json", "ok", "Đã đẩy lên Private Dataset")

    def sync_archive_structure(self, structure_path: Path, background: bool = True) -> dict[str, Any]:
        """Đồng bộ tệp cấu trúc Phông – Hồ sơ lên kho lưu trữ bền vững."""
        if not self.durable:
            return {"synced": False, "backend": self.backend}

        def _run():
            try:
                self._do_sync_archive_structure(Path(structure_path))
            except Exception as exc:
                self._record_event("sync_state", "state/archive_structure.json", "error", str(exc))

        self._submit(_run, background=background)
        return {"synced": True, "backend": self.backend, "background": background and self.backend == "hf_dataset"}

    def _do_sync_upload(self, doc_id: str, upload_dir: Path, ocr_dir: Path) -> None:
        if not _SAFE_UPLOAD_ID.match(doc_id):
            raise ValueError(f"Mã tệp tải lên không hợp lệ: {doc_id!r}")
        src_up = upload_dir / doc_id
        src_ocr = ocr_dir / doc_id
        if self.backend == "local_volume" and self.volume_dir is not None:
            cnt = _copy_tree_merge(src_up, self.volume_dir / "uploads" / doc_id, overwrite=True)
            if src_ocr.is_dir():
                cnt += _copy_tree_merge(src_ocr, self.volume_dir / "ocr" / doc_id, overwrite=True)
            self._record_event("sync_upload", doc_id, "ok", f"Đồng bộ {cnt} tệp lên Volume")
            return
        if self.backend == "hf_dataset":
            self._ensure_hf_repo()
            api = self._get_hf_api()
            with tempfile.TemporaryDirectory(prefix="hf_sync_up_") as tmp:
                stage = Path(tmp)
                if src_up.is_dir():
                    _copy_tree_merge(src_up, stage / "uploads" / doc_id, overwrite=True)
                if src_ocr.is_dir():
                    _copy_tree_merge(src_ocr, stage / "ocr" / doc_id, overwrite=True)
                api.upload_folder(
                    folder_path=str(stage),
                    repo_id=self.hf_repo,
                    repo_type="dataset",
                    commit_message=f"Sync upload {doc_id}",
                )
            self._record_event("sync_upload", doc_id, "ok", "Đã đẩy PDF & cache OCR lên Dataset")

    def sync_upload(self, doc_id: str, upload_dir: Path, ocr_dir: Path, background: bool = True) -> dict[str, Any]:
        """Đồng bộ tài liệu PDF người dùng tải lên và cache OCR lên Cloud Storage."""
        if not self.durable:
            return {"synced": False, "backend": self.backend}

        def _run():
            try:
                self._do_sync_upload(doc_id, Path(upload_dir), Path(ocr_dir))
            except Exception as exc:
                self._record_event("sync_upload", doc_id, "error", str(exc))

        self._submit(_run, background=background)
        return {"synced": True, "backend": self.backend}

    def _do_delete_upload(self, doc_id: str) -> None:
        if not _SAFE_UPLOAD_ID.match(doc_id):
            raise ValueError(f"Mã tệp tải lên không hợp lệ: {doc_id!r}")
        if self.backend == "local_volume" and self.volume_dir is not None:
            shutil.rmtree(self.volume_dir / "uploads" / doc_id, ignore_errors=True)
            shutil.rmtree(self.volume_dir / "ocr" / doc_id, ignore_errors=True)
            self._record_event("delete_upload", doc_id, "ok", "Đã xóa khỏi Volume")
            return
        if self.backend == "hf_dataset":
            api = self._get_hf_api()
            for prefix in (f"uploads/{doc_id}", f"ocr/{doc_id}"):
                try:
                    api.delete_folder(
                        path_in_repo=prefix,
                        repo_id=self.hf_repo,
                        repo_type="dataset",
                        commit_message=f"Delete remote upload {doc_id}",
                    )
                except Exception:
                    pass
            self._record_event("delete_upload", doc_id, "ok", "Đã xóa khỏi Dataset")

    def delete_remote_upload(self, doc_id: str, background: bool = True) -> dict[str, Any]:
        if not self.durable:
            return {"deleted": False, "backend": self.backend}

        def _run():
            try:
                self._do_delete_upload(doc_id)
            except Exception as exc:
                self._record_event("delete_upload", doc_id, "error", str(exc))

        self._submit(_run, background=background)
        return {"deleted": True, "backend": self.backend}

    def ensure_raw_pdf(self, doc_id: str, raw_dir: Path) -> Path | None:
        """Tìm PDF cục bộ; nếu chưa có thì tải lười (lazy fetch) từ Cloud Storage."""
        if not _SAFE_DOC_ID.match(doc_id) or ".." in doc_id:
            return None
        raw_root = Path(raw_dir).resolve()
        raw_root.mkdir(parents=True, exist_ok=True)
        local_pdf = (raw_root / f"{doc_id}.pdf").resolve()
        if not local_pdf.is_relative_to(raw_root):
            return None
        if local_pdf.is_file():
            return local_pdf

        if self.backend == "local_volume" and self.volume_dir is not None:
            vol_pdf = self.volume_dir / "raw" / f"{doc_id}.pdf"
            if vol_pdf.is_file():
                _atomic_copy(vol_pdf, local_pdf)
                with self._lock:
                    self.lazy_fetches += 1
                self._record_event("lazy_fetch", f"{doc_id}.pdf", "ok", "Nạp từ Persistent Volume")
                return local_pdf
            return None

        if self.backend == "hf_dataset":
            try:
                downloaded = Path(
                    self._hf_hub_download(
                        repo_id=self.hf_repo,
                        repo_type="dataset",
                        filename=f"raw/{doc_id}.pdf",
                        token=self.hf_token or None,
                    )
                )
                if downloaded.is_file():
                    _atomic_copy(downloaded, local_pdf)
                    with self._lock:
                        self.lazy_fetches += 1
                    self._record_event("lazy_fetch", f"{doc_id}.pdf", "ok", "Nạp lười từ HF Dataset")
                    return local_pdf
            except Exception as exc:
                self._record_event("lazy_fetch", f"{doc_id}.pdf", "error", str(exc))
        return None

    def sync_now(self, data_dir: Path, action: str = "push", models_dir: Path | None = None) -> dict[str, Any]:
        """Thực hiện đồng bộ thủ công theo yêu cầu quản trị viên ('push' hoặc 'pull')."""
        act = (action or "push").strip().lower()
        if act not in ("push", "pull"):
            raise ValueError("Hành động đồng bộ không hợp lệ (chỉ hỗ trợ 'push' hoặc 'pull').")
        data_dir = Path(data_dir)
        if act == "pull":
            return self.bootstrap_on_startup(data_dir, models_dir=models_dir)

        if not self.durable:
            self._record_event("sync_now", "ephemeral", "skipped", "Chưa gắn kho lưu trữ bền vững")
            return {"action": "push", "backend": self.backend, "durable": False, "synced_uploads": 0}

        struct_path = data_dir / "archive_structure.json"
        if struct_path.is_file():
            self._do_sync_archive_structure(struct_path)

        up_root = data_dir / "uploads"
        ocr_root = data_dir / "ocr"
        synced_uploads = 0
        if up_root.is_dir():
            for sub in sorted(up_root.iterdir()):
                if sub.is_dir() and _SAFE_UPLOAD_ID.match(sub.name):
                    self._do_sync_upload(sub.name, up_root, ocr_root)
                    synced_uploads += 1

        return {
            "action": "push",
            "backend": self.backend,
            "durable": True,
            "synced_uploads": synced_uploads,
        }

    @property
    def target_label(self) -> str:
        if self.backend == "hf_dataset":
            return self.hf_repo
        if self.backend == "local_volume" and self.volume_dir is not None:
            return str(self.volume_dir)
        return "container-local-ephemeral"

    def status(self) -> dict[str, Any]:
        with self._lock:
            pending = sum(1 for f in self._pending_futures if not f.done())
            return {
                "backend": self.backend,
                "durable": self.durable,
                "target": self.target_label,
                "has_hf_token": bool(self.hf_token),
                "bootstrapped": self.bootstrapped,
                "last_sync_at": self.last_sync_at,
                "sync_ok_count": self.sync_ok_count,
                "sync_err_count": self.sync_err_count,
                "lazy_fetches": self.lazy_fetches,
                "pending_tasks": pending,
                "recent_events": list(self._events),
            }


_CLOUD_STORE_LOCK = threading.Lock()
_cloud_store: CloudStorageManager | None = None


def get_cloud_store() -> CloudStorageManager:
    global _cloud_store
    with _CLOUD_STORE_LOCK:
        if _cloud_store is None:
            _cloud_store = CloudStorageManager()
        return _cloud_store


def reset_cloud_store(instance: CloudStorageManager | None = None) -> CloudStorageManager:
    global _cloud_store
    with _CLOUD_STORE_LOCK:
        _cloud_store = instance if instance is not None else CloudStorageManager()
        return _cloud_store
