"""Truy hồi theo nghĩa (chương 6, 8): mã hóa đoạn và câu hỏi thành vector bằng multilingual-e5-small.

- e5 cần tiền tố: câu hỏi "query: …", đoạn văn "passage: …" (mô hình được huấn luyện như vậy).
- Vector câu = trung bình các vector token (bỏ token đệm theo attention_mask), rồi chuẩn hóa L2 → tích vô hướng
  = cosine.
- Vector của các đoạn được cache ở models/dense/<băm>.npy, khóa = băm (mô hình, nội dung mọi đoạn): đổi chữ
  (làm sạch, sửa chữ OCR) thì mã hóa lại.
- Mã hóa cả kho dùng GPU nếu có; sau đó chuyển mô hình về CPU để nhường GPU cho LLM; truy vấn chạy CPU.
"""
import hashlib
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from src.config import MODELS_DIR

DENSE_MODEL = os.environ.get("DENSE_MODEL", "intfloat/multilingual-e5-small")
BGE_M3_MODEL = "BAAI/bge-m3"
RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
DENSE_MODEL_ALIASES = {
    "e5-small": "intfloat/multilingual-e5-small",
    "bge-m3": BGE_M3_MODEL,
}
DENSE_CACHE_DIR = MODELS_DIR / "dense"
MAX_TOKENS = 512
BATCH = 32


def resolve_dense_model(model_name: str) -> str:
    """Chuyển tên viết tắt (`e5-small`, `bge-m3`) sang mã mô hình HuggingFace đầy đủ."""
    return DENSE_MODEL_ALIASES.get(model_name, model_name)


@contextmanager
def _offline_hf_env(local_only: bool):
    """Đặt tạm biến offline trong khi nạp mô hình cục bộ, rồi khôi phục lại."""
    if not local_only:
        yield
        return
    prev = {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")}
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        yield
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _resolve_model_source(model_id: str, local_files_only: bool) -> str:
    """Ưu tiên đường dẫn snapshot cục bộ khi `local_files_only=True` để tránh kiểm tra mạng."""
    if not local_files_only or Path(model_id).exists():
        return model_id
    try:
        from huggingface_hub import snapshot_download

        return snapshot_download(repo_id=model_id, local_files_only=True)
    except Exception:
        return model_id


class E5Encoder:
    """Bộ mã hóa vector dày cho e5-small (mean pooling + tiền tố) và bge-m3 (CLS pooling, không tiền tố)."""

    def __init__(
        self,
        model_id: str = DENSE_MODEL,
        local_files_only: bool = True,
        use_prefix: bool | None = None,
        pooling: str = "auto",
    ):
        self.model_id = resolve_dense_model(model_id)
        self.local_files_only = local_files_only
        self.use_prefix = ("e5" in self.model_id.lower()) if use_prefix is None else use_prefix
        self.pooling = ("cls" if "bge" in self.model_id.lower() else "mean") if pooling == "auto" else pooling
        self.dim = 1024 if "bge-m3" in self.model_id.lower() else 384
        self.model = self.tokenizer = None
        self.device = "cpu"
        self._lock = threading.Lock()

    def is_downloaded(self) -> bool:
        from huggingface_hub import try_to_load_from_cache

        return isinstance(try_to_load_from_cache(self.model_id, "config.json"), str)

    def _load(self, device: str) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        if self.model is None:
            with _offline_hf_env(self.local_files_only):
                src = _resolve_model_source(self.model_id, self.local_files_only)
                self.tokenizer = AutoTokenizer.from_pretrained(src, local_files_only=self.local_files_only)
                self.model = AutoModel.from_pretrained(src, local_files_only=self.local_files_only).eval()
        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"
        if device != self.device:
            self.model.to(device)
            self.device = device

    def encode(self, texts: list[str], kind: str, device: str = "cpu", batch: int = BATCH) -> np.ndarray:
        """kind = "query" | "passage". Trả mảng (n, d) float32 đã chuẩn hóa L2."""
        import torch

        with self._lock:
            self._load(device)
            out = []
            for i in range(0, len(texts), batch):
                batch_texts = texts[i:i + batch]
                if self.use_prefix:
                    batch_texts = [f"{kind}: {t}" for t in batch_texts]
                enc = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=MAX_TOKENS,
                    return_tensors="pt",
                ).to(self.device)
                with torch.no_grad():
                    h = self.model(**enc).last_hidden_state
                if self.pooling == "cls":
                    v = h[:, 0]
                else:
                    mask = enc["attention_mask"].unsqueeze(-1).to(h.dtype)
                    v = (h * mask).sum(1) / mask.sum(1).clamp(min=1)
                out.append(torch.nn.functional.normalize(v, dim=-1).float().cpu().numpy())
            return np.concatenate(out) if out else np.zeros((0, self.dim), np.float32)

    def to_cpu(self) -> None:
        with self._lock:
            if self.model is not None and self.device != "cpu":
                import torch
                self.model.to("cpu")
                self.device = "cpu"
                torch.cuda.empty_cache()


def create_encoder(model_name: str = "e5-small", local_files_only: bool = True) -> E5Encoder:
    """Tạo bộ mã hóa theo tên ngắn (`e5-small`, `bge-m3`) hoặc mã HuggingFace."""
    return E5Encoder(model_id=resolve_dense_model(model_name), local_files_only=local_files_only)


class CrossEncoderReranker:
    """Bộ xếp hạng lại (cross-encoder) tùy chọn dùng `BAAI/bge-reranker-v2-m3`."""

    def __init__(self, model_id: str = RERANKER_MODEL, local_files_only: bool = True, max_length: int = MAX_TOKENS):
        self.model_id = model_id
        self.local_files_only = local_files_only
        self.max_length = max_length
        self.model = self.tokenizer = None
        self.device = "cpu"
        self._lock = threading.Lock()

    def is_downloaded(self) -> bool:
        from huggingface_hub import try_to_load_from_cache

        return isinstance(try_to_load_from_cache(self.model_id, "config.json"), str)

    def _load(self, device: str) -> None:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        if self.model is None:
            with _offline_hf_env(self.local_files_only):
                src = _resolve_model_source(self.model_id, self.local_files_only)
                self.tokenizer = AutoTokenizer.from_pretrained(src, local_files_only=self.local_files_only)
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    src, local_files_only=self.local_files_only
                ).eval()
        if device == "cuda" and not torch.cuda.is_available():
            device = "cpu"
        if device != self.device:
            self.model.to(device)
            self.device = device

    def score(self, query: str, texts: list[str], device: str = "cuda", batch: int = 16) -> np.ndarray:
        """Chấm điểm cặp (query, text) cho danh sách đoạn văn; trả mảng float32 1 chiều."""
        import torch

        if not texts:
            return np.zeros(0, dtype=np.float32)
        with self._lock:
            self._load(device)
            scores = []
            for i in range(0, len(texts), batch):
                pairs = [[query, t] for t in texts[i:i + batch]]
                enc = self.tokenizer(
                    pairs,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt",
                ).to(self.device)
                with torch.no_grad():
                    logits = self.model(**enc).logits.view(-1).float().cpu().numpy()
                scores.append(logits)
            return np.concatenate(scores)

    def to_cpu(self) -> None:
        with self._lock:
            if self.model is not None and self.device != "cpu":
                import torch
                self.model.to("cpu")
                self.device = "cpu"
                torch.cuda.empty_cache()


def default_encoder() -> "E5Encoder | None":
    """Bộ mã hóa nếu mô hình đã tải và không tắt bằng biến môi trường DENSE=0; ngược lại None (chỉ từ khóa)."""
    if os.environ.get("DENSE", "1") == "0":
        return None
    enc = E5Encoder()
    return enc if enc.is_downloaded() else None


def text_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _cache_path(model_id: str, cache_dir) -> "Path":
    return cache_dir / (re.sub(r"[^\w.-]+", "_", model_id) + ".npz")


def encode_corpus(encoder, texts: list[str], cache_dir=None) -> tuple[np.ndarray, dict]:
    """Vector của mọi đoạn. Cache THEO TỪNG ĐOẠN (khóa = băm nội dung đoạn): thêm một PDF chỉ mã hóa đoạn mới,
    sửa chữ một trang chỉ mã hóa lại đoạn của trang đó. Trả (ma trận theo thứ tự `texts`, thông tin)."""
    cache_dir = cache_dir or DENSE_CACHE_DIR
    path = _cache_path(encoder.model_id, cache_dir)
    cache: dict[str, np.ndarray] = {}
    if path.exists():
        with np.load(path) as z:
            cache = dict(zip(z["keys"].tolist(), z["vecs"]))
    keys = [text_key(t) for t in texts]
    todo = sorted({k for k in keys if k not in cache})
    info = {"n": len(texts), "n_new": len(todo), "seconds": 0.0, "device": None}
    if todo:
        by_key = {k: t for k, t in zip(keys, texts)}
        t0 = time.perf_counter()
        try:
            vecs = encoder.encode([by_key[k] for k in todo], "passage", device="cuda")
            info |= {"seconds": round(time.perf_counter() - t0, 1), "device": encoder.device}
        finally:
            encoder.to_cpu()
        cache.update(zip(todo, vecs))
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.stem}.tmp.{uuid.uuid4().hex[:8]}.npz")
        try:
            np.savez(tmp_path, keys=np.array(list(cache)), vecs=np.stack(list(cache.values())))
            os.replace(tmp_path, path)
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
    dim = next(iter(cache.values())).shape[0] if cache else getattr(encoder, "dim", 384)
    return (np.stack([cache[k] for k in keys]) if keys else np.zeros((0, dim), np.float32)), info
