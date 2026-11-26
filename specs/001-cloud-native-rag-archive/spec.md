# Feature Specification: Hệ thống Lưu trữ Số hóa, Tra cứu Lai và Hỏi đáp RAG Triển khai trên Hạ tầng Đám mây Công cộng

**Feature Branch**: `001-cloud-native-rag-archive`  
**Created**: 2026-11-25  
**Status**: Approved for Implementation  
**Input**: Chuyển đổi hệ thống tra cứu và hỏi đáp tài liệu lưu trữ số hóa (OCR + trích xuất metadata + tìm kiếm lai BM25/TF-IDF/e5-small + RAG) thành kiến trúc Cloud-Native hoàn chỉnh phục vụ đồ án môn Điện toán đám mây, đáp ứng yêu cầu thiết kế phân tầng, triển khai trên Public Cloud vừa và nhỏ, demo trực tuyến và báo cáo 07 phần.

## Tổng quan Bài toán (Problem Statement)

- **Đầu vào (Input):**
  1. Tệp tài liệu PDF hành chính (PDF số hóa sẵn lớp chữ hoặc PDF ảnh scan cần nhận dạng quang học Tesseract tiếng Việt).
  2. Câu hỏi truy vấn bằng tiếng Việt tự nhiên hoặc tiêu chí tra cứu đa chiều (từ khóa, mã phông, mã hồ sơ, loại văn bản, năm ban hành, cơ quan ban hành, người ký, mức độ tiếp cận).
  3. Yêu cầu thao tác quản trị Phông lưu trữ – Hồ sơ lưu trữ theo chuẩn Thông tư 02/2019/TT-BNV và cấu hình kết nối dịch vụ LLM đám mây.
- **Đầu ra (Output):**
  1. Thẻ siêu dữ liệu trích xuất theo thể thức Nghị định 30/2020/NĐ-CP và phân cấp Phông – Hồ sơ.
  2. Danh sách đoạn văn bản xếp hạng theo tìm kiếm lai (BM25 + TF-IDF + Vector ngữ nghĩa hợp nhất RRF).
  3. Câu trả lời hỏi đáp AI có dẫn nguồn kép (Hồ sơ – Văn bản – Số trang), kèm ảnh trang PDF độ phân giải cao có tô sáng đúng vùng căn cứ, hoặc từ chối an toàn khi thiếu căn cứ.
  4. Chỉ số vận hành đám mây theo thời gian thực (trạng thái sống/sẵn sàng, mức tiêu thụ RAM của Container, độ trễ P50/P95, trạng thái đồng bộ lưu trữ bền vững và lưu lượng API LLM).
- **Nội hàm bài toán:** Tái cấu trúc ứng dụng từ dạng đóng gói đơn khối chứa sẵn toàn bộ dữ liệu trong Container (dễ mất dữ liệu khi ngủ đông hoặc khởi động lại) thành kiến trúc **Cloud-Native** gồm 4 tầng phối hợp: Tầng tính toán Container phi trạng thái (Hugging Face Spaces Docker SDK), Tầng lưu trữ đối tượng và trạng thái bền vững riêng tư (Hugging Face Hub Private Dataset hoặc Persistent Volume), Tầng suy luận mô hình ngôn ngữ đám mây (OpenRouter API) và Tầng tự động hóa CI/CD (GitHub Actions).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Tra cứu lai và Hỏi đáp RAG có dẫn nguồn qua Internet (Priority: P1) 🎯 MVP

Người dùng công khai truy cập hệ thống qua đường dẫn HTTPS công cộng trên Public Cloud để tìm kiếm văn bản thuộc chế độ "Công khai", đặt câu hỏi tiếng Việt và kiểm chứng câu trả lời trực tiếp trên trang tài liệu được tô sáng.

**Why this priority**: Đây là giá trị cốt lõi phục vụ cả buổi thuyết trình Demo trực tuyến trên Internet lẫn người dùng cuối của cổng thông tin lưu trữ.

**Independent Test**: Mở trình duyệt truy cập URL công cộng của ứng dụng (hoặc `TestClient`), gửi truy vấn tìm kiếm và câu hỏi RAG ở vai trò `public`, nhận về danh sách đoạn trích dẫn kèm ảnh trang PDF tô sáng được nạp thành công (kể cả khi PDF gốc chỉ nằm trên kho lưu trữ đám mây chưa tải sẵn trong Container).

**Acceptance Scenarios**:

1. **Given** ứng dụng đã khởi động trên hạ tầng đám mây và ở trạng thái sẵn sàng (`/readyz` trả `200`), **When** người dùng gửi câu hỏi tới `POST /api/ask` ở vai trò `public`, **Then** hệ thống chỉ truy hồi trong các văn bản thuộc chế độ `"Công khai"`, trả câu trả lời kèm trích dẫn `[doc_id, trang]` và ẩn toàn bộ tài liệu `"Nội bộ"` / `"Hạn chế"` / `"Mật"`.
2. **Given** một văn bản PDF gốc chưa có sẵn trong thư mục cục bộ của Container nhưng tồn tại trên kho lưu trữ bền vững đám mây, **When** người dùng yêu cầu xem ảnh trang `/api/page/{doc_id}/{page_no}.png` hoặc tải PDF `/api/docs/{doc_id}/pdf`, **Then** hệ thống tự động tải lười (*lazy fetch*) tệp PDF từ kho lưu trữ bền vững về bộ nhớ đệm Container và trả về ảnh/PDF hợp lệ.

---

### User Story 2 - Tải lên PDF, OCR tự động và Đồng bộ Bền vững vượt qua Khởi động lại Container (Priority: P1)

Quản trị viên tải lên tài liệu PDF mới (kể cả bản scan), hệ thống thực hiện OCR và lập chỉ mục ngay trên đám mây, đồng thời đẩy toàn bộ tệp PDF, trang đã xử lý và cache OCR lên kho lưu trữ bền vững để không bị mất khi Container ngủ đông hoặc khởi động lại.

**Why this priority**: Khắc phục điểm yếu chí mạng nhất của bản đóng gói cũ trên đám mây (Ephemeral Filesystem mất sạch dữ liệu tải lên khi Space restart).

**Independent Test**: Khởi tạo ứng dụng gắn với kho lưu trữ bền vững (Local Volume hoặc Mock HF Dataset), tải lên một PDF mới và tạo một hồ sơ mới; sau đó xóa sạch dữ liệu làm việc cục bộ của Container và khởi động lại ứng dụng; xác nhận PDF tải lên và hồ sơ mới vẫn tồn tại đầy đủ.

**Acceptance Scenarios**:

1. **Given** quản trị viên đã đăng nhập hợp lệ và gửi tệp PDF qua `POST /api/upload`, **When** quá trình OCR và lập chỉ mục hoàn tất, **Then** văn bản mới xuất hiện trong danh sách kho và sự kiện đồng bộ lên Cloud Storage được ghi nhận thành công.
2. **Given** Container bị hủy bộ nhớ cục bộ và khởi động lại từ image gốc, **When** hàm `lifespan` chạy bước khôi phục khởi động (`bootstrap_on_startup`), **Then** toàn bộ tệp PDF đã tải lên, cache OCR và tệp cấu trúc hồ sơ được kéo từ Cloud Storage về trước khi dựng `Assistant`.

---

### User Story 3 - Quản trị Phông – Hồ sơ Lưu trữ & Xác thực Phi Trạng thái (Priority: P2)

Quản trị viên đăng nhập bằng tài khoản bảo vệ bởi PBKDF2-SHA256 để thêm, sửa, xóa, nhập/xuất CSV danh mục hồ sơ lưu trữ; phiên đăng nhập tiếp tục hợp lệ sau khi Container khởi động lại hoặc chuyển sang bản sao khác nhờ token ký HMAC-SHA256 phi trạng thái.

**Why this priority**: Đảm bảo tính nhất quán dữ liệu và phiên làm việc trong kiến trúc đám mây phi trạng thái (*stateless*), tránh buộc người dùng đăng nhập lại mỗi khi Container tái khởi động.

**Independent Test**: Đăng nhập trên thực thể `AuthManager` thứ nhất để nhận token `st1.*`, khởi tạo thực thể `AuthManager` thứ hai dùng cùng khóa bí mật/mật khẩu môi trường, xác nhận token vẫn hợp lệ trên thực thể thứ hai và bị từ chối khi giả mạo chữ ký hoặc sau khi đăng xuất.

**Acceptance Scenarios**:

1. **Given** biến môi trường `APP_ADMIN_PASSWORD` (hoặc `APP_SECRET_KEY`) được cấu hình thống nhất trong Space Secrets, **When** quản trị viên đăng nhập thành công qua `POST /api/auth/login`, **Then** hệ thống cấp token dạng `st1.<payload>.<signature>` có thời hạn TTL 24 giờ và vẫn xác thực được trên tiến trình mới khởi động lại.
2. **Given** quản trị viên thực hiện tạo, cập nhật, xóa hoặc nhập danh mục hồ sơ qua `/api/archive/dossiers*`, **When** thao tác thành công, **Then** tệp cấu trúc lưu trữ được cập nhật nguyên tử và đồng bộ lên tầng lưu trữ bền vững.

---

### User Story 4 - Giám sát Sức khỏe Dịch vụ, Tài nguyên và Luồng Hoạt động Đám mây (Priority: P2)

Sinh viên và giảng viên chấm thi truy cập trang bảng điều khiển đám mây (`/cloud`) và các điểm cuối quan sát (`/healthz`, `/readyz`, `/api/cloud/status`) để kiểm tra trực quan tình trạng Container, độ trễ truy vấn, lưu lượng gọi API OpenRouter và kích hoạt đồng bộ thủ công khi trình diễn Demo.

**Why this priority**: Đáp ứng trực tiếp yêu cầu báo cáo kết quả triển khai, chứng minh tính chất "vận hành trên nền tảng đám mây" trong buổi bảo vệ Mini-project.

**Independent Test**: Gửi truy vấn tới `/healthz`, `/readyz`, `/api/cloud/status`, kiểm tra trang `/cloud` trả HTML hợp lệ và kiểm tra `POST /api/cloud/sync` chặn truy cập trái phép (`401`) khi chưa đăng nhập nhưng cho phép (`200`) với token quản trị viên.

**Acceptance Scenarios**:

1. **Given** máy chủ FastAPI đang chạy, **When** nền tảng đám mây hoặc bộ giám sát gọi `GET /healthz`, **Then** máy chủ phản hồi mã `200` với thời gian sống `uptime_seconds` dưới 50 ms.
2. **Given** người dùng mở giao diện `/cloud`, **When** trình duyệt nạp dữ liệu từ `GET /api/cloud/status`, **Then** giao diện hiển thị đầy đủ 4 khối dịch vụ đám mây, RAM sử dụng, số lượng yêu cầu HTTP, độ trễ P50/P95, số lượt gọi OpenRouter, trạng thái lưu trữ bền vững và nhật ký đồng bộ gần nhất mà không lộ khóa bí mật.

---

### User Story 5 - Đóng gói Tách Mã nguồn – Dữ liệu và Tự động hóa CI/CD (Priority: P3)

Nhóm phát triển sử dụng kịch bản đóng gói đám mây (`deploy_cloud.py`) và quy trình GitHub Actions để tự động kiểm thử `pytest`, kiểm tra không lọt tệp bí mật/tệp huấn luyện, đẩy dữ liệu lên Dataset riêng tư và triển khai mã nguồn nhẹ (< 5 MB) lên Docker Space.

**Why this priority**: Minh họa quy trình DevOps/Cloud CI/CD chuẩn mực và giải quyết vấn đề phân tách mã nguồn khỏi dữ liệu nặng (~283 MB).

**Independent Test**: Chạy `python scripts/deploy_cloud.py --mode decoupled --dry-run`, kiểm chứng gói mã nguồn Container tách biệt hoàn toàn khỏi gói dữ liệu lưu trữ, không chứa `.env`, `.pt`, `.pth`, `__pycache__` và dung lượng gói mã nguồn nhỏ hơn 5 MB.

**Acceptance Scenarios**:

1. **Given** người dùng chạy `deploy_cloud.py --mode decoupled --dry-run`, **When** kịch bản thống kê danh sách tệp, **Then** gói Space chỉ gồm mã nguồn ứng dụng và cấu hình Docker (< 5 MB), còn dữ liệu chỉ mục, mô hình dense và PDF mẫu được tách riêng vào gói Storage Dataset.
2. **Given** mã nguồn được đẩy lên nhánh `main` trên GitHub, **When** GitHub Actions chạy `.github/workflows/ci-cd-cloud.yml`, **Then** toàn bộ bộ kiểm thử tự động và kiểm tra đóng gói phải đạt trước khi thực hiện bước triển khai lên Public Cloud.

### Edge Cases

- **Mất kết nối tới Cloud Storage khi khởi động Container:** Hệ thống phải ghi nhận cảnh báo vào nhật ký đồng bộ (`recent_events`) và vẫn tiếp tục khởi động bằng dữ liệu nền có sẵn (graceful degradation), không làm treo container.
- **Hết hạn mức hoặc lỗi tạm thời từ OpenRouter API (`429`, `502`, `503`, `504`):** Bộ gọi API tự động thử lại tối đa 2 lần theo khoảng trễ tăng dần (0,8s; 1,6s) và ghi nhận thống kê vào `CloudTelemetry`; nếu vẫn lỗi, trả thông báo rõ ràng hoặc người dùng có thể tắt LLM để dùng chế độ trích câu cơ sở.
- **Yêu cầu xem PDF có ký tự điều khiển hoặc đường dẫn tương đối (`../`):** Bị từ chối ngay bởi kiểm tra biểu thức chính quy `_SAFE_DOC_ID` và kiểm tra `is_relative_to` trước khi truy cập đĩa hay gọi tải từ đám mây.
- **Chưa thiết lập `APP_SECRET_KEY` và `APP_ADMIN_PASSWORD`:** Hệ thống tự sinh mật khẩu tạm một lần, sử dụng khóa ký ngẫu nhiên cho phiên hiện tại và báo rõ `stateless_across_restarts = false` trên bảng điều khiển `/cloud`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Hệ thống PHẢI triển khai dưới dạng dịch vụ web container hóa theo chuẩn OCI (`Dockerfile`) chạy bằng người dùng không đặc quyền (`UID 1000`), tích hợp Tesseract OCR tiếng Việt và mô hình nhúng `intfloat/multilingual-e5-small`.
- **FR-002**: Hệ thống PHẢI tách biệt toàn bộ mã nguồn và dữ liệu triển khai của học phần Điện toán Đám mây trong thư mục `Dien_toan_dam_may/`, độc lập hoàn toàn với thư mục học phần NLP.
- **FR-003**: Hệ thống PHẢI cung cấp lớp trừu tượng lưu trữ đám mây (`CloudStorageManager`) hỗ trợ tối thiểu ba chế độ: `hf_dataset` (Hugging Face Hub Dataset riêng tư), `local_volume` (Docker Volume gắn ngoài) và `ephemeral` (mặc định dự phòng).
- **FR-004**: Khi khởi động (`lifespan`), hệ thống PHẢI tự động kéo trạng thái mới nhất (cấu trúc hồ sơ, các tệp tải lên, cache OCR và chỉ mục nếu có) từ kho lưu trữ bền vững về bộ nhớ làm việc cục bộ trước khi phục vụ truy vấn.
- **FR-005**: Mọi thao tác làm thay đổi dữ liệu trạng thái (tạo/sửa/xóa/nhập hồ sơ lưu trữ; tải lên/xóa PDF) PHẢI kích hoạt đồng bộ lên tầng lưu trữ bền vững tương ứng.
- **FR-006**: Khi hiển thị trang ảnh hoặc tệp PDF gốc của tài liệu chưa có sẵn trong Container, hệ thống PHẢI hỗ trợ tải lười theo yêu cầu từ tầng lưu trữ bền vững và lưu đệm cục bộ.
- **FR-007**: Hệ thống xác thực PHẢI phát hành token phi trạng thái ký bằng `HMAC-SHA256` (`st1.*`) có thời hạn hết hiệu lực (TTL) và hỗ trợ thu hồi khi đăng xuất.
- **FR-008**: Khi chạy trong môi trường phi trạng thái (`CLOUD_STATELESS_ENV=1`), cấu hình API LLM qua giao diện web KHÔNG được ghi khóa bí mật xuống tệp `.env` trên đĩa Container.
- **FR-009**: Hệ thống PHẢI cung cấp các điểm cuối giám sát `GET /healthz`, `GET /readyz`, `GET /api/cloud/status`, `POST /api/cloud/sync` (yêu cầu quyền `admin`) và giao diện web `GET /cloud`.
- **FR-010**: Hệ thống PHẢI đo đạc và báo cáo lưu lượng HTTP theo nhóm chức năng, phân bố mã trạng thái, độ trễ trung bình/P50/P95, dung lượng RAM tiến trình/Container và thống kê cuộc gọi OpenRouter API.
- **FR-011**: Kịch bản triển khai (`deploy_cloud.py`) PHẢI hỗ trợ hai chế độ `decoupled` (mã nguồn < 5 MB tách khỏi kho Dataset `private=True`) và `standalone`, đồng thời tự động ngăn rò rỉ tệp bí mật và tệp huấn luyện.
- **FR-012**: Bộ tài liệu báo cáo môn học tại `reports/BAO_CAO_DIEN_TOAN_DAM_MAY.md` PHẢI đáp ứng đầy đủ 07 phần theo đề cương giảng viên và tuân thủ nghiêm ngặt quy tắc văn phong học thuật của dự án.

### Key Entities

- **CloudStorageBackend**: Trừu tượng hóa điểm lưu trữ bền vững (`hf_dataset`, `local_volume`, `ephemeral`), chứa thông tin trạng thái đồng bộ, hàng đợi tác vụ nền và nhật ký 20 sự kiện gần nhất.
- **StatelessSessionToken**: Token xác thực ký `HMAC-SHA256` chứa `u` (tên đăng nhập), `role` (vai trò RBAC), `iat` (thời điểm cấp), `exp` (thời điểm hết hạn), `jti` (mã định danh phiên duy nhất).
- **CloudTelemetrySnapshot**: Ảnh chụp tức thời tình trạng vận hành Container gồm thông tin môi trường chạy, mức tiêu thụ RAM, bộ đếm truy vấn HTTP, phân vị độ trễ P50/P95 và thống kê gọi LLM API.
- **ArchiveDossier & DocumentRecord**: Thực thể hồ sơ lưu trữ theo Thông tư 02/2019/TT-BNV và thẻ văn bản hành chính theo NĐ 30/2020/NĐ-CP được đồng bộ dưới dạng cấu trúc JSON bền vững.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Gói mã nguồn Container ở chế độ `decoupled` có tổng dung lượng **nhỏ hơn 5 MB** (giảm > 98% so với gói đơn khối ~283 MB).
- **SC-002**: Sau khi xóa toàn bộ dữ liệu làm việc cục bộ của Container và khởi động lại, **100%** hồ sơ tạo mới và tài liệu PDF đã tải lên được khôi phục nguyên vẹn từ tầng lưu trữ bền vững.
- **SC-003**: Token đăng nhập `st1.*` cấp bởi một tiến trình Container vẫn xác thực thành công trên một tiến trình Container khởi động mới với tỷ lệ **100%** khi dùng chung khóa cấu hình môi trường.
- **SC-004**: Điểm cuối `GET /healthz` phản hồi mã HTTP `200` trong thời gian **< 100 ms** và `GET /readyz` chỉ trả `200` sau khi kho văn bản và bộ máy tìm kiếm đã nạp xong.
- **SC-005**: Toàn bộ bộ kiểm thử tự động (`pytest`) trong thư mục `Dien_toan_dam_may/` đạt tỷ lệ vượt qua **100%** (bao gồm cả bộ kiểm thử kế thừa và 4 nhóm kiểm thử kiến trúc đám mây mới).
- **SC-006**: Dự án môn NLP (`Du_an/` và các thư mục liên quan) giữ nguyên trạng **100%** không có bất kỳ thay đổi nào sau khi hoàn tất toàn bộ quá trình.

## Assumptions

- Người dùng sử dụng gói miễn phí của Hugging Face Spaces (CPU Basic: 2 vCPU, 16 GB RAM), Hugging Face Hub Dataset (`private=True`), OpenRouter API và GitHub Actions.
- Kho dữ liệu mẫu trong `Dien_toan_dam_may/data/raw/` chỉ giữ 10 PDF kích thước nhỏ để phục vụ chạy thử nhanh; toàn bộ các tệp PDF khác của kho chính khi triển khai đầy đủ sẽ được đẩy lên kho Dataset riêng tư qua `deploy_cloud.py --raw-dir ...` và nạp lười khi có yêu cầu xem trang.
