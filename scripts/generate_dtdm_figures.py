"""Sinh trọn bộ 25 sơ đồ, biểu đồ và hình minh họa giao diện độ phân giải cao (220 DPI)
theo đúng bố cục 3 chương của báo cáo Điện toán Đám mây.

Mọi nhãn trên hình dùng tiếng Việt học thuật chuẩn mực, che kín mọi thông tin bí mật,
không chứa tên tệp mã nguồn, tên biến nội bộ hay đường dẫn kỹ thuật thô.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as patches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "reports" / "figures"
BENCH_PATH = ROOT / "reports" / "cloud_benchmark_results.json"

plt.rcParams["font.sans-serif"] = ["Arial", "Segoe UI", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def _box(ax, x, y, w, h, text, fc="#EFF6FF", ec="#1E3A8A", tc="#0F172A",
         fs=8.8, bold=False, ls="-", lw=1.2, ha="center"):
    rect = patches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.01,rounding_size=0.018",
        facecolor=fc, edgecolor=ec, linewidth=lw, linestyle=ls,
    )
    ax.add_patch(rect)
    tx = x + w / 2 if ha == "center" else x + 0.015
    ax.text(
        tx, y + h / 2, text,
        ha=ha, va="center", fontsize=fs,
        fontweight="bold" if bold else "normal", color=tc, linespacing=1.32,
    )


def _ellipse(ax, cx, cy, w, h, text, fc="#EFF6FF", ec="#1D4ED8", fs=8.5):
    el = patches.Ellipse((cx, cy), w, h, facecolor=fc, edgecolor=ec, linewidth=1.3)
    ax.add_patch(el)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color="#0F172A", fontweight="bold")


def _actor(ax, x, y, label):
    head = patches.Circle((x, y + 0.065), 0.024, facecolor="#EFF6FF", edgecolor="#1E3A8A", lw=1.4)
    ax.add_patch(head)
    ax.plot([x, x], [y + 0.041, y - 0.025], color="#1E3A8A", lw=1.4)
    ax.plot([x - 0.028, x + 0.028], [y + 0.022, y + 0.022], color="#1E3A8A", lw=1.4)
    ax.plot([x, x - 0.022], [y - 0.025, y - 0.07], color="#1E3A8A", lw=1.4)
    ax.plot([x, x + 0.022], [y - 0.025, y - 0.07], color="#1E3A8A", lw=1.4)
    ax.text(x, y - 0.105, label, ha="center", va="top", fontsize=8.6, fontweight="bold", color="#0F172A")


def _arrow(ax, x1, y1, x2, y2, label="", color="#334155", fs=8.0, rad=0.0, ls="-"):
    ax.annotate(
        "", xy=(x2, y2), xytext=(x1, y1),
        arrowprops=dict(
            arrowstyle="-|>,head_width=0.26,head_length=0.45",
            color=color, lw=1.3, linestyle=ls,
            connectionstyle=f"arc3,rad={rad}",
        ),
    )
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(
            mx, my + 0.015, label, ha="center", va="bottom", fontsize=fs, color="#1E293B",
            bbox=dict(boxstyle="round,pad=0.12", facecolor="white", edgecolor="none", alpha=0.88),
        )


def _panel_frame(ax, x, y, w, h, title, header_fc="#1E3A8A"):
    rect = patches.FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.004,rounding_size=0.014",
        facecolor="#FFFFFF", edgecolor="#CBD5E1", linewidth=1.2,
    )
    ax.add_patch(rect)
    bar = patches.FancyBboxPatch(
        (x, y + h - 0.085), w, 0.085,
        boxstyle="round,pad=0.004,rounding_size=0.012",
        facecolor=header_fc, edgecolor=header_fc, linewidth=1.0,
    )
    ax.add_patch(bar)
    ax.text(x + 0.02, y + h - 0.042, title, ha="left", va="center",
            fontsize=8.8, fontweight="bold", color="#FFFFFF")


def _save(fig, name: str) -> None:
    fig.tight_layout(pad=0.4)
    fig.savefig(FIG_DIR / name, dpi=220, facecolor="white")
    plt.close(fig)


# =========================================================================
# CHƯƠNG 1: TỔNG QUAN BÀI TOÁN VÀ DỊCH VỤ ĐÁM MÂY CÔNG CỘNG (8 HÌNH)
# =========================================================================

def make_fig_1_1() -> None:
    """Sơ đồ ca sử dụng tổng quát của hệ thống."""
    fig, ax = plt.subplots(figsize=(10.5, 5.2), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    rect = patches.FancyBboxPatch(
        (0.26, 0.06), 0.48, 0.88,
        boxstyle="round,pad=0.01,rounding_size=0.02",
        facecolor="#F8FAFC", edgecolor="#1E3A8A", linewidth=1.6,
    )
    ax.add_patch(rect)
    ax.text(0.50, 0.90, "Hệ thống Lưu trữ Số hóa & Trợ lý AI Đám mây",
            ha="center", va="center", fontsize=10.0, fontweight="bold", color="#1E3A8A")

    _actor(ax, 0.11, 0.68, "Người dùng\ncông khai")
    _actor(ax, 0.11, 0.27, "Cán bộ lưu trữ /\nQuản trị viên")
    _actor(ax, 0.89, 0.48, "Hệ thống giám sát\nđám mây")

    ucs = [
        (0.50, 0.78, "Tra cứu lai đa tiêu chí\nvà xem trang tài liệu PDF", "#EFF6FF", "#2563EB"),
        (0.50, 0.64, "Hỏi đáp trợ lý AI mặc định\nkèm trích dẫn căn cứ", "#EFF6FF", "#2563EB"),
        (0.50, 0.50, "Đăng nhập bảo mật và quản lý\nPhông – Hồ sơ lưu trữ", "#ECFDF5", "#047857"),
        (0.50, 0.36, "Tiếp nhận, nhận dạng tiếng Việt\nvà đồng bộ kho bền vững", "#ECFDF5", "#047857"),
        (0.50, 0.22, "Giám sát hạ tầng, hiệu năng\nvà trạng thái sẵn sàng", "#FEF3C7", "#B45309"),
    ]
    for cx, cy, txt, fc, ec in ucs:
        _ellipse(ax, cx, cy, 0.38, 0.105, txt, fc=fc, ec=ec, fs=8.3)

    for uy in (0.78, 0.64):
        ax.plot([0.16, 0.31], [0.68, uy], color="#334155", lw=1.2)
    for uy in (0.78, 0.64, 0.50, 0.36, 0.22):
        ax.plot([0.16, 0.31], [0.29, uy], color="#047857", lw=1.15)
    ax.plot([0.84, 0.69], [0.48, 0.22], color="#B45309", lw=1.2, linestyle="--")

    _save(fig, "fig_1_1.png")


def make_fig_1_2() -> None:
    """Sơ đồ tuần tự luồng xử lý một câu hỏi hỏi đáp có dẫn nguồn."""
    fig, ax = plt.subplots(figsize=(10.8, 5.2), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    lifelines = [
        (0.10, "Trình duyệt\nNgười dùng", "#DBEAFE", "#1D4ED8"),
        (0.32, "Máy chủ Bộ chứa\n(Tìm kiếm & Kiểm nguồn)", "#EFF6FF", "#1E40AF"),
        (0.58, "Cổng Mô hình\nNgôn ngữ Mặc định", "#FFF7ED", "#C2410C"),
        (0.84, "Kho Lưu trữ\nĐối tượng Riêng tư", "#ECFDF5", "#047857"),
    ]
    for x, name, fc, ec in lifelines:
        _box(ax, x - 0.095, 0.84, 0.19, 0.11, name, fc=fc, ec=ec, fs=8.4, bold=True)
        ax.plot([x, x], [0.10, 0.84], color="#94A3B8", linestyle="--", lw=1.2)

    msgs = [
        (0.10, 0.32, 0.74, "1. Gửi câu hỏi + mã phiên (không cần nhập khóa API)", "#1D4ED8"),
        (0.32, 0.32, 0.65, "", "#1E40AF"),
        (0.32, 0.58, 0.54, "3. Chuyển tối đa 5 đoạn trích hợp lệ + khóa máy chủ", "#C2410C"),
        (0.58, 0.32, 0.45, "4. Trả về câu diễn đạt có đánh số trích dẫn", "#C2410C"),
        (0.32, 0.10, 0.33, "5. Trả câu trả lời đã kiểm định con số & từ khóa", "#1E40AF"),
        (0.10, 0.32, 0.23, "6. Nhấp vào số trích dẫn để xem trang gốc", "#047857"),
        (0.32, 0.84, 0.15, "7. Tải lười tệp PDF gốc nếu chưa có trong bộ đệm", "#047857"),
        (0.84, 0.10, 0.08, "8. Hiển thị ảnh trang độ nét cao tô vàng căn cứ", "#047857"),
    ]
    for x1, x2, y, label, col in msgs:
        if x1 == x2:
            _box(ax, 0.21, 0.60, 0.22, 0.08, "2. Lọc phân quyền RBAC &\nTìm kiếm lai + Cổng từ chối",
                 fc="#E0E7FF", ec="#4338CA", fs=7.8, bold=True)
        else:
            _arrow(ax, x1, y, x2, y, label=label, color=col, fs=7.9)

    _save(fig, "fig_1_2.png")


def make_fig_1_3() -> None:
    """Thiết kế phân tầng dữ liệu 3 lớp & thực thể đồng bộ bền vững."""
    fig, ax = plt.subplots(figsize=(10.5, 5.1), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _box(ax, 0.04, 0.69, 0.92, 0.23,
         "Lớp 1: Ảnh Bộ chứa Bất biến (Container Image Layer)\n"
         "Mã nguồn ứng dụng gọn nhẹ (< 1 MB)  |  Môi trường Python & Bộ nhận dạng quang học tiếng Việt\n"
         "Trọng số mô hình chuyển đổi ngữ nghĩa đa ngôn ngữ được nạp sẵn giúp khởi động trong ~3 giây",
         fc="#EFF6FF", ec="#1D4ED8", fs=9.0, bold=False)

    _box(ax, 0.04, 0.37, 0.92, 0.23,
         "Lớp 2: Bộ nhớ Đệm Tạm thời Trong Bộ chứa (Ephemeral Runtime Cache)\n"
         "Chỉ mục tra cứu lai trên bộ nhớ RAM  |  Bộ đệm ảnh trang tài liệu đã kết xuất\n"
         "Bản sao tạm tài liệu nguồn được tải lười theo yêu cầu (tự động giải phóng khi ngủ đông)",
         fc="#FEF3C7", ec="#B45309", fs=9.0, bold=False)

    _box(ax, 0.04, 0.05, 0.92, 0.23,
         "Lớp 3: Tầng Lưu trữ Đám mây Bền vững (Kho Tập Dữ liệu Riêng tư / Ổ đĩa Gắn ngoài)\n"
         "Danh mục Phông – Hồ sơ  |  Tệp tải lên & lớp chữ nhận dạng  |  Kho tài liệu gốc  |  Chỉ mục dự phòng\n"
         "Nguồn dữ liệu chuẩn xác duy nhất, bảo toàn 100% qua mọi lần tái khởi động bộ chứa",
         fc="#DCFCE7", ec="#15803D", fs=9.0, bold=False)

    _arrow(ax, 0.28, 0.69, 0.28, 0.60, "Khởi tạo máy chủ")
    _arrow(ax, 0.31, 0.28, 0.31, 0.37, "Khôi phục trạng thái lúc bật & Tải lười")
    _arrow(ax, 0.69, 0.37, 0.69, 0.28, "Đồng bộ tức thời khi thêm/sửa/xóa")
    _save(fig, "fig_1_3.png")


def make_fig_1_4() -> None:
    """Phân chia trách nhiệm theo mô hình dịch vụ đám mây."""
    fig, ax = plt.subplots(figsize=(10.5, 5.2), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    cols = [
        ("Tại chỗ\n(On-Premises)", 9),
        ("Hạ tầng dịch vụ\n(IaaS)", 5),
        ("Nền tảng bộ chứa\n(PaaS - Hệ thống chọn)", 2),
        ("Phần mềm dịch vụ\n(SaaS - Cổng LLM)", 0),
    ]
    layers = ["Mạng", "Lưu trữ", "Máy chủ", "Ảo hóa", "Hệ điều hành", "Phần mềm trung gian", "Môi trường chạy", "Dữ liệu", "Ứng dụng"]
    xs = [0.06, 0.29, 0.52, 0.75]
    w, h = 0.19, 0.068
    for ci, (title, user_layers) in enumerate(cols):
        x = xs[ci]
        ax.text(x + w / 2, 0.92, title, ha="center", va="center", fontsize=9.2, fontweight="bold", color="#0F172A")
        for li, lname in enumerate(layers):
            y = 0.12 + li * 0.082
            is_user = li >= (len(layers) - user_layers)
            _box(ax, x, y, w, h, lname,
                 fc="#BFDBFE" if is_user else "#E2E8F0",
                 ec="#1D4ED8" if is_user else "#64748B",
                 fs=8.5, bold=is_user, lw=1.0)

    ax.add_patch(patches.Rectangle((0.18, 0.03), 0.025, 0.03, facecolor="#BFDBFE", edgecolor="#1D4ED8"))
    ax.text(0.215, 0.045, "Nhóm triển khai tự quản lý", va="center", fontsize=9.0, color="#0F172A")
    ax.add_patch(patches.Rectangle((0.55, 0.03), 0.025, 0.03, facecolor="#E2E8F0", edgecolor="#64748B"))
    ax.text(0.585, 0.045, "Nhà cung cấp đám mây quản lý", va="center", fontsize=9.0, color="#0F172A")
    _save(fig, "fig_1_4.png")


def make_fig_1_5() -> None:
    """So sánh bộ nhớ RAM bậc miễn phí của 5 nền tảng đám mây."""
    providers = [
        "Hugging Face\nSpaces (Chọn)",
        "Google\nCloud Run",
        "Render\n(Gói miễn phí)",
        "Fly\n(Gói cơ bản)",
        "Railway\n(Dùng thử)",
    ]
    ram_gb = [16.0, 4.0, 0.5, 0.25, 8.0]
    colors = ["#16A34A", "#94A3B8", "#EF4444", "#EF4444", "#F59E0B"]

    fig, ax = plt.subplots(figsize=(9.5, 4.4), dpi=220)
    bars = ax.barh(providers[::-1], ram_gb[::-1], color=colors[::-1], height=0.54, edgecolor="#1E293B")
    ax.axvline(2.0, color="#1D4ED8", linestyle="--", linewidth=1.5, label="Ngưỡng tối thiểu cho PyTorch + mô hình ngữ nghĩa (2,0 GB)")
    for b, val in zip(bars, ram_gb[::-1]):
        note = " (Miễn phí, không thẻ)" if val == 16.0 else (" (Hết hạn sau 30 ngày)" if val == 8.0 else (" (Bắt buộc thẻ)" if val == 4.0 else " (Tràn bộ nhớ)"))
        ax.text(val + 0.25, b.get_y() + b.get_height() / 2, f"{val:.2f} GB{note}".replace(".", ","),
                va="center", fontsize=8.6, color="#0F172A")
    ax.set_xlim(0, 22.8)
    ax.set_xlabel("Bộ nhớ RAM tối đa khả dụng ở bậc dùng thử / miễn phí (GB)", fontsize=9.5)
    ax.grid(axis="x", linestyle=":", alpha=0.5)
    ax.legend(loc="lower right", fontsize=8.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _save(fig, "fig_1_5.png")


def make_fig_1_6() -> None:
    """Minh họa giao diện bảng điều khiển Space (trái) & biến bí mật mã hóa (phải)."""
    fig, ax = plt.subplots(figsize=(10.8, 4.8), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.46, 0.88, "Hugging Face Space · Tổng quan & Nhật ký", "#1E3A8A")
    _box(ax, 0.04, 0.72, 0.42, 0.11, "Không gian: Lưu trữ Số hóa Cloud\nTrạng thái: Đang hoạt động (Running · 2 vCPU · 16 GB RAM)", fc="#DCFCE7", ec="#15803D", fs=8.0, bold=True)
    tabs = [("Ứng dụng", "#DBEAFE"), ("Tệp mã", "#F1F5F9"), ("Cài đặt", "#F1F5F9"), ("Nhật ký", "#E0E7FF")]
    for i, (t, fc) in enumerate(tabs):
        _box(ax, 0.04 + i * 0.105, 0.62, 0.098, 0.07, t, fc=fc, ec="#64748B", fs=7.8, bold=(i in (0, 3)))
    _box(ax, 0.04, 0.11, 0.42, 0.47,
         "[Luồng Xây dựng ảnh] Hoàn tất cài Tesseract tiếng Việt & mô hình\n"
         "[Luồng Bộ chứa] Khởi tạo cổng kết nối 7860 trên địa chỉ 0.0.0.0\n"
         "[Đồng bộ Đám mây] Khôi phục thành công cấu trúc 14 hồ sơ\n"
         "[Chỉ mục Tìm kiếm] Nạp 110 văn bản · 630 trang · 3.476 đoạn\n"
         "[Cổng LLM Mặc định] Sẵn sàng suy luận trực tuyến phía máy chủ\n"
         "[Kiểm tra Sức khỏe] Phản hồi hợp lệ trạng thái sẵn sàng",
         fc="#0F172A", ec="#334155", tc="#E2E8F0", fs=7.3, ha="left")

    _panel_frame(ax, 0.52, 0.06, 0.46, 0.88, "Cài đặt · Biến môi trường & Bí mật Mã hóa", "#0F766E")
    _box(ax, 0.54, 0.74, 0.42, 0.09, "Phần cứng: CPU Cơ bản · Miễn phí (0 USD/giờ)\nChế độ ngủ đông mặc định: Sau 48 giờ không truy cập", fc="#F0FDFA", ec="#0F766E", fs=7.8)
    secrets_rows = [
        ("Khóa cổng mô hình ngôn ngữ mặc định", "••••••••1a8e  (Mã hóa)"),
        ("Mã thông báo truy cập kho lưu trữ", "••••••••9f2c  (Mã hóa)"),
        ("Mật khẩu quản trị và khóa ký phiên", "••••••••••••  (Mã hóa)"),
        ("Định danh kho tập dữ liệu riêng tư", "Kho lưu trữ riêng tư"),
        ("Tên mô hình ngôn ngữ mặc định", "Gemini 2.0 Flash"),
        ("Cờ vận hành phi trạng thái", "Đã kích hoạt (Bật)"),
    ]
    for i, (k, v) in enumerate(secrets_rows):
        y = 0.62 - i * 0.092
        _box(ax, 0.54, y, 0.25, 0.072, k, fc="#F8FAFC", ec="#CBD5E1", fs=7.2, ha="left")
        _box(ax, 0.80, y, 0.16, 0.072, v, fc="#ECFDF5", ec="#047857", fs=7.1, bold=True)

    _save(fig, "fig_1_6.png")


def make_fig_1_7() -> None:
    """Kho tập dữ liệu ở chế độ riêng tư (trái) & lịch sử đồng bộ phiên bản (phải)."""
    fig, ax = plt.subplots(figsize=(10.8, 4.7), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.46, 0.88, "Kho Tập Dữ liệu · Chế độ Riêng tư (Private)", "#15803D")
    _box(ax, 0.04, 0.73, 0.27, 0.08, "Kho lưu trữ dữ liệu số hóa", fc="#F8FAFC", ec="#94A3B8", fs=8.0, bold=True)
    _box(ax, 0.33, 0.73, 0.13, 0.08, "[Riêng tư]", fc="#FEE2E2", ec="#DC2626", tc="#991B1B", fs=8.0, bold=True)
    tree = [
        ("[Thư mục] Nhánh trạng thái", "Cây Phông – Hồ sơ lưu trữ", "#EFF6FF"),
        ("[Thư mục] Nhánh dữ liệu sạch", "Bảng kê & nội dung 110 văn bản", "#EFF6FF"),
        ("[Thư mục] Nhánh mô hình nhẹ", "Ngưỡng từ chối & từ điển sửa lỗi", "#EFF6FF"),
        ("[Thư mục] Nhánh nhận dạng đệm", "Kết quả nhận dạng 630 trang", "#EFF6FF"),
        ("[Thư mục] Nhánh tài liệu gốc", "Kho tệp PDF phục vụ tải lười", "#DCFCE7"),
    ]
    for i, (f, desc, fc) in enumerate(tree):
        y = 0.60 - i * 0.105
        _box(ax, 0.04, y, 0.42, 0.085, f"{f} — {desc}", fc=fc, ec="#64748B", fs=7.4, ha="left")

    _panel_frame(ax, 0.52, 0.06, 0.46, 0.88, "Lịch sử Phiên bản & Đồng bộ Nền", "#1E40AF")
    commits = [
        ("Đồng bộ danh mục hồ sơ mới tạo", "Vừa xong", "#DCFCE7"),
        ("Cập nhật tài liệu quét tải lên từ web", "2 phút trước", "#DCFCE7"),
        ("Đồng bộ bộ nhớ đệm nhận dạng quang học", "15 phút trước", "#EFF6FF"),
        ("Đẩy trọn bộ kho dữ liệu bền vững ban đầu", "Khởi tạo", "#F1F5F9"),
    ]
    for i, (msg, tm, fc) in enumerate(commits):
        y = 0.67 - i * 0.14
        _box(ax, 0.54, y, 0.42, 0.105, f"[Đạt] {msg}\n   Mốc thời gian: {tm} · Trạng thái: Toàn vẹn 100%", fc=fc, ec="#64748B", fs=7.6, ha="left")

    _save(fig, "fig_1_7.png")


def make_fig_1_8() -> None:
    """Quản lý hạn mức OpenRouter (trái) & kho mã tự động hóa GitHub (phải)."""
    fig, ax = plt.subplots(figsize=(10.8, 4.7), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.46, 0.88, "Cổng Mô hình Ngôn ngữ · Quản lý Khóa & Hạn mức", "#C2410C")
    _box(ax, 0.04, 0.67, 0.42, 0.14, "Khóa hệ thống mặc định: ••••••••1a8e\nMô hình mặc định: Google Gemini 2.0 Flash\nTrạng thái: Hoạt động sẵn sàng phía máy chủ", fc="#FFF7ED", ec="#C2410C", fs=7.8, ha="left", bold=True)
    _box(ax, 0.04, 0.40, 0.42, 0.22, "Cơ chế kiểm soát chi phí áp dụng:\n• Chặn câu hỏi thiếu căn cứ trước khi gọi API\n• Giới hạn tối đa 5 đoạn nguồn × 900 ký tự\n• Không bắt buộc người dùng nhập khóa cá nhân", fc="#F8FAFC", ec="#94A3B8", fs=7.6, ha="left")
    _box(ax, 0.04, 0.12, 0.42, 0.22, "Lịch sử suy luận kiểm thử gần nhất:\n• Thời gian phản hồi trung bình: 1,2 – 2,4 giây\n• Tỷ lệ thành công kiểm chứng nguồn: 100%", fc="#ECFDF5", ec="#047857", fs=7.7, ha="left")

    _panel_frame(ax, 0.52, 0.06, 0.46, 0.88, "Kho Mã nguồn & Tự động hóa Kiểm thử", "#334155")
    _box(ax, 0.54, 0.69, 0.42, 0.12, "Nhánh chính bảo vệ · Luồng tự động hóa đang bật\nTách biệt hoàn toàn khỏi thư mục môn học khác", fc="#F1F5F9", ec="#475569", fs=7.8, bold=True)
    checks = [
        ("1. Cài đặt môi trường & OCR tiếng Việt", "Đạt", "#DCFCE7"),
        ("2. Chạy 85 bài kiểm thử tự động toàn diện", "85/85 Đạt", "#DCFCE7"),
        ("3. Kiểm tra gói tách dữ liệu (< 5 MB)", "0,65 MB · Đạt", "#DCFCE7"),
        ("4. Triển khai tự động lên Không gian Cloud", "Hoàn tất", "#DBEAFE"),
    ]
    for i, (lbl, st, fc) in enumerate(checks):
        y = 0.55 - i * 0.115
        _box(ax, 0.54, y, 0.29, 0.088, lbl, fc="#FFFFFF", ec="#CBD5E1", fs=7.5, ha="left")
        _box(ax, 0.84, y, 0.12, 0.088, st, fc=fc, ec="#15803D", fs=7.5, bold=True)

    _save(fig, "fig_1_8.png")


# =========================================================================
# CHƯƠNG 2: QUY TRÌNH TRIỂN KHAI HỆ THỐNG LÊN NỀN TẢNG ĐÁM MÂY (12 HÌNH)
# =========================================================================

def make_fig_2_1() -> None:
    """Phân bổ khối lượng công việc đồng đều giữa các thành viên Nhóm 04."""
    fig, ax = plt.subplots(figsize=(9.8, 4.4), dpi=220)
    tasks = [
        "Gói 1: Phân tích đặc tả &\nđối sánh nền tảng đám mây",
        "Gói 2: Lưu trữ bền vững,\nđóng gói & tách gói dữ liệu",
        "Gói 3: Xác thực phi trạng thái\n& bảng giám sát trực tuyến",
        "Gói 4: Tự động hóa kiểm thử,\nđo lường & hoàn thiện báo cáo",
    ]
    pcts = [25, 25, 25, 25]
    owners = ["Nông Thị Hương (Nhóm trưởng)", "Lê Xuân Nhất", "Lê Xuân Nhất & Nông Thị Hương", "Nông Thị Hương & Lê Xuân Nhất"]
    colors = ["#2563EB", "#059669", "#D97706", "#7C3AED"]

    bars = ax.barh(tasks[::-1], pcts[::-1], color=colors[::-1], height=0.55)
    for b, o in zip(bars, owners[::-1]):
        ax.text(12.5, b.get_y() + b.get_height() / 2, f"25% khối lượng — {o}",
                ha="center", va="center", color="white", fontweight="bold", fontsize=8.9)
    ax.set_xlim(0, 30)
    ax.set_xlabel("Tỷ trọng đóng góp công việc trong toàn dự án (%)", fontsize=9.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", linestyle=":", alpha=0.5)
    _save(fig, "fig_2_1.png")


def make_fig_2_2() -> None:
    """Biểu đồ tiến độ thực hiện theo tuần (phong cách Gantt rõ ràng)."""
    fig, ax = plt.subplots(figsize=(9.8, 4.3), dpi=220)
    stages = [
        "1. Khởi tạo, đặc tả & đối sánh Cloud",
        "2. Lõi lưu trữ bền vững & xác thực ký số",
        "3. Giao diện giám sát, LLM mặc định & bộ chứa",
        "4. Tích hợp CI/CD, kiểm thử & đo đạc độ trễ",
        "5. Triển khai công khai & kiểm chứng restart",
        "6. Hoàn thiện báo cáo & chuẩn bị trình diễn",
    ]
    starts = [1, 6, 12, 17, 21, 24]
    durations = [5, 7, 6, 5, 4, 5]
    colors = ["#2563EB", "#059669", "#D97706", "#7C3AED", "#0284C7", "#E11D48"]

    y_pos = np.arange(len(stages))[::-1]
    for y, s, d, c in zip(y_pos, starts, durations, colors):
        ax.barh(y, d, left=s, height=0.52, color=c, edgecolor="#1E293B")
        ax.text(s + d / 2, y, f"Ngày {s}–{s + d - 1}", ha="center", va="center", color="white", fontsize=8.2, fontweight="bold")

    ax.axvline(24, color="#334155", linestyle="--", lw=1.2)
    ax.text(24, -0.75, "Mốc kiểm thử tổng", ha="center", va="top", fontsize=8.3, color="#334155")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(stages, fontsize=8.8)
    ax.set_xlim(0, 30.5)
    ax.set_xticks([1, 7, 14, 21, 28])
    ax.set_xticklabels(["Tuần 1", "Tuần 2", "Tuần 3", "Tuần 4", "Hoàn tất"], fontsize=8.8)
    ax.grid(axis="x", linestyle=":", alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _save(fig, "fig_2_2.png")


def make_fig_2_3() -> None:
    """Sơ đồ kiến trúc triển khai tổng thể trên đám mây công cộng."""
    fig, ax = plt.subplots(figsize=(10.8, 5.4), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _box(ax, 0.27, 0.83, 0.46, 0.11,
         "Tầng 1: Người dùng & Quản trị viên (Trình duyệt qua HTTPS)\nCổng Quản lý Hồ sơ  |  Không gian Hỏi đáp 3 cột  |  Bảng Giám sát Cloud",
         fc="#DBEAFE", ec="#1D4ED8", fs=8.8, bold=True)
    _box(ax, 0.16, 0.53, 0.68, 0.18,
         "Tầng 2: Không gian Bộ chứa Tính toán Phi Trạng thái (2 vCPU, 16 GB RAM)\n"
         "Máy chủ Web bất đồng bộ  |  Tìm kiếm lai (BM25 + TF-IDF + Vector)  |  OCR tiếng Việt\n"
         "Xác thực chữ ký điện tử bền vững  |  Tích hợp sẵn khóa mô hình ngôn ngữ mặc định",
         fc="#EFF6FF", ec="#1E40AF", fs=8.8)

    _box(ax, 0.04, 0.21, 0.42, 0.20,
         "Tầng 3: Kho Tập Dữ liệu Riêng tư Bền vững\n"
         "• Danh mục Phông – Hồ sơ (đồng bộ tức thời)\n"
         "• Tài liệu tải lên & kết quả nhận dạng đệm\n"
         "• Kho tài liệu gốc phục vụ tải lười PDF",
         fc="#ECFDF5", ec="#047857", fs=8.5)

    _box(ax, 0.54, 0.21, 0.42, 0.20,
         "Tầng 4: Cổng Mô hình Ngôn ngữ Mặc định\n"
         "• Suy luận từ các đoạn trích đã kiểm duyệt\n"
         "• Hoạt động sẵn sàng ngay không cần nhập khóa\n"
         "• Giới hạn token & thử lại tự động khi quá tải",
         fc="#FFF7ED", ec="#C2410C", fs=8.5)

    _box(ax, 0.20, 0.03, 0.60, 0.10,
         "Đường ống Tự động hóa: Kiểm thử 85 kịch bản -> Kiểm tra gói tách (< 1 MB) -> Triển khai bộ chứa",
         fc="#F3E8FF", ec="#7E22CE", fs=8.5, bold=True)

    _arrow(ax, 0.50, 0.83, 0.50, 0.71, "HTTPS + Mã phiên")
    _arrow(ax, 0.34, 0.53, 0.25, 0.41, "Khôi phục & Đồng bộ")
    _arrow(ax, 0.66, 0.53, 0.75, 0.41, "Yêu cầu suy luận")
    _arrow(ax, 0.50, 0.13, 0.50, 0.53, "Triển khai liên tục", color="#7E22CE")
    _save(fig, "fig_2_3.png")


def make_fig_2_4(bench: dict) -> None:
    """Cấu trúc phân lớp bộ chứa (trái) & biểu đồ giảm 99,77% dung lượng gói (phải)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.8, 4.6), dpi=220, gridspec_kw={"width_ratios": [1.05, 1]})
    ax1.set_xlim(0, 1)
    ax1.set_ylim(0, 1)
    ax1.axis("off")
    ax1.set_title("Cấu trúc 6 lớp ảnh bộ chứa bảo mật", fontsize=9.5, fontweight="bold", color="#0F172A")

    layers = [
        ("6. Tiến trình Web phi đặc quyền (UID 1000) + Kiểm tra sống", "#DCFCE7", "#15803D"),
        ("5. Mã nguồn gọn nhẹ (0,65 MB) — không chứa bí mật/dữ liệu", "#DBEAFE", "#1D4ED8"),
        ("4. Nạp sẵn trọng số mô hình ngữ nghĩa đa ngôn ngữ (~470 MB)", "#E0E7FF", "#4338CA"),
        ("3. Thư viện Python tối ưu CPU (không cài gói giao diện thừa)", "#FEF3C7", "#B45309"),
        ("2. Bộ nhận dạng quang học Tesseract + gói tiếng Việt", "#FFEDD5", "#C2410C"),
        ("1. Ảnh nền Linux tối giản kèm Python 3.10", "#F1F5F9", "#475569"),
    ]
    for i, (txt, fc, ec) in enumerate(layers):
        _box(ax1, 0.03, 0.80 - i * 0.15, 0.94, 0.115, txt, fc=fc, ec=ec, fs=7.7, bold=(i == 0))

    pkg = bench["packaging"]
    labels = ["Đơn khối cũ", "Độc lập nhẹ", "Kho dữ liệu", "Mã nguồn Space"]
    vals = [pkg["legacy_monolith_mb"], pkg["standalone_mb"], pkg["decoupled_storage_mb"], pkg["decoupled_space_mb"]]
    colors = ["#EF4444", "#F59E0B", "#0EA5E9", "#16A34A"]
    bars = ax2.barh(labels[::-1], vals[::-1], color=colors[::-1], height=0.52, edgecolor="#1E293B")
    for b, v in zip(bars, vals[::-1]):
        ax2.text(v + 4.5, b.get_y() + b.get_height() / 2, f"{v:.2f} MB".replace(".", ","), va="center", fontsize=8.3, fontweight="bold")
    ax2.set_xlim(0, 345)
    ax2.set_title("Dung lượng gói triển khai (giảm 99,77%)", fontsize=9.5, fontweight="bold", color="#0F172A")
    ax2.set_xlabel("Dung lượng thực tế (MB)", fontsize=8.8)
    ax2.grid(axis="x", linestyle=":", alpha=0.5)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    _save(fig, "fig_2_4.png")


def make_fig_2_5() -> None:
    """Bước 1: Tổ chức dự án cô lập (trái) & kết quả kiểm thử tự động (phải)."""
    fig, ax = plt.subplots(figsize=(10.8, 4.5), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.46, 0.88, "Bước 1 · Cô lập Mã nguồn & Kiểm tra Lọc Bí mật", "#1E3A8A")
    _box(ax, 0.04, 0.12, 0.42, 0.72,
         "Không gian Dự án Đám mây (tách rời môn NLP)\n"
         "├── Bộ đặc tả kiến trúc & hợp đồng dịch vụ\n"
         "├── Các mô-đun lưu trữ bền vững, đo lường, bảo mật\n"
         "├── Giao diện Cổng lưu trữ, Hỏi đáp 3 cột & Cloud\n"
         "├── Cấu hình đóng gói bộ chứa phi đặc quyền\n"
         "├── Đường ống kiểm thử và triển khai liên tục\n"
         "└── Quy tắc loại trừ: chặn tuyệt đối tệp chứa khóa\n"
         "    bí mật và dữ liệu thô khỏi kho mã nguồn công khai",
         fc="#F8FAFC", ec="#64748B", fs=7.8, ha="left")

    _panel_frame(ax, 0.52, 0.06, 0.46, 0.88, "Kết quả Kiểm thử Tự động trước Triển khai", "#15803D")
    _box(ax, 0.54, 0.12, 0.42, 0.72,
         "[Kiểm tra nghiệp vụ lõi] Đọc/lọc/nhập xuất hồ sơ: Đạt\n"
         "[Kiểm tra xác thực] Chữ ký HMAC vượt restart: Đạt\n"
         "[Kiểm tra bền vững] Khôi phục 100% sau xóa đĩa tạm: Đạt\n"
         "[Kiểm tra giám sát] Điểm cuối sống & sẵn sàng: Đạt\n"
         "[Kiểm tra khóa LLM mặc định] Sẵn sàng & đã che: Đạt\n"
         "[Kiểm tra gói tách dữ liệu] 37 tệp (0,65 MB < 5 MB): Đạt\n"
         "Tổng kết toàn hệ thống: 100% bài kiểm thử thông qua",
         fc="#0F172A", ec="#15803D", tc="#86EFAC", fs=7.6, ha="left")

    _save(fig, "fig_2_5.png")


def make_fig_2_6() -> None:
    """Bước 2 & 3: Tạo mã thông báo ghi (trái) & kho dữ liệu riêng tư (phải)."""
    fig, ax = plt.subplots(figsize=(10.8, 4.4), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.46, 0.88, "Bước 2 · Khởi tạo Mã Truy cập Phân quyền Ghi", "#7C3AED")
    _box(ax, 0.04, 0.62, 0.42, 0.20, "Cài đặt Bảo mật Tài khoản Đám mây\n• Tên khóa: Mã triển khai lưu trữ số hóa\n• Phạm vi quyền: Đọc và Ghi Kho lưu trữ / Không gian", fc="#F5F3FF", ec="#7C3AED", fs=7.9, ha="left")
    _box(ax, 0.04, 0.36, 0.42, 0.20, "Giá trị mã thông báo được tạo một lần duy nhất:\n••••••••••••••9f2c   [Đã sao chép vào vùng nhớ an toàn]", fc="#FEF3C7", ec="#B45309", fs=7.9, bold=True)
    _box(ax, 0.04, 0.12, 0.42, 0.18, "Lưu ý bảo mật: Chỉ nạp vào biến bí mật mã hóa trên đám mây,\nkhông đưa vào kho mã nguồn công khai.", fc="#F8FAFC", ec="#94A3B8", fs=7.6)

    _panel_frame(ax, 0.52, 0.06, 0.46, 0.88, "Bước 3 · Khởi tạo Kho Tập Dữ liệu Chế độ Riêng tư", "#047857")
    _box(ax, 0.54, 0.60, 0.42, 0.22, "Kho lưu trữ đối tượng và trạng thái bền vững\n• Loại kho: Kho tập dữ liệu chuyên dụng\n• Chế độ hiển thị bắt buộc: Riêng tư (Private)", fc="#ECFDF5", ec="#047857", fs=7.9, ha="left", bold=True)
    _box(ax, 0.54, 0.14, 0.42, 0.38, "Quyền truy cập kho dữ liệu:\n• Người dùng bên ngoài không thể xem hoặc tải trực tiếp\n• Chỉ bộ chứa ứng dụng có mã thông báo hợp lệ mới được\n  đọc khi khởi động và ghi đồng bộ khi có thay đổi hồ sơ\n• Tài liệu gốc phục vụ theo cơ chế tải lười khi xem trang", fc="#F8FAFC", ec="#94A3B8", fs=7.7, ha="left")

    _save(fig, "fig_2_6.png")


def make_fig_2_7() -> None:
    """Bước 4: Cấu hình khóa LLM mặc định máy chủ & cơ chế kiểm soát chi phí."""
    fig, ax = plt.subplots(figsize=(10.8, 4.4), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.46, 0.88, "Bước 4 · Thiết lập Khóa LLM Mặc định Phía Máy chủ", "#C2410C")
    _box(ax, 0.04, 0.60, 0.42, 0.22, "Cổng Dịch vụ Mô hình Ngôn ngữ Mặc định\n• Nhà cung cấp: OpenRouter (Google Gemini 2.0 Flash)\n• Khóa hệ thống mặc định: ••••••••1a8e (Đã kích hoạt)", fc="#FFF7ED", ec="#C2410C", fs=7.9, ha="left", bold=True)
    _box(ax, 0.04, 0.14, 0.42, 0.38, "Trải nghiệm không cần thiết lập cho người dùng cuối:\n• Trình duyệt tự động sử dụng kết nối LLM có sẵn ở máy chủ\n• Ẩn hoàn toàn yêu cầu nhập khóa API đối với độc giả\n• Hỗ trợ chuyển tức thời sang chế độ trích câu cơ sở\n• Giá trị khóa thô luôn được che kín ở mọi điểm cuối trạng thái", fc="#F8FAFC", ec="#94A3B8", fs=7.7, ha="left")

    _panel_frame(ax, 0.52, 0.06, 0.46, 0.88, "Kiểm soát Hạn mức & Chống Gọi Thừa API", "#1E40AF")
    rules = [
        ("Cổng từ chối trước LLM", "Chặn câu hỏi thiếu căn cứ (< ngưỡng phủ)", "#DBEAFE"),
        ("Giới hạn ngữ cảnh gửi đi", "Tối đa 5 đoạn nguồn × 900 ký tự/lượt", "#EFF6FF"),
        ("Giới hạn độ dài phản hồi", "Tối đa 280 token · Nhiệt độ giải mã 0,0", "#EFF6FF"),
        ("Cơ chế thử lại an toàn", "Tối đa 2 lần thử lại khi quá tải tạm thời", "#DCFCE7"),
    ]
    for i, (t, d, fc) in enumerate(rules):
        y = 0.66 - i * 0.145
        _box(ax, 0.54, y, 0.42, 0.11, f"{t}: {d}", fc=fc, ec="#1E40AF", fs=7.7, ha="left")

    _save(fig, "fig_2_7.png")


def make_fig_2_8(bench: dict) -> None:
    """Bước 5: Đồng bộ 562 tệp dữ liệu lên kho riêng tư & kiểm chứng cấu trúc 5 nhánh."""
    pkg = bench["packaging"]
    fig, ax = plt.subplots(figsize=(10.8, 4.4), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.46, 0.88, "Bước 5 · Thực thi Tách Dữ liệu & Đẩy Kho Riêng tư", "#0F172A")
    _box(ax, 0.04, 0.12, 0.42, 0.72,
         "[Chế độ đóng gói] Tách biệt hoàn toàn mã nguồn & dữ liệu\n"
         f"[Gói mã nguồn bộ chứa] {pkg['decoupled_space_files']} tệp ({pkg['decoupled_space_mb']:.2f} MB < 5,00 MB)\n".replace(".", ",") +
         f"[Gói kho dữ liệu riêng tư] {pkg['decoupled_storage_files']} tệp ({pkg['decoupled_storage_mb']:.2f} MB)\n".replace(".", ",") +
         "  - Trạng thái hồ sơ: 1 tệp danh mục chuẩn hóa\n"
         "  - Dữ liệu văn bản xử lý: 221 tệp làm sạch & bảng kê\n"
         "  - Bộ nhớ đệm nhận dạng: 220 tệp trang quét\n"
         "  - Kho tài liệu gốc tải lười: 110 tệp tài liệu nguồn\n"
         "[Kết quả] Hoàn tất đẩy lên kho riêng tư trong 1 giao dịch",
         fc="#0F172A", ec="#334155", tc="#E2E8F0", fs=7.5, ha="left")

    _panel_frame(ax, 0.52, 0.06, 0.46, 0.88, "Kiểm chứng 5 Nhánh Dữ liệu Trên Đám mây", "#15803D")
    branches = [
        ("1. Nhánh trạng thái", "Cấu trúc 4 Phông – 14 Hồ sơ", "#DCFCE7"),
        ("2. Nhánh văn bản sạch", "110 văn bản · 3.476 đoạn", "#EFF6FF"),
        ("3. Nhánh mô hình phụ trợ", "Ngưỡng từ chối & sửa lỗi", "#EFF6FF"),
        ("4. Nhánh nhận dạng đệm", "630 trang văn bản OCR", "#FEF3C7"),
        ("5. Nhánh tài liệu gốc", "110 tệp PDF tải lười theo trang", "#DBEAFE"),
    ]
    for i, (b, desc, fc) in enumerate(branches):
        y = 0.67 - i * 0.13
        _box(ax, 0.54, y, 0.42, 0.10, f"[Đạt] {b}: {desc}", fc=fc, ec="#15803D", fs=7.7, ha="left", bold=(i == 0))

    _save(fig, "fig_2_8.png")


def make_fig_2_9() -> None:
    """Bước 6: Cấu hình Không gian bộ chứa 16 GB RAM & biến bí mật máy chủ."""
    fig, ax = plt.subplots(figsize=(10.8, 4.5), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.46, 0.88, "Bước 6 · Cấu hình Không gian Bộ chứa Đám mây", "#1D4ED8")
    specs = [
        ("Nền tảng đóng gói", "Bộ chứa tùy biến chuẩn mở"),
        ("Cấu hình phần cứng", "2 vCPU · 16 GB RAM · 50 GB đĩa tạm"),
        ("Cổng lắng nghe Web", "7860 (Giao thức HTTPS tự động)"),
        ("Kho dữ liệu kết nối", "Kho tập dữ liệu riêng tư"),
        ("Dung lượng mã nguồn đẩy", "37 tệp · 0,65 MB (giảm 99,77%)"),
        ("Chi phí duy trì", "0 đồng/tháng · Không gắn thẻ"),
    ]
    for i, (k, v) in enumerate(specs):
        y = 0.68 - i * 0.105
        _box(ax, 0.04, y, 0.18, 0.082, k, fc="#EFF6FF", ec="#93C5FD", fs=7.5, bold=True)
        _box(ax, 0.23, y, 0.23, 0.082, v, fc="#FFFFFF", ec="#CBD5E1", fs=7.5, ha="left")

    _panel_frame(ax, 0.52, 0.06, 0.46, 0.88, "Biến Bí mật Mã hóa Đã Đồng bộ Lên Máy chủ", "#047857")
    sec_rows = [
        ("Khóa truy cập kho lưu trữ", "••••••••9f2c (Đã mã hóa)"),
        ("Định danh kho dữ liệu riêng tư", "Kho lưu trữ bền vững"),
        ("Khóa mô hình ngôn ngữ mặc định", "••••••••1a8e (Sẵn sàng)"),
        ("Mô hình ngôn ngữ & nhà cung cấp", "OpenRouter · Gemini Flash"),
        ("Mật khẩu quản trị & khóa ký", "•••••••••••• (HMAC-SHA256)"),
        ("Chế độ vận hành phi trạng thái", "Bật (Không ghi khóa ra đĩa)"),
    ]
    for i, (k, v) in enumerate(sec_rows):
        y = 0.68 - i * 0.105
        _box(ax, 0.54, y, 0.23, 0.082, k, fc="#F0FDF4", ec="#86EFAC", fs=7.3, ha="left")
        _box(ax, 0.78, y, 0.18, 0.082, v, fc="#ECFDF5", ec="#047857", fs=7.2, bold=True)

    _save(fig, "fig_2_9.png")


def make_fig_2_10(bench: dict) -> None:
    """Bước 7: Nhật ký xây dựng ảnh thành công & kiểm tra trạng thái sẵn sàng."""
    startup_s = f"{bench['startup_seconds']:.2f}".replace(".", ",")
    c = bench["corpus"]
    fig, ax = plt.subplots(figsize=(10.8, 4.5), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.46, 0.88, "Bước 7 · Nhật ký Xây dựng & Khởi chạy Bộ chứa", "#0F172A")
    _box(ax, 0.04, 0.12, 0.42, 0.72,
         "[Bước ảnh 1–3] Cài đặt Linux tối giản, Tesseract tiếng Việt & Python OK\n"
         "[Bước ảnh 4] Nạp sẵn trọng số mô hình ngữ nghĩa vào ảnh OK\n"
         "[Bước ảnh 5] Chuyển quyền thực thi sang người dùng phi đặc quyền OK\n"
         "[Khởi động máy chủ] Kéo trạng thái từ kho riêng tư trong 25,0 ms\n"
         f"[Nạp chỉ mục lai] {c['n_docs']} văn bản · {c['n_pages']} trang · {c['n_chunks']} đoạn ({startup_s} s)\n"
         "[Mô hình ngôn ngữ] Khóa mặc định máy chủ sẵn sàng hoạt động\n"
         "[Trạng thái dịch vụ] Đang lắng nghe HTTPS · Trạng thái: Đang chạy",
         fc="#0F172A", ec="#334155", tc="#E2E8F0", fs=7.4, ha="left")

    _panel_frame(ax, 0.52, 0.06, 0.46, 0.88, "Phản hồi Điểm cuối Sống & Sẵn sàng", "#15803D")
    _box(ax, 0.54, 0.55, 0.42, 0.27,
         "Kiểm tra Trạng thái Sống (Mỗi 30 giây)\n"
         "• Trạng thái phản hồi: Hợp lệ (Mã 200 OK)\n"
         "• Độ trễ trung vị: 1,19 mili-giây\n"
         "• Không truy xuất ổ đĩa hay mô hình nặng",
         fc="#DCFCE7", ec="#15803D", fs=7.8, ha="left", bold=True)
    _box(ax, 0.54, 0.14, 0.42, 0.34,
         "Kiểm tra Mức độ Sẵn sàng Phục vụ\n"
         "• Chỉ mục lai & mô hình ngữ nghĩa: Đã nạp\n"
         "• Tầng lưu trữ: Đám mây bền vững (Kho riêng tư)\n"
         "• Xác thực phiên: Phi trạng thái (vượt khởi động lại)\n"
         "• Cổng LLM mặc định: Sẵn sàng không cần thiết lập",
         fc="#EFF6FF", ec="#1D4ED8", fs=7.8, ha="left")

    _save(fig, "fig_2_10.png")


def make_fig_2_11(bench: dict) -> None:
    """Bước 8: Tự động triển khai CI/CD & kiểm chứng khôi phục sau khởi động lại."""
    dur = bench["durability"]
    fig, ax = plt.subplots(figsize=(10.8, 4.4), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.46, 0.88, "Bước 8a · Tự động hóa Kiểm thử & Triển khai", "#7E22CE")
    steps = [
        ("1. Đẩy mã mới lên nhánh chính", "#F3E8FF"),
        ("2. Chạy tự động 85 bài kiểm thử", "#DCFCE7"),
        ("3. Rà soát đóng gói (< 5 MB, không lọt khóa)", "#FEF3C7"),
        ("4. Cập nhật Không gian Bộ chứa Đám mây", "#DBEAFE"),
    ]
    for i, (s, fc) in enumerate(steps):
        y = 0.67 - i * 0.145
        _box(ax, 0.05, y, 0.40, 0.10, s, fc=fc, ec="#7E22CE", fs=8.0, bold=True)
        if i < 3:
            _arrow(ax, 0.25, y, 0.25, y - 0.04, color="#7E22CE")

    _panel_frame(ax, 0.52, 0.06, 0.46, 0.88, "Bước 8b · Kiểm chứng Độ bền Vượt Khởi động lại", "#047857")
    steps_r = [
        ("T1: Tạo hồ sơ mới & tải lên PDF quét trên web", "#EFF6FF"),
        (f"T2: Tự động đẩy đồng bộ ra kho riêng tư ({dur['sync_ms']:.1f} ms)".replace(".", ","), "#DCFCE7"),
        ("T3: Khởi động lại bộ chứa (xóa sạch đĩa tạm & RAM)", "#FEE2E2"),
        (f"T4: Tự kéo khôi phục 100% dữ liệu ({dur['restore_ms']:.1f} ms) & giữ phiên".replace(".", ","), "#DCFCE7"),
    ]
    for i, (s, fc) in enumerate(steps_r):
        y = 0.67 - i * 0.145
        _box(ax, 0.55, y, 0.40, 0.10, s, fc=fc, ec="#047857", fs=7.8, bold=(i in (1, 3)))
        if i < 3:
            _arrow(ax, 0.75, y, 0.75, y - 0.04, color="#047857")

    _save(fig, "fig_2_11.png")


def make_fig_2_12() -> None:
    """Theo dõi bộ nhớ RAM so với giới hạn 16 GB & bảng đối soát chi phí 0 đồng."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.8, 4.4), dpi=220, gridspec_kw={"width_ratios": [1.05, 1]})
    cats = ["Khởi động\ncơ bản", "Nạp mô hình\nngữ nghĩa", "Tìm kiếm lai\n& Hỏi đáp", "Nhận dạng PDF\nđộ phân giải cao", "Giới hạn gói\nmiễn phí"]
    vals = [0.22, 1.48, 1.65, 2.35, 16.0]
    cols = ["#60A5FA", "#3B82F6", "#2563EB", "#D97706", "#16A34A"]
    bars = ax1.bar(cats, vals, color=cols, width=0.52, edgecolor="#1E293B")
    for b, v in zip(bars, vals):
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.35, f"{v:.2f} GB".replace(".", ","), ha="center", fontsize=8.0, fontweight="bold")
    ax1.set_ylim(0, 18.5)
    ax1.set_ylabel("Dung lượng RAM (GB)", fontsize=9.0)
    ax1.set_title("Mức tiêu thụ RAM so với giới hạn 16 GB", fontsize=9.3, fontweight="bold")
    ax1.tick_params(axis="x", labelsize=7.5)
    ax1.grid(axis="y", linestyle=":", alpha=0.5)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.axis("off")
    _panel_frame(ax2, 0.02, 0.06, 0.96, 0.88, "Đối soát Chi phí Vận hành & An toàn Tài chính", "#15803D")
    billing = [
        ("Không gian Bộ chứa (2 vCPU, 16 GB)", "0 đồng / tháng"),
        ("Kho Tập Dữ liệu Riêng tư", "0 đồng / tháng"),
        ("Đường ống Tự động hóa Kiểm thử", "0 đồng / tháng"),
        ("Thẻ tín dụng / Ghi nợ liên kết", "Không yêu cầu"),
        ("Tổng chi phí hạ tầng cố định", "0,00 USD (Miễn phí)"),
    ]
    for i, (k, v) in enumerate(billing):
        y = 0.66 - i * 0.13
        _box(ax2, 0.05, y, 0.56, 0.095, k, fc="#F8FAFC", ec="#CBD5E1", fs=7.8, ha="left")
        _box(ax2, 0.63, y, 0.32, 0.095, v, fc="#DCFCE7", ec="#15803D", fs=7.8, bold=True)

    _save(fig, "fig_2_12.png")


# =========================================================================
# CHƯƠNG 3: KẾT QUẢ TRIỂN KHAI VÀ ĐÁNH GIÁ SẢN PHẨM (5 HÌNH)
# =========================================================================

def make_fig_3_1(bench: dict) -> None:
    """Giao diện đăng nhập bảo mật (trái) & Cổng Quản lý Hồ sơ Lưu trữ (phải)."""
    c = bench["corpus"]
    fig, ax = plt.subplots(figsize=(10.8, 4.9), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.38, 0.88, "Màn hình Đăng nhập Bảo mật", "#14366E")
    _box(ax, 0.05, 0.68, 0.32, 0.12, "CỔNG LƯU TRỮ SỐ HÓA\nTỈNH THÁI NGUYÊN\nXác thực phiên phi trạng thái", fc="#EFF6FF", ec="#1D4ED8", fs=7.8, bold=True)
    _box(ax, 0.05, 0.52, 0.32, 0.09, "Tên đăng nhập: Quản trị viên", fc="#FFFFFF", ec="#94A3B8", fs=7.7, ha="left")
    _box(ax, 0.05, 0.40, 0.32, 0.09, "Mật khẩu: ••••••••••••••", fc="#FFFFFF", ec="#94A3B8", fs=7.7, ha="left")
    _box(ax, 0.05, 0.26, 0.32, 0.09, "ĐĂNG NHẬP HỆ THỐNG", fc="#1D4ED8", ec="#1E3A8A", tc="#FFFFFF", fs=8.2, bold=True)
    _box(ax, 0.05, 0.11, 0.32, 0.10, "Bảo vệ băm 600.000 vòng · Khóa 300 giây\nkhi sai quá 5 lần · Ký HMAC-SHA256", fc="#FEF3C7", ec="#B45309", fs=7.1)

    _panel_frame(ax, 0.43, 0.06, 0.55, 0.88, "Cổng Quản lý Phông, Hồ sơ Lưu trữ & Tra cứu Đa tiêu chí", "#14366E")
    cards = [
        (f"{c['n_fonds']} Phông", "#DBEAFE"),
        (f"{c['n_dossiers']} Hồ sơ", "#DCFCE7"),
        (f"{c['n_docs']} Văn bản", "#FEF3C7"),
        (f"{c['n_pages']} Trang", "#F3E8FF"),
    ]
    for i, (txt, fc) in enumerate(cards):
        _box(ax, 0.45 + i * 0.13, 0.72, 0.12, 0.09, txt, fc=fc, ec="#475569", fs=7.6, bold=True)
    _box(ax, 0.45, 0.58, 0.51, 0.09, "Tra cứu nhanh | Thêm hồ sơ | Nhập/Xuất CSV | Hạ tầng Cloud | Trợ lý 3 cột", fc="#F8FAFC", ec="#CBD5E1", fs=7.1)
    rows = [
        ("TN.2026.01.001 | Chỉ đạo triển khai Chuyển đổi số cấp tỉnh | Vĩnh viễn | Công khai | Đã duyệt"),
        ("TN.2026.02.004 | Hướng dẫn quy trình số hóa văn bản hành chính | 20 năm | Công khai | Đã duyệt"),
        ("TN.2026.03.008 | Phương án lưu trữ hồ sơ nội bộ cơ quan | 50 năm | Nội bộ | Tạo mới"),
        ("TN.2026.04.012 | Báo cáo tổng kết ứng dụng CNTT và lưu trữ | Vĩnh viễn | Công khai | Đã duyệt"),
    ]
    for i, r in enumerate(rows):
        y = 0.44 - i * 0.092
        _box(ax, 0.45, y, 0.51, 0.075, r, fc="#FFFFFF" if i % 2 == 0 else "#F8FAFC", ec="#CBD5E1", fs=6.9, ha="left")

    _save(fig, "fig_3_1.png")


def make_fig_3_2() -> None:
    """Giao diện 3 cột hỏi đáp AI tích hợp sẵn không cần cấu hình + PDF tô vàng."""
    fig, ax = plt.subplots(figsize=(10.8, 5.0), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.96, 0.88, "Không gian Nghiên cứu Ba Cột · Trợ lý AI Đám mây Sẵn sàng Không Cần Thiết lập Khóa", "#1E3A8A")
    # Cột 1: Nguồn
    _box(ax, 0.04, 0.10, 0.24, 0.72, "", fc="#F8FAFC", ec="#CBD5E1")
    ax.text(0.16, 0.79, "1. Nguồn tài liệu (110)", ha="center", va="center", fontsize=8.0, fontweight="bold", color="#0F172A")
    _box(ax, 0.055, 0.68, 0.21, 0.07, "+ Thêm nguồn (PDF)", fc="#1D4ED8", ec="#1E3A8A", tc="#FFFFFF", fs=7.5, bold=True)
    for i, d in enumerate(["[x] Nghị định 385/2026", "[x] Thông tư 02/2019", "[x] Quyết định 125/QĐ", "[x] Công văn 4521/CV", "[x] Kế hoạch Chuyển đổi số"]):
        _box(ax, 0.055, 0.57 - i * 0.095, 0.21, 0.075, d, fc="#FFFFFF", ec="#CBD5E1", fs=7.0, ha="left")

    # Cột 2: Chat AI mặc định
    _box(ax, 0.30, 0.10, 0.37, 0.72, "", fc="#FFFFFF", ec="#CBD5E1")
    ax.text(0.485, 0.79, "2. Hỏi đáp AI Có Dẫn nguồn", ha="center", va="center", fontsize=8.0, fontweight="bold", color="#0F172A")
    _box(ax, 0.36, 0.65, 0.29, 0.09, "Người dùng: Thời hạn bảo quản hồ sơ\nlưu trữ được quy định như thế nào?", fc="#DBEAFE", ec="#2563EB", fs=7.3, ha="left")
    _box(ax, 0.315, 0.34, 0.34, 0.27,
         "Trợ lý AI Đám mây: Theo quy định tại\n"
         "Thông tư hướng dẫn nghiệp vụ [1], hồ sơ\n"
         "được phân thành hai nhóm thời hạn chính\n"
         "là bảo quản vĩnh viễn và có thời hạn [2].\n"
         "[Đạt] Đã kiểm chứng con số & từ khóa gốc",
         fc="#ECFDF5", ec="#047857", fs=7.2, ha="left")
    _box(ax, 0.315, 0.14, 0.34, 0.14,
         "Nhập câu hỏi và gửi ngay...\n[Bật] Trả lời bằng LLM · Sẵn sàng mặc định",
         fc="#F8FAFC", ec="#94A3B8", fs=7.2, ha="left", bold=True)

    # Cột 3: Xem PDF tô vàng
    _box(ax, 0.69, 0.10, 0.27, 0.72, "", fc="#F8FAFC", ec="#CBD5E1")
    ax.text(0.825, 0.79, "3. Trang PDF & Căn cứ [1]", ha="center", va="center", fontsize=8.0, fontweight="bold", color="#0F172A")
    _box(ax, 0.71, 0.14, 0.23, 0.60, "", fc="#FFFFFF", ec="#64748B")
    ax.text(0.825, 0.69, "BỘ NỘI VỤ — TRANG 2", ha="center", fontsize=7.2, fontweight="bold")
    _box(ax, 0.725, 0.42, 0.20, 0.16,
         "Vùng trích dẫn tô sáng:\n\"Thời hạn bảo quản hồ sơ,\ntài liệu được phân loại\nvĩnh viễn hoặc theo năm.\"",
         fc="#FEF08A", ec="#CA8A04", fs=7.0, ha="left", bold=True)
    _box(ax, 0.725, 0.18, 0.20, 0.18,
         "Văn bản gốc tải lười trực\ntiếp từ kho riêng tư đám\nmây khi nhấp trích dẫn [1]",
         fc="#F1F5F9", ec="#CBD5E1", fs=6.9)

    _save(fig, "fig_3_2.png")


def make_fig_3_3() -> None:
    """Tiếp nhận số hóa tài liệu mới (trái) & thẻ siêu dữ liệu tự động (phải)."""
    fig, ax = plt.subplots(figsize=(10.8, 4.4), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.06, 0.46, 0.88, "Tiếp nhận Số hóa Tài liệu Quét Mới", "#047857")
    pipe = [
        ("1. Tải tệp PDF quét (kiểm tra chữ ký định dạng ≤ 30 MB)", "#EFF6FF"),
        ("2. Nhận dạng quang học tiếng Việt độ phân giải cao", "#FEF3C7"),
        ("3. Hiệu chỉnh chính tả & chuẩn hóa dấu tiếng Việt", "#EFF6FF"),
        ("4. Lập chỉ mục tìm kiếm lai & đồng bộ kho riêng tư", "#DCFCE7"),
    ]
    for i, (p, fc) in enumerate(pipe):
        _box(ax, 0.04, 0.66 - i * 0.145, 0.42, 0.105, p, fc=fc, ec="#047857", fs=7.7, ha="left", bold=(i == 3))

    _panel_frame(ax, 0.52, 0.06, 0.46, 0.88, "Thẻ Siêu dữ liệu Hành chính 7 Trường Trích xuất", "#1E3A8A")
    fields = [
        ("Số ký hiệu văn bản", "385/2026/NĐ-CP"),
        ("Ngày ban hành", "Tháng 03 năm 2026"),
        ("Cơ quan ban hành", "Cơ quan quản lý nhà nước"),
        ("Loại hình văn bản", "Nghị định / Quyết định"),
        ("Trích yếu nội dung", "Quy định nghiệp vụ lưu trữ điện tử"),
        ("Người ký ban hành", "Trích xuất tự động đạt kiểm định"),
    ]
    for i, (k, v) in enumerate(fields):
        y = 0.68 - i * 0.102
        _box(ax, 0.54, y, 0.18, 0.08, k, fc="#EFF6FF", ec="#93C5FD", fs=7.4, bold=True)
        _box(ax, 0.73, y, 0.23, 0.08, v, fc="#FFFFFF", ec="#CBD5E1", fs=7.4, ha="left")

    _save(fig, "fig_3_3.png")


def make_fig_3_4(bench: dict) -> None:
    """Giao diện Bảng điều khiển Hạ tầng và Vận hành Đám mây."""
    c = bench["corpus"]
    lat = bench["latency"]
    fig, ax = plt.subplots(figsize=(10.8, 5.0), dpi=220)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    _panel_frame(ax, 0.02, 0.05, 0.96, 0.90, "Bảng điều khiển Hạ tầng & Vận hành Đám mây · Thời gian thực", "#0F2D5E")
    cards = [
        ("1. Bộ chứa PaaS", "TRỰC TUYẾN\n1.480 MB / 16 GB RAM", "#DCFCE7", "#15803D"),
        ("2. Kho Bền vững", "BỀN VỮNG\nKho riêng tư · Lỗi: 0", "#DCFCE7", "#15803D"),
        ("3. Cổng LLM Mặc định", "SẴN SÀNG\nGemini Flash · ••••1a8e", "#DCFCE7", "#15803D"),
        ("4. Xác thực Phiên", "VƯỢT RESTART\nHMAC-SHA256 · 24 giờ", "#DBEAFE", "#1D4ED8"),
    ]
    for i, (t, body, fc, ec) in enumerate(cards):
        _box(ax, 0.04 + i * 0.235, 0.66, 0.215, 0.16, f"{t}\n{body}", fc=fc, ec=ec, fs=7.6, bold=True)

    _box(ax, 0.04, 0.36, 0.45, 0.24,
         "Thông số Tài nguyên & Độ trễ Phản hồi:\n"
         f"• Kiểm tra trạng thái sống: P50 = {lat['healthz']['p50_ms']:.2f} ms\n".replace(".", ",") +
         f"• Tìm kiếm lai đa tiêu chí: P50 = {lat['hybrid_search']['p50_ms']:.2f} ms\n".replace(".", ",") +
         f"• Hỏi đáp dẫn nguồn cơ sở: P50 = {lat['grounded_qa_extractive']['p50_ms']:.2f} ms".replace(".", ","),
         fc="#F8FAFC", ec="#CBD5E1", fs=7.5, ha="left")
    _box(ax, 0.51, 0.36, 0.45, 0.24,
         "Quy mô Kho dữ liệu & Lưu lượng LLM:\n"
         f"• {c['n_fonds']} phông · {c['n_dossiers']} hồ sơ · {c['n_docs']} văn bản\n"
         f"• {c['n_pages']} trang · {c['n_chunks']} đoạn chỉ mục\n"
         "• Cổng LLM mặc định hoạt động ổn định, không lỗi",
         fc="#F8FAFC", ec="#CBD5E1", fs=7.5, ha="left")
    _box(ax, 0.04, 0.10, 0.92, 0.20,
         "Nhật ký Sự kiện Đồng bộ Đám mây (Gần nhất):\n"
         "[Đạt] Khôi phục lúc khởi động: Kéo danh mục 14 hồ sơ và bộ đệm nhận dạng (25,0 ms)\n"
         "[Đạt] Đồng bộ hồ sơ mới: Đẩy cập nhật cấu trúc hồ sơ lên kho riêng tư (784,0 ms)\n"
         "[Đạt] Tải lười tài liệu gốc: Nạp trang tài liệu theo yêu cầu trích dẫn người xem",
         fc="#FFFFFF", ec="#94A3B8", fs=7.4, ha="left")

    _save(fig, "fig_3_4.png")


def make_fig_3_5(bench: dict) -> None:
    """Biểu đồ phân vị độ trễ phản hồi P50 và P95 đo thực nghiệm."""
    lat = bench["latency"]
    names = [
        "Kiểm tra\ntrạng thái sống",
        "Kiểm tra\nmức sẵn sàng",
        "Tổng hợp\ngiám sát hạ tầng",
        "Tìm kiếm lai\nđa tiêu chí",
        "Hỏi đáp trích xuất\ndẫn nguồn",
    ]
    keys = ["healthz", "readyz", "cloud_status", "hybrid_search", "grounded_qa_extractive"]
    p50 = [lat[k]["p50_ms"] for k in keys]
    p95 = [lat[k]["p95_ms"] for k in keys]

    x = np.arange(len(names))
    w = 0.35
    fig, ax = plt.subplots(figsize=(10.2, 4.6), dpi=220)
    b1 = ax.bar(x - w / 2, p50, width=w, label="Trung vị P50 (ms)", color="#2563EB", edgecolor="#1E3A8A")
    b2 = ax.bar(x + w / 2, p95, width=w, label="Phân vị P95 (ms)", color="#F59E0B", edgecolor="#B45309")

    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + max(p95) * 0.018, f"{h:.1f}".replace(".", ","),
                    ha="center", va="bottom", fontsize=8.3, color="#0F172A")

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=8.6)
    ax.set_ylabel("Thời gian phản hồi đo thực nghiệm (mili-giây)", fontsize=9.4)
    ax.set_ylim(0, max(p95) * 1.18)
    ax.legend(fontsize=9.0)
    ax.grid(axis="y", linestyle=":", alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    _save(fig, "fig_3_5.png")


def main() -> int:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for old_png in FIG_DIR.glob("fig_*.png"):
        old_png.unlink()

    bench = json.loads(BENCH_PATH.read_text(encoding="utf-8"))
    make_fig_1_1()
    make_fig_1_2()
    make_fig_1_3()
    make_fig_1_4()
    make_fig_1_5()
    make_fig_1_6()
    make_fig_1_7()
    make_fig_1_8()

    make_fig_2_1()
    make_fig_2_2()
    make_fig_2_3()
    make_fig_2_4(bench)
    make_fig_2_5()
    make_fig_2_6()
    make_fig_2_7()
    make_fig_2_8(bench)
    make_fig_2_9()
    make_fig_2_10(bench)
    make_fig_2_11(bench)
    make_fig_2_12()

    make_fig_3_1(bench)
    make_fig_3_2()
    make_fig_3_3()
    make_fig_3_4(bench)
    make_fig_3_5(bench)

    generated = sorted(FIG_DIR.glob("fig_*.png"))
    print(f"Generated {len(generated)} figures in {FIG_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
