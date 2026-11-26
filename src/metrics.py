"""Thước đo văn bản OCR: khoảng cách Levenshtein, CER/WER gộp trên cả bộ trang."""
import re
from collections.abc import Iterable, Sequence

from src.text import normalize_text

_ANY_SPACE = re.compile(r"\s+")


def levenshtein(a: Sequence, b: Sequence) -> int:
    """Số phép chèn/xóa/thay ít nhất để biến a thành b (quy hoạch động, giữ hai hàng)."""
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, start=1):
        cur = [i]
        for j, y in enumerate(b, start=1):
            cur.append(min(prev[j] + 1,              # xóa x
                           cur[j - 1] + 1,           # chèn y
                           prev[j - 1] + (x != y)))  # thay (hoặc khớp)
        prev = cur
    return prev[-1]


def normalize_for_eval(s: str) -> str:
    """NFC và gộp mọi khoảng trắng (kể cả xuống dòng) thành một dấu cách, áp cho CẢ tham chiếu lẫn bản OCR.

    Gộp xuống dòng để CER đo chữ, không đo cách ngắt dòng (nối dòng khi làm sạch không bị tính là lỗi).
    """
    return _ANY_SPACE.sub(" ", normalize_text(s)).strip()


def corpus_cer(pairs: Iterable[tuple[str, str]]) -> float:
    """CER gộp = tổng lỗi ký tự / tổng số ký tự tham chiếu. `pairs` là các cặp (tham chiếu, bản OCR)."""
    errors = total = 0
    for ref, hyp in pairs:
        ref, hyp = normalize_for_eval(ref), normalize_for_eval(hyp)
        errors += levenshtein(ref, hyp)
        total += len(ref)
    if total == 0:
        raise ValueError("tham chiếu rỗng, không tính được CER")
    return errors / total


def _keywords(s: str) -> list[str]:
    """Từ khóa để chấm trường văn bản: âm tiết chữ thường, bỏ dấu câu (đơn vị: âm tiết)."""
    return [w for w in re.findall(r"\w+", normalize_text(s).lower())]


def keyword_coverage(ref: str, hyp: str) -> float:
    """Tỉ lệ âm tiết của tham chiếu có mặt trong dự đoán (slide 9/46: trích yếu đạt khi ≥ 0,7)."""
    ref_words, hyp_words = _keywords(ref), set(_keywords(hyp))
    return sum(w in hyp_words for w in ref_words) / len(ref_words) if ref_words else 0.0


def keyword_f1(ref: str, hyp: str) -> float:
    """F1 trên túi âm tiết (đếm cả lặp) giữa tham chiếu và dự đoán (cơ quan: đạt khi ≥ 0,7)."""
    from collections import Counter

    r, h = Counter(_keywords(ref)), Counter(_keywords(hyp))
    common = sum((r & h).values())
    if common == 0:
        return 0.0
    p, rc = common / sum(h.values()), common / sum(r.values())
    return 2 * p * rc / (p + rc)


def corpus_wer(pairs: Iterable[tuple[str, str]]) -> float:
    """WER gộp = tổng lỗi từ / tổng số từ tham chiếu; từ = âm tiết/ký hiệu cách nhau bởi khoảng trắng."""
    errors = total = 0
    for ref, hyp in pairs:
        ref_words, hyp_words = normalize_for_eval(ref).split(), normalize_for_eval(hyp).split()
        errors += levenshtein(ref_words, hyp_words)
        total += len(ref_words)
    if total == 0:
        raise ValueError("tham chiếu rỗng, không tính được WER")
    return errors / total
