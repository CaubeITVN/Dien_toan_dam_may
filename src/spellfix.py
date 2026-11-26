"""Căn chỉnh chữ sau OCR: tách âm tiết dính và sửa dấu bằng mô hình bigram âm tiết + Viterbi (chương 3–4).

Với mỗi dòng, mỗi từ chữ cái w có các ứng viên:
  giữ nguyên      chi phí kênh 0
  đổi dấu         các âm tiết trong từ điển có CÙNG dạng bỏ dấu ("hoc" → học, hóc, hộc…), chi phí ACCENT_COST
  tách âm tiết    cắt w thành 2–3 âm tiết trong từ điển ("kếhoạch" → kế hoạch), chi phí SPLIT_COST mỗi chỗ cắt
Chọn chuỗi ứng viên cực đại  Σ log P_LM(âm tiết | âm tiết trước) − chi phí kênh  (Viterbi trên trạng thái =
âm tiết cuối). P_LM: bigram nội suy với unigram cộng-một (λ = LM_LAMBDA khi bigram trước đã gặp).

KHÔNG sửa: token có chữ số, từ viết tắt (không có ứng viên vì dạng bỏ dấu không phải âm tiết trong từ điển),
và từ viết hoa chữ đầu ở giữa câu (tên riêng) chỉ được sửa khi KHÔNG có trong từ điển (chi phí NAME_COST).
Mọi thay đổi trả về dạng (trước, sau) để ghi nhật ký làm sạch.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache

from src.text import normalize_text, remove_diacritics

SPELLFIX_VERSION = "5"     # 5: lưu kèm danh bạ người ký
# Lỗi gõ đo được trong kho học: "thưc" 0,04%, "hiên" 0,06% so với "thực", "hiện"; từ thật hiếm như "chinh"
# (chinh phục) ≈ 0,5% → ngưỡng 0,2% loại lỗi gõ mà giữ từ hiếm
WEAK_RATIO = 0.002
ACCENT_COST = 4.0        # log-đơn vị; đổi dấu phải làm câu "dễ hơn" e^4 ≈ 55 lần mới được chọn
SPLIT_COST = 2.0
NAME_COST = 8.0          # thêm cho từ viết hoa chữ đầu giữa câu (tên riêng) đang có trong từ điển
LM_LAMBDA = 0.7
MIN_COUNT = 2            # âm tiết gặp ít hơn số này trong kho học thì không đưa vào từ điển
MAX_VARIANTS = 8
_TOKEN = re.compile(r"[^\W\d_]+|\d[\w/.,\-]*|\s+|.", re.UNICODE)


@dataclass
class SyllableLM:
    unigram: Counter
    bigram: Counter
    n_lines: int = 0                                              # số lần "<s>" (đầu dòng)
    by_key: dict[str, list[str]] = field(default_factory=dict)    # dạng bỏ dấu → âm tiết, nhiều trước
    total: int = 0

    @classmethod
    def train(cls, texts: list[str], min_count: int = MIN_COUNT) -> "SyllableLM":
        uni, bi, n_lines = Counter(), Counter(), 0
        for t in texts:
            for line in normalize_text(t).split("\n"):
                syl = [s.lower() for s in re.findall(r"[^\W\d_]+", line)]
                if not syl:
                    continue
                n_lines += 1
                uni.update(syl)
                bi.update(zip(["<s>"] + syl, syl))
        uni = Counter({s: c for s, c in uni.items() if c >= min_count})
        # Lỗi gõ trong kho học ("thưc" 8 lần bên cạnh "thực" 20 686 lần) kéo theo bigram sai ("hiên chỉ"):
        # bỏ âm tiết hiếm hơn WEAK_RATIO lần biến thể cùng dạng bỏ dấu phổ biến nhất, bỏ luôn bigram chứa nó
        top = Counter()
        for s, c in uni.items():
            k = remove_diacritics(s)
            top[k] = max(top[k], c)
        uni = Counter({s: c for s, c in uni.items() if c >= WEAK_RATIO * top[remove_diacritics(s)]})
        bi = Counter({(a, b): c for (a, b), c in bi.items() if (a == "<s>" or a in uni) and b in uni})
        by_key: dict[str, list[str]] = {}
        for s, _ in uni.most_common():
            by_key.setdefault(remove_diacritics(s), []).append(s)
        return cls(uni, bi, n_lines, by_key, sum(uni.values()))

    def logp(self, prev: str, cur: str) -> float:
        """log P(cur | prev) = log(λ·c(prev,cur)/c(prev) + (1−λ)·P_add1(cur)); prev chưa gặp → chỉ unigram."""
        p_uni = (self.unigram.get(cur, 0) + 1) / (self.total + len(self.unigram) + 1)
        c_prev = self.n_lines if prev == "<s>" else self.unigram.get(prev, 0)
        if c_prev:
            return math.log(LM_LAMBDA * self.bigram.get((prev, cur), 0) / c_prev + (1 - LM_LAMBDA) * p_uni)
        return math.log(p_uni)

    def variants(self, syl: str) -> list[str]:
        return self.by_key.get(remove_diacritics(syl), [])[:MAX_VARIANTS]


def _restore_case(original: str, candidate: str) -> str:
    """Áp kiểu chữ hoa/thường của từ gốc lên ứng viên (độ dài bằng nhau nếu bỏ dấu cách)."""
    if original.isupper():
        return candidate.upper()
    out, i = [], 0
    for ch in candidate:
        if ch == " ":
            out.append(ch)
            continue
        out.append(ch.upper() if i < len(original) and original[i].isupper() else ch)
        i += 1
    return "".join(out)


def tone_style_key(syl: str) -> tuple[str, tuple[str, ...]]:
    """(chữ cái gốc, các dấu đã sắp xếp): "ủy" và "uỷ", "hòa" và "hoà" (kiểu đặt dấu cũ/mới) cho cùng khóa."""
    import unicodedata

    d = unicodedata.normalize("NFD", syl)
    return "".join(c for c in d if not unicodedata.combining(c)), tuple(sorted(c for c in d if unicodedata.combining(c)))


def candidates(lm: SyllableLM, word: str, sentence_start: bool) -> list[tuple[tuple[str, ...], float]]:
    """[(chuỗi âm tiết chữ thường, chi phí kênh)] của một từ."""
    low = word.lower()
    known = low in lm.unigram
    is_name = word[0].isupper() and not word.isupper() and not sentence_start
    out = [((low,), 0.0)]
    if is_name and known:
        return out                       # tên riêng đã biết: giữ nguyên
    extra = NAME_COST if is_name else 0.0
    style = tone_style_key(low)
    for v in lm.variants(low):
        if v != low and tone_style_key(v) != style:     # không đổi qua lại giữa hai kiểu đặt dấu
            out.append(((v,), ACCENT_COST + extra))
    if not known and len(remove_diacritics(low)) >= 3:
        for parts, n_changed in _splits(lm, low):
            out.append((parts, SPLIT_COST * (len(parts) - 1) + ACCENT_COST * n_changed + extra))
    return out


def _splits(lm: SyllableLM, low: str, max_parts: int = 3) -> list[tuple[tuple[str, ...], int]]:
    """Mọi cách cắt `low` thành 2..max_parts âm tiết có trong từ điển (giữ dấu, hoặc đổi dấu từng phần)."""
    @lru_cache(maxsize=None)
    def rec(s: str, k: int) -> tuple:
        res = []
        if s in lm.unigram:
            res.append(((s,), 0))
        res += [((v,), 1) for v in lm.variants(s)[:2] if v != s]
        if k > 1:
            for i in range(1, len(s)):
                heads = [(s[:i], 0)] if s[:i] in lm.unigram else [(v, 1) for v in lm.variants(s[:i])[:2]]
                for h, c in heads:
                    for tail, ct in rec(s[i:], k - 1):
                        res.append(((h,) + tail, c + ct))
        return tuple(res)

    return [(p, c) for p, c in rec(low, max_parts) if len(p) >= 2][:12]


def fix_line(lm: SyllableLM, line: str) -> tuple[str, list[tuple[str, str]]]:
    """Viterbi trên các từ chữ cái của dòng; trả (dòng đã sửa, các cặp (từ cũ, từ mới))."""
    toks = _TOKEN.findall(line)
    word_idx = [i for i, t in enumerate(toks) if t[0].isalpha()]
    if not word_idx:
        return line, []
    cands, starts = [], []
    for j, i in enumerate(word_idx):
        prev_tok = toks[word_idx[j - 1] + 1:i] if j else toks[:i]
        start = j == 0 or any(re.search(r"[.:;!?]", t) for t in prev_tok)
        starts.append(start)
        cands.append(candidates(lm, toks[i], start))
    # best[state] = (điểm, đường đi); state = âm tiết cuối của ứng viên đã chọn
    best = {"<s>": (0.0, [])}
    for cs in cands:
        nxt: dict[str, tuple[float, list]] = {}
        for prev, (score, path) in best.items():
            for parts, cost in cs:
                s, p = score - cost, prev
                for syl in parts:
                    s += lm.logp(p, syl)
                    p = syl
                if p not in nxt or s > nxt[p][0]:
                    nxt[p] = (s, path + [parts])
        best = nxt
    path = max(best.values(), key=lambda x: x[0])[1]
    changes = []
    for i, parts in zip(word_idx, path):
        new = _restore_case(toks[i], " ".join(parts))
        # Âm tiết dính liền chữ số ("số4899/BGD&ĐT", "ngày17/10"): chèn dấu cách, KHÔNG đụng vào chữ số
        if i + 1 < len(toks) and toks[i + 1][0].isdigit() and parts[-1] in lm.unigram and toks[i].islower():
            new += " "
        if new != toks[i]:
            changes.append((toks[i], new if new.rstrip() != toks[i] else toks[i] + "␣"))
            toks[i] = new
    return "".join(toks), changes


LEGAL_METADATA = ("th1nhng0/vietnamese-legal-documents", "data/metadata.parquet")   # CC BY 4.0
LEGAL_COLUMNS = ["title", "co_quan_ban_hanh", "chuc_danh", "nguoi_ky"]


def training_texts(pages: list[dict], train_ids: set[str], exclude_numbers: set[str]) -> tuple[list[str], dict]:
    """Kho học cho mô hình: (1) trang CHỮ SỐ của văn bản train; (2) trích yếu/cơ quan/chức danh/người ký của bộ
    vietnamese-legal-documents (đã có trong bộ nhớ đệm HF, không tải mới), BỎ dòng có số ký hiệu trùng văn bản
    trong kho của dự án (tránh rò rỉ khi đo trên dev/test)."""
    from src.extract_rules import normalize_doc_number

    texts = [p["text"] for p in pages if p["doc_id"] in train_ids and p["source"] == "digital"]
    info = {"train_digital_pages": len(texts), "legal_rows": 0, "legal_rows_excluded": 0, "signer_names": []}
    try:
        import pandas as pd
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(LEGAL_METADATA[0], LEGAL_METADATA[1], repo_type="dataset", local_files_only=True)
        df = pd.read_parquet(path, columns=LEGAL_COLUMNS + ["so_ky_hieu"])
        mask = df["so_ky_hieu"].fillna("").map(normalize_doc_number).isin(exclude_numbers)
        info["legal_rows_excluded"] = int(mask.sum())
        df = df[~mask]
        info["legal_rows"] = len(df)
        for col in LEGAL_COLUMNS:
            texts.extend(df[col].dropna().astype(str).tolist())
        # Danh bạ người ký (họ tên đầy đủ, có dấu) để kiểm họ tên đọc bằng OCR — KHÔNG dùng để sửa tên
        info["signer_names"] = sorted({normalize_text(n).strip() for v in df["nguoi_ky"].dropna()
                                       for n in str(v).split(";") if len(n.split()) >= 2})
    except Exception as e:      # không có bộ dữ liệu trong bộ nhớ đệm: chỉ học từ trang chữ số
        info["legal_error"] = repr(e)
    return texts, info


def load_or_train(pages: list[dict], train_ids: set[str], exclude_numbers: set[str], cache_path) -> SyllableLM:
    """Đọc mô hình đã lưu (pickle) nếu cùng SPELLFIX_VERSION, ngược lại học lại và lưu."""
    import pickle

    if cache_path.exists():
        with open(cache_path, "rb") as f:
            saved = pickle.load(f)
        if saved.get("version") == SPELLFIX_VERSION:
            return saved["lm"]
    texts, info = training_texts(pages, train_ids, exclude_numbers)
    lm = SyllableLM.train(texts)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump({"version": SPELLFIX_VERSION, "lm": lm, "info": info}, f)
    return lm


def fix_text(lm: SyllableLM, text: str) -> tuple[str, list[tuple[str, str]]]:
    lines, changes = [], []
    for line in text.split("\n"):
        fixed, ch = fix_line(lm, line)
        lines.append(fixed)
        changes += ch
    return "\n".join(lines), changes
