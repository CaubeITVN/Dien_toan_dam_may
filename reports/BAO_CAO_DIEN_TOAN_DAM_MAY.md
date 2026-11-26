# BÁO CÁO DỰ ÁN HỌC PHẦN ĐIỆN TOÁN ĐÁM MÂY

**Đề tài:** Xây dựng hệ thống lưu trữ tài liệu số trên nền tảng đám mây tích hợp trợ lý số hóa trí tuệ nhân tạo

**Nhóm thực hiện:** Nhóm 04 — Nông Thị Hương (Nhóm trưởng), Lê Xuân Nhất

**Giảng viên hướng dẫn:** TS. Nguyễn Đức Bình

---

## MỞ ĐẦU

### 1. Lý do chọn đề tài

Quá trình chuyển đổi số tại các cơ quan hành chính đặt ra yêu cầu cấp thiết về số hóa khối tài liệu giấy lịch sử và quản lý tập trung các văn bản điện tử phát sinh hằng ngày. Khi áp dụng công nghệ nhận dạng ký tự quang học tiếng Việt kết hợp tìm kiếm lai và cơ chế tạo sinh tăng cường truy hồi, một hệ thống cục bộ nguyên khối không đáp ứng được nhu cầu truy cập đồng thời qua Internet, đóng gói cồng kềnh và dễ mất toàn bộ hồ sơ mới tạo khi bộ chứa đám mây miễn phí tự động ngủ đông hoặc khởi động lại. Vì vậy, nghiên cứu tái cấu trúc và triển khai hệ thống theo kiến trúc hướng đám mây phi trạng thái, tách rời lưu trữ bền vững và tích hợp sẵn khóa mô hình ngôn ngữ mặc định phía máy chủ là giải pháp phù hợp cho đồ án học phần Điện toán Đám mây.

### 2. Mục tiêu và phạm vi thực hiện

Dự án hoàn thành quy trình phân tích thiết kế hướng đặc tả và triển khai sản phẩm lên hạ tầng đám mây công cộng với ba giao diện hợp nhất gồm cổng quản lý hồ sơ, không gian hỏi đáp ba cột và bảng giám sát hạ tầng. Phạm vi dữ liệu sử dụng bộ văn bản hành chính công khai gồm 110 văn bản, 630 trang và 3 476 đoạn chỉ mục phân cấp trong 4 phông và 14 hồ sơ mô phỏng trên bậc tài nguyên miễn phí không cần gắn thẻ thanh toán.

### 3. Bố cục báo cáo

Báo cáo được trình bày thành ba chương chính bao quát đầy đủ bảy nội dung của học phần cùng phần Kết luận và hướng phát triển: Chương 1 trình bày tổng quan bài toán, phân tích thiết kế và lựa chọn dịch vụ đám mây công cộng; Chương 2 trình bày phân công công việc, kế hoạch thực hiện, kiến trúc kỹ thuật và các bước triển khai chi tiết; Chương 3 trình bày kết quả sau triển khai, hướng dẫn sử dụng, đánh giá thực nghiệm và xử lý sự cố.

---

## CHƯƠNG 1. TỔNG QUAN BÀI TOÁN VÀ DỊCH VỤ ĐÁM MÂY CÔNG CỘNG

### 1.1. Mô tả bài toán nghiên cứu

Đầu vào của hệ thống gồm các tệp tài liệu di động hành chính (giới hạn 30 MB mỗi tệp), truy vấn lọc đa tiêu chí, câu hỏi tiếng Việt tự nhiên của người dùng cuối mà không cần tự thiết lập khóa kết nối, cùng thao tác quản trị hồ sơ và biến bí mật máy chủ. Đầu ra gồm thẻ siêu dữ liệu bảy trường hành chính, kết quả xếp hạng tìm kiếm lai, câu trả lời hỏi đáp có dẫn nguồn kèm trang tài liệu gốc tô vàng căn cứ (hoặc từ chối minh bạch khi thiếu dữ liệu) và bộ chỉ số giám sát hạ tầng thời gian thực. Nội hàm bài toán tập trung vào chuyển đổi từ ứng dụng cục bộ có trạng thái sang kiến trúc bộ chứa phi trạng thái kết hợp lưu trữ đối tượng riêng tư bền vững.

### 1.2. Phân tích và thiết kế hệ thống

Hệ thống phục vụ ba nhóm tác nhân gồm Người dùng công khai, Cán bộ lưu trữ hoặc Quản trị viên và Hệ thống giám sát đám mây thông qua cơ chế kiểm soát truy cập theo vai trò xác thực bằng mã thông báo chữ ký điện tử hai mươi bốn giờ. Dữ liệu được thiết kế phân thành ba lớp gồm ảnh bộ chứa bất biến, bộ nhớ đệm làm việc tạm thời và kho lưu trữ đối tượng bền vững chế độ riêng tư nằm ngoài bộ chứa để bảo toàn toàn vẹn danh mục hồ sơ, tài liệu tải lên, kết quả nhận dạng quang học và kho tệp gốc phục vụ tải lười theo yêu cầu.

### 1.3. Tổng quan và lựa chọn dịch vụ đám mây công cộng

Thông qua đối sánh năm nền tảng đám mây phổ biến (Hugging Face Spaces, Render, Railway, Fly và Google Cloud Run), tổ hợp bốn dịch vụ vừa và nhỏ được lựa chọn gồm không gian bộ chứa Docker của Hugging Face Spaces (2 lõi xử lý ảo, 16 GB RAM, không cần thẻ tín dụng), kho tập dữ liệu riêng tư Hugging Face Hub, cổng mô hình ngôn ngữ OpenRouter mặc định phía máy chủ và đường ống tự động hóa GitHub Actions. Sau khi đăng nhập tài khoản, bảng điều khiển đám mây cung cấp đầy đủ thẻ ứng dụng HTTPS, cửa sổ nhật ký hai luồng, khu vực quản lý biến bí mật mã hóa, trang theo dõi lịch sử phiên bản kho riêng tư và bảng kiểm soát hạn mức token.

---

## CHƯƠNG 2. QUY TRÌNH TRIỂN KHAI HỆ THỐNG LÊN NỀN TẢNG ĐÁM MÂY

### 2.1. Phân công công việc trong nhóm

Toàn bộ khối lượng công việc của Nhóm 04 được chia đều thành bốn gói gắn với các tầng kiến trúc giữa Nông Thị Hương (Nhóm trưởng: phân tích đặc tả, đối sánh dịch vụ, kiểm thử nghiệp vụ Web và đồng chủ biên báo cáo) và Lê Xuân Nhất (lõi lưu trữ bền vững, tải lười, xác thực phi trạng thái, bảng giám sát, đóng gói tách dữ liệu và tích hợp khóa mặc định máy chủ), phối hợp kiểm tra chéo ở khâu tự động hóa kiểm thử và đo đạc thực nghiệm.

### 2.2. Kế hoạch thực hiện dự án

Dự án thực hiện trong bốn tuần theo phương pháp phát triển hướng đặc tả qua sáu giai đoạn nối tiếp: khởi tạo cô lập và đặc tả; phát triển lõi lưu trữ bền vững và xác thực ký số; xây dựng giao diện giám sát, tích hợp khóa mặc định và tối ưu bộ chứa; thiết lập tự động hóa kiểm thử và đo hiệu năng; triển khai công cộng và kiểm chứng khởi động lại; cuối cùng là hoàn thiện báo cáo.

### 2.3. Kiến trúc, kỹ thuật sử dụng và tám bước triển khai chi tiết

Kiến trúc triển khai bốn tầng vận hành máy chủ ứng dụng phi trạng thái trong bộ chứa sáu lớp chạy dưới tài khoản người dùng phi đặc quyền, nạp sẵn mô hình chuyển đổi ngữ nghĩa đa ngôn ngữ và bộ nhận dạng tiếng Việt. Nhờ tách rời mã nguồn khỏi dữ liệu, gói đẩy lên không gian bộ chứa thu gọn từ 282,75 MB xuống còn 0,65 MB (37 tệp, giảm 99,77%), tách biệt hoàn toàn với 562 tệp (55,41 MB) trên kho tập dữ liệu riêng tư. Quá trình triển khai được thực hiện chuẩn mực qua tám bước từ cô lập mã nguồn, tạo mã truy cập ghi, khởi tạo kho riêng tư, kích hoạt khóa mô hình ngôn ngữ mặc định phía máy chủ, đồng bộ năm nhánh dữ liệu, tạo không gian bộ chứa kèm sáu biến bí mật mã hóa, theo dõi nhật ký dựng ảnh sẵn sàng cho tới kiểm chứng khôi phục 100% dữ liệu sau khởi động lại bộ chứa.

---

## CHƯƠNG 3. KẾT QUẢ TRIỂN KHAI VÀ ĐÁNH GIÁ SẢN PHẨM

### 3.1. Sản phẩm sau triển khai và hướng dẫn sử dụng

Sản phẩm cung cấp ba giao diện hợp nhất qua kết nối HTTPS gồm cổng quản lý lưu trữ số hóa, không gian nghiên cứu hỏi đáp ba cột (cho phép mọi người dùng hỏi đáp ngay bằng khóa mô hình ngôn ngữ mặc định trên máy chủ mà không phải nhập khóa cá nhân, kèm tô vàng căn cứ trên trang gốc tải lười) và bảng điều khiển giám sát hạ tầng cập nhật mỗi mười giây.

### 3.2. Đánh giá thực nghiệm và xử lý sự cố

Kết quả đo thực nghiệm trên kho 110 văn bản, 630 trang và 3 476 đoạn chỉ mục cho thấy thời gian khởi động nạp chỉ mục đạt 3,01 giây; các điểm cuối kiểm tra sức khỏe và giám sát đạt độ trễ P95 dưới 3 mili-giây; tìm kiếm lai đạt trung vị P50 50,64 mili-giây; hỏi đáp trích xuất đạt P50 96,91 mili-giây; chu trình xác thực phi trạng thái qua khởi động lại đạt P50 1 986,57 mili-giây; đồng bộ dữ liệu lên kho riêng tư đạt 783,99 mili-giây và tự động khôi phục 100% chỉ trong 25,00 mili-giây sau khi xóa bộ nhớ tạm của bộ chứa. Toàn bộ các bài kiểm thử tự động đều thông qua 100% và các sự cố về gói ngôn ngữ nhận dạng, chuỗi rỗng mô hình suy luận hay yêu cầu khóa phía người dùng đều được xử lý dứt điểm.

---

## KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

Đồ án đã hoàn thành việc chuyển hóa ứng dụng lưu trữ tài liệu số sang kiến trúc bốn tầng hướng đám mây bền vững, gọn nhẹ và an toàn chi phí ở mức không đồng hạ tầng, mang lại trải nghiệm hỏi đáp tức thì không cần thiết lập khóa phía người dùng. Hướng phát triển tiếp theo tập trung vào chuyển đổi lớp lưu trữ trạng thái sang cơ sở dữ liệu quan hệ quản lý kết hợp lưu trữ đối tượng tương thích chuẩn S3, tách tác vụ nhận dạng quang học sang hàng đợi công nhân xử lý bất đồng bộ và triển khai theo mô hình đám mây lai phục vụ mở rộng quy mô đa bản sao.
