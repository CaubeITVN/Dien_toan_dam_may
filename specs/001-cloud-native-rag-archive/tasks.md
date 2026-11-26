# Tasks: Hệ thống Lưu trữ Số hóa, Tra cứu Lai và Hỏi đáp RAG Triển khai trên Hạ tầng Đám mây Công cộng

**Input**: Design documents from `/specs/001-cloud-native-rag-archive/`  
**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/cloud-api.md`

## Phase 1: Setup & SpecKit Governance (Cô lập và Thiết lập Đặc tả)

- [X] T001 Ghi nhận trạng thái Git hiện tại của `Du_an/` làm mốc đối chiếu không chỉnh sửa phần NLP
- [X] T002 Khởi tạo thư mục độc lập `Dien_toan_dam_may/`, khởi tạo Git nhánh `main` và cài đặt SpecKit (`specify init`)
- [X] T003 Hoàn thiện `.specify/memory/constitution.md` và bộ tài liệu đặc tả trong `specs/001-cloud-native-rag-archive/` (`spec.md`, `research.md`, `data-model.md`, `contracts/cloud-api.md`, `plan.md`, `quickstart.md`, `tasks.md`)
- [X] T004 Sao chép tách biệt 24 mô-đun Python runtime, `web/`, dữ liệu chỉ mục/OCR nhẹ, `models/` và 10 tệp PDF mẫu sang `Dien_toan_dam_may/`

---

## Phase 2: Foundational Cloud Infrastructure (Hạ tầng Lõi Đám mây)

- [X] T005 [P] Xây dựng `src/cloud_store.py` (`CloudStorageManager`) hỗ trợ 3 chế độ `hf_dataset`, `local_volume`, `ephemeral` với `bootstrap_on_startup`, `sync_archive_structure`, `sync_upload`, `delete_remote_upload`, `ensure_raw_pdf`, `sync_now`
- [X] T006 [P] Xây dựng `src/telemetry.py` (`CloudTelemetry`) đo uptime, môi trường container, RAM RSS/cgroup limit, độ trễ HTTP P50/P95 và thống kê gọi OpenRouter LLM
- [X] T007 [P] Nâng cấp `src/auth.py` hỗ trợ token phi trạng thái ký `HMAC-SHA256` (`st1.*`), thu hồi khi đăng xuất và phương thức `status()`
- [X] T008 Nâng cấp `src/llm.py` tôn trọng `CLOUD_STATELESS_ENV=1` (không ghi `.env` ra đĩa Container), cấu hình sẵn khóa OpenRouter mặc định phía máy chủ và ghi telemetry mỗi lần gọi LLM

---

## Phase 3: User Stories 1, 2, 3 & 4 — Cloud Backend & Observability UI

- [X] T009 [US1][US2] Tích hợp `bootstrap_on_startup`, middleware telemetry, đồng bộ hồ sơ/upload và lazy-fetch PDF vào `web/app.py`
- [X] T010 [US4] Bổ sung các điểm cuối `GET /healthz`, `GET /readyz`, `GET /api/cloud/status`, `POST /api/cloud/sync`, `GET /cloud` vào `web/app.py`
- [X] T011 [US4] Tạo giao diện Bảng điều khiển Hạ tầng & Vận hành Đám mây `web/static/cloud.html`, gắn nút điều hướng nhanh trên `index.html`, `notebooklm.html` và ẩn cấu hình khóa API đối với người dùng cuối

---

## Phase 4: User Story 5 — Containerization, Packaging & CI/CD

- [X] T012 [P] Hoàn thiện `Dockerfile` (non-root `UID 1000`, `CLOUD_STATELESS_ENV=1`, `HEALTHCHECK`) và `docker-compose.yml` (Named Volume + resource limits)
- [X] T013 [P] Xây dựng `scripts/deploy_cloud.py` hỗ trợ `--mode decoupled` (< 5 MB mã nguồn, tách riêng kho Dataset `private=True`) và `--mode standalone`
- [X] T014 [P] Thiết lập pipeline `.github/workflows/ci-cd-cloud.yml`, cùng `README.md`, `hf_space_readme.md`, `.env.example`, `.gitignore`, `.dockerignore`, `requirements-deploy.txt`

---

## Phase 5: Academic Report & Verification (Báo cáo 3 Chương + Kết luận & Kiểm thử Toàn diện)

- [X] T015 Hoàn thiện báo cáo học thuật 3 chương + Kết luận (~40 trang, không trích dẫn, đủ 25 hình minh họa, mục lục và danh mục bảng/hình tự động) tại `reports/BAO CAO DU AN _DTDM_NHOM 4_2026,09mm,25.docx` và đồng bộ `reports/BAO_CAO_DIEN_TOAN_DAM_MAY.md`
- [X] T016 [P] Hoàn thiện 4 bộ kiểm thử đám mây: `tests/test_stateless_auth.py`, `tests/test_cloud_store.py`, `tests/test_cloud_observability.py`, `tests/test_deploy_and_report.py`
- [X] T017 Chạy toàn bộ `pytest`, kiểm tra `deploy_cloud.py --dry-run`, cập nhật Word COM mục lục và đối chiếu `git status` của `Du_an/` nguyên vẹn 100%
