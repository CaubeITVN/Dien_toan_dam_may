"""Web Cổng Quản lý và Khai thác Tài liệu Lưu trữ Số hóa tỉnh Thái Nguyên.

Tích hợp:
1. Mô hình Phông - Hồ sơ - Văn bản số hóa theo Thông tư 02/2019/TT-BNV và Luật Lưu trữ.
2. Tra cứu đa tiêu chí (Faceted Search) kết hợp toàn văn BM25 và ngữ nghĩa vector e5.
3. Trợ lý ảo AI Hỏi - Đáp nghiệp vụ lưu trữ đa vòng (Multi-turn RAG có dẫn nguồn kép).
4. Xem ảnh trang PDF độ phân giải cao có tô sáng dòng trích dẫn căn cứ.

Chạy từ gốc Du_an/:  python -m src.cli serve   (hoặc uvicorn web.app:app)
"""
from __future__ import annotations

import csv
import io
import os
import re
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote

import pymupdf
from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import uploads
from src.archive import ArchiveManager, get_archive_manager
from src.archive_qa import get_session_manager, handle_archive_query
from src.archive_search import SearchFilter, faceted_search
from src.cloud_store import get_cloud_store
from src.config import DATA_DIR, MODELS_DIR, OCR_DIR, RAW_DIR
from src.ingest import PAGES_PATH, read_jsonl, read_manifest
from src.llm import LocalLLM
from src.metrics import normalize_for_eval
from src.ocr import load_cached
from src.qa import FIELD_LABELS, Assistant
from src.telemetry import get_telemetry
from src.text import remove_diacritics

STATIC_DIR = Path(__file__).parent / "static"
UPLOAD_DIR = uploads.UPLOAD_DIR
VIEW_DPI = 110
OCR_DPI = 300            # bbox trong cache OCR tính trên ảnh render 300 DPI
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
_SAFE_DOC_ID = re.compile(r"^[A-Za-z0-9_.\-]{1,120}$")

state: dict = {}
_state_lock = threading.RLock()


def _archive_mgr() -> ArchiveManager:
    with _state_lock:
        if "archive_mgr" not in state:
            state["archive_mgr"] = get_archive_manager()
        return state["archive_mgr"]


def _safe_csv_cell(val: object) -> object:
    if isinstance(val, str) and val and val[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + val
    return val


def load_state(pages_path: Path = PAGES_PATH) -> None:
    """Nạp kho chính (data/processed), kho lưu trữ số hóa và các tệp tải lên."""
    pages = read_jsonl(pages_path) if pages_path.exists() else []
    meta = {r["doc_id"]: r for r in read_manifest()} if pages else {}
    paths = {d: RAW_DIR / f"{d}.pdf" for d in {p["doc_id"] for p in pages}}
    archive_mgr = ArchiveManager(auto_save=True)

    for doc_id, pdf, up_pages, up_meta in uploads.list_uploads(UPLOAD_DIR, OCR_DIR):
        pages.extend(up_pages)
        paths[doc_id] = pdf
        meta[doc_id] = up_meta | {"group": "upload", "split": "upload"}
        archive_mgr.ensure_upload_doc(doc_id, up_meta.get("original_name", ""))

    from src.dense import default_encoder

    assistant = Assistant(pages, encoder=default_encoder())
    with _state_lock:
        state.update(
            assistant=assistant,
            paths=paths,
            meta=meta,
            archive_mgr=archive_mgr,
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_cloud_store().bootstrap_on_startup(DATA_DIR, MODELS_DIR)
    if "assistant" not in state:
        load_state()
    yield


app = FastAPI(
    title="Cổng Quản lý Tài liệu Lưu trữ Số hóa tỉnh Thái Nguyên",
    description="Hệ thống quản lý, tra cứu và hỏi đáp thông minh tài liệu lưu trữ số hóa bằng AI (LLM + RAG)",
    lifespan=lifespan,
)


@app.middleware("http")
async def _security_headers_middleware(request: Request, call_next):
    t0 = time.perf_counter()
    status_code = 500
    try:
        resp = await call_next(request)
        status_code = resp.status_code
    finally:
        dur_ms = (time.perf_counter() - t0) * 1000.0
        get_telemetry().record_request(request.url.path, status_code, dur_ms)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.path.startswith("/static/") and request.url.path.endswith((".js", ".css", ".html")):
        resp.headers["Cache-Control"] = "no-cache, must-revalidate"
    return resp


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _assistant() -> Assistant:
    return state["assistant"]


def doc_summary(doc_id: str) -> dict:
    a = _assistant()
    try:
        card = a.cards[doc_id]
        pages = a.doc_pages[doc_id]
    except KeyError as exc:
        raise HTTPException(404, "Không có văn bản này") from exc
    meta = state.get("meta", {}).get(doc_id, {})
    upload = {k: meta[k] for k in ("original_name", "uploaded_at", "size_bytes") if k in meta}
    arch_info = _archive_mgr().get_doc_archive_info(doc_id)

    return {
        "doc_id": doc_id,
        "label": a.doc_label(doc_id),
        "upload": upload or None,
        "group": meta.get("group", ""),
        "split": meta.get("split", ""),
        "n_pages": len(pages),
        "n_missing": sum(p["source"] == "missing" for p in pages),
        "doc_type": card.value("doc_type"),
        "doc_number": card.value("doc_number"),
        "issue_date": card.value("issue_date"),
        "issuer": card.value("issuer"),
        "signer": card.value("signer"),
        "subject": card.value("subject") or card.value("title"),
        "flags": card.flags,
        "fond_id": arch_info.get("fond_id"),
        "fond_name": arch_info.get("fond_name"),
        "file_code": arch_info.get("file_code"),
        "ho_so_id": arch_info.get("ho_so_id"),
        "dossier_title": arch_info.get("dossier_title"),
        "retention_period": arch_info.get("retention_period"),
        "usage_mode": arch_info.get("usage_mode"),
        "simulated": arch_info.get("simulated", True),
        "simulated_fields": arch_info.get("simulated_fields", []),
    }


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache, must-revalidate"})


@app.get("/notebooklm")
@app.get("/notebook")
def notebooklm_view():
    return FileResponse(STATIC_DIR / "notebooklm.html", headers={"Cache-Control": "no-cache, must-revalidate"})


@app.get("/cloud")
def cloud_dashboard_view():
    return FileResponse(STATIC_DIR / "cloud.html", headers={"Cache-Control": "no-cache, must-revalidate"})


@app.get("/healthz")
def healthz():
    return {"status": "ok", "uptime_seconds": get_telemetry().uptime_seconds()}


@app.get("/readyz")
def readyz():
    if "assistant" not in state:
        return Response(
            content='{"ready":false,"reason":"initializing"}',
            status_code=503,
            media_type="application/json",
        )
    a = _assistant()
    st = get_cloud_store().status()
    return {
        "ready": True,
        "n_docs": len(a.doc_pages),
        "n_chunks": len(a.chunks),
        "storage_backend": st["backend"],
        "storage_durable": st["durable"],
    }


@app.get("/api/cloud/status")
def cloud_status():
    """Tổng hợp trạng thái vận hành đám mây, tài nguyên Container, lưu trữ bền vững và LLM."""
    corpus = {"n_docs": 0, "n_pages": 0, "n_chunks": 0, "n_fonds": 0, "n_dossiers": 0}
    if "assistant" in state:
        a = _assistant()
        mgr = _archive_mgr()
        corpus = {
            "n_docs": len(a.doc_pages),
            "n_pages": sum(len(ps) for ps in a.doc_pages.values()),
            "n_chunks": len(a.chunks),
            "n_fonds": len(mgr.fonds),
            "n_dossiers": len(mgr.dossiers),
        }
    return {
        "service": {
            "name": "Thai Nguyen Digital Archive Cloud RAG",
            "version": "2.0.0-cloud",
            "stateless_env": os.environ.get("CLOUD_STATELESS_ENV", "").strip() in ("1", "true", "yes"),
        },
        "telemetry": get_telemetry().snapshot(),
        "storage": get_cloud_store().status(),
        "auth": get_auth_manager().status(),
        "llm": _llm().status(),
        "corpus": corpus,
    }


class CloudSyncRequest(BaseModel):
    action: str = "push"


@app.post("/api/cloud/sync")
def cloud_sync_api(req: CloudSyncRequest, request: Request):
    """Đồng bộ thủ công dữ liệu trạng thái giữa Container và Cloud Storage (chỉ quản trị viên)."""
    _require_auth(request, ("admin",))
    act = (req.action or "push").strip().lower()
    try:
        res = get_cloud_store().sync_now(DATA_DIR, action=act, models_dir=MODELS_DIR)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if act == "pull":
        load_state()
        render_png.cache_clear()
    return {"result": res, "storage": get_cloud_store().status()}


# --- XÁC THỰC NGƯỜI DÙNG & PHÂN QUYỀN (AUTH & RBAC) ---
from src.auth import get_auth_manager


class LoginRequest(BaseModel):
    username: str
    password: str


def _extract_header_token(request: Request) -> str:
    if not isinstance(request, Request):
        return ""
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header:
        scheme, sep, tok = auth_header.partition(" ")
        if sep and scheme.lower() == "bearer":
            return tok.strip()
    return request.headers.get("x-token", "").strip()


def _extract_token(request: Request) -> str:
    hdr = _extract_header_token(request)
    if hdr:
        return hdr
    if isinstance(request, Request) and request.method in ("GET", "HEAD"):
        return request.cookies.get("archive_token", "").strip()
    return ""


def _resolve_request_role(request: Request | None, claimed_role: str | None) -> str:
    """Ưu tiên vai trò từ token đã xác thực ở Backend; HTTP chưa đăng nhập luôn ép về 'public'."""
    if not isinstance(request, Request):
        return (claimed_role or "public").strip().lower()
    hdr_token = _extract_header_token(request)
    if hdr_token:
        user = get_auth_manager().verify_token(hdr_token)
        if not user:
            raise HTTPException(401, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
        return str(user.get("role") or "public")
    if request.method in ("GET", "HEAD"):
        cookie_token = request.cookies.get("archive_token", "").strip()
        if cookie_token:
            user = get_auth_manager().verify_token(cookie_token)
            if user:
                return str(user.get("role") or "public")
    return "public"


def _require_auth(request: Request, allowed_roles: tuple[str, ...] = ("admin", "internal")) -> dict:
    """Yêu cầu xác thực bằng header Bearer/X-Token cho mọi thao tác ghi/cấu hình."""
    token = _extract_header_token(request)
    if not token:
        raise HTTPException(401, "Yêu cầu đăng nhập để thực hiện thao tác này.")
    user = get_auth_manager().verify_token(token)
    if not user:
        raise HTTPException(401, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn.")
    role = str(user.get("role") or "public").strip().lower()
    if role not in allowed_roles:
        raise HTTPException(403, "Tài khoản không có quyền thực hiện thao tác này.")
    return user


@app.post("/api/auth/login")
def login(req: LoginRequest, response: Response):
    auth_mgr = get_auth_manager()
    wait_sec = auth_mgr.is_locked(req.username)
    if wait_sec > 0:
        raise HTTPException(429, f"Tài khoản đang tạm khóa do nhập sai nhiều lần. Vui lòng thử lại sau {wait_sec} giây.")
    res = auth_mgr.authenticate(req.username, req.password)
    if not res:
        wait_after = auth_mgr.is_locked(req.username)
        if wait_after > 0:
            raise HTTPException(429, f"Nhập sai quá số lần cho phép. Tài khoản bị tạm khóa {wait_after} giây.")
        raise HTTPException(401, "Tên đăng nhập hoặc mật khẩu không chính xác")
    response.set_cookie("archive_token", res["token"], httponly=True, samesite="lax", path="/")
    return res


@app.get("/api/auth/me")
def get_current_user(request: Request):
    token = _extract_token(request)
    if not token:
        return {"authenticated": False, "user": None}
    user = get_auth_manager().verify_token(token)
    if not user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": user}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    mgr = get_auth_manager()
    for tok in (_extract_header_token(request), request.cookies.get("archive_token", "").strip()):
        if tok:
            mgr.logout(tok)
    response.delete_cookie("archive_token", path="/")
    return {"status": "logged_out"}


@app.get("/api/auth/accounts")
def list_accounts():
    """Danh sách các tài khoản kiểm thử mẫu."""
    return get_auth_manager().list_preset_accounts()


@app.get("/api/status")
def status():
    a = _assistant()
    mgr = _archive_mgr()
    pages = [p for ps in a.doc_pages.values() for p in ps]
    by_source = {}
    for p in pages:
        by_source[p["source"]] = by_source.get(p["source"], 0) + 1
    return {
        "n_docs": len(a.doc_pages),
        "n_pages": len(pages),
        "n_chunks": len(a.chunks),
        "n_fonds": len(mgr.fonds),
        "n_dossiers": len(mgr.dossiers),
        "by_source": by_source,
        "portal_meta": mgr.portal_meta,
    }


@app.get("/api/docs")
def list_docs(request: Request = None):
    """Danh sách văn bản trong kho có thông tin Phông và Hồ sơ (lọc theo quyền tiếp cận)."""
    role = _resolve_request_role(request, None)
    mgr = _archive_mgr()
    docs = [
        doc_summary(d)
        for d in _assistant().doc_pages
        if mgr.can_access_doc(d, user_role=role)
    ]
    return sorted(docs, key=lambda d: (d["group"] != "upload", d["n_missing"] == d["n_pages"], d["doc_id"]))


@app.get("/api/docs/{doc_id}")
def get_doc(doc_id: str, request: Request = None):
    a = _assistant()
    if doc_id not in a.cards:
        raise HTTPException(404, "Không có văn bản này")
    role = _resolve_request_role(request, None)
    if not _archive_mgr().can_access_doc(doc_id, user_role=role):
        raise HTTPException(403, "Bạn không có quyền truy cập văn bản thuộc chế độ hạn chế/nội bộ.")
    card = a.cards[doc_id]
    fields = [
        {"name": k, "label": FIELD_LABELS.get(k, "Chức vụ người ký"), **asdict(v)}
        for k, v in card.fields.items()
    ]
    pages = [
        {"page_no": p["page_no"], "source": p["source"], "n_chars": len(p["text"])}
        for p in a.doc_pages[doc_id]
    ]
    return doc_summary(doc_id) | {"fields": fields, "pages": pages, "suggestions": suggestions(doc_id)}


# --- CÁC ENDPOINT QUẢN LÝ LƯU TRỮ (ARCHIVE FONDS & DOSSIERS) ---

@app.get("/api/archive/tree")
def archive_tree():
    """Lấy cây Phông lưu trữ -> Mục lục -> Danh mục Hồ sơ."""
    return _archive_mgr().get_tree()


@app.get("/api/archive/fonds")
def archive_fonds():
    """Danh sách các Phông lưu trữ."""
    mgr = _archive_mgr()
    return [f.to_dict() for f in mgr.fonds.values()]


@app.get("/api/archive/dossiers")
def list_dossiers(title: str = "", file_code: str = "", status: str = ""):
    """Danh sách tất cả hồ sơ kèm bộ lọc tiêu đề, mã hồ sơ và trạng thái."""
    mgr = _archive_mgr()
    items = []
    for dos in mgr.dossiers.values():
        if title and title.lower() not in dos.title.lower():
            continue
        if file_code and file_code.lower() not in dos.file_code.lower():
            continue
        if status and status != "--Chọn trạng thái--" and getattr(dos, "status", "Tạo mới") != status:
            continue
        d = dos.to_dict()
        d["doc_count"] = len(dos.doc_ids)
        items.append(d)
    return items


class DossierUpsertRequest(BaseModel):
    file_code: str = ""
    catalog_no: str = "01"
    title: str
    fond_id: str = "P_UBND_TN"
    retention_period: str = "Vĩnh viễn"
    usage_mode: str = "Công khai"
    start_date: str = ""
    end_date: str = ""
    creator_unit: str = ""
    location: str = "UBND Tỉnh Thái Nguyên / Cơ quan / Kho số 1"
    status: str = "Tạo mới"
    doc_ids: list[str] | None = None


class DossierUpdateRequest(BaseModel):
    catalog_no: str | None = None
    title: str | None = None
    fond_id: str | None = None
    retention_period: str | None = None
    usage_mode: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    creator_unit: str | None = None
    location: str | None = None
    status: str | None = None
    doc_ids: list[str] | None = None


class DossierImportRequest(BaseModel):
    rows: list[dict] = []
    csv_text: str | None = None


DOSSIER_EXPORT_HEADERS = [
    "STT",
    "Mã hồ sơ",
    "Mục lục số",
    "Tiêu đề hồ sơ",
    "Phông lưu trữ",
    "Đơn vị lập",
    "Thời gian bắt đầu",
    "Thời gian kết thúc",
    "Thời hạn bảo quản",
    "Chế độ sử dụng",
    "Số lượng văn bản",
    "Vị trí lưu trữ",
    "Trạng thái",
]


@app.post("/api/archive/dossiers")
def create_dossier_api(req: DossierUpsertRequest, request: Request):
    """Tạo mới hồ sơ lưu trữ theo chuẩn Thông tư 02/2019/TT-BNV."""
    _require_auth(request, ("admin", "internal"))
    mgr = _archive_mgr()
    try:
        dos = mgr.create_dossier(req.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    get_cloud_store().sync_archive_structure(mgr.structure_path)
    d = dos.to_dict()
    d["doc_count"] = len(dos.doc_ids)
    return d


@app.put("/api/archive/dossiers/{file_code}")
def update_dossier_api(file_code: str, req: DossierUpdateRequest, request: Request):
    """Cập nhật thông tin, vị trí kho hoặc trạng thái duyệt của hồ sơ."""
    _require_auth(request, ("admin", "internal"))
    mgr = _archive_mgr()
    payload = {k: v for k, v in req.model_dump().items() if v is not None}
    try:
        dos = mgr.update_dossier(file_code, payload)
    except KeyError as e:
        raise HTTPException(404, f"Không tìm thấy hồ sơ có mã {file_code}") from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    get_cloud_store().sync_archive_structure(mgr.structure_path)
    d = dos.to_dict()
    d["doc_count"] = len(dos.doc_ids)
    return d


@app.delete("/api/archive/dossiers/{file_code}")
def delete_dossier_api(file_code: str, request: Request):
    """Xóa hồ sơ lưu trữ khỏi danh mục quản lý."""
    _require_auth(request, ("admin", "internal"))
    mgr = _archive_mgr()
    if not mgr.delete_dossier(file_code):
        raise HTTPException(404, f"Không tìm thấy hồ sơ có mã {file_code}")
    get_cloud_store().sync_archive_structure(mgr.structure_path)
    return {"deleted": file_code}


@app.post("/api/archive/dossiers/import")
def import_dossiers_api(req: DossierImportRequest, request: Request):
    """Nhập danh mục hồ sơ hàng loạt từ JSON hoặc nội dung CSV chuẩn UTF-8."""
    _require_auth(request, ("admin", "internal"))
    mgr = _archive_mgr()
    rows = list(req.rows)
    if req.csv_text:
        if len(req.csv_text) > 5_000_000:
            raise HTTPException(400, "Nội dung CSV vượt quá giới hạn cho phép (5 MB).")
        clean_csv = req.csv_text.lstrip("\ufeff")
        try:
            reader = csv.DictReader(io.StringIO(clean_csv))
            rows.extend(dict(r) for r in reader)
        except csv.Error as e:
            raise HTTPException(400, f"Dữ liệu CSV không hợp lệ: {e}") from e
    if not rows:
        raise HTTPException(400, "Không có dữ liệu hồ sơ hợp lệ để nhập")
    if len(rows) > 5000:
        raise HTTPException(400, "Số lượng dòng nhập vượt quá giới hạn tối đa (5.000 dòng).")
    try:
        out = mgr.import_dossiers(rows)
        get_cloud_store().sync_archive_structure(mgr.structure_path)
        return out
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/archive/dossiers-export")
def export_dossiers_csv(fond_id: str = "", status: str = "", q: str = "", file_codes: str = ""):
    """Xuất danh mục hồ sơ ra file CSV chuẩn UTF-8 BOM mở trực tiếp bằng Excel."""
    mgr = _archive_mgr()
    selected_codes = {c.strip() for c in file_codes.split(",") if c.strip()} if file_codes else None
    q_low = q.strip().lower()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(DOSSIER_EXPORT_HEADERS)

    idx = 0
    for dos in mgr.dossiers.values():
        if selected_codes is not None and dos.file_code not in selected_codes:
            continue
        if fond_id and dos.fond_id != fond_id:
            continue
        if status and status != "--Chọn trạng thái--" and getattr(dos, "status", "Tạo mới") != status:
            continue
        if q_low and q_low not in dos.title.lower() and q_low not in dos.file_code.lower():
            continue
        idx += 1
        row = [
            idx,
            dos.file_code,
            dos.catalog_no,
            dos.title,
            dos.fond_name or dos.fond_id,
            dos.creator_unit,
            dos.start_date,
            dos.end_date,
            dos.retention_period,
            dos.usage_mode,
            len(dos.doc_ids),
            dos.location,
            dos.status,
        ]
        writer.writerow([_safe_csv_cell(v) for v in row])

    csv_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="danh_muc_ho_so_tt02_2019.csv"'},
    )


@app.get("/api/archive/dossiers-template")
def download_dossiers_template():
    """Tải tệp mẫu nhập danh mục hồ sơ chuẩn Thông tư 02/2019/TT-BNV (UTF-8 BOM cho Excel)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    headers = [
        "Mã hồ sơ",
        "Mục lục số",
        "Tiêu đề hồ sơ",
        "Phông lưu trữ",
        "Đơn vị lập",
        "Thời gian bắt đầu",
        "Thời gian kết thúc",
        "Thời hạn bảo quản",
        "Chế độ sử dụng",
        "Vị trí lưu trữ",
        "Trạng thái",
    ]
    writer.writerow(headers)
    writer.writerow([
        "TN.2026.P01.02.001",
        "02",
        "Hồ sơ hội nghị tổng kết công tác chuyển đổi số tỉnh Thái Nguyên năm 2026",
        "P_UBND_TN",
        "Văn phòng UBND tỉnh Thái Nguyên",
        "01/01/2026",
        "31/12/2026",
        "Vĩnh viễn",
        "Công khai",
        "UBND Tỉnh Thái Nguyên / Cơ quan / Kho số 1 / Kệ A1",
        "Tạo mới",
    ])
    writer.writerow([
        "TN.2026.P02.02.002",
        "02",
        "Hồ sơ xét duyệt thi đua khen thưởng ngành Giáo dục năm học 2025-2026",
        "P_SGD_TN",
        "Sở Giáo dục và Đào tạo tỉnh Thái Nguyên",
        "15/05/2026",
        "30/06/2026",
        "20 năm",
        "Nội bộ",
        "Sở GD&ĐT Thái Nguyên / Cơ quan / Kho số 2 / Kệ B3",
        "Chờ hiệu chỉnh",
    ])
    csv_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="mau_nhap_danh_muc_ho_so_tt02_2019.csv"'},
    )


@app.get("/api/archive/dossiers/{file_code}")
def get_dossier(file_code: str, request: Request = None):
    """Chi tiết một hồ sơ kèm danh sách văn bản và trạng thái số hóa."""
    mgr = _archive_mgr()
    if file_code not in mgr.dossiers:
        raise HTTPException(404, f"Không tìm thấy hồ sơ có mã {file_code}")
    dos = mgr.dossiers[file_code]
    role = _resolve_request_role(request, None)
    if not mgr.is_access_allowed(dos.usage_mode, user_role=role):
        return dos.to_dict() | {"documents": [], "access_restricted": True}
    a = _assistant()
    docs = [doc_summary(d) for d in dos.doc_ids if d in a.cards]
    return dos.to_dict() | {"documents": docs}


class FacetedSearchRequest(BaseModel):
    query: str = ""
    fond_id: str | None = None
    file_code: str | None = None
    doc_type: str | None = None
    year: str | None = None
    issuer: str | None = None
    signer: str | None = None
    retention_period: str | None = None
    usage_mode: str | None = None
    user_role: str = "public"
    search_mode: str = "content"
    page: int = 1
    page_size: int = 10


@app.post("/api/archive/search")
def search_archive(req: FacetedSearchRequest, request: Request = None):
    """Tra cứu đa tiêu chí nghiệp vụ kết hợp toàn văn BM25 và ngữ nghĩa vector e5."""
    effective_role = _resolve_request_role(request, req.user_role)
    filters = SearchFilter(
        query=req.query,
        fond_id=req.fond_id,
        file_code=req.file_code,
        doc_type=req.doc_type,
        year=req.year,
        issuer=req.issuer,
        signer=req.signer,
        retention_period=req.retention_period,
        usage_mode=req.usage_mode,
        user_role=effective_role,
        search_mode=req.search_mode,
        page=max(1, req.page),
        page_size=min(50, max(1, req.page_size)),
    )
    return faceted_search(_assistant(), filters, _archive_mgr())


# --- HỎI ĐÁP VÀ TRỢ LÝ ẢO (CHATBOT & RAG) ---

class AskRequest(BaseModel):
    question: str
    doc_ids: list[str] | None = None     # nguồn đang chọn; None = cả kho
    use_llm: bool = False
    session_id: str | None = None
    user_role: str = "public"
    file_code: str | None = None
    year: str | None = None
    usage_mode: str | None = None


def _llm() -> LocalLLM:
    with _state_lock:
        if "llm" not in state:
            state["llm"] = LocalLLM()
        return state["llm"]


@app.get("/api/ask")
def ask(q: str, request: Request = None):
    if not q.strip():
        raise HTTPException(400, "Câu hỏi rỗng")
    req = AskRequest(question=q)
    return ask_post(req, request=request)


@app.post("/api/ask")
def ask_post(req: AskRequest, request: Request = None):
    """Hỏi đáp đa vòng có nhớ ngữ cảnh phiên, dẫn nguồn kép chuẩn Phông-Hồ sơ-Trang."""
    q = req.question.strip()[:500]
    if not q:
        raise HTTPException(400, "Câu hỏi rỗng")
    effective_role = _resolve_request_role(request, req.user_role)
    generator = None
    if req.use_llm:
        llm = _llm()
        if llm.provider == "openrouter":
            if not llm.has_api_key:
                raise HTTPException(503, "Chưa cấu hình OPENROUTER_API_KEY. Hãy bấm «Cấu hình API» để nhập khóa OpenRouter.")
        elif not llm.is_downloaded():
            raise HTTPException(503, f"Chưa tải mô hình {llm.model_id}")
        generator = llm

    session = get_session_manager().get_or_create(req.session_id)
    out = handle_archive_query(
        q,
        session=session,
        assistant=_assistant(),
        archive_mgr=_archive_mgr(),
        generator=generator,
        doc_ids=req.doc_ids,
        user_role=effective_role,
        file_code=req.file_code,
        year=req.year,
        usage_mode=req.usage_mode,
    )
    for c in out.get("citations", []):
        if not c.get("label"):
            c["label"] = _assistant().doc_label(c.get("doc_id", ""))
    return out


@app.get("/api/docs/{doc_id}/summary")
def doc_summary_api(
    doc_id: str,
    use_llm: bool = False,
    cached_only: bool = False,
    refresh: bool = False,
    request: Request = None,
):
    """Tóm tắt có trích dẫn của một văn bản (src.summarize); lưu cache tách theo chế độ LLM/extractive."""
    from src.summarize import SUMMARY_DIR, cache_path, summarize_doc

    a = _assistant()
    if doc_id not in a.cards:
        raise HTTPException(404, "Không có văn bản này")
    role = _resolve_request_role(request, None)
    if not _archive_mgr().can_access_doc(doc_id, user_role=role):
        raise HTTPException(403, "Bạn không có quyền truy cập văn bản thuộc chế độ hạn chế/nội bộ.")
    if cached_only:
        import json

        expected_kind = "llm" if use_llm else "extractive"
        expected_model = _llm().model_id if use_llm else None
        safe_id = re.sub(r"[^A-Za-z0-9_.\-]+", "_", doc_id).strip("._") or "doc"
        s = None
        for candidate, check_kind in (
            (cache_path(doc_id, use_llm=use_llm), False),
            (SUMMARY_DIR / f"{safe_id}.json", True),
        ):
            if candidate.exists():
                try:
                    with open(candidate, encoding="utf-8") as f:
                        loaded = json.load(f)
                    if not isinstance(loaded, dict):
                        continue
                    if check_kind and loaded.get("kind") != expected_kind:
                        continue
                    if use_llm and (
                        loaded.get("kind") != "llm"
                        or (loaded.get("meta") or {}).get("model") != expected_model
                    ):
                        continue
                    s = loaded
                    break
                except (OSError, json.JSONDecodeError):
                    pass
        if s is None:
            return {"doc_id": doc_id, "kind": "none", "points": [], "citations": [], "meta": {}}
    else:
        generator = None
        if use_llm:
            llm = _llm()
            if llm.provider == "openrouter":
                if not llm.has_api_key:
                    raise HTTPException(503, "Chưa cấu hình OPENROUTER_API_KEY. Hãy bấm «Cấu hình API» để nhập khóa OpenRouter.")
            elif not llm.is_downloaded():
                raise HTTPException(503, f"Chưa tải mô hình {llm.model_id}")
            generator = llm
        s = summarize_doc(a, doc_id, generator, use_cache=not refresh)
    for c in s.get("citations", []):
        c["label"] = a.doc_label(c["doc_id"])
    return s


class LLMConfigRequest(BaseModel):
    api_key: str | None = None
    model: str | None = None
    provider: str | None = None


@app.get("/api/llm/status")
def llm_status():
    return _llm().status()


@app.get("/api/llm/config")
def llm_config_get():
    return _llm().status()


@app.post("/api/llm/config")
def llm_config_post(req: LLMConfigRequest, request: Request):
    _require_auth(request, ("admin",))
    llm = _llm()
    try:
        return llm.configure(api_key=req.api_key, model=req.model, provider=req.provider, persist=True)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/llm/load")
def llm_load(request: Request):
    """Nạp mô hình cục bộ trước hoặc kiểm tra trạng thái OpenRouter API."""
    _require_auth(request, ("admin",))
    llm = _llm()
    if llm.provider == "openrouter":
        if not llm.has_api_key:
            raise HTTPException(503, "Chưa cấu hình OPENROUTER_API_KEY.")
        return llm.status()
    if not llm.is_downloaded():
        raise HTTPException(503, f"Chưa tải mô hình {llm.model_id}")
    with llm._lock:
        if llm.model is None:
            llm.load()
    return llm.status()


def suggestions(doc_id: str) -> list[str]:
    """Câu hỏi gợi ý dựng từ thẻ thông tin và hồ sơ."""
    a = _assistant()
    card = a.cards[doc_id]
    label = a.doc_label(doc_id)
    out = [f"Tóm tắt {label}"]
    if card.value("signer"):
        out.append(f"Ai ký {label}?")
    if card.value("recipients"):
        out.append(f"{label} gửi tới những nơi nào?")
    out.append("Văn bản này thuộc hồ sơ lưu trữ nào?")
    return out


def _highlight_rects(page: pymupdf.Page, doc_id: str, page_no: int, source: str, cited: str) -> list:
    """Vùng cần tô sáng cho đoạn trích: tìm từng cụm 5 âm tiết trên lớp chữ, hoặc dùng bbox dòng OCR."""
    if source == "tesseract":
        rec = load_cached(doc_id, page_no, OCR_DIR)
        if rec is None:
            return []
        key = lambda s: re.sub(r"\W+", "", remove_diacritics(normalize_for_eval(s)).lower())
        target = key(cited)
        scale = 72 / OCR_DPI
        return [
            pymupdf.Rect(*(v * scale for v in line["bbox"]))
            for line in rec["lines"]
            if len(key(line["text"])) >= 6 and key(line["text"]) in target
        ]
    words = cited.split()
    frags = [" ".join(words[i:i + 5]) for i in range(0, len(words), 5)]
    hits = [page.search_for(f) for f in frags if len(f) >= 6]
    return _contiguous_chain([h for h in hits if h])


def _contiguous_chain(hits: list[list]) -> list:
    if not hits:
        return []

    def with_wrap(r, cands):
        return [r] + [o for o in cands if o is not r and 0 < o.y0 - r.y0 <= 1.6 * max(r.height, 8)]

    best, best_cost = [], float("inf")
    for start in hits[0]:
        chain, cost, prev = with_wrap(start, hits[0]), 0.0, start
        for cands in hits[1:]:
            nxt = min(cands, key=lambda r: abs(r.y0 - prev.y0) * 4 + abs(r.x0 - prev.x1) * 0.2)
            d = abs(nxt.y0 - prev.y0)
            if d > 3 * max(prev.height, 8):
                cost += 50
                continue
            part = with_wrap(nxt, cands)
            chain.extend(part)
            cost += d
            prev = part[-1]
        if cost < best_cost:
            best, best_cost = chain, cost
    return best


@lru_cache(maxsize=64)
def render_png(doc_id: str, page_no: int, start: int, end: int) -> bytes:
    a = _assistant()
    page_rec = a.pages.get((doc_id, page_no))
    if page_rec is None:
        raise HTTPException(404, "Không có trang này")
    path = state.get("paths", {}).get(doc_id)
    if path is None or not path.exists():
        fetched = get_cloud_store().ensure_raw_pdf(doc_id, RAW_DIR)
        if fetched is not None:
            with _state_lock:
                state.setdefault("paths", {})[doc_id] = fetched
            path = fetched
    if path is None or not path.exists():
        raise HTTPException(404, "Không có trang này")
    with pymupdf.open(path) as doc:
        page = doc[page_no - 1]
        if end > start:
            for r in _highlight_rects(page, doc_id, page_no, page_rec["source"], page_rec["text"][start:end]):
                page.add_highlight_annot(r)
        return page.get_pixmap(dpi=VIEW_DPI, alpha=False).tobytes("png")


@app.get("/api/page/{doc_id}/{page_no}.png")
def page_image(doc_id: str, page_no: int, start: int = 0, end: int = 0, request: Request = None):
    a = _assistant()
    if (doc_id, page_no) not in a.pages:
        raise HTTPException(404, "Không có trang này")
    role = _resolve_request_role(request, None)
    if not _archive_mgr().can_access_doc(doc_id, user_role=role):
        raise HTTPException(403, "Bạn không có quyền xem trang của văn bản thuộc chế độ hạn chế/nội bộ.")
    s = max(0, int(start))
    e = max(0, int(end))
    if e <= s:
        s, e = 0, 0
    return Response(
        render_png(doc_id, page_no, s, e),
        media_type="image/png",
        headers={"Cache-Control": "private, no-cache, must-revalidate"},
    )


@app.get("/api/docs/{doc_id}/pdf")
@app.get("/api/pdf/{doc_id}")
def doc_pdf(doc_id: str, request: Request = None):
    """Mở hoặc xem trực tiếp tệp PDF gốc của văn bản lưu trữ (chặn Path Traversal)."""
    if not _SAFE_DOC_ID.match(doc_id) or ".." in doc_id:
        raise HTTPException(400, "Mã văn bản không hợp lệ")
    role = _resolve_request_role(request, None)
    if not _archive_mgr().can_access_doc(doc_id, user_role=role):
        raise HTTPException(403, "Bạn không có quyền truy cập tệp PDF của văn bản thuộc chế độ hạn chế/nội bộ.")
    with _state_lock:
        path = state.get("paths", {}).get(doc_id)
    if path is None or not path.exists():
        raw_root = RAW_DIR.resolve()
        candidate = (raw_root / f"{doc_id}.pdf").resolve()
        if candidate.is_relative_to(raw_root) and candidate.exists():
            path = candidate
        else:
            fetched = get_cloud_store().ensure_raw_pdf(doc_id, RAW_DIR)
            if fetched is None or not fetched.exists():
                raise HTTPException(404, "Không tìm thấy tệp PDF của văn bản này trong kho nguồn")
            with _state_lock:
                state.setdefault("paths", {})[doc_id] = fetched
            path = fetched
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


def _register_uploaded_doc(doc_id: str, pages: list[dict], meta: dict, raw_name: str) -> dict:
    with _state_lock:
        state.setdefault("paths", {})[doc_id] = uploads.upload_folder(doc_id, UPLOAD_DIR) / uploads.PDF_NAME
        state.setdefault("meta", {})[doc_id] = meta | {"group": "upload", "split": "upload"}
        _assistant().add_document(pages)
        _archive_mgr().ensure_upload_doc(doc_id, raw_name)
        render_png.cache_clear()
        return get_doc(doc_id)


@app.post("/api/upload")
async def upload(request: Request):
    """Nhận một PDF, OCR trang scan, lấy chữ, trích thẻ và nạp vào hồ sơ tiếp nhận số hóa."""
    _require_auth(request, ("admin", "internal"))
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "Tệp quá lớn (tối đa 30 MB)")
    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        total_bytes += len(chunk)
        if total_bytes > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Tệp quá lớn (tối đa 30 MB)")
        chunks.append(chunk)
    body = b"".join(chunks)
    if not body.startswith(b"%PDF"):
        raise HTTPException(400, "Tệp không phải PDF")
    raw_name = Path(unquote(request.headers.get("x-filename", "tai_len.pdf")).replace("\\", "/")).name or "tai_len.pdf"
    try:
        doc_id, pages, meta = await run_in_threadpool(uploads.save_upload, body, raw_name, UPLOAD_DIR, OCR_DIR)
        doc_out = await run_in_threadpool(_register_uploaded_doc, doc_id, pages, meta, raw_name)
        get_cloud_store().sync_upload(doc_id, UPLOAD_DIR, OCR_DIR)
        get_cloud_store().sync_archive_structure(_archive_mgr().structure_path)
        return doc_out
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Không đọc được PDF: {e}") from e


@app.get("/api/uploads")
def list_uploaded(request: Request = None):
    role = _resolve_request_role(request, None)
    mgr = _archive_mgr()
    with _state_lock:
        return [
            m
            for doc_id, m in state.get("meta", {}).items()
            if m.get("group") == "upload" and mgr.can_access_doc(doc_id, user_role=role)
        ]


@app.delete("/api/uploads/{doc_id}")
def delete_uploaded(doc_id: str, request: Request):
    _require_auth(request, ("admin", "internal"))
    from src.summarize import SUMMARY_DIR, cache_path

    with _state_lock:
        if state.get("meta", {}).get(doc_id, {}).get("group") != "upload":
            raise HTTPException(404, "Không có tệp tải lên này (văn bản của kho chính không xóa qua web)")
        _assistant().remove_document(doc_id)
        _archive_mgr().remove_upload_doc(doc_id)
        state.get("paths", {}).pop(doc_id, None)
        state.get("meta", {}).pop(doc_id, None)
        render_png.cache_clear()
    uploads.delete_upload(doc_id, UPLOAD_DIR, OCR_DIR)
    get_cloud_store().delete_remote_upload(doc_id)
    get_cloud_store().sync_archive_structure(_archive_mgr().structure_path)
    for p in (cache_path(doc_id, False), cache_path(doc_id, True), SUMMARY_DIR / f"{doc_id}.json"):
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
    return {"deleted": doc_id}
