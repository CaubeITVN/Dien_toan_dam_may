# Hiến pháp Dự án: Hệ thống Tra cứu và Hỏi đáp Lưu trữ Số hóa Đám mây (Cloud-Native Digital Archive RAG)

## Nguyên tắc Cốt lõi

### I. Cô lập Tuyệt đối khỏi Học phần Xử lý Ngôn ngữ Tự nhiên (NLP)
Mọi mã nguồn, cấu hình, bộ kiểm thử, kho Git, kịch bản triển khai và báo cáo thuộc học phần Điện toán Đám mây **PHẢI** nằm hoàn toàn trong thư mục độc lập `Dien_toan_dam_may/`. Tuyệt đối không chỉnh sửa, xóa, ghi đè hay làm thay đổi trạng thái của thư mục `Du_an/`, các bài thực hành `Thuc_hanh/`, tài liệu `Document/`, cấu hình `.claude/`, `.agents/`, hay môi trường ảo `.venv/`.

### II. Tách biệt Tính toán Phi Trạng thái và Lưu trữ Bền vững (Stateless Compute vs. Durable Storage)
Tầng ứng dụng chạy trong Container phải phi trạng thái (*stateless*), nhẹ (< 5 MB mã nguồn khi triển khai tách dữ liệu) và có thể khởi tạo lại bất kỳ lúc nào mà không làm mất dữ liệu phát sinh. Mọi trạng thái có thể thay đổi sau triển khai (danh mục Phông – Hồ sơ lưu trữ, tệp PDF tải lên, kết quả OCR tương ứng và kho văn bản PDF nguồn) phải được đồng bộ với tầng lưu trữ bền vững bên ngoài (`hf_dataset` riêng tư hoặc `local_volume` gắn ngoài) khi ghi và tự động khôi phục khi khởi động.

### III. Quản trị Chi phí Đám mây An toàn (Zero-Credit-Card / Free-Tier Governance)
Ưu tiên lựa chọn tổ hợp dịch vụ Public Cloud vừa và nhỏ có gói miễn phí rõ ràng, đủ tài nguyên RAM/CPU cho mô hình nhúng vector và Tesseract OCR tiếng Việt, **không yêu cầu thẻ thanh toán quốc tế** cho hạ tầng cốt lõi. Mọi kết nối tới API mô hình ngôn ngữ bên ngoài (OpenRouter) phải áp dụng giới hạn token, cơ chế thử lại có kiểm soát (*exponential backoff*) và cấu hình qua biến bí mật (*Secrets*) để ngăn rò rỉ khóa và phát sinh chi phí ngoài ý muốn.

### IV. Bảo mật Đa lớp, Xác thực Phi Trạng thái & Quyền riêng tư Dữ liệu
Tuyệt đối không lưu khóa bí mật (`OPENROUTER_API_KEY`, `HF_TOKEN`, `APP_ADMIN_PASSWORD`, `APP_SECRET_KEY`) trong mã nguồn hoặc gói Docker/Git. Kho lưu trữ đối tượng chứa dữ liệu văn bản hành chính trên Hugging Face Hub **BẮT BUỘC** đặt ở chế độ riêng tư (`private=True`). Phiên đăng nhập quản trị sử dụng token ký `HMAC-SHA256` phi trạng thái (`st1.*`) để duy trì hiệu lực qua các lần khởi động lại Container hoặc mở rộng nhiều bản sao (*replicas*), đồng thời giữ nguyên cơ chế PBKDF2-SHA256 (600.000 vòng) và khóa tạm chống tấn công dò mật khẩu.

### V. Khả năng Quan sát Đám mây và Phục hồi Lỗi (Observability & Resilience)
Hệ thống phải cung cấp đầy đủ các điểm cuối kiểm tra sức khỏe chuẩn đám mây (`/healthz` cho *liveness probe*, `/readyz` cho *readiness probe*), API tổng hợp chỉ số hạ tầng (`/api/cloud/status`), thao tác đồng bộ cưỡng bức có xác thực (`/api/cloud/sync`) và bảng điều khiển trực quan (`/cloud`) phục vụ theo dõi bộ nhớ Container, độ trễ P50/P95, trạng thái đồng bộ lưu trữ và lưu lượng gọi mô hình ngôn ngữ đám mây.

### VI. Chuẩn mực Văn phong Báo cáo Học thuật
Mọi tài liệu báo cáo nộp giảng viên (bao gồm `reports/BAO_CAO_DIEN_TOAN_DAM_MAY.md`) phải tuân thủ nghiêm ngặt quy tắc tiếng Việt học thuật chuẩn mực: ngôi thứ ba hoặc diễn đạt vô nhân xưng, đánh số phân cấp `1.1`, `1.1.1` khớp đúng 07 phần quy định, không chèn mã định danh kỹ thuật thô, tên tệp mã nguồn, đường dẫn máy tính hay tên biến lập trình vào nội dung văn xuôi; thông tin chưa đo đạc hoặc cần nhóm tự điền phải đánh dấu rõ bằng `[...]`.

## Ràng buộc Công nghệ & Triển khai
- Ngôn ngữ & Runtime: Python 3.10+, FastAPI + Uvicorn, PyMuPDF, Tesseract OCR (`tesseract-ocr-vie`), `intfloat/multilingual-e5-small` (CPU).
- Đóng gói: Docker image non-root (`UID 1000`), `HEALTHCHECK` tự động, cổng động `${PORT:-7860}`.
- Điều phối & Tự động hóa: `docker-compose.yml` cho môi trường cục bộ/VPS có Persistent Volume và GitHub Actions (`.github/workflows/ci-cd-cloud.yml`) cho CI/CD lên Public Cloud.

## Quản trị Thay đổi
Mọi thay đổi kiến trúc hoặc bổ sung API mới phải được cập nhật đồng bộ trong `specs/001-cloud-native-rag-archive/` (`spec.md`, `plan.md`, `data-model.md`, `contracts/cloud-api.md`, `tasks.md`) và phải vượt qua toàn bộ bộ kiểm thử tự động `pytest` trước khi đóng gói triển khai.

**Version**: 1.0.0 | **Ratified**: 2026-11-25 | **Last Amended**: 2026-11-25
