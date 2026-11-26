"""Tiền xử lý ảnh trang scan trước khi OCR. Mỗi bước bật/tắt được để so trên dev; ghi lại bước đã làm.

Các bước (theo thứ tự):
  remove_red  bỏ mực đỏ/hồng (con dấu, chữ ký số đỏ) → trắng; GIỮ mực xanh (số, ngày viết tay)
  gray        ảnh xám
  flatten     làm phẳng nền: chia cho ảnh nền ước lượng bằng phép ĐÓNG hình thái học kích thước lớn
              (khử giấy ố vàng, chỗ sáng tối không đều mà ngưỡng toàn cục không xử lý được)
  deskew      xoay ảnh theo góc làm phương sai tổng hàng điểm đen lớn nhất (dòng chữ nằm ngang), |góc| ≤ 5°
  denoise     lọc trung vị 3×3 (chấm nhiễu nhỏ)
  binarize    nhị phân hóa Otsu (sau flatten thì nền đã phẳng nên ngưỡng toàn cục dùng được)
"""
import time
from dataclasses import dataclass, field

import cv2
import numpy as np

PREPROCESS_VERSION = "1"
ALL_STEPS = ("remove_red", "remove_color", "gray", "flatten", "deskew", "denoise", "binarize")
COLOR_MIN_SAT = 60
FLATTEN_KERNEL = 51          # px ở 300 DPI, lớn hơn nét chữ (~5–8 px) để phép đóng xóa hết chữ, chỉ còn nền
MAX_SKEW_DEG = 5.0
SKEW_STEP_DEG = 0.25
RED_MIN_SAT, RED_MIN_VAL = 70, 60


@dataclass
class PreprocessResult:
    image: np.ndarray                    # ảnh xám/nhị phân (H, W) uint8, hoặc RGB nếu không chạy bước gray
    steps: list[str] = field(default_factory=list)
    skew_deg: float = 0.0
    seconds: float = 0.0


def remove_red(rgb: np.ndarray) -> np.ndarray:
    """Đổi điểm ảnh đỏ/hồng đủ đậm thành trắng. Màu đỏ quanh hue 0 nên lấy cả hai đầu thang HSV (0–10, 160–180)."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    mask = ((h <= 10) | (h >= 160)) & (s >= RED_MIN_SAT) & (v >= RED_MIN_VAL)
    out = rgb.copy()
    out[mask] = 255
    return out


def remove_color(rgb: np.ndarray) -> np.ndarray:
    """Đổi MỌI điểm ảnh có màu (độ bão hòa cao) thành trắng, chỉ giữ mực đen/xám: dùng cho khối chữ ký,
    nơi chữ ký tay (mực xanh/tím) và con dấu (đỏ) đè lên dòng họ tên in (mực đen)."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = (hsv[..., 1] >= COLOR_MIN_SAT) & (hsv[..., 2] >= RED_MIN_VAL)
    out = rgb.copy()
    out[mask] = 255
    return out


def flatten_background(gray: np.ndarray, kernel: int = FLATTEN_KERNEL) -> np.ndarray:
    """gray / nền × 255. Phép đóng (giãn rồi co) với phần tử cấu trúc lớn hơn nét chữ xóa chữ tối, còn lại nền."""
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel, kernel))
    background = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, k)
    return cv2.divide(gray, background, scale=255)


def estimate_skew(gray: np.ndarray, max_deg: float = MAX_SKEW_DEG, step: float = SKEW_STEP_DEG) -> float:
    """Góc nghiêng (độ) theo phương pháp chiếu ngang: dòng chữ nằm ngang thì tổng điểm đen theo hàng
    dao động mạnh nhất (hàng chữ / hàng trắng xen kẽ). Thử trên ảnh thu nhỏ 1/4 cho nhanh."""
    small = cv2.resize(gray, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    ink = (small < 128).astype(np.float32)
    h, w = ink.shape
    best, best_score = 0.0, -1.0
    for deg in np.arange(-max_deg, max_deg + 1e-9, step):
        m = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
        rot = cv2.warpAffine(ink, m, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)
        score = float(np.var(rot.sum(axis=1)))
        if score > best_score:
            best, best_score = float(deg), score
    return best


def rotate(gray: np.ndarray, deg: float) -> np.ndarray:
    h, w = gray.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    return cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)


def preprocess(rgb: np.ndarray, steps: tuple[str, ...] = ALL_STEPS) -> PreprocessResult:
    """Chạy các bước theo thứ tự cố định của ALL_STEPS (bỏ qua bước không có trong `steps`)."""
    t0 = time.perf_counter()
    img, done, skew = rgb, [], 0.0
    for step in ALL_STEPS:
        if step not in steps:
            continue
        if step == "remove_red" and img.ndim == 3:
            img = remove_red(img)
        elif step == "remove_color" and img.ndim == 3:
            img = remove_color(img)
        elif step == "gray" and img.ndim == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        elif step == "flatten" and img.ndim == 2:
            img = flatten_background(img)
        elif step == "deskew" and img.ndim == 2:
            skew = estimate_skew(img)
            if abs(skew) >= SKEW_STEP_DEG:
                img = rotate(img, skew)
        elif step == "denoise" and img.ndim == 2:
            img = cv2.medianBlur(img, 3)
        elif step == "binarize" and img.ndim == 2:
            _, img = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            continue
        done.append(step)
    return PreprocessResult(img, done, skew, round(time.perf_counter() - t0, 3))


def steps_id(steps: tuple[str, ...]) -> str:
    """Chuỗi định danh cấu hình tiền xử lý, đưa vào khóa cache OCR (đổi cấu hình → OCR lại)."""
    return f"pre{PREPROCESS_VERSION}:" + "+".join(s for s in ALL_STEPS if s in steps) if steps else "raw"
