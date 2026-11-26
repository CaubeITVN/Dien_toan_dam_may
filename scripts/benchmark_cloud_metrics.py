"""Đo đạc thông số thực tế của hệ thống Cloud-Native trong `Dien_toan_dam_may/`.

Xuất kết quả ra `reports/cloud_benchmark_results.json` để làm nguồn số liệu
chính xác cho báo cáo học phần Điện toán Đám mây và biểu đồ minh họa.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402
import pymupdf  # noqa: E402

from scripts.deploy_cloud import collect_space_files, collect_storage_files  # noqa: E402
from src.archive import ArchiveManager  # noqa: E402
from src.auth import AuthManager  # noqa: E402
from src.cloud_store import CloudStorageManager, reset_cloud_store  # noqa: E402
from src.telemetry import get_telemetry, reset_telemetry  # noqa: E402
from src.uploads import save_upload  # noqa: E402
from web import app as web_app  # noqa: E402


def _pct(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 3)
    idx = (len(sorted_vals) - 1) * (p / 100.0)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return round(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac, 3)


def _measure(fn, n: int = 30) -> dict[str, float]:
    # Làm nóng 2 lần
    for _ in range(2):
        fn()
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    s = sorted(samples)
    return {
        "n": n,
        "min_ms": round(s[0], 3),
        "avg_ms": round(sum(s) / len(s), 3),
        "p50_ms": _pct(s, 50.0),
        "p95_ms": _pct(s, 95.0),
        "max_ms": round(s[-1], 3),
    }


def main() -> int:
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

    # 1. Đo kích thước đóng gói
    dec_space = collect_space_files(ROOT, mode="decoupled")
    dec_storage = collect_storage_files(ROOT)
    standalone = collect_space_files(ROOT, mode="standalone")

    dec_space_mb = round(sum(s.stat().st_size for s, _ in dec_space) / (1024 * 1024), 2)
    dec_storage_mb = round(sum(s.stat().st_size for s, _ in dec_storage) / (1024 * 1024), 2)
    standalone_mb = round(sum(s.stat().st_size for s, _ in standalone) / (1024 * 1024), 2)

    # 2. Đo hiệu năng API thật trên dữ liệu thực tế của Dien_toan_dam_may
    reset_telemetry()
    reset_cloud_store(CloudStorageManager())
    web_app.state.clear()
    t_load0 = time.perf_counter()
    web_app.load_state()
    startup_sec = round(time.perf_counter() - t_load0, 3)

    with TestClient(web_app.app) as client:
        st_json = client.get("/api/cloud/status").json()
        corpus = st_json["corpus"]

        lat_healthz = _measure(lambda: client.get("/healthz"), n=40)
        lat_readyz = _measure(lambda: client.get("/readyz"), n=40)
        lat_status = _measure(lambda: client.get("/api/cloud/status"), n=30)
        lat_search = _measure(
            lambda: client.post(
                "/api/archive/search",
                json={"query": "chuyển đổi số giáo dục đào tạo", "search_mode": "content", "page_size": 10},
            ),
            n=20,
        )
        lat_ask = _measure(
            lambda: client.post(
                "/api/ask",
                json={"question": "Nội dung chính của kế hoạch chuyển đổi số là gì?", "use_llm": False},
            ),
            n=20,
        )

        # Kiểm thử xác thực phi trạng thái qua khởi động lại
        auth_lat = []
        for _ in range(10):
            t0 = time.perf_counter()
            m1 = AuthManager(admin_password="BenchCloud!2026", announce=lambda _m: None)
            tok = m1.authenticate("admin", "BenchCloud!2026")["token"]
            m2 = AuthManager(admin_password="BenchCloud!2026", announce=lambda _m: None)
            ok = m2.verify_token(tok)
            assert ok is not None and ok["role"] == "admin"
            auth_lat.append((time.perf_counter() - t0) * 1000.0)
        auth_lat.sort()

        # Kiểm thử độ bền lưu trữ khi xóa toàn bộ dữ liệu container tạm
        with tempfile.TemporaryDirectory() as tmp:
            tp = Path(tmp)
            vol = tp / "vol"
            c_a = tp / "c_a" / "data"
            c_b = tp / "c_b" / "data"
            (c_a / "uploads").mkdir(parents=True)
            (c_a / "ocr").mkdir(parents=True)
            c_b.mkdir(parents=True)
            struct_p = c_a / "archive_structure.json"
            struct_p.write_text('{"portal_name":"Bench","fonds":[]}', encoding="utf-8")

            s_a = CloudStorageManager(volume_dir=vol)
            mgr_a = ArchiveManager(structure_path=struct_p, auto_save=True)
            mgr_a.create_dossier({"file_code": "BENCH.2026.01", "title": "Hồ sơ đo độ bền đám mây"})
            t_sync0 = time.perf_counter()
            s_a.sync_archive_structure(struct_p, background=False)

            doc = pymupdf.open()
            doc.new_page().insert_text((50, 60), "Van ban thu nghiem luu tru dam may", fontsize=11)
            pdf_bytes = doc.tobytes()
            doc.close()
            doc_id, _, _ = save_upload(pdf_bytes, "bench_cloud.pdf", root=c_a / "uploads", ocr_dir=c_a / "ocr")
            s_a.sync_upload(doc_id, c_a / "uploads", c_a / "ocr", background=False)
            sync_ms = round((time.perf_counter() - t_sync0) * 1000.0, 2)

            t_boot0 = time.perf_counter()
            s_b = CloudStorageManager(volume_dir=vol)
            boot_res = s_b.bootstrap_on_startup(c_b, tp / "c_b" / "models")
            restore_ms = round((time.perf_counter() - t_boot0) * 1000.0, 2)
            mgr_b = ArchiveManager(structure_path=c_b / "archive_structure.json")
            durable_ok = ("BENCH.2026.01" in mgr_b.dossiers) and (c_b / "uploads" / doc_id / "source.pdf").is_file()

        final_telemetry = get_telemetry().snapshot()

    out = {
        "corpus": corpus,
        "startup_seconds": startup_sec,
        "packaging": {
            "decoupled_space_files": len(dec_space),
            "decoupled_space_mb": dec_space_mb,
            "decoupled_storage_files": len(dec_storage),
            "decoupled_storage_mb": dec_storage_mb,
            "standalone_files": len(standalone),
            "standalone_mb": standalone_mb,
            "legacy_monolith_mb": 282.75,
            "reduction_vs_legacy_pct": round((1.0 - dec_space_mb / 282.75) * 100.0, 2),
        },
        "latency": {
            "healthz": lat_healthz,
            "readyz": lat_readyz,
            "cloud_status": lat_status,
            "hybrid_search": lat_search,
            "grounded_qa_extractive": lat_ask,
            "stateless_auth_p50_ms": _pct(auth_lat, 50.0),
        },
        "durability": {
            "sync_ms": sync_ms,
            "restore_ms": restore_ms,
            "restored_100pct": durable_ok,
            "boot_details": boot_res,
        },
        "runtime_snapshot": final_telemetry["runtime"],
    }

    res_path = ROOT / "reports" / "cloud_benchmark_results.json"
    res_path.parent.mkdir(parents=True, exist_ok=True)
    res_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
