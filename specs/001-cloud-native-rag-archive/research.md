# Nghiên cứu & Luận giải Lựa chọn Dịch vụ Public Cloud

**Feature**: `001-cloud-native-rag-archive` | **Date**: 2026-11-25

## 1. Phân tích Đặc thù Tải công việc (Workload Profile)

Hệ thống Tra cứu và Hỏi đáp Tài liệu Lưu trữ Số hóa thuộc nhóm ứng dụng **AI/NLP lai (Hybrid AI Web Application)** với các yêu cầu tài nguyên đặc thù:
1. **Tiêu thụ RAM tĩnh cao lúc khởi động:** Nạp thư viện PyTorch CPU, bộ mã hóa ngữ nghĩa `intfloat/multilingual-e5-small` (~470 MB trọng số), chỉ mục vector numpy, từ điển BM25/TF-IDF và bộ xử lý PDF PyMuPDF đòi hỏi tối thiểu **1,5 GB – 3,0 GB RAM** khi vận hành thực tế.
2. **Phụ thuộc thư viện hệ điều hành Linux (System Packages):** Cần cài đặt `tesseract-ocr` và `tesseract-ocr-vie` bằng `apt-get` để nhận dạng chữ tiếng Việt trên tài liệu scan tải lên trực tiếp; do đó các nền tảng Serverless thuần Python không hỗ trợ tùy biến hệ điều hành (như Vercel Functions) không đáp ứng được.
3. **Tác vụ suy luận LLM tách rời:** Chạy mô hình ngôn ngữ 1,5B–7B trên CPU mất hàng chục giây mỗi câu trả lời; do đó cần tách sang dịch vụ LLM API đám mây (**OpenRouter**) để đạt thời gian phản hồi 1–3 giây.
4. **Ràng buộc an toàn tài chính sinh viên:** Theo yêu cầu môn học, nhóm ưu tiên nhà cung cấp vừa và nhỏ có gói dùng thử miễn phí, minh bạch hạn mức và tránh rủi ro phát sinh cước phí ngoài ý muốn khi nhập thẻ thanh toán quốc tế.

## 2. Bảng Đối sánh 5 Nền tảng Public Cloud Phổ biến

| Tiêu chí đánh giá | Hugging Face Spaces (Docker SDK) | Render (Web Service Free) | Railway (Trial / Hobby) | Fly.io (Free / Pay-as-you-go) | Google Cloud Run |
|---|---|---|---|---|---|
| **Gói miễn phí (Compute)** | **2 vCPU, 16 GB RAM, 50 GB đĩa tạm** (miễn phí không giới hạn giờ) | 0,1 vCPU, **512 MB RAM** (ngủ sau 15 phút) | Dùng thử \$5 tín dụng một lần (hết hạn sau 30 ngày) | Tối đa 3 VM 256 MB RAM (đã thu hẹp gói free cho tài khoản mới) | 2 triệu req/tháng (tối đa 4 GB RAM, có tính phí egress/vượt quota) |
| **Đáp ứng RAM cho PyTorch + e5-small** | **Đạt dư dả** (16 GB RAM) | **Không đạt** (OOM crash ngay khi nạp PyTorch + e5) | Đạt nhưng hết tín dụng rất nhanh | **Không đạt** ở gói 256 MB | Đạt nhưng giới hạn thời gian cấu hình |
| **Yêu cầu thẻ thanh toán** | **Không bắt buộc** | Không cho gói Free (nhưng thiếu RAM) | **Bắt buộc** nâng cấp sau khi hết trial | **Bắt buộc** add thẻ với tài khoản mới | **Bắt buộc** tài khoản Google Billing có thẻ |
| **Hỗ trợ Dockerfile + Tesseract OCR** | **Có** (tùy biến đầy đủ) | Có (chậm build trên gói Free) | Có | Có | Có |
| **Lưu trữ bền vững đi kèm** | **HF Hub Private Dataset API** (miễn phí, tách rời Container) | Không có Disk trên gói Free | Có Volume (tính phí theo GB/tháng) | Có Volume (tính phí nếu vượt mức nhỏ) | Cần gắn Cloud Storage / Cloud SQL (tính phí) |
| **Quản lý Secrets & Logs** | Tích hợp sẵn **Settings → Variables and Secrets**, Build/Container Logs trực quan | Có | Có | Có qua CLI | Có (Cloud Logging, Secret Manager) |

## 3. Quyết định Kiến trúc Đám mây Đề xuất (4 Thành phần)

1. **Compute PaaS/CaaS — Hugging Face Spaces (Docker SDK):**
   - Cung cấp 16 GB RAM miễn phí không cần thẻ ngân hàng, phù hợp duy nhất trong nhóm nhà cung cấp vừa và nhỏ cho tải PyTorch CPU + Tesseract OCR.
   - Hỗ trợ cổng 7860 qua HTTPS có chứng chỉ SSL tự động, có màn hình quản trị *Logs* (Build & Container) và *Secrets* trực quan để chụp minh chứng đưa vào báo cáo môn học.
2. **Durable Cloud Storage — Hugging Face Hub Private Dataset (`HF_STORAGE_REPO`, `private=True`) + Hỗ trợ Docker Volume (`CLOUD_VOLUME_DIR`):**
   - Giải quyết triệt để nhược điểm đĩa tạm (*ephemeral disk*) của Container miễn phí.
   - Cho phép lưu bền vững cấu trúc Phông – Hồ sơ, tài liệu PDF người dùng tải lên, cache OCR và kho PDF gốc ở chế độ riêng tư tuyệt đối.
   - Cho phép chạy song song trên Docker Compose cục bộ/VPS thông qua chế độ `local_volume` mà không cần sửa mã nghiệp vụ.
3. **Cloud MaaS (Model-as-a-Service) — OpenRouter API:**
   - Cung cấp cổng thống nhất truy cập nhiều mô hình ngôn ngữ lớn (Gemini 2.0 Flash, Qwen, DeepSeek Free) với cơ chế nạp khóa động trên giao diện hoặc qua Space Secrets.
   - Sinh viên kiểm soát hạn mức trực tiếp bằng prepaid credit hoặc dùng các mô hình `:free` nên chi phí có thể giữ ở mức **0 VNĐ**.
4. **Cloud CI/CD — GitHub Actions:**
   - Tự động kiểm tra toàn bộ kiểm thử tự động `pytest`, kiểm tra rò rỉ bí mật và triển khai đồng bộ lên Space mỗi khi cập nhật nhánh chính.
