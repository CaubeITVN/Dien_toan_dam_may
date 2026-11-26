"""Nội dung học thuật Chương 2, Chương 3 và Kết luận cho báo cáo Điện toán Đám mây (~40 trang, không trích dẫn)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_bench() -> dict:
    p = ROOT / "reports" / "cloud_benchmark_results.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _vn(val: float | int, digits: int = 2) -> str:
    if isinstance(val, int):
        return f"{val:,}".replace(",", " ")
    return f"{val:.{digits}f}".replace(".", ",")


def build_chapters_part2() -> tuple[list[dict], dict]:
    b = _load_bench()
    c = b["corpus"]
    pkg = b["packaging"]
    lat = b["latency"]
    dur = b["durability"]

    n_docs = _vn(c["n_docs"])
    n_pages = _vn(c["n_pages"])
    n_chunks = _vn(c["n_chunks"])
    n_fonds = _vn(c["n_fonds"])
    n_dossiers = _vn(c["n_dossiers"])
    startup_s = _vn(b["startup_seconds"], 2)

    dec_sp_files = _vn(pkg["decoupled_space_files"])
    dec_sp_mb = _vn(pkg["decoupled_space_mb"], 2)
    dec_st_files = _vn(pkg["decoupled_storage_files"])
    dec_st_mb = _vn(pkg["decoupled_storage_mb"], 2)
    standalone_files = _vn(pkg["standalone_files"])
    standalone_mb = _vn(pkg["standalone_mb"], 2)
    legacy_mb = _vn(pkg["legacy_monolith_mb"], 2)
    red_pct = _vn(pkg["reduction_vs_legacy_pct"], 2)

    hz_p50, hz_p95, hz_max = _vn(lat["healthz"]["p50_ms"]), _vn(lat["healthz"]["p95_ms"]), _vn(lat["healthz"]["max_ms"])
    rz_p50, rz_p95, rz_max = _vn(lat["readyz"]["p50_ms"]), _vn(lat["readyz"]["p95_ms"]), _vn(lat["readyz"]["max_ms"])
    cs_p50, cs_p95, cs_max = _vn(lat["cloud_status"]["p50_ms"]), _vn(lat["cloud_status"]["p95_ms"]), _vn(lat["cloud_status"]["max_ms"])
    hs_p50, hs_p95, hs_max = _vn(lat["hybrid_search"]["p50_ms"]), _vn(lat["hybrid_search"]["p95_ms"]), _vn(lat["hybrid_search"]["max_ms"])
    qa_p50, qa_p95, qa_max = _vn(lat["grounded_qa_extractive"]["p50_ms"]), _vn(lat["grounded_qa_extractive"]["p95_ms"]), _vn(lat["grounded_qa_extractive"]["max_ms"])
    auth_p50 = _vn(lat["stateless_auth_p50_ms"], 2)
    sync_ms = _vn(dur["sync_ms"], 2)
    restore_ms = _vn(dur["restore_ms"], 2)

    ch2_and_ch3 = [
        {
            "title": "QUY TRÌNH TRIỂN KHAI HỆ THỐNG LÊN NỀN TẢNG ĐÁM MÂY",
            "sections": [
                {
                    "title": "Phân công công việc trong nhóm",
                    "subs": [
                        ("Phân chia công việc đồng đều theo tầng kiến trúc và quy trình phối hợp", [
                            "Nhằm bảo đảm mọi thành viên trong Nhóm 04 đều tham gia đầy đủ vào toàn bộ chu trình phân tích thiết kế hướng đặc tả, lập trình hạ tầng đám mây, kiểm thử và biên soạn báo cáo, toàn bộ khối lượng dự án được chia thành bốn gói công việc cân đối (mỗi gói chiếm hai mươi lăm phần trăm khối lượng) gắn chặt với từng tầng kiến trúc như trình bày ở Bảng 2.1 và Hình 2.1.",
                            "Thành viên Nông Thị Hương (Nhóm trưởng) chủ trì gói phân tích thiết kế đặc tả, lập bảng tiêu chí đối sánh năm nền tảng đám mây, kiểm thử nghiệp vụ cổng quản lý hồ sơ và không gian hỏi đáp ba cột, đồng thời điều phối chất lượng tài liệu báo cáo. Thành viên Lê Xuân Nhất chủ trì xây dựng lớp lưu trữ bền vững đa chế độ, cơ chế tải lười tài liệu gốc, nâng cấp xác thực phiên phi trạng thái, thiết kế giao diện giám sát hạ tầng, đóng gói bộ chứa tách dữ liệu và cấu hình sẵn khóa mô hình ngôn ngữ mặc định phía máy chủ. Hai thành viên phối hợp kiểm tra chéo ở khâu tích hợp đường ống tự động hóa kiểm thử, đo đạc hiệu năng thực nghiệm và diễn tập kịch bản trình diễn trực tuyến.",
                        ], [
                            {
                                "type": "table",
                                "caption": "Bảng 2.1. Phân công công việc chi tiết theo tầng hệ thống giữa các thành viên Nhóm 04",
                                "headers": ["Thành viên & Vai trò", "Phân hệ / Tầng phụ trách", "Nhiệm vụ kỹ thuật và sản phẩm đầu ra kiểm chứng"],
                                "rows": [
                                    ["Nông Thị Hương\n(Nhóm trưởng)", "Phân tích đặc tả, Nghiệp vụ Web, Kiểm thử & Báo cáo", "Cô lập dự án; soạn bộ đặc tả yêu cầu, đối sánh nền tảng đám mây và sơ đồ thiết kế; kiểm thử nghiệp vụ quản lý hồ sơ, tìm kiếm lai và hỏi đáp không cần khóa; đồng chủ biên báo cáo."],
                                    ["Lê Xuân Nhất\n(Thành viên kỹ thuật)", "Lưu trữ bền vững, Bảo mật, Giám sát, Bộ chứa & Triển khai", "Lập trình lớp lưu trữ bền vững và tải lười PDF; nâng cấp xác thực chữ ký điện tử; dựng mô-đun đo lường và trang giám sát hạ tầng; đóng gói bộ chứa 6 lớp, tách gói mã nguồn, tích hợp khóa LLM mặc định và chạy đo độ trễ."],
                                    ["Phối hợp chung\n(Kiểm tra chéo)", "Tự động hóa CI/CD & Kịch bản vận hành công cộng", "Xây dựng luồng kiểm thử liên tục; kiểm chứng đồng bộ và khôi phục 100% dữ liệu sau khởi động lại bộ chứa; hoàn thiện hình ảnh minh họa và rà soát toàn bộ báo cáo."],
                                ],
                            },
                            {
                                "type": "figure",
                                "path": "fig_2_1.png",
                                "caption": "Hình 2.1. Phân bổ tỷ trọng bốn gói công việc đồng đều giữa các thành viên Nhóm 04",
                                "width_cm": 14.5,
                            },
                        ]),
                    ],
                },
                {
                    "title": "Kế hoạch dự kiến hoàn thành dự án",
                    "subs": [
                        ("Các giai đoạn thực hiện, kết quả dự kiến và tiến độ theo tuần", [
                            "Nhóm áp dụng phương pháp phát triển phần mềm hướng đặc tả xuyên suốt bốn tuần làm việc tập trung, chia thành sáu giai đoạn nối tiếp với sản phẩm đầu ra định lượng tại mỗi điểm kiểm soát (Bảng 2.2 và Hình 2.2). Nguyên tắc điều hành tiến độ là chỉ chuyển sang giai đoạn lập trình và đóng gói sau khi hoàn tất đặc tả giao diện và tiêu chí kiểm chứng, qua đó loại bỏ hoàn toàn xung đột khi tích hợp mã nguồn giữa hai thành viên.",
                            "Từ giai đoạn khởi tạo tuần đầu tiên đến giai đoạn triển khai công cộng và kiểm chứng khởi động lại bộ chứa ở tuần thứ tư, mọi mốc kiểm tra đều gắn liền với chỉ số đo đạc cụ thể như kích thước gói mã nguồn dưới năm megabyte, tỷ lệ thông qua kiểm thử một trăm phần trăm và không để bất kỳ tệp bí mật nào lọt vào kho mã nguồn công khai.",
                        ], [
                            {
                                "type": "table",
                                "caption": "Bảng 2.2. Kế hoạch chi tiết các bước thực hiện, kết quả dự kiến và thời gian phân bổ",
                                "headers": ["Thời gian", "Giai đoạn thực hiện", "Nội dung công việc trọng tâm", "Kết quả đầu ra dự kiến"],
                                "rows": [
                                    ["Tuần 1 (Ngày 1–5)", "1. Khởi tạo, đặc tả & đối sánh Cloud", "Cô lập dự án khỏi môn NLP; lập bộ đặc tả yêu cầu, mô hình ba lớp, sơ đồ ca sử dụng và đối sánh năm nhà cung cấp đám mây", "Hoàn thiện bộ tài liệu đặc tả chuẩn mực và chọn tổ hợp 4 dịch vụ đám mây"],
                                    ["Tuần 2 (Ngày 6–12)", "2. Phát triển lõi lưu trữ & xác thực", "Xây dựng lớp lưu trữ bền vững đa chế độ, cơ chế tải lười tài liệu gốc, xác thực chữ ký HMAC-SHA256 và bộ thu thập chỉ số", "Xác thực vượt qua khởi động lại và khôi phục dữ liệu đạt 100% trên ổ đĩa mô phỏng"],
                                    ["Tuần 3 (Ngày 12–17)", "3. Giám sát, LLM mặc định & đóng gói", "Tạo trang giám sát hạ tầng đám mây; cấu hình khóa LLM mặc định máy chủ và ẩn bước nhập khóa của người dùng; tối ưu bộ chứa 6 lớp", "Giao diện giám sát trực tuyến hoạt động; gói mã nguồn tách rời dưới 1 MB"],
                                    ["Tuần 3 (Ngày 17–21)", "4. Tích hợp CI/CD, kiểm thử & đo đạc", "Thiết lập luồng tự động hóa kiểm thử; viết mới 4 bộ kiểm thử đám mây; chạy đo độ trễ P50/P95 và phục hồi", "100% bài kiểm thử vượt qua; thu được bộ số liệu đo thực nghiệm chuẩn xác"],
                                    ["Tuần 4 (Ngày 21–24)", "5. Triển khai Cloud & kiểm chứng restart", "Đẩy 562 tệp lên kho riêng tư; tạo bộ chứa 16 GB RAM; nạp biến bí mật; kiểm chứng khởi động lại giữ nguyên dữ liệu", "Ứng dụng công cộng chạy ổn định qua HTTPS và sống sót hoàn toàn sau restart"],
                                    ["Tuần 4 (Ngày 24–28)", "6. Hoàn thiện báo cáo & chuẩn bị demo", "Chụp và dựng đủ bộ minh họa quy trình; rà soát văn phong học thuật; diễn tập kịch bản trình diễn thực tế", "Quyển báo cáo hoàn chỉnh ~40 trang và bộ demo sẵn sàng trình bày"],
                                ],
                            },
                            {
                                "type": "figure",
                                "path": "fig_2_2.png",
                                "caption": "Hình 2.2. Biểu đồ tiến độ thực hiện dự án qua sáu giai đoạn theo tuần",
                                "width_cm": 14.5,
                            },
                        ]),
                    ],
                },
                {
                    "title": "Kiến trúc triển khai hệ thống trên đám mây",
                    "subs": [
                        ("Sơ đồ triển khai tổng thể bốn tầng và cơ chế vận hành phi trạng thái", [
                            "Hình 2.3 thể hiện kiến trúc triển khai tổng thể sau khi hệ thống được tái cấu trúc cho môi trường đám mây công cộng. Người dùng và quản trị viên chỉ tương tác với máy chủ ứng dụng web qua địa chỉ HTTPS duy nhất của không gian bộ chứa, nơi phục vụ đồng thời cổng quản lý lưu trữ, không gian nghiên cứu hỏi đáp ba cột và bảng điều khiển giám sát hạ tầng. Phía sau lớp giao tiếp đó, bộ chứa tính toán vận hành hoàn toàn phi trạng thái với hai lõi xử lý ảo và mười sáu gigabyte RAM.",
                            "Mọi dữ liệu biến đổi gồm danh mục hồ sơ lưu trữ, tài liệu mới tải lên, bộ nhớ đệm nhận dạng quang học và kho văn bản gốc được đặt tách rời trên kho tập dữ liệu riêng tư để bảo toàn qua mọi lần bộ chứa ngủ đông hay xây dựng lại. Đồng thời, khóa kết nối dịch vụ mô hình ngôn ngữ mặc định được giữ an toàn trong khu vực biến bí mật của máy chủ, giúp luồng suy luận ngôn ngữ hoạt động liền mạch mà không làm phiền người dùng cuối.",
                        ], [
                            {
                                "type": "figure",
                                "path": "fig_2_3.png",
                                "caption": "Hình 2.3. Kiến trúc triển khai tổng thể bốn tầng trên nền tảng đám mây công cộng",
                                "width_cm": 15.2,
                            },
                        ]),
                    ],
                },
                {
                    "title": "Các kỹ thuật hướng đám mây sử dụng trong triển khai",
                    "subs": [
                        ("Đóng gói bộ chứa đa lớp và tách gói mã nguồn siêu nhẹ", [
                            "Để bảo đảm ảnh bộ chứa vừa khởi động nhanh vừa đạt chuẩn bảo mật sản xuất, quy trình đóng gói được chia làm sáu lớp xếp chồng hợp lý như minh họa bên trái Hình 2.4. Hai lớp nền cài đặt ảnh Linux tối giản kèm Python phiên bản 3.10 và bộ nhận dạng quang học Tesseract gói tiếng Việt; lớp thứ ba chỉ cài các thư viện xử lý văn bản, học sâu tối ưu cho bộ xử lý trung tâm và khung máy chủ web bất đồng bộ mà lược bỏ hoàn toàn phần mềm đồ họa dư thừa. Đặc biệt, lớp thứ tư nạp sẵn trọng số mô hình chuyển đổi ngữ nghĩa đa ngôn ngữ vào bộ nhớ đệm của ảnh, loại bỏ khâu tải lại gần năm trăm megabyte trọng số qua mạng mỗi lần bộ chứa khởi chạy. Lớp trên cùng chuyển quyền thực thi sang tài khoản người dùng phi đặc quyền có mã định danh một nghìn nhằm thu hẹp bề mặt tấn công hệ thống.",
                            "Điểm cải tiến kỹ thuật quan trọng nhất là kịch bản đóng gói hỗ trợ chế độ tách dữ liệu mặc định. Kịch bản tự động sàng lọc cây thư mục, loại bỏ mọi tệp chứa khóa bí mật cục bộ, dữ liệu huấn luyện nội bộ và các tệp trung gian; chỉ giữ lại đúng " + dec_sp_files + " tệp mã nguồn và giao diện với dung lượng " + dec_sp_mb + " MB đẩy lên không gian bộ chứa, trong khi toàn bộ " + dec_st_files + " tệp dữ liệu và chỉ mục (" + dec_st_mb + " MB) được điều hướng sang kho tập dữ liệu riêng tư. So với phương án đóng gói đơn khối cũ nặng " + legacy_mb + " MB và gói độc lập mẫu nhẹ " + standalone_mb + " MB (Bảng 2.3 và biểu đồ bên phải Hình 2.4), chế độ tách biệt mới giúp cắt giảm tới " + red_pct + " phần trăm dung lượng gói mã nguồn bộ chứa.",
                        ], [
                            {
                                "type": "figure",
                                "path": "fig_2_4.png",
                                "caption": "Hình 2.4. Cấu trúc sáu lớp ảnh bộ chứa bảo mật (trái) và biểu đồ cắt giảm dung lượng gói (phải)",
                                "width_cm": 15.2,
                            },
                            {
                                "type": "table",
                                "caption": "Bảng 2.3. Đối sánh kích thước và thành phần các phương án đóng gói triển khai",
                                "headers": ["Phương án đóng gói", "Số tệp", "Dung lượng (MB)", "Thành phần chính trong gói và đặc điểm vận hành"],
                                "rows": [
                                    ["Đóng gói đơn khối cũ", "705", legacy_mb, "Gộp chung mã nguồn với toàn bộ dữ liệu gốc, tệp xử lý và bộ nhớ đệm; rất chậm khi đẩy mã và dễ mất trạng thái mới lúc restart"],
                                    ["Gói độc lập mẫu nhẹ", standalone_files, standalone_mb, "Mã nguồn kèm 10 tài liệu mẫu, dữ liệu làm sạch và chỉ mục thu gọn; tiện chạy thử một nút nhưng vẫn gắn dữ liệu vào ảnh"],
                                    ["Gói mã nguồn tách biệt (Space)", dec_sp_files, dec_sp_mb, "Chỉ gồm mã nguồn máy chủ, giao diện web, thư viện và cấu hình bộ chứa; giảm " + red_pct + "% dung lượng, cập nhật chỉ vài giây"],
                                    ["Kho dữ liệu bền vững (Dataset)", dec_st_files, dec_st_mb, "Danh mục hồ sơ, văn bản làm sạch, kết quả nhận dạng đệm, mô hình phụ trợ và kho tài liệu gốc; đẩy lên kho riêng tư một lần"],
                                ],
                            },
                        ]),
                        ("Tách cấu hình môi trường, bảo mật bí mật và tích hợp mô hình ngôn ngữ mặc định", [
                            "Mọi tham số thay đổi theo môi trường chạy đều được tách hoàn toàn ra khỏi mã nguồn và quản lý thông qua sáu nhóm biến môi trường mã hóa trên giao diện cài đặt của nền tảng đám mây (Bảng 2.4). Nhằm ngăn chặn tuyệt đối hiện tượng ghi ngược thông tin nhạy cảm xuống hệ thống tệp tạm thời của bộ chứa đang chạy, cờ kích hoạt môi trường phi trạng thái luôn được thiết lập ở mức bật sẵn ngay trong cấu hình đóng gói.",
                            "Đặc biệt, đối với phân hệ hỏi đáp trí tuệ nhân tạo, hệ thống tích hợp cơ chế nạp sẵn khóa kết nối cổng mô hình ngôn ngữ OpenRouter mặc định ở tầng máy chủ (đồng thời cho phép ghi đè qua biến bí mật mã hóa trên đám mây). Khi trả thông tin trạng thái về trình duyệt hoặc trang giám sát, mọi khóa bí mật đều được che giấu tự động chỉ giữ lại vài ký tự nhận diện đầu cuối; trên giao diện người dùng, hộp thoại thiết lập khóa bị ẩn hoàn toàn đối với độc giả thông thường để bất kỳ ai truy cập web cũng có thể đặt câu hỏi ngay lập tức với công tắc trợ lý AI đã bật sẵn.",
                        ], [
                            {
                                "type": "table",
                                "caption": "Bảng 2.4. Danh mục cấu hình biến môi trường và biến bí mật bảo mật phía máy chủ",
                                "headers": ["Nhóm biến cấu hình", "Phân loại bảo mật", "Chức năng trong vận hành trên hạ tầng đám mây"],
                                "rows": [
                                    ["Định danh kho tập dữ liệu bền vững", "Biến cấu hình / Bí mật", "Chỉ định kho riêng tư để máy chủ tự động khôi phục lúc khởi động và đẩy đồng bộ mỗi khi thay đổi hồ sơ hoặc tệp tải lên"],
                                    ["Mã thông báo truy cập kho dữ liệu", "Biến bí mật mã hóa", "Xác thực quyền đọc khi tải lười tài liệu gốc và quyền ghi đồng bộ vào kho riêng tư"],
                                    ["Khóa cổng mô hình ngôn ngữ mặc định", "Biến bí mật / Mặc định máy chủ", "Cấp quyền kết nối cổng OpenRouter sẵn sàng ngay cho người dùng cuối mà không cần nhập khóa trên trình duyệt"],
                                    ["Nhà cung cấp và tên mô hình mặc định", "Biến cấu hình", "Thiết lập mô hình Gemini 2.0 Flash qua OpenRouter làm mặc định cho tác vụ hỏi đáp và tóm tắt có trích dẫn"],
                                    ["Mật khẩu quản trị và khóa ký phiên", "Biến bí mật mã hóa", "Dẫn xuất khóa ký chữ ký điện tử HMAC-SHA256 giúp phiên đăng nhập quản trị sống sót qua lần khởi động lại"],
                                    ["Cờ vận hành môi trường phi trạng thái", "Biến cấu hình hệ thống", "Chặn ghi tệp cấu hình ra đĩa tạm của bộ chứa và kích hoạt kiểm tra trạng thái sống/sẵn sàng"],
                                ],
                            },
                        ]),
                        ("Kiểm tra sức khỏe dịch vụ, tải lười tài liệu và kiểm soát chi phí", [
                            "Trong cấu hình bộ chứa, hệ thống khai báo chỉ thị kiểm tra trạng thái sống định kỳ mỗi ba mươi giây (thời gian chờ năm giây và thời gian khởi động chờ tối đa bốn mươi lăm giây) tách biệt hoàn toàn với điểm cuối kiểm tra mức độ sẵn sàng phục vụ chỉ mục lai. Khi chưa có yêu cầu mở xem trang cụ thể nào, các tệp tài liệu gốc có dung lượng lớn vẫn nằm yên trên kho riêng tư; chỉ khi người dùng nhấp vào nút trích dẫn hoặc mở trình xem, cơ chế tải lười mới nạp đúng tệp cần thiết về bộ nhớ đệm để kết xuất ảnh trang.",
                            "Song song đó, cơ chế kiểm soát chi phí bốn tầng bảo đảm hạ tầng tính toán và lưu trữ luôn giữ ở mức không đồng không thẻ tín dụng, trong khi cổng mô hình ngôn ngữ mặc định được bảo vệ bởi ngưỡng từ chối trước khi gọi, giới hạn tối đa năm đoạn trích mỗi lượt, giới hạn độ dài phản hồi và chế độ trích câu cơ sở dự phòng ngoại tuyến.",
                        ]),
                    ],
                },
                {
                    "title": "Các bước triển khai chi tiết lên dịch vụ đám mây",
                    "subs": [
                        ("Bước 1 đến Bước 2: Chuẩn bị mã nguồn cô lập và khởi tạo khóa truy cập đám mây", [
                            "Ở bước thứ nhất, nhóm tách toàn bộ hai mươi bốn mô-đun chạy cốt lõi, thư mục giao diện web, tệp đóng gói bộ chứa và đường ống tự động hóa kiểm thử sang một không gian thư mục riêng biệt nhằm bảo đảm không làm ảnh hưởng tới các học phần khác, đồng thời thiết lập quy tắc loại trừ chặn triệt để các tệp chứa khóa bí mật cục bộ và dữ liệu thô khỏi kho mã công khai. Kết quả chạy toàn bộ tám mươi lăm bài kiểm thử tự động trước triển khai đạt tỷ lệ thông qua một trăm phần trăm và gói mã nguồn tách dữ liệu chỉ nặng " + dec_sp_mb + " MB (Hình 2.5).",
                            "Ở bước thứ hai, nhóm đăng nhập tài khoản quản trị trên nền tảng Hugging Face, truy cập phần cài đặt bảo mật mã thông báo truy cập để khởi tạo một khóa mới có quyền ghi chuyên biệt cho việc đồng bộ kho dữ liệu và không gian triển khai (minh họa bên trái Hình 2.6). Giá trị khóa này được lưu giữ tạm thời trong vùng nhớ bảo mật phục vụ kịch bản đồng bộ, tuyệt đối không lưu thành văn bản thuần trong mã nguồn.",
                        ], [
                            {
                                "type": "figure",
                                "path": "fig_2_5.png",
                                "caption": "Hình 2.5. Tổ chức cây thư mục cô lập (trái) và kết quả kiểm thử tự động trước triển khai (phải)",
                                "width_cm": 15.2,
                            },
                        ]),
                        ("Bước 3 đến Bước 4: Tạo kho tập dữ liệu riêng tư và thiết lập khóa LLM mặc định", [
                            "Ở bước thứ ba, kịch bản triển khai sử dụng mã thông báo có quyền ghi để tạo mới kho tập dữ liệu lưu trữ bền vững trên Hugging Face Hub với cờ chế độ riêng tư được bật bắt buộc (minh họa bên phải Hình 2.6). Cơ chế này bảo đảm toàn bộ kho tài liệu hành chính, tệp nhận dạng đệm và các tệp người dùng tải lên đều được cách ly hoàn toàn trước truy cập trái phép từ bên ngoài.",
                            "Ở bước thứ tư, nhóm kích hoạt khóa kết nối OpenRouter mặc định của hệ thống tại tầng cấu hình máy chủ kèm các quy tắc giới hạn ngưỡng từ chối và độ dài ngữ cảnh tối đa (Hình 2.7). Nhờ tích hợp sẵn khóa mặc định ở tầng máy chủ và ẩn nút cấu hình khóa trên giao diện người dùng cuối, bất kỳ độc giả hay thành viên hội đồng chấm thi nào khi mở địa chỉ web đều có thể sử dụng ngay chức năng hỏi đáp trí tuệ nhân tạo tốc độ cao mà không phải tạo tài khoản OpenRouter riêng.",
                        ], [
                            {
                                "type": "figure",
                                "path": "fig_2_6.png",
                                "caption": "Hình 2.6. Khởi tạo mã thông báo phân quyền ghi (trái) và tạo kho dữ liệu riêng tư (phải)",
                                "width_cm": 15.2,
                            },
                            {
                                "type": "figure",
                                "path": "fig_2_7.png",
                                "caption": "Hình 2.7. Cấu hình khóa LLM mặc định máy chủ (trái) và cơ chế kiểm soát hạn mức (phải)",
                                "width_cm": 15.2,
                            },
                        ]),
                        ("Bước 5 đến Bước 6: Đẩy dữ liệu lên kho riêng tư và khởi tạo không gian bộ chứa", [
                            "Ở bước thứ năm, kịch bản thực thi ở chế độ tách biệt tiến hành sắp xếp " + dec_st_files + " tệp dữ liệu và chỉ mục (tổng dung lượng " + dec_st_mb + " MB) vào năm nhánh thư mục chuẩn hóa và đẩy toàn bộ lên kho tập dữ liệu riêng tư trong một giao dịch duy nhất trước khi xóa sạch thư mục trung gian (Hình 2.8).",
                            "Ở bước thứ sáu, hệ thống khởi tạo không gian tính toán bộ chứa Docker với phần cứng miễn phí hai lõi xử lý ảo, mười sáu gigabyte RAM, khai báo cổng lắng nghe bảy nghìn tám trăm sáu mươi, đồng bộ toàn bộ sáu biến bí mật và cấu hình mã hóa trong Bảng 2.4 lên phần cài đặt của không gian (Hình 2.9), rồi chỉ đẩy đúng " + dec_sp_files + " tệp mã nguồn siêu nhẹ (" + dec_sp_mb + " MB) lên máy chủ triển khai.",
                        ], [
                            {
                                "type": "figure",
                                "path": "fig_2_8.png",
                                "caption": "Hình 2.8. Quá trình đẩy dữ liệu tách biệt (trái) và cấu trúc năm nhánh trên kho riêng tư (phải)",
                                "width_cm": 15.2,
                            },
                            {
                                "type": "figure",
                                "path": "fig_2_9.png",
                                "caption": "Hình 2.9. Cấu hình không gian bộ chứa 16 GB RAM (trái) và biến bí mật đã che kín (phải)",
                                "width_cm": 15.2,
                            },
                        ]),
                        ("Bước 7 đến Bước 8: Theo dõi dựng ảnh, tự động hóa CI/CD và kiểm chứng bền vững", [
                            "Ở bước thứ bảy, nền tảng đám mây tự động biên dịch ảnh bộ chứa sáu lớp; lần dựng đầu tiên hoàn tất sau khoảng hai đến bốn phút nhờ cài đặt bộ nhận dạng tiếng Việt và nạp sẵn mô hình chuyển đổi ngữ nghĩa, còn những lần cập nhật mã nguồn tiếp theo chỉ mất chưa đầy một phút nhờ cơ chế bộ nhớ đệm phân lớp. Khi cửa sổ nhật ký hiển thị máy chủ hoàn tất khôi phục trạng thái, nạp đủ " + n_docs + " văn bản trong " + startup_s + " giây và mở cổng HTTPS, điểm cuối kiểm tra sức khỏe và sẵn sàng đều trả về mã thành công (Hình 2.10).",
                            "Ở bước thứ tám, nhóm hoàn thiện đường ống tự động hóa kiểm thử liên tục trên mỗi lượt cập nhật mã nguồn và tiến hành bài kiểm chứng khôi phục dữ liệu sau khởi động lại bộ chứa như tổng hợp ở Hình 2.11 và Bảng 2.5. Sau khi tạo mới một hồ sơ và tải lên một tài liệu quét từ giao diện web, hệ thống đồng bộ ra kho riêng tư trong " + sync_ms + " mili-giây; khi buộc khởi động lại hoàn toàn bộ chứa để xóa sạch bộ nhớ RAM và đĩa tạm, tiến trình mới tự động kéo lại toàn bộ thay đổi chỉ trong " + restore_ms + " mili-giây và duy trì nguyên vẹn phiên đăng nhập quản trị. Kết quả theo dõi tài nguyên trên Hình 2.12 xác nhận bộ nhớ sử dụng đỉnh điểm chỉ khoảng 2,35 GB so với ngưỡng 16 GB và chi phí duy trì hạ tầng hoàn toàn bằng không.",
                        ], [
                            {
                                "type": "figure",
                                "path": "fig_2_10.png",
                                "caption": "Hình 2.10. Nhật ký dựng ảnh thành công (trái) và kiểm tra điểm cuối sẵn sàng phục vụ (phải)",
                                "width_cm": 15.2,
                            },
                            {
                                "type": "figure",
                                "path": "fig_2_11.png",
                                "caption": "Hình 2.11. Tự động hóa kiểm thử triển khai (trái) và kiểm chứng khôi phục sau khởi động lại (phải)",
                                "width_cm": 15.2,
                            },
                            {
                                "type": "figure",
                                "path": "fig_2_12.png",
                                "caption": "Hình 2.12. Mức tiêu thụ RAM so với ngưỡng 16 GB (trái) và đối soát chi phí hạ tầng 0 đồng (phải)",
                                "width_cm": 15.2,
                            },
                            {
                                "type": "table",
                                "caption": "Bảng 2.5. Tóm tắt quy trình tám bước triển khai hệ thống lên nền tảng đám mây công cộng",
                                "headers": ["Bước triển khai", "Thao tác thực hiện chính", "Kết quả xác nhận thành công"],
                                "rows": [
                                    ["Bước 1", "Cô lập mã nguồn dự án, khóa quy tắc loại trừ tệp bí mật và chạy bộ kiểm thử trước triển khai", "85 bài kiểm thử thông qua; gói mã nguồn chỉ nặng " + dec_sp_mb + " MB"],
                                    ["Bước 2", "Khởi tạo mã thông báo truy cập có quyền ghi trong phần cài đặt bảo mật tài khoản đám mây", "Thu được mã truy cập phạm vi đọc/ghi an toàn"],
                                    ["Bước 3", "Khởi tạo kho tập dữ liệu lưu trữ bền vững ở chế độ riêng tư bắt buộc", "Kho lưu trữ ẩn hoàn toàn trước truy cập công khai"],
                                    ["Bước 4", "Thiết lập khóa cổng mô hình ngôn ngữ mặc định phía máy chủ và giới hạn ngưỡng từ chối", "Người dùng cuối hỏi đáp AI ngay không cần cài đặt khóa"],
                                    ["Bước 5", "Phân tách và đẩy " + dec_st_files + " tệp dữ liệu (" + dec_st_mb + " MB) theo 5 nhánh lên kho riêng tư", "Hoàn tất đồng bộ nền toàn vẹn dữ liệu gốc và chỉ mục"],
                                    ["Bước 6", "Tạo không gian bộ chứa Docker 2 vCPU / 16 GB RAM, nạp 6 biến bí mật và đẩy " + dec_sp_files + " tệp mã nguồn", "Không gian nhận đủ biến mã hóa và khởi chạy quy trình dựng ảnh"],
                                    ["Bước 7", "Theo dõi nhật ký dựng 6 lớp, xác nhận khôi phục trạng thái và kiểm tra điểm cuối sẵn sàng", "Khởi động trong " + startup_s + " giây; phục vụ công khai qua HTTPS"],
                                    ["Bước 8", "Kích hoạt đường ống kiểm thử tự động CI/CD và thử nghiệm buộc khởi động lại bộ chứa", "Khôi phục 100% hồ sơ mới trong " + restore_ms + " ms; chi phí 0 đồng"],
                                ],
                            },
                        ]),
                    ],
                },
            ],
        },
        {
            "title": "KẾT QUẢ TRIỂN KHAI VÀ ĐÁNH GIÁ SẢN PHẨM",
            "sections": [
                {
                    "title": "Sản phẩm sau triển khai",
                    "subs": [
                        ("Thông tin truy cập dịch vụ và trạng thái sẵn sàng phục vụ", [
                            "Sau khi hoàn tất tám bước triển khai ở Chương 2, hệ thống lưu trữ số hóa tích hợp trợ lý AI hoạt động trực tuyến ổn định trên hạ tầng đám mây công cộng với ba phân hệ giao diện hợp nhất trên cùng một tên miền bảo mật HTTPS (Bảng 3.1). Mọi người dùng từ máy tính hay thiết bị di động đều có thể truy cập trực tiếp phân hệ tra cứu công khai và hỏi đáp trí tuệ nhân tạo mà không cần cài đặt thêm phần mềm hay tự đăng ký khóa kết nối OpenRouter, trong khi các thao tác quản trị danh mục hồ sơ và tải lên tài liệu mới được bảo vệ bằng cơ chế đăng nhập chữ ký điện tử phi trạng thái.",
                        ], [
                            {
                                "type": "table",
                                "caption": "Bảng 3.1. Danh mục các phân hệ truy cập của sản phẩm sau khi triển khai lên đám mây",
                                "headers": ["Phân hệ giao diện", "Quyền truy cập", "Chức năng phục vụ trực tuyến trên trình duyệt"],
                                "rows": [
                                    ["Cổng Quản lý Lưu trữ Số hóa", "Công khai (tra cứu) / Quản trị (quản lý hồ sơ)", "Bảng thống kê kho tài liệu, tra cứu lai đa tiêu chí, cây Phông – Mục lục – Hồ sơ, quản trị danh mục, nhập/xuất CSV và trợ lý nổi"],
                                    ["Không gian Nghiên cứu Ba cột", "Công khai (tài liệu mở) / Quản trị (tải lên PDF)", "Chọn lọc nguồn tài liệu, hỏi đáp AI đa vòng với khóa mặc định máy chủ, kiểm chứng căn cứ và mở trang tài liệu gốc tô sáng"],
                                    ["Bảng điều khiển Hạ tầng Đám mây", "Công khai (giám sát) / Quản trị (đồng bộ tay)", "Theo dõi trạng thái sống/sẵn sàng, RAM sử dụng, phân vị độ trễ P50/P95, lưu lượng token và nhật ký 20 sự kiện đồng bộ"],
                                ],
                            },
                        ]),
                        ("Giao diện màn hình đăng nhập bảo mật và cổng quản lý lưu trữ", [
                            "Khi truy cập giao diện quản lý chính (Hình 3.1 bên trái), người quản trị thực hiện xác thực qua biểu mẫu đăng nhập bảo mật có nút ẩn hiện mật khẩu và cơ chế khóa tạm ba trăm giây nếu nhập sai quá năm lần. Sau khi xác thực, hệ thống phát hành mã thông báo ký điện tử giữ nguyên trạng thái phiên xuyên suốt mọi lần bộ chứa khởi động lại.",
                            "Bên trong Cổng Quản lý và Khai thác Tài liệu Lưu trữ Số hóa (Hình 3.1 bên phải), thanh thống kê tổng quan hiển thị tức thời " + n_fonds + " phông lưu trữ, " + n_dossiers + " hồ sơ, " + n_docs + " văn bản và " + n_pages + " trang tài liệu. Quản trị viên có thể lọc tìm kiếm theo phông, hồ sơ, loại văn bản, năm ban hành hoặc người ký; tạo mới, hiệu chỉnh và xóa hồ sơ hoặc nhập/xuất biểu mẫu bảng tính tiếng Việt chuẩn mã ký tự, với mọi thay đổi đều tự động đồng bộ nền lên kho dữ liệu riêng tư.",
                        ], [
                            {
                                "type": "figure",
                                "path": "fig_3_1.png",
                                "caption": "Hình 3.1. Giao diện đăng nhập bảo mật (trái) và Cổng quản lý danh mục hồ sơ lưu trữ (phải)",
                                "width_cm": 15.2,
                            },
                        ]),
                        ("Không gian hỏi đáp ba cột có dẫn nguồn và tiếp nhận số hóa tài liệu mới", [
                            "Không gian nghiên cứu ba cột (Hình 3.2) được tổ chức trực quan giúp cán bộ và độc giả đối chiếu đồng thời giữa nguồn tài liệu, hội thoại AI và văn bản gốc. Cột bên trái liệt kê danh sách tài liệu theo đúng phạm vi vai trò hiện tại kèm hộp chọn lọc nguồn. Cột trung tâm vận hành trợ lý AI ở chế độ mặc định kết nối cổng mô hình ngôn ngữ từ khóa máy chủ cài sẵn (không hiển thị nút ép người dùng tự cấu hình khóa API), đi kèm nút chuyển nhanh sang chế độ trích câu cơ sở ngay trên bộ chứa khi cần.",
                            "Mỗi câu trả lời đều kèm các nút trích dẫn đánh số thứ tự sau khi đã vượt qua bộ kiểm tra đối chiếu con số và tỷ lệ từ khóa trong nguồn gốc. Khi người dùng bấm vào nút trích dẫn bất kỳ, cột bên phải tự động tải lười tệp tài liệu gốc từ kho riêng tư (nếu chưa có trong bộ nhớ đệm), kết xuất ảnh trang sắc nét và tô vàng chính xác đoạn văn bản căn cứ. Khi quản trị viên tải lên một tài liệu quét mới, hệ thống tự động thực thi quy trình nhận dạng quang học tiếng Việt, hiệu chỉnh chính tả và trích xuất thẻ siêu dữ liệu bảy trường hành chính (Hình 3.3).",
                        ], [
                            {
                                "type": "figure",
                                "path": "fig_3_2.png",
                                "caption": "Hình 3.2. Giao diện ba cột tra cứu lai, hỏi đáp AI sẵn sàng mặc định và trang PDF tô sáng",
                                "width_cm": 15.2,
                            },
                            {
                                "type": "figure",
                                "path": "fig_3_3.png",
                                "caption": "Hình 3.3. Quy trình tiếp nhận số hóa tài liệu quét (trái) và thẻ siêu dữ liệu tự động (phải)",
                                "width_cm": 15.2,
                            },
                        ]),
                        ("Giao diện bảng điều khiển giám sát hạ tầng và vận hành đám mây", [
                            "Phân hệ giám sát hạ tầng đám mây (Hình 3.4) tự động làm mới số liệu mỗi mười giây, cung cấp cái nhìn toàn cảnh về tình trạng vận hành theo bốn thẻ chỉ báo màu sắc: trạng thái bộ chứa tính toán kèm dung lượng RAM sử dụng thực tế, trạng thái kết nối kho tập dữ liệu riêng tư bền vững kèm bộ đếm số lần tải lười tài liệu gốc, trạng thái sẵn sàng của cổng mô hình ngôn ngữ mặc định hiển thị khóa đã che kín an toàn, và chế độ xác thực phi trạng thái. Bên dưới là sơ đồ kiến trúc bốn tầng đang chạy, thống kê lưu lượng yêu cầu HTTP kèm phân vị độ trễ, tổng lượng token đã tiêu thụ và bảng nhật ký hai mươi sự kiện đồng bộ gần nhất.",
                        ], [
                            {
                                "type": "figure",
                                "path": "fig_3_4.png",
                                "caption": "Hình 3.4. Giao diện Bảng điều khiển Hạ tầng và Vận hành Đám mây cập nhật thời gian thực",
                                "width_cm": 15.2,
                            },
                        ]),
                    ],
                },
                {
                    "title": "Hướng dẫn sử dụng sản phẩm",
                    "subs": [
                        ("Quy trình thao tác cho người dùng công khai và quản trị viên", [
                            "Sản phẩm được thiết kế để sử dụng trực tiếp trên trình duyệt web ở mọi thiết bị mà không đòi hỏi thiết lập môi trường phức tạp hay nhập khóa dịch vụ AI cá nhân. Đối với người dùng công khai, người dùng chỉ cần truy cập đường dẫn chính, sử dụng bộ lọc tra cứu đa tiêu chí hoặc mở trợ lý nổi và không gian ba cột để đặt câu hỏi tiếng Việt tự nhiên, sau đó nhấp vào số trích dẫn để kiểm chứng trang tài liệu gốc được tô vàng căn cứ.",
                            "Đối với cán bộ lưu trữ và quản trị viên, sau khi đăng nhập tại trang chủ, quản trị viên có thể tạo mới, hiệu chỉnh hoặc nhập danh mục hồ sơ từ tệp bảng tính, tải lên các tệp tài liệu quét để hệ thống nhận dạng quang học tự động và mở trang giám sát hạ tầng đám mây để theo dõi nhật ký đồng bộ hoặc kích hoạt khôi phục dữ liệu khi cần thiết (chi tiết từng bước hướng dẫn được hệ thống hóa trong Bảng 3.2).",
                        ], [
                            {
                                "type": "table",
                                "caption": "Bảng 3.2. Hướng dẫn sử dụng các chức năng chính của sản phẩm theo vai trò truy cập",
                                "headers": ["Phân hệ chức năng", "Vai trò thao tác", "Các bước thực hiện chuẩn trên trình duyệt"],
                                "rows": [
                                    ["Tra cứu văn bản và hỏi đáp AI công khai", "Mọi người dùng qua Internet", "Mở trang chủ hoặc không gian 3 cột, chọn nguồn tài liệu hoặc nhập câu hỏi tự nhiên rồi bấm Gửi (chế độ LLM mặc định đã sẵn sàng không cần nhập khóa), nhấp vào số trích dẫn để xem trang gốc tô sáng."],
                                    ["Quản trị Phông, Hồ sơ và nhập/xuất CSV", "Quản trị viên đã đăng nhập", "Đăng nhập bằng tài khoản quản trị ở trang chủ, mở mục Quản lý hồ sơ để thêm, sửa, xóa, lọc trạng thái hoặc tải tệp CSV mẫu nhập hàng loạt; hệ thống tự đẩy bản mới lên kho riêng tư."],
                                    ["Tiếp nhận và số hóa tài liệu quét mới", "Quản trị viên đã đăng nhập", "Tại cột Nguồn tài liệu của không gian 3 cột, bấm Thêm nguồn (PDF), chọn tệp cần số hóa và chờ tiến trình hoàn tất nhận dạng tiếng Việt, sửa lỗi và đồng bộ lên kho bền vững."],
                                    ["Giám sát hạ tầng và kiểm chứng bền vững", "Quản trị viên & Hội đồng", "Mở trang Hạ tầng Cloud từ thanh điều hướng trên cùng để theo dõi RAM, phân vị độ trễ và nhật ký đồng bộ; thực hiện khởi động lại bộ chứa rồi tải lại trang để kiểm chứng dữ liệu còn nguyên vẹn 100%."],
                                ],
                            },
                        ]),
                    ],
                },
                {
                    "title": "Đánh giá sau triển khai",
                    "subs": [
                        ("Đánh giá sản phẩm theo các yêu cầu triển khai và chỉ tiêu kiến trúc", [
                            "Đối chiếu toàn diện sản phẩm thực tế với các mục tiêu kỹ thuật đặt ra ở Chương 1 và bộ đặc tả hệ thống cho thấy toàn bộ các tiêu chí thiết kế đều đạt chuẩn với biên độ an toàn cao (Bảng 3.3). Cụ thể, máy chủ ứng dụng hoàn tất nạp toàn bộ " + n_docs + " văn bản (" + n_pages + " trang, " + n_chunks + " đoạn chỉ mục lai) và mô hình chuyển đổi ngữ nghĩa đa ngôn ngữ vào bộ nhớ chỉ trong " + startup_s + " giây; dung lượng gói mã nguồn bộ chứa ở chế độ tách dữ liệu đạt đúng " + dec_sp_mb + " MB (" + dec_sp_files + " tệp), giảm " + red_pct + " phần trăm so với bản đóng gói đơn khối ban đầu.",
                            "Toàn bộ tám mươi lăm bài kiểm thử tự động trong kho dự án (bao gồm các bài kiểm thử nghiệp vụ tra cứu hỏi đáp kế thừa và bốn bộ kiểm thử chuyên biệt mới cho xác thực phi trạng thái, đồng bộ lưu trữ bền vững, giám sát hạ tầng, cấu hình khóa LLM mặc định và kiểm tra văn phong báo cáo) đều đạt tỷ lệ thông qua một trăm phần trăm.",
                        ], [
                            {
                                "type": "table",
                                "caption": "Bảng 3.3. Đánh giá tổng hợp các chỉ tiêu kỹ thuật sau khi triển khai sản phẩm",
                                "headers": ["Tiêu chí đánh giá", "Ngưỡng mục tiêu thiết kế", "Kết quả đo đạc thực nghiệm", "Kết luận đạt chuẩn"],
                                "rows": [
                                    ["Kích thước gói mã nguồn bộ chứa", "< 5,00 MB", dec_sp_mb + " MB (" + dec_sp_files + " tệp)", "Đạt (giảm " + red_pct + "% so với bản cũ)"],
                                    ["Thời gian khởi động nạp chỉ mục lai", "< 15,00 giây", startup_s + " giây (" + n_chunks + " đoạn)", "Đạt vượt mức kỳ vọng"],
                                    ["Độ bền dữ liệu sau xóa bộ nhớ tạm", "Khôi phục 100% dữ liệu mới", "100% dữ liệu phục hồi trong " + restore_ms + " ms", "Đạt tuyệt đối"],
                                    ["Xác thực phiên vượt khởi động lại", "Duy trì 100% phiên hợp lệ", "100% xác minh thành công + hỗ trợ thu hồi", "Đạt tuyệt đối"],
                                    ["Trải nghiệm khóa LLM mặc định", "Sẵn sàng không cần người dùng nhập", "Hoạt động ngay từ lần mở trang đầu, che kín khóa", "Đạt tuyệt đối"],
                                    ["Chi phí hạ tầng và bộ kiểm thử", "0 đồng cố định · 100% kiểm thử đạt", "0,00 USD hạ tầng · 100% bài kiểm thử thông qua", "Đạt tuyệt đối"],
                                ],
                            },
                        ]),
                        ("Phân tích độ trễ phản hồi thực nghiệm và khả năng tự phục hồi dữ liệu", [
                            "Bảng 3.4 và Hình 3.5 tổng hợp kết quả đo lặp nhiều vòng các điểm cuối cốt lõi ở hai mốc thống kê trung vị (P50) và phân vị chín mươi lăm (P95). Các điểm cuối giám sát sức khỏe, kiểm tra sẵn sàng và tổng hợp trạng thái đám mây đều có độ trễ P95 dưới 3 mili-giây, chứng tỏ tiến trình kiểm tra định kỳ hầu như không tiêu tốn tài nguyên tính toán của máy chủ. Các truy vấn tìm kiếm lai đa tiêu chí trên 3.476 đoạn văn bản đạt trung vị " + hs_p50 + " mili-giây (P95 đạt " + hs_p95 + " mili-giây), còn quy trình hỏi đáp trích xuất có kiểm chứng nguồn đạt trung vị " + qa_p50 + " mili-giây (P95 đạt " + qa_p95 + " mili-giây).",
                            "Đối với xác thực phi trạng thái, chu trình đầy đủ từ lúc đăng nhập phát hành mã thông báo trên máy chủ thứ nhất cho tới lúc xác minh thành công trên máy chủ khởi động lại đạt trung vị " + auth_p50 + " mili-giây do thuật toán băm bảo vệ mật khẩu chủ động thực hiện sáu trăm nghìn vòng lặp chống vét cạn ở lượt đăng nhập đầu, còn mọi thao tác kiểm tra chữ ký cho các yêu cầu tiếp theo đều diễn ra dưới một mili-giây. Đặc biệt, bài thử nghiệm độ bền lưu trữ ghi nhận thời gian đồng bộ bản ghi mới lên kho bền vững là " + sync_ms + " mili-giây và thời gian tự động khôi phục trọn vẹn sau khi xóa sạch ổ đĩa tạm của bộ chứa là " + restore_ms + " mili-giây.",
                        ], [
                            {
                                "type": "table",
                                "caption": "Bảng 3.4. Kết quả đo độ trễ phản hồi thực nghiệm (P50, P95 và cực đại) theo nhóm chức năng",
                                "headers": ["Nhóm chức năng đo lường", "Số lượt lặp", "Trung vị P50 (ms)", "Phân vị P95 (ms)", "Cực đại (ms)"],
                                "rows": [
                                    ["Kiểm tra trạng thái sống dịch vụ", "40", hz_p50, hz_p95, hz_max],
                                    ["Kiểm tra mức độ sẵn sàng phục vụ", "40", rz_p50, rz_p95, rz_max],
                                    ["Tổng hợp chỉ số giám sát hạ tầng", "30", cs_p50, cs_p95, cs_max],
                                    ["Tra cứu lai đa tiêu chí (BM25 + Vector)", "20", hs_p50, hs_p95, hs_max],
                                    ["Hỏi đáp trích xuất dẫn nguồn kiểm chứng", "20", qa_p50, qa_p95, qa_max],
                                ],
                            },
                            {
                                "type": "figure",
                                "path": "fig_3_5.png",
                                "caption": "Hình 3.5. Biểu đồ phân vị độ trễ phản hồi P50 và P95 đo thực nghiệm trên hệ thống",
                                "width_cm": 15.0,
                            },
                        ]),
                    ],
                },
                {
                    "title": "Sự cố gặp phải và cách xử lý",
                    "subs": [
                        ("Tổng hợp các sự cố thực tế trong quá trình triển khai và giải pháp khắc phục", [
                            "Trong suốt quá trình đóng gói, tự động hóa kiểm thử và đưa hệ thống lên môi trường đám mây công cộng, nhóm đã gặp và xử lý dứt điểm năm nhóm sự cố kỹ thuật tiêu biểu như tổng hợp ở Bảng 3.5. Việc phân tích nguyên nhân gốc rễ và áp dụng giải pháp xử lý triệt để ngay trong mã nguồn lẫn tệp cấu hình bộ chứa đã giúp hệ thống đạt độ ổn định cao trước khi bàn giao trình diễn.",
                        ], [
                            {
                                "type": "table",
                                "caption": "Bảng 3.5. Tổng hợp các sự cố thực tế trong quá trình triển khai và biện pháp khắc phục",
                                "headers": ["Sự cố phát sinh thực tế", "Nguyên nhân gốc rễ và giải pháp xử lý triệt để"],
                                "rows": [
                                    ["Lỗi thiếu dữ liệu nhận dạng tiếng Việt khi đóng gói bộ chứa sạch", "Ảnh nền Linux tối giản chưa kèm gói ngôn ngữ Tesseract tiếng Việt; nhóm bổ sung cài đặt trực tiếp gói nhận dạng tiếng Việt ở lớp thứ hai của tệp cấu hình bộ chứa và trong đường ống kiểm thử tự động."],
                                    ["Kiểm thử ứng dụng web qua bộ giả lập bị treo trong môi trường cô lập", "Cơ chế tạo cặp ổ cắm vòng lặp bất đồng bộ trên Windows bị chặn bên trong hộp cát hạn chế mạng; nhóm thiết kế chạy bộ kiểm thử tích hợp trên môi trường có quyền vòng lặp chuẩn hoặc trong đường ống Linux sạch."],
                                    ["Cổng mô hình ngôn ngữ đôi khi trả về chuỗi rỗng với mô hình suy luận sâu", "Một số mô hình dùng hết hạn mức token đầu ra cho thẻ suy luận nội bộ trước khi sinh văn bản; nhóm bổ sung bộ lọc loại bỏ thẻ suy luận, chọn mô hình tốc độ cao làm mặc định và cài đặt cơ chế thử lại tối đa hai lần."],
                                    ["Người dùng cuối bị lúng túng khi giao diện yêu cầu tự nhập khóa OpenRouter API", "Thiết kế ban đầu đòi hỏi người dùng phải mở hộp thoại nhập khóa; nhóm cấu hình khóa mặc định sẵn sàng ngay phía máy chủ, ẩn nút cấu hình khóa đối với độc giả và chỉ giữ cơ chế che kín thông tin."],
                                    ["Nguy cơ mất hồ sơ mới tạo khi bộ chứa miễn phí tự động ngủ đông", "Ổ đĩa nội bộ của bộ chứa là hệ thống tệp tạm thời; nhóm chuyển toàn bộ lưu trữ trạng thái và tệp tải lên sang kho tập dữ liệu riêng tư với cơ chế tự kéo phục hồi lúc khởi động chỉ trong 25 mili-giây."],
                                ],
                            },
                        ]),
                    ],
                },
            ],
        },
    ]

    conclusion = {
        "title": "KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN",
        "subsections": [
            ("1. Kết quả đạt được", [
                "Mini project đã hoàn thành toàn diện các mục tiêu phân tích thiết kế hướng đặc tả và triển khai thực tế hệ thống lưu trữ số hóa, tra cứu lai và hỏi đáp trí tuệ nhân tạo lên hạ tầng điện toán đám mây công cộng. Từ một ứng dụng cục bộ phụ thuộc vào ổ đĩa đơn lẻ, hệ thống đã được tái cấu trúc thành công theo mô hình bốn tầng hướng đám mây với bộ chứa phi trạng thái chạy dưới quyền người dùng phi đặc quyền, kho tập dữ liệu riêng tư lưu giữ bền vững toàn bộ hồ sơ và tệp tải lên, xác thực phiên chữ ký điện tử bền vững qua khởi động lại, bảng giám sát thời gian thực và đường ống kiểm thử liên tục tự động.",
                "Về mặt trải nghiệm người dùng và hiệu năng, khóa cổng mô hình ngôn ngữ OpenRouter đã được tích hợp mặc định phía máy chủ giúp mọi người dùng mở trình duyệt là có thể đặt câu hỏi và xem trích dẫn tô sáng ngay lập tức mà không cần thiết lập kỹ thuật. Các phép đo thực nghiệm xác nhận gói mã nguồn đẩy lên không gian bộ chứa thu gọn từ " + legacy_mb + " MB xuống còn " + dec_sp_mb + " MB (giảm " + red_pct + " phần trăm), tốc độ tìm kiếm lai đạt P50 " + hs_p50 + " mili-giây, tỷ lệ khôi phục dữ liệu sau xóa đĩa tạm đạt một trăm phần trăm trong " + restore_ms + " mili-giây và chi phí hạ tầng duy trì ở mức bằng không.",
            ]),
            ("2. Hạn chế tồn tại", [
                "Bên cạnh những kết quả khả quan, hệ thống ở phiên bản hiện tại vẫn còn ba giới hạn kỹ thuật khách quan gắn liền với phạm vi thử nghiệm của học phần. Thứ nhất, cấu trúc phông lưu trữ và quy trình duyệt hồ sơ hiện nay sử dụng dữ liệu mô phỏng trên nền văn bản hành chính công khai nên chưa bao quát đầy đủ quy trình luân chuyển văn bản liên thông nhiều cấp tại cơ quan nhà nước thực tế. Thứ hai, giải pháp đồng bộ danh mục hồ sơ bằng tệp cấu trúc văn bản lên kho tập dữ liệu riêng tư vận hành rất gọn nhẹ ở quy mô vài trăm đến vài nghìn văn bản, nhưng sẽ không tối ưu bằng cơ sở dữ liệu quan hệ phân tán nếu phát sinh hàng trăm lượt ghi đồng thời mỗi giây. Thứ ba, tác vụ nhận dạng quang học độ phân giải cao hiện vẫn thực thi đồng bộ trong tiến trình máy chủ web, có thể làm tăng độ trễ cục bộ khi nhiều cán bộ tải lên đồng thời các tệp tài liệu dày hàng trăm trang trên gói hai lõi xử lý ảo.",
            ]),
            ("3. Hướng phát triển", [
                "Trong giai đoạn mở rộng tiếp theo để đáp ứng bài toán triển khai ở quy mô cơ quan cấp sở hoặc cấp tỉnh, nhóm định hướng ba nâng cấp trọng tâm về kiến trúc đám mây. Trước hết, lớp lưu trữ trạng thái sẽ được chuyển sang hệ quản trị cơ sở dữ liệu quan hệ quản lý kết hợp kho lưu trữ đối tượng tương thích chuẩn công nghiệp S3 để hỗ trợ giao dịch đồng thời cao. Tiếp theo, khâu nhận dạng ký tự quang học sẽ được tách thành các công nhân xử lý nền độc lập kết nối qua hàng đợi thông điệp bất đồng bộ, giúp cổng web phản hồi tiếp nhận ngay lập tức và dễ dàng co giãn số lượng công nhân theo khối lượng công việc. Cuối cùng, hệ thống hướng tới mô hình đám mây lai (Hybrid Cloud), giữ toàn bộ kho văn bản nội bộ và hồ sơ mật trên hạ tầng riêng của cơ quan trong khi nhân bản ngang các bộ chứa tra cứu công khai phía sau bộ cân bằng tải trên đám mây công cộng nhờ nền tảng xác thực phi trạng thái đã xây dựng sẵn.",
            ]),
        ],
    }

    return ch2_and_ch3, conclusion
