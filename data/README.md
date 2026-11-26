# Dữ liệu

| Thư mục/tệp | Nội dung | Đưa lên git? |
|---|---|---|
| `raw/` | PDF gốc | Không (có họ tên người ký) |
| `ocr/` | Cache OCR theo trang `<doc_id>/pNNN.json` | Không, cho tới khi ẩn danh |
| `manifest.csv` | `doc_id`, nguồn, loại văn bản, số trang, md5, tập (`train`/`dev`/`test`) | Có |
| `gold/` | Chuẩn vàng do người duyệt: `ocr_gold/`, `fields.jsonl`, `questions.jsonl` | Có, sau khi ẩn danh |
| `processed/` | `pages.jsonl` (chữ từng trang đã làm sạch), `cards.jsonl` (thẻ thông tin bạc) của kho chính | Không |
| `uploads/<doc_id>/` | PDF tải lên qua web demo, **mỗi tệp một thư mục**: `source.pdf`, `meta.json` (tên gốc, thời điểm tải, md5, kích thước, số trang, số trang chưa OCR), `pages.jsonl`. Không thuộc manifest, không thuộc tập train/dev/test nào. Xem/xóa: giao diện web hoặc `python -m src.cli uploads [--delete DOC_ID]` | Không |

## Nguồn
- 17 PDF scan văn bản của Sở GD&ĐT Thái Nguyên, kế thừa từ `NLP.7z`, phiên bản trước của nhóm (Nông Thị Hương, repo `nthuong0145/NLP`). Năm PDF tự sinh trong bản nén bị loại.
- Nguồn bổ sung (chốt ở C1, 2026-10-26), tải bằng `scripts/fetch_public.py`, giãn 1,5 giây mỗi yêu cầu:
  - `cp_<docid>`: vanban.chinhphu.vn. Cột `ref_*` trong `sources.csv` lấy từ trang chi tiết (số ký hiệu, ngày, loại, cơ quan, người ký, trích yếu). Đây là **nhãn bạc đối chiếu**.
  - `tn_<id>`: thainguyen.gov.vn, mục chỉ đạo. Chỉ có tóm tắt.
  - Điều kiện sử dụng: ghi nguồn. Không phân phối lại PDF.
- `sources.csv`: URL, ngày tải, md5, số trang của từng PDF tải về.

## Quy tắc
- Chia tập **theo văn bản**. Một văn bản chỉ thuộc một tập.
- Nhãn do luật hoặc OCR sinh ra là **nhãn bạc**. Chỉ khi người duyệt (có trường `reviewed_by`) mới thành **vàng**. Bộ vàng được khóa bằng hash trước khi chỉnh mô hình.
