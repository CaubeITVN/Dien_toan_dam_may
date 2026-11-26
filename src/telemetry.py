"""Thu thập chỉ số vận hành đám mây (Cloud Telemetry & Observability).

Ghi nhận thông số tài nguyên Container (RAM RSS, giới hạn cgroup, CPU),
lưu lượng truy vấn HTTP theo nhóm chức năng, phân vị độ trễ P50/P95
và lưu lượng gọi dịch vụ LLM đám mây (OpenRouter).
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import os
from pathlib import Path
import platform
import socket
import threading
import time
from typing import Any


def _classify_route(path: str) -> str:
    p = path or "/"
    if p.startswith("/api/ask"):
        return "ask_rag"
    if p.startswith("/api/archive/search"):
        return "archive_search"
    if p.startswith("/api/upload"):
        return "upload_ocr"
    if p.startswith("/api/archive/"):
        return "archive_crud"
    if p.startswith("/api/page/") or p.endswith("/pdf") or p.startswith("/api/pdf/"):
        return "pdf_render"
    if p in ("/healthz", "/readyz", "/cloud") or p.startswith("/api/cloud/"):
        return "cloud_ops"
    return "other"


def _read_linux_rss_mb() -> float | None:
    status_path = Path("/proc/self/status")
    if not status_path.is_file():
        return None
    try:
        for line in status_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("VmRSS:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    return round(int(parts[1]) / 1024.0, 2)
    except OSError:
        pass
    return None


def _read_windows_rss_mb() -> float | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return round(counters.WorkingSetSize / (1024.0 * 1024.0), 2)
    except Exception:
        pass
    return None


def _read_cgroup_memory_limit_mb() -> float | None:
    for candidate in (
        Path("/sys/fs/cgroup/memory.max"),
        Path("/sys/fs/cgroup/memory/memory.limit_in_bytes"),
    ):
        if not candidate.is_file():
            continue
        try:
            raw = candidate.read_text(encoding="utf-8").strip()
            if not raw or raw == "max":
                continue
            val = int(raw)
            if 0 < val < (1 << 50):
                return round(val / (1024.0 * 1024.0), 1)
        except (OSError, ValueError):
            pass
    return None


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return round(sorted_vals[0], 2)
    idx = (len(sorted_vals) - 1) * (pct / 100.0)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return round(sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac, 2)


class CloudTelemetry:
    """Bộ đếm chỉ số vận hành đám mây an toàn đa luồng."""

    def __init__(self, latency_window: int = 500):
        self._lock = threading.Lock()
        self.started_mono = time.monotonic()
        self.started_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        self._latencies: deque[float] = deque(maxlen=max(10, int(latency_window)))
        self.total_requests = 0
        self.status_2xx = 0
        self.status_4xx = 0
        self.status_5xx = 0
        self.by_group: dict[str, int] = {}

        self.llm_total = 0
        self.llm_success = 0
        self.llm_errors = 0
        self.llm_retries = 0
        self.llm_prompt_tokens = 0
        self.llm_completion_tokens = 0
        self.llm_total_seconds = 0.0
        self.llm_last_model = ""
        self.llm_last_provider = ""

    def uptime_seconds(self) -> float:
        return round(max(0.0, time.monotonic() - self.started_mono), 2)

    def record_request(self, path: str, status_code: int, duration_ms: float) -> None:
        grp = _classify_route(path)
        ms = max(0.0, float(duration_ms))
        with self._lock:
            self.total_requests += 1
            if 200 <= status_code < 400:
                self.status_2xx += 1
            elif 400 <= status_code < 500:
                self.status_4xx += 1
            elif status_code >= 500:
                self.status_5xx += 1
            self.by_group[grp] = self.by_group.get(grp, 0) + 1
            self._latencies.append(ms)

    def record_llm_call(
        self,
        *,
        provider: str,
        model: str,
        elapsed_sec: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        success: bool = True,
        retries: int = 0,
    ) -> None:
        with self._lock:
            self.llm_total += 1
            if success:
                self.llm_success += 1
            else:
                self.llm_errors += 1
            self.llm_retries += max(0, int(retries))
            self.llm_prompt_tokens += max(0, int(prompt_tokens))
            self.llm_completion_tokens += max(0, int(completion_tokens))
            self.llm_total_seconds += max(0.0, float(elapsed_sec))
            self.llm_last_model = model
            self.llm_last_provider = provider

    def snapshot(self) -> dict[str, Any]:
        rss_mb = _read_linux_rss_mb()
        if rss_mb is None:
            rss_mb = _read_windows_rss_mb()
        limit_mb = _read_cgroup_memory_limit_mb()
        is_container = Path("/.dockerenv").exists() or bool(os.environ.get("SPACE_ID"))

        with self._lock:
            lats = sorted(self._latencies)
            avg_ms = round(sum(lats) / len(lats), 2) if lats else 0.0
            p50_ms = _percentile(lats, 50.0)
            p95_ms = _percentile(lats, 95.0)
            http_stats = {
                "total_requests": self.total_requests,
                "status_2xx": self.status_2xx,
                "status_4xx": self.status_4xx,
                "status_5xx": self.status_5xx,
                "latency_avg_ms": avg_ms,
                "latency_p50_ms": p50_ms,
                "latency_p95_ms": p95_ms,
                "by_group": dict(self.by_group),
            }
            llm_avg_ms = round((self.llm_total_seconds / self.llm_success) * 1000.0, 1) if self.llm_success else 0.0
            llm_stats = {
                "total": self.llm_total,
                "success": self.llm_success,
                "errors": self.llm_errors,
                "retries": self.llm_retries,
                "prompt_tokens": self.llm_prompt_tokens,
                "completion_tokens": self.llm_completion_tokens,
                "avg_latency_ms": llm_avg_ms,
                "last_model": self.llm_last_model,
                "last_provider": self.llm_last_provider,
            }

        return {
            "uptime_seconds": self.uptime_seconds(),
            "started_at": self.started_at,
            "runtime": {
                "hostname": socket.gethostname(),
                "platform": platform.system(),
                "python_version": platform.python_version(),
                "cpu_count": os.cpu_count() or 1,
                "is_container": is_container,
                "space_id": os.environ.get("SPACE_ID") or None,
                "space_host": os.environ.get("SPACE_HOST") or None,
                "memory_rss_mb": rss_mb,
                "memory_limit_mb": limit_mb,
            },
            "http": http_stats,
            "llm_calls": llm_stats,
        }


_TELEMETRY_LOCK = threading.Lock()
_telemetry = CloudTelemetry()


def get_telemetry() -> CloudTelemetry:
    return _telemetry


def reset_telemetry() -> CloudTelemetry:
    global _telemetry
    with _TELEMETRY_LOCK:
        _telemetry = CloudTelemetry()
        return _telemetry
