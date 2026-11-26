"""OCR theo trang bằng Tesseract 5 (`vie`): gom từ thành dòng, sắp thứ tự đọc hai cột, cache JSON theo trang.

Chạy từ gốc Du_an/:  python -m src.ocr [--split dev] [--docs id1,id2] [--only-scan] [--limit N]
"""
import argparse
import gc
import hashlib
import re
import json
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from src.config import MANIFEST_PATH, MODELS_DIR, OCR_DIR, RAW_DIR, SCALE
from src.preprocess import ALL_STEPS, preprocess, steps_id
from src.text import normalize_text

TESSDATA_DIR = MODELS_DIR / "tessdata"
# Chọn trên trang scan TRAIN (scripts/ocr_preprocess_eval.py, 2026-10-28). remove_red BẬT dù tỉ lệ âm tiết hợp lệ
# cả trang giảm ~1 điểm (trong nhiễu): con dấu đỏ đè khối chữ ký, không bỏ thì mất dòng chức vụ + họ tên người ký
# (cp_219934 tr. 8). deskew/denoise không giúp nên tắt.
DEFAULT_STEPS: tuple[str, ...] = ("remove_red", "gray", "flatten", "binarize")

TESS_LANG = "vie"
TESS_CONFIG = "--oem 1 --psm 3"
# Hai từ liền nhau cách xa hơn hệ số này × chiều cao dòng thì tách làm hai đoạn (hai cột bị gộp chung hàng)
GAP_FACTOR = 3.0
# Dòng rộng từ tỉ lệ này của vùng chữ trở lên là dòng chạy suốt trang.
# Không đặt thấp hơn: dòng quốc hiệu ở cột phải đã rộng khoảng 2/3 vùng chữ
SPAN_WIDTH_RATIO = 0.75
# Tâm dòng lệch tâm ảnh ít hơn tỉ lệ này của bề rộng ảnh là dòng căn giữa (tên loại, trích yếu)
CENTER_TOL = 0.05
CACHE_FORMAT = 1
SMALL_N_DOCS = 3


@dataclass
class OcrLine:
    text: str
    bbox: tuple[int, int, int, int]   # x0, y0, x1, y1 theo pixel của ảnh
    conf: float                       # trung bình độ tin cậy các từ, thang 0–1


def _merge_words(words: list[tuple]) -> OcrLine:
    """Gộp các từ (x0, y0, x1, y1, chữ, conf 0–100) thành một dòng."""
    text = normalize_text(" ".join(w[4] for w in words))
    bbox = (min(w[0] for w in words), min(w[1] for w in words),
            max(w[2] for w in words), max(w[3] for w in words))
    conf = sum(w[5] for w in words) / len(words) / 100
    return OcrLine(text, bbox, round(conf, 4))


def group_words(data: dict) -> list[OcrLine]:
    """Gom kết quả từng từ của `pytesseract.image_to_data` thành dòng.

    Hai từ trong cùng dòng Tesseract mà cách nhau quá GAP_FACTOR × chiều cao dòng thì tách thành
    hai dòng riêng, để `Số: …` (cột trái) và `Thái Nguyên, ngày …` (cột phải) không dính làm một.
    """
    rows: dict[tuple, list] = {}
    for i, word in enumerate(data["text"]):
        word = word.strip()
        conf = float(data["conf"][i])
        if not word or conf < 0:      # conf = -1 là dòng mô tả khối/đoạn, không phải từ
            continue
        x0, y0 = int(data["left"][i]), int(data["top"][i])
        x1, y1 = x0 + int(data["width"][i]), y0 + int(data["height"][i])
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        rows.setdefault(key, []).append((x0, y0, x1, y1, word, conf))
    lines = []
    for words in rows.values():
        words.sort(key=lambda w: w[0])
        height = float(np.median([w[3] - w[1] for w in words]))
        segment = [words[0]]
        for prev, cur in zip(words, words[1:]):
            if cur[0] - prev[2] > GAP_FACTOR * height:
                lines.append(_merge_words(segment))
                segment = []
            segment.append(cur)
        lines.append(_merge_words(segment))
    return lines


def _is_full_width(line: OcrLine, page_width: int, area_width: int) -> bool:
    x0, _, x1, _ = line.bbox
    centered = abs((x0 + x1) / 2 - page_width / 2) < CENTER_TOL * page_width
    return centered or (x1 - x0) >= SPAN_WIDTH_RATIO * area_width


def order_lines(lines: list[OcrLine], page_width: int) -> list[OcrLine]:
    """Sắp thứ tự đọc cho văn bản hành chính.

    Dòng chạy suốt trang hoặc căn giữa cắt trang thành các dải ngang. Trong một dải, dòng có tâm
    bên trái tâm ảnh thuộc cột trái, còn lại thuộc cột phải; đọc hết cột trái (trên xuống) rồi cột
    phải. Áp cho cả phần đầu (cơ quan | quốc hiệu) lẫn phần cuối (nơi nhận | chữ ký).
    """
    if not lines:
        return []
    area_width = max(l.bbox[2] for l in lines) - min(l.bbox[0] for l in lines)
    ordered, band = [], []

    def flush():
        left = [l for l in band if (l.bbox[0] + l.bbox[2]) / 2 < page_width / 2]
        right = [l for l in band if (l.bbox[0] + l.bbox[2]) / 2 >= page_width / 2]
        ordered.extend(sorted(left, key=lambda l: l.bbox[1]) + sorted(right, key=lambda l: l.bbox[1]))
        band.clear()

    for line in sorted(lines, key=lambda l: (l.bbox[1], l.bbox[0])):
        if _is_full_width(line, page_width, area_width):
            flush()
            ordered.append(line)
        else:
            band.append(line)
    flush()
    return ordered


def page_text(lines: list[OcrLine]) -> str:
    return "\n".join(l.text for l in lines)


def find_tesseract_cmd() -> str | None:
    """tesseract.exe: biến môi trường TESSERACT_CMD → PATH → chỗ cài mặc định của bộ UB Mannheim trên Windows."""
    import shutil

    cmd = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract")
    if cmd:
        return cmd
    for p in (Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
              Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe")):
        if p.exists():
            return str(p)
    return None


def find_tessdata_dir() -> Path | None:
    """Thư mục gói ngôn ngữ: TESSDATA_DIR → models/tessdata của dự án (có vie.traineddata bản tessdata_best)."""
    env = os.environ.get("TESSDATA_DIR")
    if env:
        return Path(env)
    return TESSDATA_DIR if (TESSDATA_DIR / f"{TESS_LANG}.traineddata").exists() else None


class TesseractEngine:
    """Gọi Tesseract qua pytesseract, có bước tiền xử lý ảnh (src.preprocess) trước khi nhận dạng."""
    name = "tesseract"

    def __init__(self, lang: str = TESS_LANG, config: str = TESS_CONFIG, cmd: str | None = None,
                 steps: tuple[str, ...] = DEFAULT_STEPS, tessdata: Path | None = None):
        import pytesseract
        os.environ.setdefault("OMP_THREAD_LIMIT", "1")
        cmd = cmd or find_tesseract_cmd()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
        self._pt = pytesseract
        self.steps = tuple(steps)
        tessdata = tessdata or find_tessdata_dir()
        if tessdata:
            # Qua biến môi trường (tiến trình con tesseract kế thừa): pytesseract trên Windows giữ nguyên
            # dấu nháy nếu truyền --tessdata-dir "…" trong config
            os.environ["TESSDATA_PREFIX"] = str(tessdata)
        self.config = config
        self.lang = lang
        self.version = f"{pytesseract.get_tesseract_version()}|{lang}|{config}|{steps_id(self.steps)}"

    def __call__(self, image: np.ndarray) -> list[OcrLine]:
        prepared = preprocess(image, self.steps).image if self.steps else image
        data = self._pt.image_to_data(prepared, lang=self.lang, config=self.config,
                                      output_type=self._pt.Output.DICT)
        return order_lines(group_words(data), prepared.shape[1])


def image_key(image: np.ndarray) -> str:
    h = hashlib.sha1(str(image.shape).encode())
    h.update(np.ascontiguousarray(image).tobytes())
    return h.hexdigest()


def machine_name() -> str:
    return f"{platform.system()} {platform.machine()} · {platform.processor() or '?'} · {os.cpu_count()} luồng"


def cache_path(doc_id: str, page_no: int, cache_dir: Path = OCR_DIR, part: str = "") -> Path:
    """part="" : cả trang (pNNN.json) · part="header": vùng đầu trang (pNNN_header.json)."""
    return cache_dir / doc_id / (f"p{page_no:03d}_{part}.json" if part else f"p{page_no:03d}.json")


def load_cached(doc_id: str, page_no: int, cache_dir: Path = OCR_DIR,
                key: str | None = None, engine_id: str | None = None, part: str = "") -> dict | None:
    """Đọc bản cache của một trang. Có `key`/`engine_id` thì chỉ nhận khi khớp (ảnh đổi hay engine đổi là bỏ)."""
    path = cache_path(doc_id, page_no, cache_dir, part)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        rec = json.load(f)
    if rec.get("format") != CACHE_FORMAT:
        return None
    if key is not None and rec["image_key"] != key:
        return None
    if engine_id is not None and rec["engine"] != engine_id:
        return None
    return rec


def ocr_page_cached(doc_id: str, page_no: int, image: np.ndarray, engine=None,
                    cache_dir: Path = OCR_DIR, part: str = "") -> dict:
    """OCR một trang (hoặc một phần trang, `part`), ưu tiên cache. `engine=None`: chỉ đọc cache (SCALE="small")."""
    key = image_key(image)
    engine_id = f"{engine.name}|{engine.version}" if engine is not None else None
    rec = load_cached(doc_id, page_no, cache_dir, key=key, engine_id=engine_id, part=part)
    if rec is not None:
        return rec | {"from_cache": True}
    if engine is None:
        raise RuntimeError(f"{doc_id} trang {page_no}: chưa có cache OCR mà không được gọi engine")
    t0 = time.perf_counter()
    lines = engine(image)
    seconds = time.perf_counter() - t0
    rec = {"format": CACHE_FORMAT, "doc_id": doc_id, "page_no": page_no, "image_key": key,
           "image_shape": list(image.shape[:2]), "engine": engine_id, "seconds": round(seconds, 3),
           "machine": machine_name(),
           "lines": [{"text": l.text, "bbox": list(l.bbox), "conf": l.conf} for l in lines]}
    path = cache_path(doc_id, page_no, cache_dir, part)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)
    tmp.replace(path)
    return rec | {"from_cache": False}


def latency_summary(records: list[dict]) -> dict:
    """P50/P95 thời gian OCR mỗi trang (giây), đo lúc chạy engine và lưu trong cache."""
    secs = [r["seconds"] for r in records]
    if not secs:
        return {"n": 0}
    return {"n": len(secs), "p50": float(np.percentile(secs, 50)), "p95": float(np.percentile(secs, 95)),
            "machines": sorted({r["machine"] for r in records})}


def _select_docs(split: str | None, docs: str | None) -> list[str]:
    import csv
    with open(MANIFEST_PATH, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if docs:
        wanted = set(docs.split(","))
        rows = [r for r in rows if r["doc_id"] in wanted]
    if split:
        rows = [r for r in rows if r["split"] == split]
    return [r["doc_id"] for r in rows]


_worker_engine = None


def _init_worker() -> None:
    """Mỗi tiến trình con một engine, một luồng Tesseract (tránh 10 tiến trình × nhiều luồng tranh CPU)."""
    global _worker_engine
    os.environ["OMP_THREAD_LIMIT"] = "1"
    _worker_engine = TesseractEngine()


HEADER_FRACTION = 0.35   # vùng đầu trang 1 chứa cơ quan, số ký hiệu, địa danh–ngày, tên loại


def header_crop(image: np.ndarray, fraction: float = HEADER_FRACTION) -> np.ndarray:
    return image[: int(image.shape[0] * fraction)]


# Khối chữ ký: dòng chức vụ in hoa ở nửa dưới trang; họ tên in nằm dưới dòng chức vụ CUỐI cùng
_SIGN_TITLE = re.compile(r"(THỦ TƯỚNG|BỘ TRƯỞNG|THỨ TRƯỞNG|CHỦ NHIỆM|CHỦ TỊCH|GIÁM Đ[ỐÔO]C|CHÁNH VĂN PH|TRƯỞNG BAN"
                         r"|^\W*(KT|TM|TL)\s*[./])")
SIGN_STEPS = ("remove_color", "gray", "flatten", "binarize")   # bỏ chữ ký tay (xanh/tím) + con dấu (đỏ)
SIGN_CONFIG = "--oem 1 --psm 6"                                  # một khối chữ đều
SIGN_DEPTH = 0.20                                               # vùng cắt cao 20% trang dưới dòng chức vụ
SIGN_LEFT_MARGIN = 150                                          # px ở 300 DPI, nới sang trái dòng chức vụ


def signature_box(rec: dict) -> tuple[int, int, int, int] | None:
    """(x0, y0, x1, y1) vùng họ tên người ký, tính từ bbox các dòng OCR của trang; None nếu không thấy khối chữ ký."""
    h, w = rec["image_shape"]
    titles = [l for l in rec["lines"] if l["bbox"][1] > 0.3 * h and _SIGN_TITLE.search(l["text"].upper())]
    if not titles:
        return None
    last = max(titles, key=lambda l: l["bbox"][3])
    block = [l for l in titles if last["bbox"][3] - l["bbox"][3] < 0.12 * h]
    x0 = max(0, min(l["bbox"][0] for l in block) - SIGN_LEFT_MARGIN)
    y0 = max(0, last["bbox"][3] - 10)
    return x0, y0, w, min(h, y0 + int(SIGN_DEPTH * h))


def signature_page(doc_id: str, cache_dir: Path = OCR_DIR) -> int | None:
    """Trang chứa khối chữ ký: trang OCR đầu tiên có "Nơi nhận" mà có dòng chức vụ, không có thì trang cuối có."""
    recs = [load_cached(doc_id, int(p.stem[1:]), cache_dir) for p in sorted((cache_dir / doc_id).glob("p[0-9][0-9][0-9].json"))]
    recs = [r for r in recs if r and signature_box(r)]
    if not recs:
        return None
    with_recipients = [r for r in recs if any(re.match(r"\W*N[ơo]i\s*nh", l["text"]) for l in r["lines"])]
    return (with_recipients or recs[-1:])[0]["page_no"]


_sign_engine = None


def _ocr_task(task: tuple) -> dict:
    """task = (doc_id, page_no) cả trang; (doc_id, page_no, "header") vùng đầu trang 1;
    (doc_id, page_no, "sign") khối họ tên người ký, đã xóa mực màu."""
    global _sign_engine
    from src.pdf_io import render_page

    doc_id, page_no, *rest = task
    part = rest[0] if rest else ""
    image = render_page(RAW_DIR / f"{doc_id}.pdf", page_no)
    engine = _worker_engine
    if part == "header":
        image = header_crop(image)
    elif part == "sign":
        x0, y0, x1, y1 = signature_box(load_cached(doc_id, page_no))
        image = image[y0:y1, x0:x1]
        if _sign_engine is None:
            _sign_engine = TesseractEngine(steps=SIGN_STEPS, config=SIGN_CONFIG)
        engine = _sign_engine
    rec = ocr_page_cached(doc_id, page_no, image, engine, part=part)
    return {k: rec[k] for k in ("doc_id", "page_no", "seconds", "machine", "from_cache")} | {"n_lines": len(rec["lines"])}


def ocr_document(pdf_path: Path, doc_id: str, engine=None, cache_dir: Path = OCR_DIR) -> list[dict]:
    """OCR một PDF bất kỳ (dùng cho tệp tải lên), cùng ba bước như kho chính, có cache:
    cả trang cho trang scan · vùng đầu trang 1 nếu là trang chữ số · khối họ tên người ký trên trang scan.
    `engine=None`: tự tạo TesseractEngine. Trả các bản ghi cache (có `from_cache`)."""
    from src.pdf_io import load_pages, render_page

    pages = load_pages(pdf_path)
    engine = engine or TesseractEngine()
    records = []
    for page in pages:
        if page.is_scan:
            records.append(ocr_page_cached(doc_id, page.page_no, render_page(pdf_path, page.page_no), engine,
                                           cache_dir))
            gc.collect()
    if pages and pages[0].layer_kind == "digital":
        image = header_crop(render_page(pdf_path, 1))
        records.append(ocr_page_cached(doc_id, 1, image, engine, cache_dir, part="header"))
    page_no = signature_page(doc_id, cache_dir)
    if page_no is not None:
        x0, y0, x1, y1 = signature_box(load_cached(doc_id, page_no, cache_dir))
        image = render_page(pdf_path, page_no)[y0:y1, x0:x1]
        sign_engine = (TesseractEngine(steps=SIGN_STEPS, config=SIGN_CONFIG)
                       if isinstance(engine, TesseractEngine) else engine)   # engine giả trong test
        records.append(ocr_page_cached(doc_id, page_no, image, sign_engine, cache_dir, part="sign"))
    gc.collect()
    return records


def main() -> None:
    from concurrent.futures import ProcessPoolExecutor

    from src.pdf_io import load_pages

    ap = argparse.ArgumentParser(description="OCR các trang PDF trong data/raw, có cache")
    ap.add_argument("--split", choices=["train", "dev", "test"])
    ap.add_argument("--docs", help="danh sách doc_id, cách nhau bằng dấu phẩy")
    ap.add_argument("--only-scan", action="store_true", help="bỏ trang có chữ thật")
    ap.add_argument("--limit", type=int, help="dừng sau N trang")
    ap.add_argument("--workers", type=int, default=1, help="số tiến trình song song")
    ap.add_argument("--headers", action="store_true",
                    help="chỉ OCR vùng đầu trang 1 của PDF chữ số (số/ngày đóng dạng ảnh khi ký số)")
    ap.add_argument("--signatures", action="store_true",
                    help="OCR lại khối họ tên người ký trên trang scan, sau khi xóa chữ ký tay và con dấu")
    args = ap.parse_args()

    doc_ids = _select_docs(args.split, args.docs)
    if SCALE == "small":
        doc_ids = doc_ids[:SMALL_N_DOCS]
    tasks = []
    for doc_id in doc_ids:
        if args.signatures:
            page_no = signature_page(doc_id)
            if page_no is not None:
                tasks.append((doc_id, page_no, "sign"))
            continue
        pages = load_pages(RAW_DIR / f"{doc_id}.pdf")
        if args.headers:
            if pages and pages[0].layer_kind == "digital":
                tasks.append((doc_id, 1, "header"))
            continue
        for page in pages:
            if not (args.only_scan and not page.is_scan):
                tasks.append((doc_id, page.page_no))
    tasks = tasks[:args.limit] if args.limit else tasks

    if SCALE == "small":
        print("SCALE=small: chỉ đọc cache, không gọi Tesseract")
        records = [r for r in (load_cached(t[0], t[1], part=t[2] if len(t) > 2 else "") for t in tasks)
                   if r is not None]
        print(f"Trang: {len(records)} có cache, {len(tasks) - len(records)} thiếu")
    else:
        engine = TesseractEngine()
        print(f"Engine: {engine.name} {engine.version} · máy: {machine_name()} · {args.workers} tiến trình · "
              f"{len(tasks)} trang")
        t0 = time.perf_counter()
        records = []
        with ProcessPoolExecutor(args.workers, initializer=_init_worker) as ex:
            for i, rec in enumerate(ex.map(_ocr_task, tasks), start=1):
                records.append(rec)
                if not rec["from_cache"] and (i % 20 == 0 or i == len(tasks)):
                    print(f"  {i}/{len(tasks)} trang · {time.perf_counter() - t0:.0f} s", flush=True)
        n_new = sum(not r["from_cache"] for r in records)
        print(f"Trang: {len(records)} (mới OCR {n_new}, từ cache {len(records) - n_new}) · "
              f"tổng {time.perf_counter() - t0:.0f} s")
    new = [r for r in records if not r.get("from_cache", True)]
    s = latency_summary(new)
    if s["n"]:
        print(f"Thời gian/trang (mỗi tiến trình): P50 = {s['p50']:.2f} s · P95 = {s['p95']:.2f} s · "
              f"máy: {'; '.join(s['machines'])}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
