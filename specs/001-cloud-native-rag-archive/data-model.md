# Mô hình Dữ liệu và Phân tầng Lưu trữ Đám mây (Data Model)

**Feature**: `001-cloud-native-rag-archive` | **Date**: 2026-11-25

## 1. Phân tầng Lưu trữ 3 Lớp (3-Layer Cloud Storage Architecture)

| Lớp lưu trữ | Vị trí vật lý | Tính chất vòng đời | Dữ liệu lưu giữ |
|---|---|---|---|
| **Lớp 1: Container Image Layer** | Docker Image trên Hugging Face Space | Bất biến (*Immutable*) theo phiên bản build | Mã nguồn ứng dụng (`src/`, `web/`), thư viện Python, Tesseract OCR `vie`, trọng số `intfloat/multilingual-e5-small` nạp sẵn trong `/app/.cache/huggingface` |
| **Lớp 2: Durable Cloud Storage Layer** | Hugging Face Hub Private Dataset (`HF_STORAGE_REPO`, `private=True`) hoặc Docker Volume (`CLOUD_VOLUME_DIR`) | Bền vững (*Durable*), sống sót qua mọi lần Space ngủ đông / khởi động lại / build lại | `state/archive_structure.json`, `data/manifest.csv`, `data/processed/pages.jsonl`, `models/refusal_threshold.json`, `models/spellfix_lm.pkl`, `models/dense/*`, `uploads/<doc_id>/*`, `ocr/<doc_id>/*`, `raw/<doc_id>.pdf` |
| **Lớp 3: Ephemeral Runtime Cache Layer** | Thư mục làm việc `/app/data/`, `/app/models/` và RAM tiến trình Uvicorn | Tạm thời (*Ephemeral*), tái tạo khi khởi động | Bản sao dữ liệu phục vụ đọc nhanh, tệp PDF được tải lười theo yêu cầu (`ensure_raw_pdf`), bộ nhớ đệm ảnh PNG (`render_png` LRU 64), lịch sử phiên hội thoại tạm thời và ảnh chụp telemetry |

## 2. Sơ đồ Thực thể Chính

### 2.1. `CloudStorageState` (Quản lý bởi `src/cloud_store.py`)
- `backend`: `"hf_dataset"` | `"local_volume"` | `"ephemeral"`
- `durable`: `bool` (`True` khi `backend` là `"hf_dataset"` hoặc `"local_volume"`)
- `target_masked`: tên kho đích (ẩn token, ví dụ `"username/tra-cuu-luu-tru-so-storage"` hoặc `"/app/cloud_volume"`)
- `bootstrapped`: `bool` (đã đồng bộ khởi động xong hay chưa)
- `last_sync_at`: ISO-8601 timestamp hoặc `null`
- `sync_ok_count`: `int`
- `sync_err_count`: `int`
- `pending_tasks`: `int`
- `recent_events`: danh sách tối đa 20 bản ghi `{timestamp, action, target, status, detail}`

### 2.2. `StatelessSessionPayload` (Quản lý bởi `src/auth.py`)
Token có định dạng `st1.<payload_b64url>.<signature_b64url>` ký bằng `HMAC-SHA256`:
- `u`: tên tài khoản (`"admin"`)
- `role`: vai trò RBAC (`"admin"`)
- `iat`: epoch giây phát hành
- `exp`: epoch giây hết hạn (`iat + 86400`)
- `jti`: mã ngẫu nhiên chống trùng lặp và hỗ trợ thu hồi cục bộ khi đăng xuất

### 2.3. `CloudTelemetrySnapshot` (Quản lý bởi `src/telemetry.py`)
- `uptime_seconds`: `float`
- `started_at`: ISO-8601 timestamp
- `runtime`: `{hostname, platform, python_version, cpu_count, is_container, space_id, space_host, memory_rss_mb, memory_limit_mb}`
- `http`: `{total_requests, status_2xx, status_4xx, status_5xx, latency_avg_ms, latency_p50_ms, latency_p95_ms, by_group}`
- `llm_calls`: `{total, success, errors, retries, prompt_tokens, completion_tokens, last_model, last_provider}`

### 2.4. Thực thể Nghiệp vụ Lưu trữ & Tài liệu (Kế thừa và Đồng bộ hóa)
- **`Fond`**: `{fond_id, fond_name, agency_name, time_range, description, dossiers[]}`
- **`Dossier`**: `{file_code, catalog_no, title, retention_period, usage_mode, start_date, end_date, creator_unit, location, status, doc_ids[], simulated=True}`
- **`UploadedDocument`**: `{doc_id, original_name, uploaded_at, md5, size_bytes, n_pages, n_missing, clean_version, ingest_version, ocr_done}`
- **`DocumentCard`**: Trích xuất 7 trường theo NĐ 30/2020/NĐ-CP (`doc_type`, `doc_number`, `issue_date`, `issuer`, `signer`, `subject`, `recipients`) kèm cờ kiểm định `flags`.
