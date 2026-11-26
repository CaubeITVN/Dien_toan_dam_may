# BÁO CÁO DỰ ÁN HỌC PHẦN ĐIỆN TOÁN ĐÁM MÂY

**Đề tài:** Xây dựng hệ thống lưu trữ tài liệu số trên nền tảng đám mây tích hợp trợ lý số hóa trí tuệ nhân tạo

**Nhóm thực hiện:** Nhóm 04 — Nông Thị Hương (Nhóm trưởng), Lê Xuân Nhất

**Giảng viên hướng dẫn:** TS. Nguyễn Đức Bình

---

## MỞ ĐẦU

### 1. Lý do chọn đề tài

Quá trình chuyển đổi số tại các cơ quan hành chính đặt ra yêu cầu cấp thiết về số hóa khối tài liệu giấy lịch sử và quản lý tập trung các văn bản điện tử phát sinh hằng ngày. Khi áp dụng công nghệ nhận dạng ký tự quang học tiếng Việt kết hợp tìm kiếm đa tiêu chí và cơ chế tạo sinh tăng cường truy hồi, một hệ thống cục bộ nguyên khối không đáp ứng được nhu cầu truy cập đồng thời qua Internet, đóng gói cồng kềnh và dễ mất toàn bộ hồ sơ mới tạo khi bộ chứa đám mây miễn phí tự động ngủ đông hoặc khởi động lại. Vì vậy, nghiên cứu tái cấu trúc và triển khai hệ thống theo kiến trúc hướng đám mây phi trạng thái, tách rời lưu trữ bền vững và tích hợp sẵn khóa mô hình ngôn ngữ mặc định phía máy chủ là giải pháp phù hợp cho đồ án học phần Điện toán Đám mây.

### 2. Mục tiêu và phạm vi thực hiện

Dự án hoàn thành quy trình phân tích thiết kế hướng đặc tả và triển khai sản phẩm lên hạ tầng đám mây công cộng với ba giao diện hợp nhất gồm cổng quản lý hồ sơ, không gian hỏi đáp ba cột và bảng giám sát hạ tầng. Phạm vi dữ liệu sử dụng bộ văn bản hành chính công khai gồm 110 văn bản, 630 trang và 3 476 đoạn chỉ mục phân cấp trong 4 phông và 14 hồ sơ mô phỏng trên bậc tài nguyên miễn phí không cần gắn thẻ thanh toán (vận hành trực tuyến trên dịch vụ bộ chứa Render gói miễn phí 512 MB RAM tại cụm máy chủ Singapore).

### 3. Bố cục báo cáo

Báo cáo được trình bày thành ba chương chính bao quát đầy đủ bảy nội dung của học phần cùng phần Kết luận và hướng phát triển: Chương 1 trình bày tổng quan bài toán, phân tích thiết kế và lựa chọn dịch vụ đám mây công cộng; Chương 2 trình bày phân công công việc, kế hoạch thực hiện, kiến trúc kỹ thuật và các bước triển khai chi tiết; Chương 3 trình bày kết quả sau triển khai, hướng dẫn sử dụng, đánh giá thực nghiệm và xử lý sự cố.

---

## CHƯƠNG 1. TỔNG QUAN BÀI TOÁN VÀ DỊCH VỤ ĐÁM MÂY CÔNG CỘNG

### 1.1. Mô tả bài toán nghiên cứu

Đầu vào của hệ thống gồm các tệp tài liệu di động hành chính (giới hạn 30 MB mỗi tệp), truy vấn lọc đa tiêu chí, câu hỏi tiếng Việt tự nhiên của người dùng cuối mà không cần tự thiết lập khóa kết nối, cùng thao tác quản trị hồ sơ và biến bí mật máy chủ. Đầu ra gồm thẻ siêu dữ liệu bảy trường hành chính, kết quả xếp hạng tìm kiếm đa nguồn điểm (chế độ tối giản từ vựng chuẩn hóa trên gói 512 MB RAM hoặc lai ngữ nghĩa trên máy chủ từ 2 GB RAM), câu trả lời hỏi đáp có dẫn nguồn kèm trang tài liệu gốc tô vàng căn cứ (hoặc từ chối minh bạch khi thiếu dữ liệu) và bộ chỉ số giám sát hạ tầng thời gian thực. Nội hàm bài toán tập trung vào chuyển đổi từ ứng dụng cục bộ có trạng thái sang kiến trúc bộ chứa phi trạng thái kết hợp lưu trữ đối tượng riêng tư bền vững.

### 1.2. Phân tích và thiết kế hệ thống

Hệ thống phục vụ ba nhóm tác nhân gồm Người dùng công khai, Cán bộ lưu trữ hoặc Quản trị viên và Hệ thống giám sát đám mây thông qua cơ chế kiểm soát truy cập theo vai trò xác thực bằng mã thông báo chữ ký điện tử hai mươi bốn giờ. Dữ liệu được thiết kế phân thành ba lớp gồm ảnh bộ chứa bất biến (hỗ trợ cấu hình kép thích ứng ngưỡng bộ nhớ), bộ nhớ đệm làm việc tạm thời và kho lưu trữ đối tượng bền vững chế độ riêng tư nằm ngoài bộ chứa để bảo toàn toàn vẹn danh mục hồ sơ, tài liệu tải lên, kết quả nhận dạng quang học và kho tệp gốc phục vụ tải lười theo yêu cầu.

### 1.3. Tổng quan và lựa chọn dịch vụ đám mây công cộng

Thông qua đối sánh thực tế năm nền tảng đám mây phổ biến (Render, Hugging Face Spaces, Railway, Fly và Google Cloud Run), tổ hợp bốn dịch vụ đa đám mây vừa và nhỏ được lựa chọn ở mức chi phí không đồng không cần thẻ thanh toán. Cụ thể, dịch vụ bộ chứa tùy biến trên Hugging Face Spaces hiện đã chuyển sang yêu cầu gói trả phí chuyên nghiệp (phát sinh mã lỗi yêu cầu thanh toán 402 ở tài khoản miễn phí), Google Cloud Run bắt buộc thẻ thanh toán quốc tế, Railway giới hạn dùng thử năm đô la trong ba mươi ngày, còn Fly chỉ cấp 256 MB RAM nên tràn bộ nhớ khi khởi chạy. Do đó, nhóm lựa chọn dịch vụ bộ chứa web miễn phí trên Render đặt tại cụm máy chủ Singapore (0,1 lõi xử lý ảo, 512 MB RAM, lắng nghe cổng 10000, tự động triển khai qua bản thiết kế gắn kết GitHub và tự nghỉ sau mười lăm phút không có truy cập), kết hợp kho tập dữ liệu riêng tư Hugging Face Hub (lưu giữ năm nhánh dữ liệu và 110 tệp tài liệu gốc tải lười), cổng mô hình ngôn ngữ OpenRouter với mô hình mặc định Nemotron 3 Ultra 550B bậc miễn phí và đường ống tự động hóa GitHub Actions. Sau khi đăng nhập tài khoản quản trị trên Render, bảng điều khiển cung cấp đầy đủ phân hệ Tổng quan tên miền HTTPS, Sự kiện triển khai, Nhật ký hai luồng và khu vực quản lý biến môi trường cùng biến bí mật mã hóa.

---

## CHƯƠNG 2. QUY TRÌNH TRIỂN KHAI HỆ THỐNG LÊN NỀN TẢNG ĐÁM MÂY

### 2.1. Phân công công việc trong nhóm

Toàn bộ khối lượng công việc của Nhóm 04 được chia đều thành bốn gói gắn với các tầng kiến trúc giữa Nông Thị Hương (Nhóm trưởng: phân tích đặc tả, đối sánh dịch vụ, kiểm thử nghiệp vụ Web và đồng chủ biên báo cáo) và Lê Xuân Nhất (lõi lưu trữ bền vững, tải lười, xác thực phi trạng thái, bảng giám sát, đóng gói bộ chứa cấu hình kép tối ưu cho Render 512 MB RAM, tách gói dữ liệu và tích hợp khóa mặc định máy chủ), phối hợp kiểm tra chéo ở khâu tự động hóa kiểm thử và đo đạc thực nghiệm.

### 2.2. Kế hoạch thực hiện dự án

Dự án thực hiện trong bốn tuần theo phương pháp phát triển hướng đặc tả qua sáu giai đoạn nối tiếp: khởi tạo cô lập và đặc tả; phát triển lõi lưu trữ bền vững và xác thực ký số; xây dựng giao diện giám sát, tích hợp khóa mặc định và tối ưu bộ chứa; thiết lập tự động hóa kiểm thử và đo hiệu năng; triển khai công cộng lên Render kết hợp kho riêng tư và kiểm chứng khởi động lại; cuối cùng là hoàn thiện báo cáo.

### 2.3. Kiến trúc, kỹ thuật sử dụng và tám bước triển khai chi tiết

Kiến trúc triển khai bốn tầng vận hành máy chủ ứng dụng phi trạng thái trên dịch vụ bộ chứa Render tại cụm Singapore trong một ảnh sáu lớp chạy dưới tài khoản người dùng phi đặc quyền. Nhằm vượt qua giới hạn 512 MB RAM của gói miễn phí Render, ảnh bộ chứa áp dụng thiết kế cấu hình kép: cấu hình nhẹ chuyên biệt cho Render tạm lược bỏ thư viện học sâu và trọng số mô hình ngữ nghĩa nặng để giữ mức RAM thực tế khi vận hành trực tuyến quanh ngưỡng 444,58 MB trên 512 MB cho phép (vẫn bảo toàn đầy đủ nhận dạng quang học Tesseract tiếng Việt, tìm kiếm từ vựng chuẩn hóa, hỏi đáp dẫn nguồn và tải lười tài liệu gốc), trong khi vẫn duy trì cấu hình đầy đủ có tìm kiếm lai ngữ nghĩa cho máy chủ từ 2 GB RAM trở lên. Ở tầng suy luận ngôn ngữ lớn, mô hình mặc định Nemotron 3 Ultra 550B bậc miễn phí qua OpenRouter được tinh chỉnh ở mức suy luận thấp, trần 1.500 token đầu ra, nhiệt độ giải mã bằng không và tự động dự phòng sang mô hình cục bộ khi có sẵn hoặc trích xuất nguyên văn khi cổng mạng lỗi. Nhờ tách rời mã nguồn khỏi dữ liệu, gói mã nguồn thu gọn từ 282,75 MB xuống còn 0,65 MB (37 tệp, giảm 99,77%), tách biệt hoàn toàn với 562 tệp (55,41 MB) trên kho tập dữ liệu riêng tư Hugging Face Hub. Quá trình triển khai được thực hiện chuẩn mực qua tám bước từ cô lập mã nguồn, tạo mã truy cập ghi, khởi tạo kho riêng tư, kích hoạt khóa mô hình ngôn ngữ mặc định phía máy chủ, đồng bộ năm nhánh dữ liệu, triển khai bản thiết kế Render kèm cổng 10000 và biến bí mật mã hóa, theo dõi nhật ký dựng ảnh tối giản sẵn sàng cho tới kiểm chứng khôi phục 100% dữ liệu sau khởi động lại bộ chứa.

---

## CHƯƠNG 3. KẾT QUẢ TRIỂN KHAI VÀ ĐÁNH GIÁ SẢN PHẨM

### 3.1. Sản phẩm sau triển khai và hướng dẫn sử dụng

Sản phẩm hoạt động trực tuyến ổn định trên nền tảng Render tại địa chỉ bảo mật HTTPS (https://tra-cuu-luu-tru-so-cloud.onrender.com) với ba giao diện hợp nhất gồm cổng quản lý lưu trữ số hóa, không gian nghiên cứu hỏi đáp ba cột (cho phép mọi người dùng hỏi đáp ngay bằng mô hình Nemotron 3 Ultra 550B mặc định trên máy chủ mà không phải nhập khóa cá nhân, kèm tô vàng căn cứ trên trang gốc tải lười) và bảng điều khiển giám sát hạ tầng cập nhật mỗi mười giây.

### 3.2. Đánh giá thực nghiệm và xử lý sự cố

Kết quả vận hành thực tế và đo thực nghiệm trên kho 110 văn bản, 630 trang và 3 476 đoạn chỉ mục cho thấy thời gian khởi động nạp chỉ mục trong phép đo chuẩn đạt 3,01 giây; mức tiêu thụ bộ nhớ thực tế trên dịch vụ Render đang chạy chỉ duy trì ở khoảng 444,58 MB trên giới hạn 512 MB RAM; các điểm cuối kiểm tra sức khỏe và giám sát đạt độ trễ P95 dưới 3 mili-giây; tìm kiếm lai đạt trung vị P50 50,64 mili-giây; hỏi đáp trích xuất đạt P50 96,91 mili-giây; chu trình xác thực phi trạng thái qua khởi động lại đạt P50 1 986,57 mili-giây; đồng bộ dữ liệu lên kho riêng tư đạt 783,99 mili-giây và tự động khôi phục 100% chỉ trong 25,00 mili-giây sau khi xóa bộ nhớ tạm của bộ chứa. Toàn bộ 85 bài kiểm thử tự động đều thông qua 100% và các sự cố về chuyển đổi nền tảng do Hugging Face Spaces yêu cầu gói trả phí PRO cho bộ chứa tùy biến, tối ưu RAM dưới 512 MB trên Render, gói ngôn ngữ nhận dạng tiếng Việt, chuỗi rỗng của mô hình suy luận sâu (xử lý bằng mô hình Nemotron 3 Ultra mức suy luận thấp, trần 1.500 token và dự phòng tự động) hay yêu cầu khóa phía người dùng đều được xử lý dứt điểm.

---

## KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN

Đồ án đã hoàn thành việc chuyển hóa ứng dụng lưu trữ tài liệu số sang kiến trúc đa đám mây bốn tầng bền vững (Render 512 MB RAM tại cụm Singapore kết hợp kho tập dữ liệu riêng tư Hugging Face Hub, cổng OpenRouter Nemotron 3 Ultra 550B và GitHub Actions) với chi phí hạ tầng bằng không và trải nghiệm hỏi đáp tức thì không cần thiết lập khóa phía người dùng. Hướng phát triển tiếp theo tập trung vào chuyển đổi lớp lưu trữ trạng thái sang cơ sở dữ liệu quan hệ quản lý kết hợp lưu trữ đối tượng tương thích chuẩn S3, tách tác vụ nhận dạng quang học sang hàng đợi công nhân xử lý bất đồng bộ và mở rộng lên máy chủ từ 2 GB RAM trở lên theo mô hình đám mây lai để kích hoạt đồng thời tầng tìm kiếm ngữ nghĩa đa ngôn ngữ và phục vụ đa bản sao.
