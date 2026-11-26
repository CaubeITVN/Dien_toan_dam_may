# Đặc tả Hợp đồng API Đám mây (REST API Contracts)

**Feature**: `001-cloud-native-rag-archive` | **Base URL**: `https://<space-host>` hoặc `http://127.0.0.1:7860`

## 1. Nhóm API Vận hành & Giám sát Đám mây (Cloud Observability & Sync)

### `GET /healthz` (Liveness Probe)
- **Mục đích:** Kiểm tra tiến trình Web Container còn sống. Không yêu cầu xác thực.
- **Response `200 OK`**:
```json
{
  "status": "ok",
  "uptime_seconds": 142.5
}
```

### `GET /readyz` (Readiness Probe)
- **Mục đích:** Kiểm tra hệ thống đã khôi phục dữ liệu từ Cloud Storage và nạp xong mô hình tìm kiếm hay chưa.
- **Response `200 OK`** (khi sẵn sàng):
```json
{
  "ready": true,
  "n_docs": 245,
  "n_chunks": 1840,
  "storage_backend": "hf_dataset",
  "storage_durable": true
}
```
- **Response `503 Service Unavailable`** (khi đang nạp): `{"ready": false, "reason": "initializing"}`

### `GET /api/cloud/status`
- **Mục đích:** Cung cấp bức tranh vận hành đám mây đầy đủ cho bảng điều khiển `/cloud`. Không lộ khóa bí mật.
- **Response `200 OK`**:
```json
{
  "service": {
    "name": "Thai Nguyen Digital Archive Cloud RAG",
    "version": "2.0.0-cloud",
    "stateless_env": true
  },
  "telemetry": {
    "uptime_seconds": 360.2,
    "started_at": "2026-11-25T15:00:00Z",
    "runtime": {
      "hostname": "r-space-...",
      "platform": "Linux",
      "python_version": "3.10.12",
      "cpu_count": 2,
      "is_container": true,
      "space_id": "user/tra-cuu-luu-tru-so-cloud",
      "space_host": "user-tra-cuu-luu-tru-so-cloud.hf.space",
      "memory_rss_mb": 1245.6,
      "memory_limit_mb": 16384.0
    },
    "http": {
      "total_requests": 42,
      "status_2xx": 40,
      "status_4xx": 2,
      "status_5xx": 0,
      "latency_avg_ms": 28.4,
      "latency_p50_ms": 14.2,
      "latency_p95_ms": 85.1,
      "by_group": {"cloud_ops": 12, "ask_rag": 8}
    },
    "llm_calls": {
      "total": 5,
      "success": 5,
      "errors": 0,
      "retries": 0,
      "prompt_tokens": 3120,
      "completion_tokens": 410
    }
  },
  "storage": {
    "backend": "hf_dataset",
    "durable": true,
    "target": "user/tra-cuu-luu-tru-so-storage",
    "bootstrapped": true,
    "last_sync_at": "2026-11-25T15:04:12Z",
    "sync_ok_count": 3,
    "sync_err_count": 0,
    "pending_tasks": 0,
    "recent_events": []
  },
  "auth": {
    "mode": "stateless_hmac_sha256",
    "stateless_across_restarts": true,
    "token_ttl_seconds": 86400,
    "active_sessions_count": 1
  },
  "llm": {
    "provider": "openrouter",
    "model": "google/gemini-2.0-flash-001",
    "has_api_key": true,
    "api_key_masked": "sk-or-v1••••1234"
  },
  "corpus": {
    "n_docs": 245,
    "n_pages": 527,
    "n_chunks": 1840,
    "n_fonds": 4,
    "n_dossiers": 25
  }
}
```

### `POST /api/cloud/sync`
- **Xác thực:** Bắt buộc `Authorization: Bearer <token>` hoặc `X-Token` với vai trò `admin`.
- **Request JSON**: `{"action": "push"}` hoặc `{"action": "pull"}` (mặc định `"push"`).
- **Response `200 OK`**: Trả kết quả đồng bộ kèm `storage` status mới nhất. Trả `401`/`403` nếu thiếu quyền hoặc `400` nếu `action` không hợp lệ.

### `GET /cloud`
- Trả về trang HTML Bảng điều khiển Hạ tầng & Vận hành Đám mây (`web/static/cloud.html`).

---

## 2. Nhóm API Nghiệp vụ Lưu trữ, Tìm kiếm & RAG (Tích hợp Đồng bộ Đám mây)

| Phương thức & Đường dẫn | Quyền truy cập | Hành vi Cloud-Native bổ sung |
|---|---|---|
| `POST /api/auth/login` | Công khai | Cấp token ký phi trạng thái `st1.*`, đặt cookie `HttpOnly` |
| `GET /api/auth/me`, `POST /api/auth/logout` | Đã xác thực | Xác minh `st1.*` không phụ thuộc RAM; thu hồi token khi thoát |
| `GET /api/docs`, `GET /api/docs/{doc_id}` | Công khai / RBAC | Lọc tài liệu theo quyền vai trò; dữ liệu được đồng bộ từ Cloud Storage |
| `POST /api/archive/search` | Công khai / RBAC | Tìm kiếm lai BM25 + TF-IDF + `e5-small` RRF lọc theo Phông/Hồ sơ/Quyền |
| `POST /api/ask`, `GET /api/ask` | Công khai / RBAC | Hỏi đáp RAG đa vòng + ghi nhận thống kê LLM vào `CloudTelemetry` |
| `GET /api/page/{doc_id}/{page_no}.png` | Công khai / RBAC | Nếu PDF chưa có trong Container, tự động gọi `ensure_raw_pdf()` từ Cloud Storage |
| `GET /api/docs/{doc_id}/pdf` | Công khai / RBAC | Tải lười PDF từ Cloud Storage nếu chưa có cục bộ; chặn Path Traversal |
| `POST /api/upload`, `DELETE /api/uploads/{doc_id}` | `admin` / `internal` | OCR tự động + đồng bộ hoặc xóa thư mục tài liệu trên Cloud Storage |
| `POST/PUT/DELETE /api/archive/dossiers*` | `admin` / `internal` | Cập nhật nguyên tử + đồng bộ `archive_structure.json` lên Cloud Storage |
| `POST /api/llm/config`, `POST /api/llm/load` | `admin` | Không ghi khóa API xuống `.env` khi `CLOUD_STATELESS_ENV=1` |
