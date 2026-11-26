"""Cấu hình chung: đường dẫn, quy mô chạy, hạt giống."""
import os
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"          # PDF gốc (gitignore)
OCR_DIR = DATA_DIR / "ocr"          # cache OCR theo trang (gitignore)
GOLD_DIR = DATA_DIR / "gold"        # chuẩn vàng do người duyệt
MANIFEST_PATH = DATA_DIR / "manifest.csv"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
RESULTS_DIR = REPORTS_DIR / "results"

# "small": vài văn bản, không gọi engine OCR (chỉ đọc cache); "full": cả kho
SCALE = os.environ.get("SCALE", "full")
# Chỉ bật sau điểm dừng C2, đo test MỘT LẦN
EVAL_TEST = False
SEEDS = [13, 42, 2024]


def set_seed(seed: int) -> None:
    """Đặt seed cho random, numpy và torch (nếu có cài)."""
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
    except ImportError:
        return
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False
