"""Tìm kiếm đoạn văn bản: BM25 (tự cài đặt, chương 5), TF-IDF âm tiết 1–2 gram, hợp nhất RRF.

Đơn vị token là ÂM TIẾT chữ thường (tokenize của src.text, giữ số ký hiệu "385/2026/nđ-cp" thành một token).
Truy vấn không dấu ("nghi dinh kiem soat") thì so với chỉ mục đã bỏ dấu của cùng các đoạn đó.
"""
import math
import re
from collections import Counter

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from src.chunking import Chunk
from src.text import expand_admin_terms, normalize_text, remove_diacritics, tokenize

_WORD = re.compile(r"\w")
BM25_K1 = 1.5        # chọn trên dev ở T12 khi có bộ câu hỏi vàng; hiện là giá trị mặc định phổ biến
BM25_B = 0.75
RRF_K = 60


def index_tokens(text: str, strip_accents: bool = False) -> list[str]:
    """Token để lập chỉ mục/truy vấn: chữ thường, bỏ token chỉ là dấu câu."""
    s = normalize_text(text).lower()
    if strip_accents:
        s = remove_diacritics(s)
    return [t for t in tokenize(s) if _WORD.search(t)]


def has_diacritics(text: str) -> bool:
    s = normalize_text(text)
    return remove_diacritics(s) != s


class BM25:
    """Okapi BM25: idf(t) = ln(1 + (N − df + 0,5)/(df + 0,5)); tf bão hòa theo k1, chuẩn hóa độ dài theo b."""

    def __init__(self, docs: list[list[str]], k1: float = BM25_K1, b: float = BM25_B):
        self.k1, self.b = k1, b
        self.tfs = [Counter(d) for d in docs]
        self.lens = np.array([len(d) for d in docs], dtype=float)
        self.avgdl = float(self.lens.mean()) if len(docs) else 0.0
        df = Counter(t for tf in self.tfs for t in tf)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.postings: dict[str, list[int]] = {}
        for i, tf in enumerate(self.tfs):
            for t in tf:
                self.postings.setdefault(t, []).append(i)

    def scores(self, query: list[str]) -> np.ndarray:
        out = np.zeros(len(self.tfs))
        for t in set(query):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i in self.postings[t]:
                f = self.tfs[i][t]
                norm = self.k1 * (1 - self.b + self.b * self.lens[i] / self.avgdl)
                out[i] += idf * f * (self.k1 + 1) / (f + norm)
        return out


def rrf(rankings: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    """Reciprocal Rank Fusion: điểm(d) = Σ_hệ 1 / (k + hạng của d trong hệ đó), hạng tính từ 1."""
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank)
    return fused


def _score_reranker(reranker, query: str, texts: list[str]) -> list[float]:
    """Chấm điểm reranker cho cả hàm callable (test CPU) và lớp CrossEncoderReranker."""
    if not texts:
        return []
    raw = reranker(query, texts) if callable(reranker) else reranker.score(query, texts)
    return [float(x) for x in raw]


class HybridIndex:
    """Chỉ mục lai trên danh sách đoạn: BM25 + TF-IDF (có dấu và không dấu) + vector dày (nếu có), hợp nhất RRF, tùy chọn reranker."""

    def __init__(self, chunks: list[Chunk], k1: float = BM25_K1, b: float = BM25_B, encoder=None, reranker=None):
        self.chunks = chunks
        self.reranker = reranker
        texts = [getattr(c, "index_text", c.text) for c in chunks]
        self._views = {}
        for strip in (False, True):
            toks = [index_tokens(t, strip) for t in texts]
            tfidf = TfidfVectorizer(analyzer=lambda x: x, ngram_range=(1, 1), sublinear_tf=True)
            grams = [t + [f"{a} {b_}" for a, b_ in zip(t, t[1:])] for t in toks]
            matrix = tfidf.fit_transform(grams) if chunks else None
            self._views[strip] = {"bm25": BM25(toks, k1, b), "tfidf": tfidf, "matrix": matrix}
        self.encoder, self.dense, self.dense_info = encoder, None, {}
        if encoder is not None and chunks:
            from src.dense import encode_corpus
            self.dense, self.dense_info = encode_corpus(encoder, texts)

    @property
    def methods(self) -> tuple[str, ...]:
        return ("bm25", "tfidf", "dense") if self.dense is not None else ("bm25", "tfidf")

    def dense_scores(self, query: str) -> np.ndarray:
        """Cosine giữa câu hỏi ("query: …") và mọi đoạn ("passage: …")."""
        return self.dense @ self.encoder.encode([query], "query")[0]

    def search(self, query: str, k: int = 10, methods: tuple[str, ...] | None = None,
               doc_ids: set[str] | None = None, pool: int = 50, extra_queries: list[str] | None = None,
               rerank_top_n: int | None = None, use_reranker: bool = True,
               return_parent: bool = False) -> list[dict]:
        """k đoạn tốt nhất; mỗi kết quả có chunk, điểm RRF, điểm và hạng của từng hệ. Lọc theo doc_ids nếu có.

        extra_queries: các cách diễn đạt khác của câu hỏi (vd. LLM viết lại); mỗi câu thêm một bảng xếp hạng BM25
        vào RRF, nên đoạn khớp với cách diễn đạt khác vẫn được kéo lên.
        rerank_top_n / use_reranker: nếu có `self.reranker` và `use_reranker=True`, chấm điểm lại top ứng viên RRF.
        return_parent: nếu True và đoạn có `parent_text`, đính kèm `parent_id` và `parent_text` vào kết quả.
        """
        methods = methods or self.methods
        strip = not has_diacritics(query)
        view = self._views[strip]
        q = index_tokens(query, strip)
        if not self.chunks or (not q and "dense" not in methods):
            return []
        allowed = np.ones(len(self.chunks), dtype=bool)
        if doc_ids is not None:
            allowed = np.array([c.doc_id in doc_ids for c in self.chunks])
        per_method = {}
        if "bm25" in methods and q:
            per_method["bm25"] = view["bm25"].scores(q)
        if "tfidf" in methods and q:
            qv = view["tfidf"].transform([q + [f"{a} {b_}" for a, b_ in zip(q, q[1:])]])
            per_method["tfidf"] = (view["matrix"] @ qv.T).toarray().ravel()
        if "dense" in methods and self.dense is not None:
            per_method["dense"] = self.dense_scores(query)
        all_extras = list(extra_queries or [])
        for exp in expand_admin_terms(query):
            if exp not in all_extras and exp != query:
                all_extras.append(exp)
        for j, extra in enumerate(all_extras):
            s2 = not has_diacritics(extra)
            eq = index_tokens(extra, s2)
            if eq:
                per_method[f"bm25_rw{j + 1}"] = self._views[s2]["bm25"].scores(eq)
        rankings, ranks = [], {}
        for name, s in per_method.items():
            s = np.where(allowed, s, -np.inf)
            order = [int(i) for i in np.argsort(-s, kind="stable")[:pool] if s[i] > 0]
            rankings.append(order)
            ranks[name] = {idx: r for r, idx in enumerate(order, start=1)}
        fused = rrf(rankings)
        rerank_scores: dict[int, float] = {}
        if self.reranker is not None and use_reranker and fused:
            cand_limit = rerank_top_n if rerank_top_n is not None else max(k * 3, 20)
            candidates = sorted(fused, key=lambda i: (-fused[i], i))[:cand_limit]
            scores = _score_reranker(self.reranker, query, [self.chunks[i].text for i in candidates])
            rerank_scores = dict(zip(candidates, scores))
            top = sorted(candidates, key=lambda i: (-rerank_scores[i], -fused[i], i))[:k]
        else:
            top = sorted(fused, key=lambda i: (-fused[i], i))[:k]

        results = []
        for i in top:
            c = self.chunks[i]
            item = {
                "chunk": c,
                "rrf": fused[i],
                **{f"{m}_score": float(per_method[m][i]) for m in per_method},
                **{f"{m}_rank": ranks[m].get(i) for m in per_method},
            }
            if i in rerank_scores:
                item["rerank_score"] = rerank_scores[i]
            if return_parent and getattr(c, "parent_text", ""):
                item["parent_id"] = c.parent_id
                item["parent_text"] = c.parent_text
            results.append(item)
        return results

    def query_tokens(self, query: str) -> tuple[list[str], bool]:
        strip = not has_diacritics(query)
        return index_tokens(query, strip), strip

    def idf(self, token: str, strip: bool) -> float:
        """idf BM25 của token; token không có trong kho (df = 0) nhận idf lớn nhất, không phải 0:
        từ khóa câu hỏi vắng mặt hoàn toàn là bằng chứng mạnh rằng câu hỏi nằm ngoài kho."""
        bm25 = self._views[strip]["bm25"]
        n = len(bm25.tfs)
        return bm25.idf.get(token, math.log(1 + (n + 0.5) / 0.5))
