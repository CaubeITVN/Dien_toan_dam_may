"""Nội dung học thuật Phần Đầu, Mở Đầu và Chương 1 (3 Chương + Kết luận, không trích dẫn).

Tuân thủ tuyệt đối quy tắc AGENTS.md và phong cách trình bày học thuật ICTU.
"""
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


FRONT_MATTER = {
    "nhan_xet_diem": [
        ["1", "Nông Thị Hương", "", ""],
        ["2", "Lê Xuân Nhất", "", ""],
    ],
    "loi_cam_doan": [
        "Nhóm sinh viên thực hiện gồm Nông Thị Hương và Lê Xuân Nhất xin cam đoan rằng báo cáo dự án học phần Điện toán Đám mây với đề tài xây dựng và triển khai hệ thống lưu trữ tài liệu số trên nền tảng đám mây tích hợp trợ lý số hóa trí tuệ nhân tạo là kết quả nghiên cứu, phân tích thiết kế, lập trình hạ tầng và thực nghiệm nghiêm túc của nhóm dưới sự hướng dẫn của Tiến sĩ Nguyễn Đức Bình.",
        "Hệ thống đã triển khai là sản phẩm do nhóm tự thiết kế kiến trúc, lập trình và tích hợp; mọi thông số cấu hình dịch vụ, chỉ số tài nguyên, độ trễ phản hồi và kết quả khôi phục dữ liệu trình bày trong báo cáo đều được đo đạc trung thực từ hệ thống thực tế và có thể kiểm chứng lặp lại qua bộ kiểm thử tự động đi kèm. Nhóm cũng khai báo minh bạch việc sử dụng công cụ hỗ trợ kỹ thuật để rà soát văn phong học thuật và kiểm tra chéo mã nguồn, nhưng toàn bộ nội dung chuyên môn và chất lượng sản phẩm cuối cùng đều do nhóm trực tiếp kiểm định và chịu hoàn toàn trách nhiệm.",
        "Nếu phát hiện có bất kỳ sự thiếu trung thực hoặc sao chép trái quy định nào trong kết quả thực hiện, nhóm xin chịu hoàn toàn trách nhiệm trước giảng viên hướng dẫn và Khoa Công nghệ Thông tin.",
        "Thái Nguyên, ngày …… tháng …… năm 2026",
    ],
    "loi_cam_on": [
        "Trước hết, nhóm sinh viên thực hiện xin gửi lời cảm ơn chân thành và sâu sắc nhất tới Tiến sĩ Nguyễn Đức Bình, giảng viên trực tiếp giảng dạy và hướng dẫn học phần Điện toán Đám mây. Trong suốt quá trình tìm hiểu bài toán, thực hiện phân tích thiết kế hướng đặc tả, khảo sát lựa chọn dịch vụ đám mây vừa và nhỏ phù hợp, triển khai hệ thống lên hạ tầng công cộng và hoàn thiện sản phẩm, sự chỉ bảo tận tình cùng những yêu cầu chặt chẽ của Thầy về tính thực tiễn và khả năng kiểm soát chi phí đã giúp nhóm tiếp cận điện toán đám mây ở mức độ vận hành một sản phẩm hoàn chỉnh.",
        "Nhóm cũng xin trân trọng cảm ơn Ban Giám hiệu và quý Thầy, Cô Khoa Công nghệ Thông tin, Trường Đại học Công nghệ Thông tin và Truyền thông – Đại học Thái Nguyên đã xây dựng chương trình đào tạo hiện đại, tạo điều kiện thuận lợi về môi trường học tập và nghiên cứu để sinh viên rèn luyện kỹ năng phát triển hệ thống phân tán và dịch vụ đám mây.",
        "Mặc dù nhóm đã dành nhiều thời gian nghiên cứu, thử nghiệm và hoàn thiện, báo cáo khó tránh khỏi những hạn chế nhất định về phạm vi dữ liệu thử nghiệm cũng như chiều sâu tối ưu hóa ở quy mô tải lớn. Nhóm rất mong nhận được những ý kiến đóng góp quý báu từ Thầy để tiếp tục hoàn thiện hệ thống trong thời gian tới.",
        "Thái Nguyên, ngày …… tháng …… năm 2026",
    ],
    "phan_cong": [
        [
            "1",
            "Nông Thị Hương\n(Nhóm trưởng)",
            "Chủ trì lập kế hoạch, điều phối tiến độ, phân tích thiết kế hướng đặc tả (mô hình dữ liệu ba lớp, sơ đồ ca sử dụng, bảng tiêu chí lựa chọn đám mây); kiểm thử nghiệp vụ cổng lưu trữ và không gian hỏi đáp ba cột; tích hợp đường ống kiểm thử tự động và đồng chủ biên hoàn thiện báo cáo.",
            "",
        ],
        [
            "2",
            "Lê Xuân Nhất\n(Thành viên kỹ thuật)",
            "Phát triển tầng lưu trữ bền vững đa chế độ, cơ chế tải lười tài liệu gốc, nâng cấp xác thực phiên phi trạng thái và mô-đun thu thập chỉ số vận hành; xây dựng giao diện giám sát hạ tầng đám mây; đóng gói bộ chứa bảo mật, tách gói mã nguồn, thiết lập khóa mô hình ngôn ngữ mặc định và đo đạc hiệu năng.",
            "",
        ],
    ],
    "tu_viet_tat": [
        ["1", "API", "Application Programming Interface – Giao diện lập trình ứng dụng"],
        ["2", "BM25", "Best Matching 25 – Thuật toán xếp hạng văn bản xác suất theo từ khóa"],
        ["3", "CI/CD", "Continuous Integration / Continuous Deployment – Tích hợp và triển khai liên tục"],
        ["4", "CPU", "Central Processing Unit – Bộ xử lý trung tâm"],
        ["5", "CSDL", "Cơ sở dữ liệu"],
        ["6", "HMAC", "Hash-based Message Authentication Code – Mã xác thực thông điệp dựa trên hàm băm"],
        ["7", "HTTPS", "Hypertext Transfer Protocol Secure – Giao thức truyền siêu văn bản bảo mật"],
        ["8", "IaaS", "Infrastructure as a Service – Hạ tầng dưới dạng dịch vụ"],
        ["9", "LLM", "Large Language Model – Mô hình ngôn ngữ lớn"],
        ["10", "OCR", "Optical Character Recognition – Nhận dạng ký tự quang học"],
        ["11", "PaaS", "Platform as a Service – Nền tảng dưới dạng dịch vụ"],
        ["12", "PDF", "Portable Document Format – Định dạng tài liệu di động"],
        ["13", "RAG", "Retrieval-Augmented Generation – Tạo sinh tăng cường truy hồi"],
        ["14", "RAM", "Random Access Memory – Bộ nhớ truy cập ngẫu nhiên"],
        ["15", "RBAC", "Role-Based Access Control – Kiểm soát truy cập theo vai trò"],
        ["16", "RRF", "Reciprocal Rank Fusion – Thuật toán dung hợp thứ hạng nghịch đảo"],
        ["17", "SaaS", "Software as a Service – Phần mềm dưới dạng dịch vụ"],
        ["18", "SSL/TLS", "Secure Sockets Layer / Transport Layer Security – Giao thức mã hóa kết nối"],
    ],
    "mo_dau": [
        ("1. Lý do chọn đề tài", [
            "Quá trình chuyển đổi số tại các cơ quan hành chính và đơn vị sự nghiệp đang đặt ra nhu cầu cấp bách về số hóa khối tài liệu giấy lịch sử lẫn quản lý tập trung các văn bản điện tử phát sinh hằng ngày. Trong thực tế vận hành, phần lớn tài liệu quét mới dừng ở mức lưu giữ tệp rời rạc hoặc tra cứu theo tên tệp đơn thuần, khiến cán bộ chuyên môn mất nhiều thời gian rà soát thủ công khi cần tổng hợp căn cứ từ nhiều văn bản hành chính khác nhau. Việc kết hợp công nghệ nhận dạng ký tự quang học tiếng Việt với kỹ thuật tìm kiếm lai và cơ chế tạo sinh tăng cường truy hồi giúp tự động trích xuất thông tin và trả lời câu hỏi có dẫn nguồn xác thực tới từng trang văn bản.",
            "Tuy nhiên, nếu triển khai nguyên khối một ứng dụng trí tuệ nhân tạo có trạng thái nặng lên một máy chủ cá nhân hoặc đưa nguyên trạng lên một bộ chứa đám mây miễn phí, hệ thống sẽ bộc lộ ngay những điểm nghẽn nghiêm trọng như không thể chia sẻ qua mạng Internet cho nhiều người dùng, gói triển khai quá nặng do gộp cả dữ liệu gốc, và đặc biệt là mất sạch hồ sơ mới tạo hoặc tệp tải lên mỗi khi bộ chứa trên đám mây tự động ngủ đông hay khởi động lại. Vì vậy, việc nghiên cứu phân tích thiết kế lại toàn bộ hệ thống theo kiến trúc hướng đám mây phi trạng thái, tách rời lưu trữ bền vững và cấu hình sẵn sàng dịch vụ mô hình ngôn ngữ mặc định phía máy chủ là lựa chọn giàu tính thực tiễn cho đồ án học phần Điện toán Đám mây.",
        ]),
        ("2. Mục tiêu nghiên cứu và triển khai", [
            "Mục tiêu trọng tâm của dự án là hoàn thành trọn vẹn quy trình phân tích thiết kế hướng đặc tả và triển khai thành công hệ thống lưu trữ tài liệu số tích hợp trợ lý hỏi đáp trí tuệ nhân tạo lên hạ tầng điện toán đám mây công cộng với chất lượng vận hành ổn định. Để hiện thực hóa mục tiêu này, nhóm tập trung giải quyết bốn nhóm nhiệm vụ kỹ thuật then chốt: cô lập hoàn toàn không gian phát triển của học phần Điện toán Đám mây; khảo sát và lựa chọn nhà cung cấp đám mây vừa và nhỏ có năng lực bộ nhớ phù hợp mà không phát sinh rủi ro thẻ thanh toán; thiết kế và lập trình tầng lưu trữ bền vững, cơ chế tải lười tài liệu gốc, xác thực phiên phi trạng thái cùng bảng giám sát hạ tầng thời gian thực; và cấu hình sẵn khóa mô hình ngôn ngữ mặc định phía máy chủ để người dùng cuối mở web sử dụng ngay mà không cần thao tác cài đặt kỹ thuật.",
        ]),
        ("3. Đối tượng và phạm vi thực hiện", [
            "Đối tượng nghiên cứu của đề tài là kiến trúc ứng dụng web phân tầng phục vụ quản lý lưu trữ số hóa và hỏi đáp tài liệu hành chính trên môi trường bộ chứa đám mây công cộng. Hệ thống vận hành đồng thời ba giao diện web qua giao thức bảo mật gồm cổng quản lý phông và hồ sơ lưu trữ, không gian nghiên cứu ba cột phục vụ tìm kiếm lai và hỏi đáp có tô sáng căn cứ, cùng bảng điều khiển theo dõi tài nguyên hạ tầng. Phạm vi dữ liệu thử nghiệm sử dụng bộ văn bản hành chính công khai kết hợp cấu trúc phân cấp hồ sơ mô phỏng trên bậc tài nguyên miễn phí không gắn thẻ thanh toán, đồng bộ qua kho tập dữ liệu riêng tư và không sử dụng các cụm máy chủ ảo tự quản đắt đỏ.",
        ]),
        ("4. Bố cục của báo cáo", [
            "Ngoài phần Mở đầu và phần Kết luận và hướng phát triển, nội dung báo cáo được tổ chức chặt chẽ thành ba chương chính bao quát đầy đủ bảy nội dung yêu cầu của học phần. Chương 1 trình bày tổng quan bài toán (đầu vào, đầu ra, nội hàm), phân tích thiết kế hệ thống và khảo sát lựa chọn các dịch vụ đám mây công cộng kèm giao diện quản trị sau khi đăng nhập. Chương 2 trình bày phân công công việc đồng đều trong nhóm, kế hoạch tiến độ theo phương pháp hướng đặc tả, kiến trúc triển khai, các kỹ thuật đóng gói tách dữ liệu và tám bước triển khai chi tiết lên đám mây kèm hình ảnh minh họa. Chương 3 giới thiệu sản phẩm thực tế sau triển khai, hướng dẫn sử dụng chi tiết theo từng vai trò, đánh giá kết quả đo đạc thực nghiệm và tổng hợp xử lý sự cố vận hành.",
        ]),
    ],
}


def build_chapter_1() -> dict:
    b = _load_bench()
    c = b["corpus"]
    pkg = b["packaging"]
    n_docs = _vn(c["n_docs"])
    n_pages = _vn(c["n_pages"])
    n_chunks = _vn(c["n_chunks"])
    n_fonds = _vn(c["n_fonds"])
    n_dossiers = _vn(c["n_dossiers"])
    dec_sp_mb = _vn(pkg["decoupled_space_mb"], 2)
    dec_st_mb = _vn(pkg["decoupled_storage_mb"], 2)

    return {
        "title": "TỔNG QUAN BÀI TOÁN VÀ DỊCH VỤ ĐÁM MÂY CÔNG CỘNG",
        "sections": [
            {
                "title": "Mô tả bài toán nghiên cứu",
                "subs": [
                    ("Bối cảnh nghiệp vụ lưu trữ số hóa và yêu cầu đưa lên đám mây", [
                        "Tại các cơ quan hành chính và tổ chức lưu trữ, khối lượng văn bản quy phạm pháp luật, quyết định chỉ đạo, công văn hướng dẫn và hồ sơ công việc phát sinh mỗi năm rất lớn với cấu trúc đa dạng từ văn bản điện tử sẵn lớp chữ cho tới bản sao quét hình ảnh. Trong mô hình làm việc truyền thống, cán bộ văn thư phải mở từng tệp văn bản để đọc lướt tìm điều khoản liên quan, mất nhiều công sức khi cần tổng hợp câu trả lời kết hợp thông tin từ nhiều hồ sơ khác nhau. Mặc dù kho dữ liệu thử nghiệm của hệ thống đã được chuẩn hóa gồm " + n_docs + " văn bản với " + n_pages + " trang tài liệu, phân tách thành " + n_chunks + " đoạn văn bản thuộc " + n_fonds + " phông và " + n_dossiers + " hồ sơ lưu trữ, việc chỉ vận hành sản phẩm trên một máy tính cá nhân cục bộ khiến người dùng bên ngoài không thể truy cập đồng thời và thiếu hoàn toàn khả năng sao lưu bền vững trên môi trường mạng.",
                        "Dưới góc nhìn của học phần Điện toán Đám mây, bài toán đặt ra là làm thế nào để chuyển đổi toàn diện ứng dụng xử lý tài liệu và trợ lý trí tuệ nhân tạo vốn phụ thuộc nặng nề vào đĩa cục bộ trở thành một hệ thống dịch vụ web công khai tin cậy. Khác với một trang giới thiệu tĩnh chỉ phục vụ nội dung cố định, hệ thống vừa phải nạp thư viện học sâu và mô hình chuyển đổi ngữ nghĩa đa ngôn ngữ ngay trong bộ nhớ RAM lúc khởi động, vừa phải thực hiện nhận dạng quang học tiếng Việt khi người dùng tải lên tài liệu quét mới, vừa phải giữ trọn vẹn dữ liệu hồ sơ qua những lần nền tảng miễn phí đưa bộ chứa vào trạng thái ngủ đông hoặc tái khởi tạo.",
                    ]),
                    ("Đặc tả đầu vào, đầu ra và nội hàm của bài toán", [
                        "Để định hình ranh giới xử lý rõ ràng trước khi lựa chọn dịch vụ đám mây, toàn bộ bài toán được đặc tả qua bộ dữ liệu đầu vào, kết quả đầu ra và nội hàm kỹ thuật như tổng hợp trong Bảng 1.1. Ở chiều đầu vào, người dùng cuối gửi tới hệ thống các truy vấn tìm kiếm đa chiều theo phông lưu trữ, mã hồ sơ, loại văn bản, năm ban hành, người ký hoặc đặt câu hỏi tiếng Việt tự nhiên cho trợ lý ảo mà không phải thực hiện bất kỳ thao tác thiết lập khóa API nào. Phía cán bộ quản trị cung cấp các tệp tài liệu di động bổ sung (bao gồm bản quét hình ảnh cần nhận dạng quang học), các thao tác cập nhật danh mục hồ sơ và bộ biến bí mật cấu hình tập trung ở tầng máy chủ.",
                        "Ở chiều đầu ra, hệ thống trả về thẻ siêu dữ liệu bảy trường hành chính chuẩn hóa kèm cờ kiểm định chất lượng văn bản, danh sách đoạn văn bản xếp hạng theo tìm kiếm lai có tô đậm từ khóa phù hợp, câu trả lời hỏi đáp đi kèm trích dẫn kép chỉ rõ văn bản và số trang cụ thể cùng ảnh trang gốc được tô vàng vùng căn cứ (Bảng 1.2). Đối với bài toán quản trị hạ tầng, hệ thống còn xuất ra bảng thông số vận hành thời gian thực gồm trạng thái sống, mức sẵn sàng, dung lượng bộ nhớ tiêu thụ và nhật ký đồng bộ lưu trữ bền vững. Nội hàm cốt lõi của đề tài vì thế tập trung vào giải quyết sự mâu thuẫn giữa giới hạn ổ đĩa tạm thời của bộ chứa miễn phí với yêu cầu bảo toàn dữ liệu một trăm phần trăm và tối ưu hóa gói triển khai.",
                    ], [
                        {
                            "type": "table",
                            "caption": "Bảng 1.1. Đặc tả đầu vào, đầu ra và nội hàm kỹ thuật của bài toán",
                            "headers": ["Thành phần", "Nội dung đặc tả chi tiết"],
                            "rows": [
                                ["Dữ liệu đầu vào", "Tệp tài liệu di động hành chính (bản điện tử và bản quét hình ảnh giới hạn 30 MB mỗi tệp); truy vấn lọc đa tiêu chí; câu hỏi tiếng Việt tự nhiên từ người dùng cuối (không cần tự cấu hình khóa API); thao tác thêm, sửa, xóa, nhập danh mục hồ sơ và bộ biến bí mật cấu hình phía máy chủ."],
                                ["Kết quả đầu ra", "Thẻ siêu dữ liệu bảy trường hành chính; danh sách đoạn trích tìm kiếm lai kèm hồ sơ chủ quản; câu trả lời hỏi đáp có dẫn nguồn theo từng trang hoặc từ chối minh bạch khi thiếu căn cứ; hình ảnh trang tài liệu tô vàng vùng trích dẫn; bảng chỉ số sức khỏe, độ trễ và đồng bộ đám mây."],
                                ["Nội hàm bài toán", "Tách biệt tầng tính toán bộ chứa phi trạng thái khỏi tầng lưu trữ bền vững; đóng gói gọn nhẹ mã nguồn (" + dec_sp_mb + " MB) riêng biệt với kho dữ liệu (" + dec_st_mb + " MB); duy trì phiên quản trị vượt qua khởi động lại bộ chứa; tích hợp sẵn khóa cổng mô hình ngôn ngữ mặc định phía máy chủ với chi phí hạ tầng bằng không."],
                            ],
                        },
                        {
                            "type": "table",
                            "caption": "Bảng 1.2. Minh họa quy trình phân định quyền tiếp cận và kiểm chứng căn cứ câu trả lời",
                            "headers": ["Tình huống truy vấn", "Vai trò phiên", "Hành vi xử lý và kết quả đầu ra mong đợi"],
                            "rows": [
                                ["Hỏi về nội dung Nghị định hoặc Thông tư thuộc hồ sơ Công khai", "Độc giả công khai", "Hệ thống tìm kiếm lai trên tập Công khai, kiểm tra đủ căn cứ rồi gọi cổng mô hình ngôn ngữ mặc định diễn đạt câu trả lời kèm nút trích dẫn đánh số thứ tự, cho phép nhấp mở trang tài liệu tô sáng."],
                                ["Hỏi về số liệu trong hồ sơ gắn nhãn Nội bộ khi chưa đăng nhập", "Độc giả công khai", "Bộ lọc phân quyền loại bỏ tài liệu Nội bộ trước bước xếp hạng; cổng từ chối an toàn trả về thông báo không đủ căn cứ trong phạm vi công khai, tuyệt đối không rò rỉ dữ liệu."],
                                ["Đặt câu hỏi nằm ngoài hoàn toàn kho văn bản hành chính của tỉnh", "Quản trị viên", "Độ phủ từ khóa và điểm ngữ nghĩa thấp hơn ngưỡng an toàn nên hệ thống từ chối ngay tại bộ chứa, không gửi yêu cầu thừa sang cổng mô hình ngôn ngữ bên ngoài."],
                            ],
                        },
                    ]),
                ],
            },
            {
                "title": "Phân tích và thiết kế hệ thống",
                "subs": [
                    ("Tác nhân, phân quyền tiếp cận và nhóm chức năng cốt lõi", [
                        "Hệ thống được thiết kế phục vụ đồng thời ba nhóm tác nhân chính thông qua cơ chế kiểm soát truy cập theo vai trò kết hợp chế độ sử dụng của từng hồ sơ lưu trữ như thể hiện trên sơ đồ ca sử dụng tại Hình 1.1 và đặc tả giao diện dịch vụ tại Bảng 1.3. Nhóm tác nhân thứ nhất là Người dùng công khai (độc giả truy cập qua Internet) được phép tra cứu đa tiêu chí, hỏi đáp với trợ lý trí tuệ nhân tạo mặc định sẵn sàng ngay khi mở trang, xem ảnh trang và tải tài liệu gốc thuộc nhóm công khai. Nhóm tác nhân thứ hai là Cán bộ lưu trữ và Quản trị viên (đăng nhập bảo mật) có toàn quyền tạo lập, chỉnh sửa, nhập xuất danh mục hồ sơ chuẩn tiếng Việt, tải lên số hóa tài liệu quét mới và kích hoạt đồng bộ kho lưu trữ bền vững.",
                        "Nhóm tác nhân thứ ba là Hệ thống giám sát hạ tầng đám mây tự động truy cập các điểm cuối kiểm tra trạng thái sống và mức sẵn sàng mà không làm lộ bất kỳ thông tin nghiệp vụ hay khóa bí mật nào. Nguyên tắc thiết kế bảo mật nhất quán là vai trò của mỗi yêu cầu gửi về máy chủ luôn được xác định lại từ chữ ký số của mã thông báo phiên trên đường truyền, kiên quyết bác bỏ mọi giả mạo vai trò từ phía trình duyệt.",
                    ], [
                        {
                            "type": "table",
                            "caption": "Bảng 1.3. Tổng hợp các tác nhân, nhóm chức năng và giao diện dịch vụ của hệ thống",
                            "headers": ["Tác nhân", "Nhóm chức năng chính", "Cơ chế kiểm soát và giao tiếp tầng máy chủ"],
                            "rows": [
                                ["Người dùng công khai", "Tra cứu lai đa tiêu chí; hỏi đáp trợ lý AI mặc định có dẫn nguồn; xem ảnh trang tô sáng và tải tài liệu công khai", "Mặc định truy cập mở trên các hồ sơ Công khai; không yêu cầu đăng nhập hay nhập khóa API cá nhân"],
                                ["Cán bộ / Quản trị viên", "Đăng nhập bảo mật; thêm, sửa, xóa, nhập/xuất CSV hồ sơ; tải lên PDF kèm OCR tiếng Việt; xem chi tiết hồ sơ Nội bộ; kích hoạt đồng bộ đám mây", "Yêu cầu mã thông báo phiên ký HMAC-SHA256 hợp lệ; khóa tạm tài khoản 300 giây nếu nhập sai quá 5 lần"],
                                ["Hệ thống giám sát", "Kiểm tra trạng thái sống định kỳ, trạng thái sẵn sàng nạp chỉ mục và thu thập ảnh chụp tài nguyên thời gian thực", "Điểm cuối công khai chỉ trả về chỉ số kỹ thuật tổng hợp, che kín tuyệt đối giá trị khóa bí mật"],
                            ],
                        },
                        {
                            "type": "figure",
                            "path": "fig_1_1.png",
                            "caption": "Hình 1.1. Sơ đồ ca sử dụng tổng quát của hệ thống lưu trữ số hóa trên đám mây",
                            "width_cm": 14.5,
                        },
                    ]),
                    ("Luồng xử lý tuần tự một câu hỏi hỏi đáp có dẫn nguồn", [
                        "Hình 1.2 mô tả trình tự tương tác giữa bốn thành phần từ lúc người dùng gửi câu hỏi tiếng Việt trên trình duyệt cho tới khi nhận được câu trả lời kèm hình ảnh trang văn bản gốc được tô sáng. Ngay khi tiếp nhận câu hỏi, máy chủ bộ chứa thực thi đồng thời bộ lọc phân quyền theo vai trò phiên và thuật toán tìm kiếm lai kết hợp ba nguồn điểm: khớp từ khóa xác suất, trọng số tần suất nghịch đảo và độ tương đồng ngữ nghĩa đa ngôn ngữ. Kết quả được dung hợp bằng thuật toán xếp hạng nghịch đảo để chọn ra những đoạn văn bản giàu thông tin nhất.",
                        "Trước khi gọi dịch vụ mô hình ngôn ngữ bên ngoài, bộ kiểm soát ngưỡng từ chối đánh giá mức độ liên quan giữa câu hỏi và các đoạn trích thu được. Nếu dữ liệu đạt ngưỡng tin cậy, máy chủ tự động đính kèm khóa mô hình ngôn ngữ mặc định lưu sẵn trong môi trường máy chủ và gửi tối đa năm đoạn trích lên cổng suy luận, sau đó kiểm tra từng câu sinh ra về tính chính xác của mọi con số và tỷ lệ từ khóa gốc. Cuối cùng, khi người dùng nhấp chuột vào bất kỳ số trích dẫn nào, máy chủ kiểm tra bộ nhớ đệm; nếu tệp tài liệu gốc chưa có trên đĩa tạm, cơ chế tải lười sẽ kéo tệp từ kho lưu trữ riêng tư để kết xuất ảnh trang tô vàng vùng căn cứ.",
                    ], [
                        {
                            "type": "figure",
                            "path": "fig_1_2.png",
                            "caption": "Hình 1.2. Sơ đồ tuần tự quy trình xử lý hỏi đáp dẫn nguồn và tải lười trang tài liệu",
                            "width_cm": 15.0,
                        },
                    ]),
                    ("Thiết kế phân tầng lưu trữ dữ liệu ba lớp và xác thực phi trạng thái", [
                        "Để loại bỏ hoàn toàn nguy cơ mất dữ liệu khi bộ chứa ngủ đông hoặc bị nền tảng đám mây tái khởi tạo mới, toàn bộ dữ liệu và trạng thái của hệ thống được tổ chức theo mô hình ba lớp như trình bày ở Hình 1.3 và chi tiết đồng bộ ở Bảng 1.4. Lớp thứ nhất là ảnh bộ chứa bất biến chỉ giữ mã nguồn ứng dụng, môi trường thực thi Python, bộ nhận dạng quang học tiếng Việt và trọng số mô hình chuyển đổi ngữ nghĩa nhằm bảo đảm tốc độ khởi động chỉ khoảng vài giây. Lớp thứ hai là bộ nhớ đệm làm việc tạm thời phục vụ truy xuất chỉ mục tốc độ cao và kết xuất ảnh trang gần nhất.",
                        "Lớp thứ ba là kho lưu trữ đối tượng bền vững đặt tách rời hoàn toàn ở chế độ riêng tư bên ngoài bộ chứa, lưu giữ năm nhánh tài nguyên gồm cây cấu trúc hồ sơ, dữ liệu văn bản sạch, mô hình phụ trợ nhẹ, bộ nhớ đệm nhận dạng quang học và kho tệp tài liệu gốc. Song song với dữ liệu, phiên đăng nhập quản trị được bảo đảm bằng mã thông báo chữ ký điện tử ba phần có thời hạn hai mươi bốn giờ dẫn xuất từ khóa bí mật của máy chủ, giúp người dùng giữ nguyên trạng thái đã đăng nhập xuyên suốt mọi lần bộ chứa khởi động lại mà không cần cơ sở dữ liệu phiên riêng.",
                    ], [
                        {
                            "type": "figure",
                            "path": "fig_1_3.png",
                            "caption": "Hình 1.3. Thiết kế mô hình phân tầng dữ liệu ba lớp bảo đảm tính bền vững trên đám mây",
                            "width_cm": 14.8,
                        },
                        {
                            "type": "table",
                            "caption": "Bảng 1.4. Các nhóm thực thể dữ liệu cốt lõi và cơ chế đồng bộ với kho bền vững",
                            "headers": ["Nhóm thực thể dữ liệu", "Thành phần lưu giữ chính", "Cơ chế đồng bộ giữa bộ chứa và kho riêng tư"],
                            "rows": [
                                ["Cấu trúc Phông và Hồ sơ", "Mã hồ sơ, số mục lục, tiêu đề, thời hạn bảo quản, chế độ sử dụng, vị trí kho và danh sách mã văn bản", "Ghi nguyên tử và tự động đẩy đồng bộ nền ngay sau mọi thao tác thêm, sửa, xóa hoặc nhập hàng loạt"],
                                ["Tài liệu mới tải lên & OCR", "Tệp gốc định dạng di động, thời điểm tải lên, lớp chữ sạch và tệp kết quả nhận dạng đệm theo trang", "Đẩy trọn thư mục tài liệu mới lên kho bền vững sau khi xử lý xong OCR; xóa đồng bộ hai nơi khi hủy bỏ"],
                                ["Kho tài liệu gốc lịch sử", "110 tệp văn bản gốc đặt tên theo mã văn bản duy nhất phục vụ xem trang và tải xuống", "Không gói vào mã nguồn bộ chứa; tự động kéo tải lười từng tệp từ kho riêng tư khi người dùng mở xem trang"],
                                ["Phiên đăng nhập & Giám sát", "Mã thông báo chữ ký HMAC-SHA256 kèm danh sách thu hồi khi đăng xuất và ảnh chụp độ trễ P50/P95", "Xác minh chữ ký trực tiếp trong bộ nhớ tiến trình qua khóa bí mật môi trường; thống kê tài nguyên thời gian thực"],
                            ],
                        },
                    ]),
                ],
            },
            {
                "title": "Tổng quan về điện toán đám mây vận dụng trong đề tài",
                "subs": [
                    ("Khái niệm và năm đặc trưng cốt lõi áp dụng vào bài toán", [
                        "Theo chuẩn mực học thuật phổ biến của Viện Tiêu chuẩn và Công nghệ Quốc gia Hoa Kỳ, điện toán đám mây là mô hình cho phép truy cập thuận tiện qua mạng diện rộng, theo nhu cầu, tới một tập tài nguyên tính toán dùng chung có khả năng cấu hình linh hoạt như máy chủ, lưu trữ, ứng dụng và dịch vụ với công sức quản trị tối thiểu. Năm đặc trưng cơ bản của mô hình này gồm tự phục vụ theo nhu cầu, truy cập mạng diện rộng trên mọi thiết bị, gộp chung tài nguyên đa người thuê, khả năng co giãn nhanh và dịch vụ được đo lường minh bạch.",
                        "Trong phạm vi của mini project, năm đặc trưng đó được chuyển hóa trực tiếp thành các lợi ích vận hành cụ thể. Nhóm có thể tự khởi tạo không gian chạy bộ chứa và kho tập dữ liệu riêng tư trực tiếp trên giao diện web của nhà cung cấp chỉ trong vài phút mà không cần mua sắm máy chủ vật lý. Sản phẩm sau triển khai cho phép mọi người dùng truy cập đồng thời từ trình duyệt máy tính hoặc điện thoại thông qua kết nối mã hóa HTTPS, đồng thời mọi lượt gọi mô hình ngôn ngữ và mức tiêu thụ RAM đều được đo lường chi tiết trên bảng giám sát.",
                    ]),
                    ("Phân chia trách nhiệm theo các mô hình dịch vụ đám mây", [
                        "Trên phương diện kiến trúc, các dịch vụ điện toán đám mây được phân thành ba mô hình nền tảng gồm Hạ tầng như một dịch vụ (IaaS), Nền tảng như một dịch vụ (PaaS) và Phần mềm như một dịch vụ (SaaS), phản ánh ranh giới phân chia trách nhiệm quản trị giữa nhà cung cấp và đơn vị phát triển như minh họa tại Hình 1.4 và Bảng 1.5. Mô hình hạ tầng đòi hỏi người dùng phải tự cấu hình hệ điều hành, bản vá bảo mật, tường lửa và chứng chỉ số; ngược lại, mô hình phần mềm cung cấp sẵn ứng dụng đóng kín không cho phép tùy biến sâu nghiệp vụ lưu trữ.",
                        "Do bài toán đòi hỏi phải cài đặt bộ nhận dạng quang học tiếng Việt cấp hệ điều hành Linux cùng mô hình chuyển đổi ngữ nghĩa đa ngôn ngữ nhưng vẫn muốn miễn trừ gánh nặng quản trị máy chủ vật lý, nhóm lựa chọn kiến trúc kết hợp giữa nền tảng bộ chứa tùy biến (PaaS) cho máy chủ ứng dụng và kho dữ liệu đối tượng, đi kèm dịch vụ phần mềm (SaaS) cho cổng suy luận mô hình ngôn ngữ lớn và đường ống kiểm thử tự động.",
                    ], [
                        {
                            "type": "table",
                            "caption": "Bảng 1.5. Đối sánh các mô hình dịch vụ đám mây và vị trí vận dụng trong đề tài",
                            "headers": ["Mô hình dịch vụ", "Nhà cung cấp quản lý", "Nhóm phát triển quản lý", "Áp dụng trong dự án"],
                            "rows": [
                                ["Hạ tầng dịch vụ (IaaS)", "Phần cứng vật lý, mạng lõi, lớp ảo hóa", "Hệ điều hành, thư viện, dữ liệu, mã ứng dụng", "Không dùng nhằm tránh chi phí thuê máy ảo và công sức vá lỗi hệ điều hành"],
                                ["Nền tảng bộ chứa (PaaS)", "Phần cứng, mạng, nhân hệ điều hành chủ, cân bằng tải và chứng chỉ HTTPS", "Tệp đóng gói bộ chứa, mã nguồn ứng dụng, cấu hình bí mật và luồng đồng bộ dữ liệu", "Không gian bộ chứa Docker kết hợp kho tập dữ liệu riêng tư"],
                                ["Phần mềm dịch vụ (SaaS)", "Toàn bộ hạ tầng, phần mềm ứng dụng và giao diện quản trị sẵn có", "Cấu hình quyền truy cập, khóa kết nối và hạn mức sử dụng dịch vụ", "Cổng mô hình ngôn ngữ OpenRouter và nền tảng kiểm thử tự động"],
                            ],
                        },
                        {
                            "type": "figure",
                            "path": "fig_1_4.png",
                            "caption": "Hình 1.4. Phân chia trách nhiệm quản lý giữa nhóm triển khai và nhà cung cấp dịch vụ",
                            "width_cm": 14.8,
                        },
                    ]),
                    ("Công nghệ bộ chứa, quản lý bí mật và hiện tượng khởi động nguội", [
                        "Để hiện thực hóa khả năng đóng gói nhất quán giữa máy tính phát triển và hạ tầng đám mây công cộng, dự án sử dụng bốn khái niệm kỹ thuật trọng tâm được tóm tắt tại Bảng 1.6. Trước hết, công nghệ bộ chứa đóng gói ứng dụng cùng toàn bộ thư viện thực thi và bộ nhận dạng tiếng Việt vào một ảnh chuẩn hóa chia sẻ nhân hệ điều hành chủ, giúp khởi tạo chỉ trong vài giây thay vì tốn nhiều gigabyte và hàng phút như máy ảo truyền thống.",
                        "Thứ hai, nguyên tắc quản lý biến môi trường và bí mật nghiêm cấm việc lưu mật khẩu quản trị, khóa truy cập kho dữ liệu hay khóa dịch vụ mô hình ngôn ngữ bên trong kho mã nguồn công khai. Thứ ba, quy trình tích hợp và triển khai liên tục tự động kích hoạt kiểm thử mỗi khi cập nhật mã nguồn. Thứ tư, hiện tượng khởi động nguội xuất hiện khi nền tảng miễn phí đưa bộ chứa vào trạng thái ngủ đông để tiết kiệm năng lượng nếu lâu không có lưu lượng truy cập; giải pháp nạp sẵn trọng số mô hình vào ảnh bộ chứa kết hợp khôi phục dữ liệu tự động đã rút ngắn thời gian thức dậy của hệ thống xuống mức rất thấp.",
                    ], [
                        {
                            "type": "table",
                            "caption": "Bảng 1.6. Tổng hợp các khái niệm kỹ thuật điện toán đám mây áp dụng trong dự án",
                            "headers": ["Khái niệm kỹ thuật", "Bản chất và vai trò trong vận hành thực tế", "Giải pháp áp dụng của nhóm"],
                            "rows": [
                                ["Bộ chứa ứng dụng (Container)", "Cô lập tiến trình, cổng mạng và thư viện ở tầng hệ điều hành, bảo đảm chạy đồng nhất mọi nơi", "Đóng gói ảnh nhiều lớp kèm Python tối giản, Tesseract tiếng Việt và chạy dưới người dùng phi đặc quyền"],
                                ["Biến môi trường và Bí mật", "Cơ chế tiêm giá trị nhạy cảm từ tầng hạ tầng vào bộ nhớ tiến trình lúc khởi chạy mà không ghi đĩa", "Lưu mã hóa khóa kho lưu trữ, khóa LLM mặc định và khóa ký phiên trên giao diện quản trị đám mây"],
                                ["Tích hợp & Triển khai liên tục", "Tự động kiểm chứng chất lượng phần mềm và đồng bộ bản cập nhật an toàn lên môi trường chạy", "Kiểm tra toàn bộ 85 bài kiểm thử và rà soát dung lượng gói tách dữ liệu trước khi cập nhật bộ chứa"],
                                ["Khởi động nguội & Đĩa tạm", "Tài nguyên miễn phí giải phóng RAM và ổ đĩa cục bộ của bộ chứa sau chu kỳ không hoạt động", "Lưu toàn bộ trạng thái phát sinh ở kho riêng tư tách rời; tự động phục hồi chỉ trong khoảng 25 mili-giây"],
                            ],
                        },
                    ]),
                ],
            },
            {
                "title": "Lựa chọn dịch vụ đám mây công cộng",
                "subs": [
                    ("Tiêu chí lựa chọn và đối sánh định lượng các nền tảng vừa và nhỏ", [
                        "Theo định hướng chuyên môn của học phần là ưu tiên các nhà cung cấp dịch vụ đám mây vừa và nhỏ có chính sách dùng thử miễn phí minh bạch và kiểm soát chặt chẽ rủi ro phát sinh cước phí khi gắn thẻ ngân hàng, nhóm xây dựng bộ tiêu chí sàng lọc gắn liền với hồ sơ tiêu thụ tài nguyên của ứng dụng trí tuệ nhân tạo. Về kỹ thuật, nền tảng tính toán miễn phí bắt buộc phải cấp tối thiểu hai gigabyte RAM trở lên để nạp được thư viện tính toán tensor cho bộ xử lý trung tâm và mô hình chuyển đổi ngữ nghĩa đa ngôn ngữ, hỗ trợ bộ chứa tùy biến để cài đặt gói nhận dạng tiếng Việt, đồng thời có giải pháp lưu trữ riêng tư bền vững đi kèm.",
                        "Nhóm tiến hành khảo sát và đối sánh năm nền tảng phổ biến gồm Hugging Face Spaces, Render, Railway, Fly và Google Cloud Run như trình bày ở Bảng 1.7 và Hình 1.5. Kết quả cho thấy các gói miễn phí của Render (512 MB RAM) và Fly (256 MB RAM) đều gặp lỗi tràn bộ nhớ ngay khi nạp mô hình ngữ nghĩa; Railway chỉ cho dùng thử năm đô la trong ba mươi ngày đầu; Google Cloud Run tuy đáp ứng năng lực tính toán nhưng yêu cầu bắt buộc kích hoạt tài khoản thanh toán quốc tế gắn thẻ ngân hàng và tự thiết lập thêm nhiều dịch vụ lưu trữ tính phí riêng.",
                    ], [
                        {
                            "type": "table",
                            "caption": "Bảng 1.7. Đối sánh năng lực tài nguyên và ràng buộc thanh toán giữa năm nền tảng khảo sát",
                            "headers": ["Nền tảng khảo sát", "Tài nguyên miễn phí / dùng thử", "Đáp ứng PyTorch & OCR", "Yêu cầu thẻ ngân hàng", "Kho bền vững đi kèm"],
                            "rows": [
                                ["Hugging Face Spaces (Chọn)", "2 vCPU, 16 GB RAM, 50 GB đĩa tạm", "Đáp ứng dư dả (~1,5 GB dùng)", "Không bắt buộc thẻ", "Kho tập dữ liệu riêng tư miễn phí"],
                                ["Render (Gói miễn phí)", "0,1 vCPU, 512 MB RAM", "Không đạt (tràn bộ nhớ)", "Không bắt buộc", "Không có ổ đĩa bền vững miễn phí"],
                                ["Railway (Gói dùng thử)", "Tín dụng 5 USD giới hạn 30 ngày", "Đạt nhưng nhanh hết hạn", "Phải nâng cấp sau trial", "Tính phí theo dung lượng sử dụng"],
                                ["Fly (Gói cơ bản)", "Tối đa 256 MB RAM / máy ảo", "Không đạt (tràn bộ nhớ)", "Bắt buộc xác minh thẻ", "Tính phí nếu vượt mức nhỏ"],
                                ["Google Cloud Run", "Tối đa 4 GB RAM theo lượt gọi", "Đạt nếu gắn dịch vụ phụ", "Bắt buộc tài khoản thanh toán", "Phải gắn Cloud Storage tính phí"],
                            ],
                        },
                        {
                            "type": "figure",
                            "path": "fig_1_5.png",
                            "caption": "Hình 1.5. Đối sánh bộ nhớ RAM tối đa ở bậc dùng thử giữa năm nền tảng đám mây công cộng",
                            "width_cm": 14.5,
                        },
                    ]),
                    ("Tổ hợp bốn dịch vụ đám mây được lựa chọn", [
                        "Từ kết quả đối sánh định lượng trên, nhóm lựa chọn tổ hợp bốn dịch vụ đám mây vừa và nhỏ phối hợp theo đúng vai trò chuyên biệt trong kiến trúc hệ thống (Bảng 1.8). Không gian bộ chứa Docker trên Hugging Face Spaces đảm nhiệm tầng tính toán máy chủ web với nguồn lực vượt trội hai lõi xử lý ảo và mười sáu gigabyte RAM hoàn toàn miễn phí. Kho tập dữ liệu ở chế độ riêng tư trên Hugging Face Hub đóng vai trò tầng lưu trữ đối tượng bền vững giúp tách rời toàn bộ văn bản gốc, hồ sơ lưu trữ và bộ nhớ đệm nhận dạng khỏi bộ chứa.",
                        "Ở tầng trí tuệ nhân tạo tạo sinh, dịch vụ cổng mô hình ngôn ngữ OpenRouter được cấu hình mặc định phía máy chủ để sinh câu trả lời súc tích từ các đoạn trích đã lọc mà không đòi hỏi bộ chứa phải trang bị bộ xử lý đồ họa. Cuối cùng, dịch vụ GitHub Actions tự động hóa toàn bộ quá trình kiểm thử hồi quy và kiểm tra an toàn gói triển khai trước khi cập nhật lên môi trường công cộng.",
                    ], [
                        {
                            "type": "table",
                            "caption": "Bảng 1.8. Vai trò và cấu hình gói sử dụng của bốn dịch vụ đám mây được lựa chọn",
                            "headers": ["Dịch vụ đám mây", "Bậc gói và tài nguyên cấp phát", "Ràng buộc thẻ", "Vai trò trong hệ thống"],
                            "rows": [
                                ["Hugging Face Spaces", "Docker SDK miễn phí: 2 vCPU, 16 GB RAM, 50 GB đĩa tạm, tự cấp HTTPS", "Không yêu cầu", "Chạy máy chủ web bất đồng bộ, tìm kiếm lai, nhận dạng quang học và phục vụ ba giao diện"],
                                ["Hugging Face Hub Dataset", "Kho tập dữ liệu riêng tư miễn phí có quản lý lịch sử phiên bản", "Không yêu cầu", "Lưu giữ bền vững danh mục hồ sơ, tài liệu tải lên, kết quả OCR và kho tài liệu gốc"],
                                ["OpenRouter Cloud API", "Khóa mặc định tích hợp sẵn phía máy chủ, hỗ trợ cả mô hình miễn phí và chi phí cực thấp", "Kiểm soát hạn mức nhỏ", "Cổng suy luận mô hình ngôn ngữ lớn cho chức năng hỏi đáp và tóm tắt có trích dẫn"],
                                ["GitHub Actions", "2.000 phút chạy mỗi tháng trên môi trường Linux sạch miễn phí", "Không yêu cầu", "Chạy bộ kiểm thử tự động, kiểm tra đóng gói tách dữ liệu và kích hoạt triển khai liên tục"],
                            ],
                        },
                    ]),
                    ("Luận giải tính hợp lý của lựa chọn với yêu cầu bài toán", [
                        "Bảng 1.9 tổng hợp mức độ đáp ứng của tổ hợp bốn dịch vụ đối với từng ràng buộc kỹ thuật và tài chính của đồ án. Việc cấp phát sẵn mười sáu gigabyte RAM miễn phí tạo ra biên độ an toàn gấp mười lần mức tiêu thụ tĩnh của tiến trình máy chủ, loại bỏ hoàn toàn rủi ro treo ứng dụng khi vừa phục vụ nhiều phiên truy vấn tìm kiếm lai vừa thực hiện nhận dạng quang học độ phân giải cao. Đồng thời, cơ chế tách rời dữ liệu sang kho riêng tư và đẩy khâu suy luận ngôn ngữ lớn ra cổng dịch vụ bên ngoài giúp chi phí vận hành hạ tầng cốt lõi giữ nguyên ở mức không đồng mà không cần liên kết thẻ tín dụng.",
                    ], [
                        {
                            "type": "table",
                            "caption": "Bảng 1.9. Đánh giá mức độ tương thích của các dịch vụ được chọn với yêu cầu bài toán",
                            "headers": ["Yêu cầu kỹ thuật / tài chính của bài toán", "Cách thức tổ hợp dịch vụ đám mây đáp ứng thực tế"],
                            "rows": [
                                ["Nạp mô hình ngữ nghĩa đa ngôn ngữ và chạy nhận dạng tiếng Việt trên cùng máy chủ", "Ảnh bộ chứa tùy biến trên không gian 16 GB RAM cho phép cài trực tiếp Tesseract tiếng Việt và nạp mô hình ngữ nghĩa chỉ mất khoảng 1,5 GB RAM."],
                                ["Bảo toàn dữ liệu hồ sơ và tệp tải lên khi bộ chứa ngủ đông hoặc tái tạo", "Kho tập dữ liệu riêng tư lưu giữ phiên bản mới nhất ngoài bộ chứa và phục hồi chỉ trong 25 mili-giây khi máy chủ khởi động."],
                                ["Đưa khóa mô hình ngôn ngữ mặc định vào hệ thống để người dùng sử dụng ngay", "Khóa cổng OpenRouter được khai báo trong vùng bí mật mã hóa trên máy chủ; người dùng cuối chỉ mở trình duyệt và hỏi đáp ngay lập tức."],
                                ["Giữ gói cập nhật mã nguồn gọn nhẹ và triển khai tự động không cần thao tác tay", "Chế độ đóng gói tách dữ liệu nén phần mã nguồn xuống còn " + dec_sp_mb + " MB, tự động kiểm thử và cập nhật qua đường ống liên tục."],
                                ["Tuyệt đối không phát sinh cước phí ngoài ý muốn cho sinh viên", "Toàn bộ hạ tầng tính toán, lưu trữ riêng tư và CI/CD không yêu cầu thẻ thanh toán; cổng LLM được bảo vệ bởi cổng từ chối trước khi gọi."],
                            ],
                        },
                    ]),
                ],
            },
            {
                "title": "Giao diện và tính năng các dịch vụ sau khi đăng nhập tài khoản",
                "subs": [
                    ("Không gian quản trị bộ chứa và khu vực biến bí mật trên Hugging Face Spaces", [
                        "Sau khi đăng nhập tài khoản cá nhân trên cổng Hugging Face và mở không gian triển khai bộ chứa, người quản trị có quyền điều khiển tập trung thông qua bốn nhóm giao diện chức năng (Bảng 1.10 và Hình 1.6). Thẻ Ứng dụng hiển thị trực tiếp sản phẩm chạy dưới tên miền bảo mật HTTPS kèm huy hiệu trạng thái vòng đời (đang xây dựng ảnh, đang hoạt động hoặc đang tạm nghỉ). Cửa sổ Nhật ký tách biệt rạch ròi hai luồng thông tin là nhật ký quá trình xây dựng ảnh bộ chứa từng lớp và nhật ký thực thi của tiến trình máy chủ ứng dụng.",
                        "Tại thẻ Cài đặt, nền tảng cung cấp khu vực quản lý Biến môi trường và Bí mật được mã hóa chuyên dụng. Mọi thông số nhạy cảm như khóa truy cập kho lưu trữ, khóa cổng mô hình ngôn ngữ mặc định, mật khẩu quản trị và khóa ký phiên đều được nền tảng mã hóa lưu trữ ở tầng hạ tầng và che kín vĩnh viễn trên giao diện quản trị để bảo đảm không bị đọc ngược qua màn hình hay nhật ký vận hành. Ngoài ra, quản trị viên có thể thực hiện khởi động lại bộ chứa hoặc xây dựng lại sạch hoàn toàn từ ảnh gốc chỉ với một cú nhấp chuột để kiểm chứng khả năng phục hồi dữ liệu.",
                    ], [
                        {
                            "type": "table",
                            "caption": "Bảng 1.10. Các phân hệ giao diện và tính năng quản trị của dịch vụ chính sau khi đăng nhập",
                            "headers": ["Khu vực giao diện", "Tính năng nền tảng cung cấp", "Mục đích sử dụng trong triển khai và trình diễn"],
                            "rows": [
                                ["Thẻ Ứng dụng (App)", "Hiển thị giao diện web nhúng trực tiếp qua HTTPS cùng huy hiệu trạng thái chạy theo thời gian thực", "Kiểm thử nhanh sản phẩm, chia sẻ đường dẫn công cộng cho giảng viên và hội đồng chấm thi"],
                                ["Thẻ Tệp mã (Files)", "Duyệt cây thư mục mã nguồn bộ chứa, xem lịch sử thay đổi và kích thước từng tệp đẩy lên", "Xác nhận gói mã nguồn tách biệt siêu nhẹ dưới 1 MB và hoàn toàn sạch tệp chứa khóa bí mật"],
                                ["Cửa sổ Nhật ký (Logs)", "Theo dõi song song nhật ký dựng ảnh hệ thống và nhật ký tiến trình máy chủ web đang chạy", "Truy vết lỗi cài đặt gói tiếng Việt, đo thời gian nạp chỉ mục và quan sát thông báo đồng bộ"],
                                ["Biến & Bí mật (Settings)", "Khai báo biến cấu hình thường và biến bí mật mã hóa tiêm tự động vào môi trường tiến trình", "Cất giữ an toàn khóa kho dữ liệu, khóa LLM mặc định, khóa ký phiên và bật cờ phi trạng thái"],
                                ["Điều khiển Vòng đời", "Cung cấp nút Khởi động lại bộ chứa, Xây dựng lại từ đầu và đổi cấu hình phần cứng", "Mô phỏng trực tiếp tình huống mất ổ đĩa tạm ngay trên lớp để chứng minh khả năng tự phục hồi 100%"],
                            ],
                        },
                        {
                            "type": "figure",
                            "path": "fig_1_6.png",
                            "caption": "Hình 1.6. Giao diện tổng quan kèm cửa sổ nhật ký (trái) và khu vực biến bí mật mã hóa (phải)",
                            "width_cm": 15.2,
                        },
                    ]),
                    ("Giao diện kho tập dữ liệu riêng tư và cổng điều phối mô hình ngôn ngữ", [
                        "Đối với tầng lưu trữ bền vững trên Hugging Face Hub, trang quản lý kho tập dữ liệu sau khi đăng nhập hiển thị nổi bật huy hiệu Riêng tư ở góc trên nhằm khẳng định dữ liệu hành chính hoàn toàn cách ly khỏi tìm kiếm công cộng (Hình 1.7). Bên trong thẻ Tệp dữ liệu, quản trị viên quan sát được cấu trúc năm nhánh thư mục rõ ràng từ tệp trạng thái hồ sơ, văn bản sạch, mô hình phụ trợ nhẹ, bộ nhớ đệm nhận dạng cho tới kho tài liệu gốc phục vụ tải lười, đồng thời theo dõi được từng phiên bản đồng bộ kèm mốc thời gian tương ứng.",
                        "Trên cổng điều phối OpenRouter và trang mã nguồn GitHub (Hình 1.8), bảng điều khiển sau đăng nhập cung cấp công cụ tạo khóa riêng biệt có đặt hạn mức chi tiêu an toàn, biểu đồ theo dõi tổng lưu lượng token đã gọi theo ngày và thẻ Tự động hóa kiểm thử hiển thị dấu đạt màu xanh cho từng lượt đẩy mã nguồn mới.",
                    ], [
                        {
                            "type": "figure",
                            "path": "fig_1_7.png",
                            "caption": "Hình 1.7. Kho tập dữ liệu ở chế độ riêng tư (trái) và lịch sử phiên bản đồng bộ (phải)",
                            "width_cm": 15.2,
                        },
                        {
                            "type": "figure",
                            "path": "fig_1_8.png",
                            "caption": "Hình 1.8. Quản lý khóa mô hình ngôn ngữ đã che kín (trái) và trạng thái kiểm thử tự động (phải)",
                            "width_cm": 15.2,
                        },
                    ]),
                ],
            },
        ],
    }
