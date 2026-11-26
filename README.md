# Hệ thống Lưu trữ Số hóa, Tra cứu Lai và Hỏi đáp RAG trên Hạ tầng Đám mây Công cộng

Dự án học phần **Điện toán Đám mây** — xây dựng và tái cấu trúc hệ thống tra cứu và hỏi đáp tài liệu lưu trữ số hóa theo kiến trúc **Cloud-Native** (tách biệt hoàn toàn với thư mục học phần Xử lý Ngôn ngữ Tự nhiên).

## 1. Kiến trúc Đám mây 4 Tầng

1. **Compute PaaS/CaaS (Hugging Face Spaces – Docker SDK):** Chạy ứng dụng FastAPI + Uvicorn trên container non-root `python:3.10-slim` (2 vCPU, 16 GB RAM miễn phí, không yêu cầu thẻ thanh toán), tích hợp Tesseract OCR tiếng Việt và mô hình nhúng `intfloat/multilingual-e5-small`.
2. **Durable Cloud Storage (`src/cloud_store.py`):** Lưu trữ bền vững qua **Hugging Face Private Dataset** (`HF_STORAGE_REPO`, `private=True`) hoặc **Docker Persistent Volume** (`CLOUD_VOLUME_DIR`). Tự động khôi phục dữ liệu khi Container khởi động, đồng bộ hồ sơ/PDF tải lên và tải lười (*lazy fetch*) PDF gốc theo yêu cầu.
3. **SaaS LLM Gateway (`src/llm.py`):** Kết nối OpenRouter Cloud API kèm thử lại lũy thừa và kiểm soát token; tôn trọng `CLOUD_STATELESS_ENV=1`.
4. **Cloud Observability & CI/CD (`src/telemetry.py`, `/cloud`, `.github/workflows/ci-cd-cloud.yml`):** Điểm cuối `/healthz`, `/readyz`, `/api/cloud/status`, `/api/cloud/sync`, giao diện `/cloud` theo dõi RAM/P50/P95/đồng bộ theo thời gian thực và pipeline GitHub Actions tự động kiểm thử + triển khai.

## 2. Chạy Thử Cục bộ (Python hoặc Docker Compose)

```bash
# Chạy trực tiếp bằng Python trong môi trường ảo
uvicorn web.app:app --host 127.0.0.1 --port 7860

# Hoặc chạy bằng Docker Compose gắn Persistent Volume
cp .env.example .env
docker compose up --build
```

Sau khi chạy, truy cập:
- Cổng Quản lý Lưu trữ: `http://127.0.0.1:7860/`
- Không gian Tra cứu & Hỏi đáp (3 cột): `http://127.0.0.1:7860/notebooklm`
- Bảng điều khiển Hạ tầng Đám mây: `http://127.0.0.1:7860/cloud`
- Kiểm tra sức khỏe Container: `http://127.0.0.1:7860/healthz` và `/readyz`

## 3. Triển khai lên Public Cloud (Chế độ Tách Dữ liệu)

```bash
# 1) Kiểm tra đóng gói tách mã nguồn (< 5 MB) và gói lưu trữ
python scripts/deploy_cloud.py --mode decoupled --dry-run

# 2) Triển khai thật lên Hugging Face Private Dataset + Docker Space
python scripts/deploy_cloud.py --mode decoupled --token <HF_WRITE_TOKEN> --sync-secrets --admin-password "<MAT_KHAU>"
```

## 4. Kiểm thử Tự động & Hồ sơ SpecKit

- Bộ hồ sơ phân tích thiết kế hướng đặc tả (SDD) nằm tại `.specify/` và `specs/001-cloud-native-rag-archive/`.
- Chạy toàn bộ kiểm thử: `python -m pytest -q`.
- Bản thảo báo cáo 07 phần theo đề cương giảng viên nằm tại `reports/BAO_CAO_DIEN_TOAN_DAM_MAY.md`.
