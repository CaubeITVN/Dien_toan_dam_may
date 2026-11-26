"""Quản lý Phông, Mục lục và Hồ sơ lưu trữ theo tiêu chuẩn Thông tư 02/2019/TT-BNV và Luật Lưu trữ.

Mô hình phân cấp:
Phông lưu trữ (Fonds) -> Mục lục hồ sơ (Catalog) -> Hồ sơ lưu trữ (Dossier) -> Văn bản số hóa (Document)
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

from src.config import DATA_DIR

ARCHIVE_STRUCTURE_PATH = DATA_DIR / "archive_structure.json"

# Các trường siêu dữ liệu hồ sơ lưu trữ được tạo mô phỏng (không phải dữ liệu thật của Sở)
SIMULATED_DOSSIER_FIELDS: tuple[str, ...] = (
    "file_code",
    "title",
    "retention_period",
    "usage_mode",
    "start_date",
    "end_date",
    "total_sheets",
    "doc_ids",
)

PUBLIC_USAGE_MODES = {"", "công khai", "cong khai"}
PRIVILEGED_ROLES = {"internal", "admin"}


def is_access_allowed(usage_mode: str | None, user_role: str = "public") -> bool:
    """Kiểm tra quyền tiếp cận theo chế độ sử dụng hồ sơ (mô phỏng).

    - "Công khai": cho phép mọi vai trò.
    - "Nội bộ" / "Hạn chế" / "Mật": chỉ cho phép "internal" hoặc "admin".
    """
    role = (user_role or "public").strip().lower()
    mode = (usage_mode or "Công khai").strip().lower()
    if mode in PUBLIC_USAGE_MODES:
        return True
    return role in PRIVILEGED_ROLES


@dataclass
class Dossier:
    file_code: str
    catalog_no: str
    title: str
    retention_period: str
    usage_mode: str
    start_date: str
    end_date: str
    creator_unit: str
    doc_ids: list[str] = field(default_factory=list)
    fond_id: str = ""
    fond_name: str = ""
    location: str = "UBND Tỉnh Thái Nguyên / Cơ quan / Kho số 1"
    status: str = "Tạo mới"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["ho_so_id"] = self.file_code
        d["total_sheets"] = len(self.doc_ids)
        d["simulated"] = True
        d["simulated_fields"] = list(SIMULATED_DOSSIER_FIELDS)
        return d


@dataclass
class Fond:
    fond_id: str
    fond_name: str
    agency_name: str
    time_range: str
    description: str
    dossiers: list[Dossier] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["total_dossiers"] = len(self.dossiers)
        d["total_docs"] = sum(len(dos.doc_ids) for dos in self.dossiers)
        return d


def _validate_file_code(code: str) -> str:
    cleaned = code.strip()
    if not cleaned:
        return ""
    if len(cleaned) > 80 or ".." in cleaned or "/" in cleaned or "\\" in cleaned or any(ord(c) < 32 for c in cleaned):
        raise ValueError("Mã hồ sơ chứa ký tự không hợp lệ (không được chứa '/', '\\', '..' hoặc ký tự điều khiển)")
    return cleaned


class ArchiveManager:
    """Quản trị phông, hồ sơ lưu trữ và ánh xạ văn bản (an toàn đa luồng)."""

    def __init__(self, structure_path: Path = ARCHIVE_STRUCTURE_PATH, auto_save: bool = False):
        self._lock = threading.RLock()
        self.structure_path = Path(structure_path)
        self.auto_save = bool(auto_save)
        self.fonds: dict[str, Fond] = {}
        self.dossiers: dict[str, Dossier] = {}
        self.doc_to_dossier: dict[str, Dossier] = {}
        self.portal_meta: dict = {}
        self.load()

    def load(self) -> None:
        with self._lock:
            if not self.structure_path.exists():
                return
            with open(self.structure_path, encoding="utf-8") as f:
                data = json.load(f)

            self.portal_meta = {
                "portal_name": data.get("portal_name", "Cổng Quản lý Tài liệu Lưu trữ Số hóa"),
                "portal_url": data.get("portal_url", "https://quanlytlltsohoa.thainguyen.gov.vn"),
                "managing_unit": data.get("managing_unit", "Sở Nội vụ tỉnh Thái Nguyên"),
                "regulations": data.get("regulations", []),
            }

            self.fonds.clear()
            self.dossiers.clear()
            self.doc_to_dossier.clear()

            for f_data in data.get("fonds", []):
                fond = Fond(
                    fond_id=f_data["fond_id"],
                    fond_name=f_data["fond_name"],
                    agency_name=f_data["agency_name"],
                    time_range=f_data["time_range"],
                    description=f_data.get("description", ""),
                )
                for d_data in f_data.get("dossiers", []):
                    dossier = Dossier(
                        file_code=d_data["file_code"],
                        catalog_no=d_data.get("catalog_no", "01"),
                        title=d_data["title"],
                        retention_period=d_data.get("retention_period", "Vĩnh viễn"),
                        usage_mode=d_data.get("usage_mode", "Công khai"),
                        start_date=d_data.get("start_date", ""),
                        end_date=d_data.get("end_date", ""),
                        creator_unit=d_data.get("creator_unit", ""),
                        doc_ids=list(d_data.get("doc_ids", [])),
                        fond_id=fond.fond_id,
                        fond_name=fond.fond_name,
                        location=d_data.get("location", "UBND Tỉnh Thái Nguyên / Cơ quan / Kho số 1"),
                        status=d_data.get("status", "Tạo mới"),
                    )
                    fond.dossiers.append(dossier)
                    self.dossiers[dossier.file_code] = dossier
                    for doc_id in dossier.doc_ids:
                        self.doc_to_dossier[doc_id] = dossier
                self.fonds[fond.fond_id] = fond

    def save(self, path: Path | None = None) -> None:
        """Ghi nguyên tử toàn bộ cấu trúc Phông/Hồ sơ xuống tệp JSON."""
        with self._lock:
            target = Path(path) if path is not None else self.structure_path
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "portal_name": self.portal_meta.get("portal_name", "Cổng Quản lý Tài liệu Lưu trữ Số hóa tỉnh Thái Nguyên"),
                "portal_url": self.portal_meta.get("portal_url", "https://quanlytlltsohoa.thainguyen.gov.vn"),
                "managing_unit": self.portal_meta.get("managing_unit", "Sở Nội vụ tỉnh Thái Nguyên"),
                "regulations": list(self.portal_meta.get("regulations", [])),
                "fonds": [
                    {
                        "fond_id": f.fond_id,
                        "fond_name": f.fond_name,
                        "agency_name": f.agency_name,
                        "time_range": f.time_range,
                        "description": f.description,
                        "dossiers": [
                            {
                                "file_code": d.file_code,
                                "catalog_no": d.catalog_no,
                                "title": d.title,
                                "retention_period": d.retention_period,
                                "usage_mode": d.usage_mode,
                                "start_date": d.start_date,
                                "end_date": d.end_date,
                                "creator_unit": d.creator_unit,
                                "location": d.location,
                                "status": d.status,
                                "doc_ids": list(d.doc_ids),
                            }
                            for d in f.dossiers
                        ],
                    }
                    for f in self.fonds.values()
                ],
            }
            fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=f".{target.name}.tmp.")
            tmp_path = Path(tmp_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, ensure_ascii=False, indent=2)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp_path, target)
            finally:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass

    def _maybe_save_unlocked(self) -> None:
        if self.auto_save:
            self.save()

    def _resolve_fond(self, fond_id: str | None) -> Fond:
        fid = (fond_id or "").strip()
        if fid and fid in self.fonds:
            return self.fonds[fid]
        if fid:
            for f in self.fonds.values():
                if f.fond_name.strip().lower() == fid.lower():
                    return f
        if "P_UBND_TN" in self.fonds:
            return self.fonds["P_UBND_TN"]
        if self.fonds:
            return next(iter(self.fonds.values()))
        default_fond = Fond(
            fond_id="P_UBND_TN",
            fond_name="Phông Ủy ban nhân dân tỉnh Thái Nguyên",
            agency_name="Ủy ban nhân dân tỉnh Thái Nguyên",
            time_range="2026",
            description="Phông mặc định quản lý hồ sơ số hóa.",
        )
        self.fonds[default_fond.fond_id] = default_fond
        return default_fond

    def create_dossier(self, data: dict) -> Dossier:
        """Tạo mới một hồ sơ lưu trữ theo chuẩn Thông tư 02/2019/TT-BNV."""
        with self._lock:
            title = (data.get("title") or "").strip()
            if not title:
                raise ValueError("Tiêu đề hồ sơ không được để trống")

            fond = self._resolve_fond(data.get("fond_id"))
            file_code = _validate_file_code(data.get("file_code") or "")
            if not file_code:
                idx = len(self.dossiers) + 1
                while f"TN.2026.HS.{idx:03d}" in self.dossiers:
                    idx += 1
                file_code = f"TN.2026.HS.{idx:03d}"

            if file_code in self.dossiers:
                raise ValueError(f"Mã hồ sơ '{file_code}' đã tồn tại")

            raw_doc_ids = data.get("doc_ids") or []
            if isinstance(raw_doc_ids, str):
                doc_ids = [x.strip() for x in raw_doc_ids.split(",") if x.strip()]
            else:
                doc_ids = [str(x).strip() for x in raw_doc_ids if str(x).strip()]

            dossier = Dossier(
                file_code=file_code,
                catalog_no=(data.get("catalog_no") or "01").strip() or "01",
                title=title,
                retention_period=(data.get("retention_period") or "Vĩnh viễn").strip() or "Vĩnh viễn",
                usage_mode=(data.get("usage_mode") or "Công khai").strip() or "Công khai",
                start_date=(data.get("start_date") or "").strip(),
                end_date=(data.get("end_date") or "").strip(),
                creator_unit=(data.get("creator_unit") or fond.agency_name).strip(),
                doc_ids=doc_ids,
                fond_id=fond.fond_id,
                fond_name=fond.fond_name,
                location=(data.get("location") or "UBND Tỉnh Thái Nguyên / Cơ quan / Kho số 1").strip(),
                status=(data.get("status") or "Tạo mới").strip() or "Tạo mới",
            )
            fond.dossiers.append(dossier)
            self.dossiers[dossier.file_code] = dossier
            for doc_id in dossier.doc_ids:
                self.doc_to_dossier[doc_id] = dossier
            self._maybe_save_unlocked()
            return dossier

    def update_dossier(self, file_code: str, data: dict) -> Dossier:
        """Cập nhật siêu dữ liệu, vị trí lưu trữ hoặc trạng thái nghiệp vụ hồ sơ."""
        with self._lock:
            dos = self.dossiers.get(file_code)
            if not dos:
                raise KeyError(file_code)

            for field_name in (
                "catalog_no",
                "title",
                "retention_period",
                "usage_mode",
                "start_date",
                "end_date",
                "creator_unit",
                "location",
                "status",
            ):
                if field_name in data and data[field_name] is not None:
                    val = str(data[field_name]).strip()
                    if field_name == "title" and not val:
                        raise ValueError("Tiêu đề hồ sơ không được để trống")
                    setattr(dos, field_name, val)

            new_fond_ref = (data.get("fond_id") or "").strip() if "fond_id" in data else ""
            if new_fond_ref and new_fond_ref != dos.fond_id:
                old_fond = self.fonds.get(dos.fond_id)
                target_fond = self._resolve_fond(new_fond_ref)
                if old_fond and dos in old_fond.dossiers:
                    old_fond.dossiers.remove(dos)
                if dos not in target_fond.dossiers:
                    target_fond.dossiers.append(dos)
                dos.fond_id = target_fond.fond_id
                dos.fond_name = target_fond.fond_name

            if "doc_ids" in data and data["doc_ids"] is not None:
                raw_doc_ids = data["doc_ids"]
                if isinstance(raw_doc_ids, str):
                    new_doc_ids = [x.strip() for x in raw_doc_ids.split(",") if x.strip()]
                else:
                    new_doc_ids = [str(x).strip() for x in raw_doc_ids if str(x).strip()]
                for old_doc_id in dos.doc_ids:
                    if old_doc_id not in new_doc_ids and self.doc_to_dossier.get(old_doc_id) is dos:
                        self.doc_to_dossier.pop(old_doc_id, None)
                dos.doc_ids = new_doc_ids
                for doc_id in dos.doc_ids:
                    self.doc_to_dossier[doc_id] = dos

            self._maybe_save_unlocked()
            return dos

    def delete_dossier(self, file_code: str) -> bool:
        """Xóa một hồ sơ khỏi kho lưu trữ và gỡ ánh xạ tài liệu."""
        with self._lock:
            dos = self.dossiers.pop(file_code, None)
            if not dos:
                return False
            fond = self.fonds.get(dos.fond_id)
            if fond and dos in fond.dossiers:
                fond.dossiers.remove(dos)
            for doc_id in dos.doc_ids:
                if self.doc_to_dossier.get(doc_id) is dos:
                    self.doc_to_dossier.pop(doc_id, None)
            self._maybe_save_unlocked()
            return True

    def import_dossiers(self, rows: list[dict]) -> dict:
        """Nhập hàng loạt hồ sơ từ CSV hoặc JSON theo mẫu Thông tư 02/2019/TT-BNV."""
        with self._lock:
            imported = 0
            updated = 0
            was_auto = self.auto_save
            self.auto_save = False
            try:
                for raw in rows:
                    if not isinstance(raw, dict):
                        continue
                    code = _validate_file_code(str(raw.get("file_code") or raw.get("Mã hồ sơ") or ""))
                    title = str(raw.get("title") or raw.get("Tiêu đề hồ sơ") or raw.get("Tiêu đề") or "").strip()
                    if not title:
                        continue

                    time_span = str(raw.get("Thời gian tài liệu") or "").strip()
                    start_d = str(raw.get("start_date") or raw.get("Thời gian bắt đầu") or "").strip()
                    end_d = str(raw.get("end_date") or raw.get("Thời gian kết thúc") or "").strip()
                    if time_span and not (start_d or end_d) and "-" in time_span:
                        parts = [p.strip() for p in time_span.split("-", 1)]
                        start_d, end_d = parts[0], parts[1]

                    payload = {
                        "file_code": code,
                        "catalog_no": str(raw.get("catalog_no") or raw.get("Mục lục số") or "01").strip(),
                        "title": title,
                        "fond_id": str(raw.get("fond_id") or raw.get("Phông lưu trữ") or "P_UBND_TN").strip(),
                        "creator_unit": str(raw.get("creator_unit") or raw.get("Đơn vị lập") or "").strip(),
                        "start_date": start_d,
                        "end_date": end_d,
                        "retention_period": str(raw.get("retention_period") or raw.get("Thời hạn bảo quản") or "Vĩnh viễn").strip(),
                        "usage_mode": str(raw.get("usage_mode") or raw.get("Chế độ sử dụng") or "Công khai").strip(),
                        "location": str(raw.get("location") or raw.get("Vị trí lưu trữ") or raw.get("Vị trí") or "UBND Tỉnh Thái Nguyên / Cơ quan / Kho số 1").strip(),
                        "status": str(raw.get("status") or raw.get("Trạng thái") or "Tạo mới").strip(),
                    }
                    if code and code in self.dossiers:
                        self.update_dossier(code, payload)
                        updated += 1
                    else:
                        self.create_dossier(payload)
                        imported += 1
            finally:
                self.auto_save = was_auto

            self._maybe_save_unlocked()
            return {"imported": imported, "updated": updated, "total": len(self.dossiers)}

    def ensure_upload_doc(self, doc_id: str, original_name: str = "") -> Dossier:
        """Đưa văn bản tải lên vào Hồ sơ tiếp nhận nộp lưu điện tử (không văng KeyError nếu hồ sơ từng bị xóa)."""
        with self._lock:
            upload_fond_id = "P_TIEP_NHAN"
            upload_code = "TN.2026.P99.01.001"
            changed = False
            if upload_fond_id not in self.fonds:
                fond = Fond(
                    fond_id=upload_fond_id,
                    fond_name="Phông Tiếp nhận hồ sơ số hóa mới",
                    agency_name="Bộ phận Một cửa / Tiếp nhận số hóa",
                    time_range="2026",
                    description="Các tài liệu văn bản scan được tải lên tiếp nhận để bóc tách thông tin và phân loại vào phông lưu trữ.",
                )
                self.fonds[upload_fond_id] = fond
                changed = True
            else:
                fond = self.fonds[upload_fond_id]

            if upload_code not in self.dossiers:
                dossier = Dossier(
                    file_code=upload_code,
                    catalog_no="01",
                    title="Hồ sơ tiếp nhận văn bản số hóa mới tải lên hệ thống",
                    retention_period="Chờ duyệt",
                    usage_mode="Công khai",
                    start_date="2026",
                    end_date="2026",
                    creator_unit="Bộ phận Tiếp nhận số hóa",
                    doc_ids=[],
                    fond_id=upload_fond_id,
                    fond_name=fond.fond_name,
                )
                fond.dossiers.append(dossier)
                self.dossiers[upload_code] = dossier
                changed = True
            else:
                dossier = self.dossiers[upload_code]

            if doc_id not in dossier.doc_ids:
                dossier.doc_ids.append(doc_id)
                changed = True
            if self.doc_to_dossier.get(doc_id) is not dossier:
                self.doc_to_dossier[doc_id] = dossier
                changed = True
            if changed:
                self._maybe_save_unlocked()
            return dossier

    def remove_upload_doc(self, doc_id: str) -> None:
        """Gỡ văn bản tải lên khỏi mọi hồ sơ đang chứa nó và lưu lại nếu cần."""
        with self._lock:
            changed = False
            for dos in self.dossiers.values():
                if doc_id in dos.doc_ids:
                    dos.doc_ids = [d for d in dos.doc_ids if d != doc_id]
                    changed = True
            if self.doc_to_dossier.pop(doc_id, None) is not None:
                changed = True
            if changed:
                self._maybe_save_unlocked()

    def get_doc_archive_info(self, doc_id: str) -> dict:
        """Lấy siêu dữ liệu lưu trữ cấp hồ sơ cho một văn bản."""
        dos = self.doc_to_dossier.get(doc_id)
        if not dos:
            # Fallback nếu văn bản chưa được gán hồ sơ
            return {
                "fond_id": "P_CHUA_PHAN_LOAI",
                "fond_name": "Chưa phân loại phông",
                "file_code": "CHUA_LAP_HO_SO",
                "ho_so_id": "CHUA_LAP_HO_SO",
                "dossier_title": "Tài liệu chưa lập hồ sơ",
                "retention_period": "Chưa xác định",
                "usage_mode": "Công khai",
                "start_date": "",
                "end_date": "",
                "creator_unit": "",
                "simulated": True,
                "simulated_fields": list(SIMULATED_DOSSIER_FIELDS),
            }
        return {
            "fond_id": dos.fond_id,
            "fond_name": dos.fond_name,
            "file_code": dos.file_code,
            "ho_so_id": dos.file_code,
            "dossier_title": dos.title,
            "retention_period": dos.retention_period,
            "usage_mode": dos.usage_mode,
            "start_date": dos.start_date,
            "end_date": dos.end_date,
            "creator_unit": dos.creator_unit,
            "simulated": True,
            "simulated_fields": list(SIMULATED_DOSSIER_FIELDS),
        }

    def is_access_allowed(self, usage_mode: str | None, user_role: str = "public") -> bool:
        """Kiểm tra quyền tiếp cận theo chế độ sử dụng của hồ sơ."""
        return is_access_allowed(usage_mode, user_role=user_role)

    def can_access_doc(self, doc_id: str, user_role: str = "public") -> bool:
        """Kiểm tra người dùng có quyền tiếp cận văn bản theo mức tiếp cận của hồ sơ."""
        info = self.get_doc_archive_info(doc_id)
        return is_access_allowed(info.get("usage_mode"), user_role=user_role)

    def get_tree(self) -> list[dict]:
        """Cây Phông - Hồ sơ phục vụ hiển thị trên giao diện."""
        with self._lock:
            tree = []
            for f in self.fonds.values():
                f_dict = f.to_dict()
                f_dict["dossiers"] = [d.to_dict() for d in f.dossiers]
                tree.append(f_dict)
            return tree

    def filter_doc_ids(
        self,
        fond_id: str | None = None,
        file_code: str | None = None,
        retention_period: str | None = None,
        usage_mode: str | None = None,
    ) -> set[str] | None:
        """Lọc danh sách doc_id theo tiêu chí lưu trữ; None nghĩa là không lọc."""
        with self._lock:
            conditions = [fond_id, file_code, retention_period, usage_mode]
            if not any(conditions):
                return None

            if file_code:
                dos = self.dossiers.get(file_code)
                if not dos:
                    return set()
                if fond_id and dos.fond_id != fond_id:
                    return set()
                if retention_period and dos.retention_period != retention_period:
                    return set()
                if usage_mode and dos.usage_mode != usage_mode:
                    return set()
                return set(dos.doc_ids)

            candidates = set()
            for doc_id, dos in self.doc_to_dossier.items():
                if fond_id and dos.fond_id != fond_id:
                    continue
                if retention_period and dos.retention_period != retention_period:
                    continue
                if usage_mode and dos.usage_mode != usage_mode:
                    continue
                candidates.add(doc_id)
            return candidates


_manager: ArchiveManager | None = None
_manager_lock = threading.Lock()


def get_archive_manager() -> ArchiveManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = ArchiveManager()
    return _manager
