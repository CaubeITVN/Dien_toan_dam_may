# Hướng dẫn Triển khai & Kịch bản Trình diễn Demo trên Public Cloud

**Feature**: `001-cloud-native-rag-archive` | **Date**: 2026-11-25

## 1. Kiểm thử Đóng gói và Chạy Cục bộ với Docker Compose

1. Tạo tệp `.env` từ mẫu:
   ```bash
   cp .env.example .env
   # Điền OPENROUTER_API_KEY và APP_ADMIN_PASSWORD
   ```
2. Khởi chạy Container kèm Persistent Volume cục bộ:
   ```bash
   docker compose up --build
   ```
3. Truy cập `http://127.0.0.1:7860` (Cổng chính), `http://127.0.0.1:7860/notebooklm` (Không gian 3 cột) và `http://127.0.0.1:7860/cloud` (Bảng điều khiển Đám mây).

## 2. Triển khai lên Public Cloud (Hugging Face Spaces + Private Dataset Storage)

1. Tạo tài khoản miễn phí tại `https://huggingface.co` (không yêu cầu thẻ tín dụng) và tạo **Write Token** trong mục *Settings → Access Tokens*.
2. Tạo tài khoản miễn phí tại `https://openrouter.ai` để lấy `OPENROUTER_API_KEY`.
3. Kiểm tra đóng gói chế độ tách lưu trữ (`decoupled`):
   ```bash
   python scripts/deploy_cloud.py --mode decoupled --dry-run
   ```
4. Đẩy dữ liệu lên kho Dataset riêng tư (`private=True`) và đẩy mã nguồn nhẹ lên Docker Space:
   ```bash
   python scripts/deploy_cloud.py --mode decoupled --token <HF_WRITE_TOKEN> --sync-secrets --admin-password "<MAT_KHAU_QUAN_TRI>"
   ```
   *(Nếu muốn đồng bộ toàn bộ 245+ PDF gốc từ thư mục khác vào kho Dataset riêng tư, bổ sung `--raw-dir ../Du_an/data/raw`)*.

## 3. Kịch bản Trình diễn Demo trước Giảng viên (5 Bước Chuẩn)

1. **Giới thiệu bài toán & kiến trúc (`/cloud`):** Mở trang `/cloud` trên URL HTTPS công cộng, trình bày sơ đồ 4 tầng đám mây và chỉ ra thông số `storage.backend = hf_dataset`, `durable = true`, `memory_rss_mb`, độ trễ P50/P95 và trạng thái OpenRouter API.
2. **Tra cứu & Hỏi đáp RAG có dẫn nguồn:** Chuyển về `/` hoặc `/notebooklm`, tìm kiếm văn bản, đặt câu hỏi nghiệp vụ, mở trang ảnh PDF có vùng tô sáng căn cứ (chứng minh cơ chế tải lười PDF từ kho Dataset riêng tư).
3. **Thao tác tạo dữ liệu mới trên Cloud:** Đăng nhập `admin`, tải lên một tệp PDF mới (hoặc tạo một Hồ sơ lưu trữ mới), kiểm tra đồng bộ thành công trên `/cloud` (`sync_ok_count` tăng lên).
4. **Kiểm chứng tính bền vững sau Restart Space:** Vào phần *Settings → Factory Reboot / Restart this Space* trên Hugging Face Space, chờ Container khởi động lại hoàn toàn.
5. **Xác nhận không mất dữ liệu & giữ nguyên phiên:** Tải lại trang web (token `st1.*` vẫn hợp lệ hoặc đăng nhập lại), kiểm chứng tệp PDF mới tải lên và hồ sơ mới tạo vẫn tồn tại nguyên vẹn 100%.
