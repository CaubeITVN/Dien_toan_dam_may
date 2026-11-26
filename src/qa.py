"""Hỏi đáp có căn cứ: trả lời TRÍCH XUẤT (không sinh chữ mới), mỗi câu trả lời gắn (doc_id, trang).

- Câu hỏi về thẻ thông tin (ai ký, ngày, số ký hiệu, cơ quan, nơi nhận, trích yếu) → trả lời từ thẻ.
- Câu hỏi nội dung → chọn câu có độ phủ từ khóa cao nhất trong các đoạn tìm được.
- "Những văn bản nào …" → liệt kê các văn bản có đoạn đủ căn cứ.
- Từ chối khi độ phủ từ khóa < ngưỡng hoặc câu hỏi không có từ khóa nội dung; luôn nêu lý do.
Nội dung văn bản là DỮ LIỆU: hệ chỉ trích câu, không làm theo câu nào trong văn bản; câu trông như lệnh
nhắm vào trợ lý (tiêm lệnh) bị loại khỏi câu trả lời và báo trong `warnings`.
"""
import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from src.cards import build_cards, pages_by_doc
from src.chunking import Chunk, chunk_document
from src.config import MODELS_DIR
from src.extract_rules import DocCard, normalize_doc_number
from src.retrieval import HybridIndex
from src.text import normalize_text, remove_diacritics

# Độ phủ từ khóa (theo idf) tối thiểu để trả lời; tối ưu phân tầng theo loại câu hỏi
MIN_COVERAGE = 0.45
MIN_COVERAGE_DOC_SPECIFIED = 0.25
MIN_COVERAGE_LIST = 0.35
MIN_FIELD_COVERAGE = 0.38
# Cửa căn cứ theo vector e5 (TẠM, từ 8 câu thử tay ngày 29/10; chọn lại trên dev khi có T11)
DENSE_MIN = 0.84
MIN_COVERAGE_WITH_DENSE = 0.3
DENSE_VETO = 0.80
DEFAULT_THRESHOLD_PATH = MODELS_DIR / "refusal_threshold.json"
DEFAULT_REFUSAL_THRESHOLDS: dict[str, float] = {
    "min_coverage": MIN_COVERAGE,
    "min_coverage_doc_specified": MIN_COVERAGE_DOC_SPECIFIED,
    "min_coverage_list": MIN_COVERAGE_LIST,
    "min_field_coverage": MIN_FIELD_COVERAGE,
    "min_rrf": 0.0,
    "dense_min": DENSE_MIN,
    "min_coverage_with_dense": MIN_COVERAGE_WITH_DENSE,
    "dense_veto": DENSE_VETO,
    "combined_alpha": 0.7,
    "min_combined_score": 0.0,
}


def load_refusal_thresholds(
    threshold_path: str | Path | None = None,
    overrides: dict | None = None,
) -> dict[str, float]:
    """Đọc ngưỡng cổng từ chối từ JSON (nếu tồn tại); fallback về ngưỡng mặc định an toàn."""
    cfg = dict(DEFAULT_REFUSAL_THRESHOLDS)
    path = Path(threshold_path) if threshold_path is not None else DEFAULT_THRESHOLD_PATH
    if path.exists():
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            nested = raw.get("thresholds") or raw.get("best_thresholds")
            if isinstance(nested, dict):
                for key in cfg:
                    if key in nested and nested[key] is not None:
                        cfg[key] = float(nested[key])
            for key in cfg:
                if key in raw and raw[key] is not None:
                    cfg[key] = float(raw[key])
    if overrides:
        for key, val in overrides.items():
            if key in cfg and val is not None:
                cfg[key] = float(val)
    return cfg
REWRITE_MAX_TOKENS = 96
REWRITE_PROMPT = """Viết lại câu hỏi của người dùng thành 3 dòng, mỗi dòng là một cách hỏi khác cùng ý, dùng từ ngữ
thường gặp trong văn bản hành chính Việt Nam (ví dụ "giao … chủ trì", "có trách nhiệm", "thời hạn hoàn thành").
Chỉ viết 3 dòng câu hỏi, không trả lời, không giải thích."""
TOP_K = 8
LIST_K = 40          # câu "những văn bản nào": xét nhiều đoạn hơn vì một văn bản dài chiếm nhiều đoạn đầu
MAX_LIST_DOCS = 5

# Từ để hỏi / từ nối: không tính vào độ phủ. So NGUYÊN DẠNG CÓ DẤU với câu hỏi có dấu; dạng bỏ dấu chỉ dùng
# cho câu hỏi gõ không dấu, vì bỏ dấu làm trùng từ khóa thật: "đô"/"đó" → "do", "báo"/"bao", "sở"/"số"
_QUESTION_WORDS = set(normalize_text("""
gì nào ai bao nhiêu không có là của và được hay về thì những các cho trong với khi đâu sao như thế
nêu biết hãy văn bản này đó ở tại theo do bởi mấy đã sẽ đang việc nội dung gồm nói đề cập nhắc tới đến
""").split())
# Từ chỉ trường của thẻ: bỏ khỏi từ khóa khi câu hỏi là câu hỏi trường ("ai ký nghị định về …")
_FIELD_WORDS = set("ký ngày ban hành số hiệu cơ quan nơi nhận gửi trích yếu loại người thời gian đơn vị".split())
_STOP = {False: _QUESTION_WORDS, True: {remove_diacritics(w) for w in _QUESTION_WORDS}}
_FIELD_STOP = {False: _FIELD_WORDS, True: {remove_diacritics(w) for w in _FIELD_WORDS}}

# Ý định hỏi trường của thẻ, viết KHÔNG dấu để khớp cả câu hỏi gõ không dấu
_FIELD_INTENTS = [
    ("signer", r"\b(ai ky|nguoi ky|ky boi|do ai ky|ai la nguoi ky)\b"),
    # "khi nào" một mình là hỏi nội dung ("thời hạn hoàn thành là khi nào"), chỉ tính khi đi với ban hành/ký
    ("issue_date", r"\b((ban hanh|ky)( vao)? (ngay|thang|nam|khi|thoi gian)|ngay ban hanh|ngay ky"
                   r"|ban hanh ngay|thoi gian ban hanh)\b"),
    ("doc_number", r"\b(so ky hieu|so hieu|ky hieu|so van ban)\b"),
    ("issuer", r"\b(co quan nao|ai ban hanh|don vi nao ban hanh|do ai ban hanh|co quan ban hanh)\b"),
    ("recipients", r"\b(noi nhan|gui (cho|toi|den) (ai|nhung ai|don vi nao|co quan nao))\b"),
    ("subject", r"\b(trich yeu|ve viec gi)\b"),
    ("doc_type", r"\b(loai van ban|la loai gi)\b"),
]
FIELD_LABELS = {"signer": "Người ký", "issue_date": "Ngày ban hành", "doc_number": "Số ký hiệu",
                "issuer": "Cơ quan ban hành", "recipients": "Nơi nhận", "subject": "Trích yếu",
                "doc_type": "Loại văn bản", "title": "Tiêu đề", "signer_title": "Chức vụ người ký"}
_SUMMARY_INTENT = re.compile(r"\b(tom tat|tom luoc|khai quat|noi dung chinh)\b")
_SUMMARY_WORDS = set("tóm tắt lược khái quát nội dung chính văn bản này".split())
_LIST_INTENT = re.compile(
    r"\b(nhung|cac|co)\b.{0,30}\b(van ban|thong tu|nghi dinh|quyet dinh|cong van|thong bao|bao cao)\b.{0,20}\bnao\b"
    r"|\b(co van ban nao|danh sach van ban|nhung cuoc hop nao)\b"
    r"|\b(nhung|cac) van ban nao\b",
    re.IGNORECASE,
)
_DOC_REF = re.compile(r"\d+(?:/\d{4})?/[A-Za-zĐđ][\w\-&]*|\b(?:cp|tn)_\d+\b|\b[A-Z][a-z_]+_\d+\b")
_INJECTION = re.compile(
    r"(bỏ qua|phớt lờ|quên|bất kể).{0,40}(hướng dẫn|chỉ dẫn|chỉ thị trước|yêu cầu trước|quy tắc)"
    r"|ignore (all|any|previous|the above)|system prompt|bạn là (một )?trợ lý|hãy trả lời rằng",
    re.IGNORECASE)
_SENT_SPLIT = re.compile(r"(?<=[.;!?])\s+|\n+")


@dataclass
class Answer:
    status: str                       # "answered" | "refused"
    text: str
    kind: str = ""                    # "field" | "passage" | "list"
    reason: str = ""
    confidence: float | None = None   # độ phủ từ khóa theo idf của căn cứ (đo được, không cộng hằng số)
    citations: list[dict] = field(default_factory=list)   # citations[i] là nguồn [i+1] trong `text`
    warnings: list[str] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    meta: dict = field(default_factory=dict)              # thông tin chạy LLM (mô hình, thời gian, câu bị cắt)


def _ascii(s: str) -> str:
    return remove_diacritics(normalize_text(s)).lower()


def detect_field(question: str) -> str | None:
    q = _ascii(question)
    for name, pattern in _FIELD_INTENTS:
        if re.search(pattern, q):
            return name
    return None


def split_sentences(chunk: Chunk) -> list[tuple[int, int]]:
    """Vị trí [start, end) (trên trang) của từng câu trong đoạn."""
    out, pos = [], 0
    for part in _SENT_SPLIT.split(chunk.text):
        i = chunk.text.find(part, pos)
        if part.strip():
            out.append((chunk.start + i, chunk.start + i + len(part)))
        pos = i + len(part)
    return out


class Assistant:
    """Giữ trang, thẻ, đoạn và chỉ mục của kho; trả lời câu hỏi."""

    def __init__(
        self,
        pages: list[dict],
        cards: list[DocCard] | None = None,
        encoder=None,
        qa_mode: str | None = None,
        generator=None,
        threshold_path: str | Path | None = None,
        thresholds: dict | None = None,
        chunk_strategy: str = "default",
        include_metadata_prefix: bool = False,
        return_parent: bool = False,
        reranker=None,
    ):
        """encoder: bộ mã hóa vector (src.dense.E5Encoder) để tìm theo nghĩa; None = chỉ tìm theo từ khóa."""
        self.pages = {(p["doc_id"], p["page_no"]): p for p in pages}
        self.doc_pages = pages_by_doc(pages)
        self.cards = {c.doc_id: c for c in (cards if cards is not None else build_cards(pages))}
        self.encoder = encoder
        self.qa_mode = qa_mode
        self.generator = generator
        self._generators: dict[tuple[str, str], object] = {}
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()
        self.threshold_path = Path(threshold_path) if threshold_path is not None else DEFAULT_THRESHOLD_PATH
        self.thresholds = load_refusal_thresholds(self.threshold_path, overrides=thresholds)
        self.chunk_strategy = chunk_strategy
        self.include_metadata_prefix = include_metadata_prefix
        self.return_parent = return_parent
        self.reranker = reranker
        self._reindex()

    def _resolve_generator(self, generator=None, qa_mode: str | None = None, llm_factory=None) -> tuple[str, object | None]:
        """Chọn chế độ QA (`extractive`, `qwen25_1_5b`, `qwen3_1_7b`) và bộ sinh LLM tương ứng."""
        from src.llm import create_generator, resolve_qa_mode

        mode, model_id = resolve_qa_mode(qa_mode if qa_mode is not None else self.qa_mode)
        if generator is not None:
            return mode, generator
        if mode == "extractive" or model_id is None:
            return mode, None
        if self.generator is not None and getattr(self.generator, "model_id", None) == model_id:
            return mode, self.generator
        with self._lock:
            if llm_factory is None and (mode, model_id) in self._generators:
                return mode, self._generators[(mode, model_id)]
            gen = create_generator(qa_mode=mode, model_id=model_id, llm_factory=llm_factory)
            if llm_factory is None and gen is not None:
                self._generators[(mode, model_id)] = gen
            return mode, gen

    def _build_chunks_and_index(self, doc_pages_map: dict[str, list[dict]]) -> tuple[list[Chunk], HybridIndex]:
        chunks_new: list[Chunk] = []
        for ps in doc_pages_map.values():
            chunks_new.extend(
                chunk_document(
                    ps,
                    strategy=self.chunk_strategy,
                    include_metadata_prefix=self.include_metadata_prefix,
                )
            )
        index_new = HybridIndex(chunks_new, encoder=self.encoder, reranker=self.reranker)
        return chunks_new, index_new

    def _reindex(self) -> None:
        with self._write_lock:
            with self._lock:
                doc_pages_snap = dict(self.doc_pages)
            chunks_new, index_new = self._build_chunks_and_index(doc_pages_snap)
            with self._lock:
                self.chunks = chunks_new
                self.index = index_new

    def add_document(self, pages: list[dict]) -> DocCard:
        """Thêm (hoặc thay) một văn bản rồi lập lại chỉ mục nguyên tử; trả thẻ thông tin của nó."""
        doc_id = pages[0]["doc_id"]
        new_card = build_cards(pages)[0]
        sorted_pages = sorted(pages, key=lambda p: p["page_no"])
        with self._write_lock:
            with self._lock:
                pages_new = {k: v for k, v in self.pages.items() if k[0] != doc_id}
                pages_new.update({(p["doc_id"], p["page_no"]): p for p in pages})
                doc_pages_new = dict(self.doc_pages)
                doc_pages_new[doc_id] = sorted_pages
                cards_new = dict(self.cards)
                cards_new[doc_id] = new_card
            chunks_new, index_new = self._build_chunks_and_index(doc_pages_new)
            with self._lock:
                self.pages = pages_new
                self.doc_pages = doc_pages_new
                self.cards = cards_new
                self.chunks = chunks_new
                self.index = index_new
                return new_card

    def remove_document(self, doc_id: str) -> None:
        """Gỡ văn bản và hoán đổi chỉ mục mới nguyên tử."""
        with self._write_lock:
            with self._lock:
                pages_new = {k: v for k, v in self.pages.items() if k[0] != doc_id}
                doc_pages_new = dict(self.doc_pages)
                doc_pages_new.pop(doc_id, None)
                cards_new = dict(self.cards)
                cards_new.pop(doc_id, None)
            chunks_new, index_new = self._build_chunks_and_index(doc_pages_new)
            with self._lock:
                self.pages = pages_new
                self.doc_pages = doc_pages_new
                self.cards = cards_new
                self.chunks = chunks_new
                self.index = index_new

    # ---------- căn cứ ----------
    def content_tokens(self, question: str) -> tuple[list[str], bool]:
        tokens, strip = self.index.query_tokens(question)
        return [t for t in dict.fromkeys(tokens) if t not in _STOP[strip]], strip

    def coverage(self, tokens: list[str], strip: bool, text: str, bigrams: set | None = None) -> float:
        """Độ phủ căn cứ của `text` cho câu hỏi, trong [0, 1].

        = tổng idf của âm tiết khóa có trong text / tổng idf mọi âm tiết khóa; nếu câu hỏi có cặp âm tiết
        liền nhau thì lấy trung bình với tỉ lệ cặp có trong text. Cặp âm tiết chặn trường hợp các âm tiết
        khớp rời rạc: "thủ đô" không được tính là có khi text chỉ có "thủ tục" và "đô thị".
        """
        from src.retrieval import index_tokens

        seq = index_tokens(text, strip)
        present = set(seq)
        weights = {t: self.index.idf(t, strip) for t in tokens}
        total = sum(weights.values())
        uni = sum(w for t, w in weights.items() if t in present) / total if total else 0.0
        if not bigrams:
            return uni
        bi = len(bigrams & set(zip(seq, seq[1:]))) / len(bigrams)
        return (uni + bi) / 2

    def citation(self, doc_id: str, page_no: int, start: int, end: int) -> dict:
        text = self.pages[(doc_id, page_no)]["text"][start:end]
        return {"doc_id": doc_id, "page_no": page_no, "start": start, "end": end, "text": text}

    def find_doc(self, question: str, allowed: set[str] | None = None) -> str | None:
        """Văn bản được nhắc rõ trong câu hỏi qua số ký hiệu hoặc mã văn bản (chỉ trong `allowed` nếu có)."""
        cards = {d: c for d, c in self.cards.items() if allowed is None or d in allowed}
        for m in _DOC_REF.finditer(question):
            ref = m.group(0)
            if ref in cards:
                return ref
            key = normalize_doc_number(ref)
            for doc_id, card in cards.items():
                num = card.value("doc_number")
                if num and (normalize_doc_number(num) == key or (len(key) >= 6 and key in normalize_doc_number(num))):
                    return doc_id
        return None

    # ---------- trả lời ----------
    def ask(
        self,
        question: str,
        doc_ids: list[str] | set[str] | None = None,
        generator=None,
        qa_mode: str | None = None,
        llm_factory=None,
    ) -> Answer:
        """Trả lời một câu hỏi.

        doc_ids: chỉ dùng các văn bản này làm nguồn (None = cả kho; tập rỗng = từ chối).
        generator: LLM (src.llm.LocalLLM) để diễn đạt câu trả lời nội dung; None = theo `QA_MODE` (mặc định trích nguyên văn).
        """
        active_mode, active_gen = self._resolve_generator(generator=generator, qa_mode=qa_mode, llm_factory=llm_factory)
        question = normalize_text(question).strip()
        q_ascii = _ascii(question)
        if _INJECTION.search(question):
            return Answer("refused", "Yêu cầu không hợp lệ.", reason="Phát hiện chỉ thị can thiệp hệ thống prompt.",
                          meta={"qa_mode": active_mode})

        allowed = set(doc_ids) if doc_ids is not None else None
        if allowed is not None and not allowed:
            return Answer("refused", "Chưa chọn nguồn nào.", reason="Hãy chọn ít nhất một văn bản ở cột Nguồn.",
                          meta={"qa_mode": active_mode})
        tokens, strip = self.content_tokens(question)
        if _SUMMARY_INTENT.search(q_ascii):
            ans = self.answer_summary(question, tokens, strip, allowed, active_gen)
            ans.meta["qa_mode"] = active_mode
            return ans
        field_name = detect_field(question)
        doc_id = self.find_doc(question, allowed)
        if field_name:
            tokens = [t for t in tokens if t not in _FIELD_STOP[strip]]
        field_how = "số ký hiệu/mã nêu trong câu hỏi"
        if field_name and doc_id is None and allowed is not None and len(allowed) == 1 and not _DOC_REF.search(question) and not tokens:
            doc_id = next(iter(allowed))
            field_how = "nguồn duy nhất đang chọn"
        if field_name and doc_id:
            ans = self.answer_field(field_name, doc_id, confidence=1.0, how=field_how)
            ans.meta["qa_mode"] = active_mode
            return ans
        if not tokens:
            return Answer("refused", "Tôi không trả lời câu này.", reason="Câu hỏi không có từ khóa nội dung để tìm căn cứ.",
                          meta={"qa_mode": active_mode})
        is_list = bool(_LIST_INTENT.search(q_ascii)) and not field_name
        search_q = " ".join(tokens) if field_name else question
        bigrams = self.query_bigrams(question, drop_field_words=bool(field_name))
        scope = {doc_id} if doc_id else allowed
        k_top = LIST_K if is_list else TOP_K
        rewrites: list[str] = []

        def _run_search(extra_queries: list[str] | None = None):
            h_list = self.index.search(search_q, k=k_top, doc_ids=scope,
                                       extra_queries=extra_queries, return_parent=self.return_parent)
            ret = [{"doc_id": h["chunk"].doc_id, "page_no": h["chunk"].page_no, "section": h["chunk"].section,
                    "rrf": round(h["rrf"], 4),
                    "coverage": round(self.coverage(tokens, strip, h["chunk"].text, bigrams), 3),
                    **({"dense": round(h["dense_score"], 3)} if "dense_score" in h else {})}
                   for h in h_list]
            g = self.evidence_gate(ret, has_doc_id=bool(doc_id), is_list=is_list) if ret else None
            return h_list, ret, g

        hits, retrieved, gate = _run_search(None)
        if active_gen is not None and not field_name and (not hits or not gate["ok"]):
            rewrites = self.rewrite_query(question, active_gen)
            if rewrites:
                hits, retrieved, gate = _run_search(rewrites)

        if not hits:
            return Answer("refused", "Không tìm thấy văn bản nào liên quan.", reason="Không đoạn nào chứa từ khóa của câu hỏi.",
                          meta={"rewrites": rewrites, "qa_mode": active_mode})
        best = max(retrieved, key=lambda r: r["coverage"])
        if not field_name and not gate["ok"]:
            return Answer("refused", "Tôi không tìm thấy đủ căn cứ trong kho văn bản để trả lời.",
                          confidence=best["coverage"], retrieved=retrieved, reason=gate["reason"],
                          meta={"rewrites": rewrites, "gate": gate, "qa_mode": active_mode})
        if field_name:
            # Hỏi trường nhưng không nêu số: xác định văn bản bằng tìm kiếm, bỏ từ chỉ trường khỏi độ phủ
            top = retrieved[0]
            min_field_cov = self.thresholds["min_field_coverage"]
            if top["coverage"] < min_field_cov:
                return Answer("refused", "Không xác định được văn bản bạn hỏi.", kind="field", confidence=top["coverage"],
                              reason=f"Văn bản tìm được khớp yếu (độ phủ {top['coverage']:.2f} < {min_field_cov}). "
                                     "Hãy nêu số ký hiệu văn bản.", retrieved=retrieved,
                              meta={"qa_mode": active_mode})
            ans = self.answer_field(field_name, top["doc_id"], confidence=top["coverage"],
                                    how="tìm kiếm theo nội dung câu hỏi", retrieved=retrieved)
            ans.meta["qa_mode"] = active_mode
            return ans
        if is_list:
            ans = self.answer_list(hits, retrieved, min_cov=self.thresholds["min_coverage_list"])
            ans.meta["qa_mode"] = active_mode
            return ans
        extractive = self.answer_passage(hits, tokens, strip, retrieved, bigrams, question)
        extractive.meta |= {"rewrites": rewrites, "gate": gate, "qa_mode": active_mode}
        if active_gen is None or extractive.status != "answered":
            return extractive
        return self.answer_llm(question, hits, retrieved, active_gen, extractive)

    def evidence_gate(self, retrieved: list[dict], has_doc_id: bool = False, is_list: bool = False) -> dict:
        """Có đủ căn cứ để trả lời không, dựa trên cặp (độ phủ, điểm gần nghĩa) trên cùng một đoạn."""
        t = getattr(self, "thresholds", DEFAULT_REFUSAL_THRESHOLDS)
        if not retrieved:
            return {"ok": False, "coverage": 0.0, "rrf": 0.0, "combined": 0.0, "dense": None,
                    "reason": "Không tìm thấy đoạn văn bản nào."}
        best_cov_item = max(retrieved, key=lambda r: (r["coverage"], r.get("dense", -1.0)))
        cov = best_cov_item["coverage"]
        rrf_score = max((float(r.get("rrf", 0.0)) for r in retrieved), default=0.0)
        best_paired_dense = best_cov_item.get("dense")
        dense = best_paired_dense if best_paired_dense is not None else max(
            (r["dense"] for r in retrieved if "dense" in r), default=None
        )
        rrf_norm = min(1.0, rrf_score / 0.0328) if rrf_score > 0 else 0.0
        alpha = float(t.get("combined_alpha", 0.7))
        combined = round(alpha * cov + (1.0 - alpha) * rrf_norm, 4)

        threshold = (t["min_coverage_doc_specified"] if has_doc_id
                     else (t["min_coverage_list"] if is_list else t["min_coverage"]))
        dense_veto = float(t["dense_veto"])

        def _not_vetoed(r: dict) -> bool:
            return "dense" not in r or r["dense"] >= dense_veto

        kw_pair = next((r for r in retrieved if r["coverage"] >= threshold and _not_vetoed(r)), None)
        sem_pair = next(
            (r for r in retrieved
             if r.get("dense") is not None and r["dense"] >= t["dense_min"] and r["coverage"] >= t["min_coverage_with_dense"]),
            None,
        )

        if dense is not None and kw_pair is None and sem_pair is None and dense < dense_veto:
            return {"ok": False, "coverage": cov, "rrf": rrf_score, "combined": combined, "dense": dense,
                    "reason": f"Nội dung kho không gần nghĩa với câu hỏi (độ gần nghĩa {dense:.2f} < {dense_veto})."}
        min_rrf = float(t.get("min_rrf", 0.0))
        if rrf_score < min_rrf:
            return {"ok": False, "coverage": cov, "rrf": rrf_score, "combined": combined, "dense": dense,
                    "reason": f"Điểm truy hồi RRF {rrf_score:.4f} < ngưỡng {min_rrf:.4f} (độ phủ {cov:.0%})."}
        min_combined = float(t.get("min_combined_score", 0.0))
        if min_combined > 0.0 and combined < min_combined:
            return {"ok": False, "coverage": cov, "rrf": rrf_score, "combined": combined, "dense": dense,
                    "reason": f"Điểm tổng hợp truy hồi và độ phủ {combined:.3f} < ngưỡng {min_combined:.3f}."}
        if kw_pair is not None:
            return {"ok": True, "coverage": kw_pair["coverage"], "rrf": rrf_score, "combined": combined,
                    "dense": kw_pair.get("dense", dense), "via": "từ khóa"}
        if sem_pair is not None:
            return {"ok": True, "coverage": sem_pair["coverage"], "rrf": rrf_score, "combined": combined,
                    "dense": sem_pair["dense"], "via": "nghĩa"}
        reason = f"Đoạn khớp nhất chỉ đạt độ phủ căn cứ {cov:.0%} (ngưỡng {threshold:.0%}), điểm truy hồi RRF {rrf_score:.4f}"
        if dense is not None:
            reason += f", độ gần nghĩa {dense:.2f} (cần ≥ {t['dense_min']} kèm độ phủ ≥ {t['min_coverage_with_dense']:.0%})"
        return {"ok": False, "coverage": cov, "rrf": rrf_score, "combined": combined, "dense": dense, "reason": reason + "."}

    def rewrite_query(self, question: str, generator) -> list[str]:
        """LLM viết lại câu hỏi thành ≤ 3 cách diễn đạt theo văn phong văn bản hành chính (chỉ để TÌM RỘNG hơn:
        cửa từ chối và bộ kiểm câu trả lời vẫn so với câu hỏi gốc và nguồn)."""
        msgs = [{"role": "system", "content": REWRITE_PROMPT}, {"role": "user", "content": question}]
        try:
            try:
                out = generator(msgs, max_new_tokens=REWRITE_MAX_TOKENS)["text"]
            except TypeError:          # bộ sinh không nhận max_new_tokens (vd. bộ sinh giả trong test)
                out = generator(msgs)["text"]
        except (RuntimeError, ValueError, OSError):
            return []
        lines = [re.sub(r"^\s*(\d+[.)]|[-*•])\s*", "", l).strip(" \"'") for l in out.split("\n")]
        return [l for l in lines if 3 <= len(l.split()) <= 30 and not _INJECTION.search(l)][:3]

    def answer_summary(self, question, tokens, strip, allowed, generator) -> Answer:
        """Tóm tắt văn bản được nhắc: số ký hiệu/mã trong câu hỏi → nguồn duy nhất đang chọn → văn bản khớp nhất."""
        from src.summarize import summarize_doc, summary_text

        doc_id = self.find_doc(question, allowed)
        how = "số ký hiệu/mã nêu trong câu hỏi"
        if doc_id is None and allowed is not None and len(allowed) == 1:
            doc_id, how = next(iter(allowed)), "nguồn duy nhất đang chọn"
        if doc_id is None:
            stop = {remove_diacritics(w) for w in _SUMMARY_WORDS} if strip else _SUMMARY_WORDS
            words = [t for t in tokens if t not in stop]
            hits = self.index.search(" ".join(words), k=TOP_K, doc_ids=allowed) if words else []
            cov = self.coverage(words, strip, hits[0]["chunk"].text) if hits else 0.0
            min_cov = getattr(self, "thresholds", DEFAULT_REFUSAL_THRESHOLDS)["min_coverage"]
            if not hits or cov < min_cov:
                return Answer("refused", "Không xác định được văn bản cần tóm tắt.", kind="summary",
                              confidence=cov if hits else None,
                              reason="Hãy nêu số ký hiệu, hoặc chỉ chọn một nguồn ở cột Nguồn rồi hỏi lại.")
            doc_id, how = hits[0]["chunk"].doc_id, f"tìm kiếm (độ phủ {cov:.2f})"
        s = summarize_doc(self, doc_id, generator)
        if not s["points"]:
            return Answer("refused", "Không tóm tắt được văn bản này.", kind="summary",
                          reason=s["meta"].get("reason", "Không có đoạn nào đủ dài."))
        label = self.doc_label(doc_id)
        warnings = []
        if s["meta"].get("fallback"):
            warnings.append(s["meta"]["fallback"] + " Hiển thị tóm tắt trích nguyên văn.")
        if s["meta"].get("dropped"):
            warnings.append(f"Đã cắt {len(s['meta']['dropped'])} ý của LLM không khớp nguồn.")
        kind_txt = "LLM tóm tắt từ" if s["kind"] == "llm" else "Tóm tắt trích nguyên văn từ"
        return Answer("answered", f"Tóm tắt {label}:\n" + summary_text(s), kind="summary",
                      reason=f"{kind_txt} {s['meta']['n_passages']} đoạn tiêu biểu (trang "
                             f"{', '.join(map(str, s['meta']['pages']))}); văn bản xác định qua {how}.",
                      citations=s["citations"], warnings=warnings, meta=s["meta"])

    def query_bigrams(self, question: str, drop_field_words: bool = False) -> set[tuple[str, str]]:
        """Cặp âm tiết liền nhau của câu hỏi, bỏ cặp chứa từ để hỏi: "phạm vi", "vi điều", "điều chỉnh"."""
        toks, strip = self.index.query_tokens(question)
        stop = _STOP[strip] | (_FIELD_STOP[strip] if drop_field_words else set())
        return {(a, b) for a, b in zip(toks, toks[1:]) if a not in stop and b not in stop}

    def answer_field(self, name: str, doc_id: str, confidence: float, how: str, retrieved=None) -> Answer:
        card = self.cards[doc_id]
        f = card.fields.get(name)
        label = FIELD_LABELS[name]
        if f is None:
            reason = f"Luật không trích được trường «{label}» của văn bản {doc_id}."
            if name == "issue_date" and "issue_date_blank" in card.flags:
                reason += " PDF để trống ngày (số và ngày nằm trên chữ ký số)."
            if "first_page_missing" in card.flags or "no_text" in card.flags:
                reason += " Trang đầu chưa có chữ (scan chưa OCR)."
            return Answer("refused", f"Không có thông tin «{label}» cho văn bản này.", kind="field", reason=reason,
                          confidence=confidence, retrieved=retrieved or [])
        value = "; ".join(f.value) if isinstance(f.value, list) else f.value
        warnings = []
        if name == "doc_number" and "doc_number_blank" in card.flags:
            warnings.append("PDF để trống phần số, chỉ có ký hiệu.")
        title = card.value("signer_title")
        text = f"{label}: {value}" + (f" ({title})" if name == "signer" and title else "") + " [1]"
        cite = self.citation(doc_id, f.page_no, f.start, f.end)
        if f.end <= f.start:     # giá trị đọc bằng OCR vùng đầu trang, không nằm trong lớp chữ của PDF
            cite["text"] = f"{value} (đọc bằng OCR vùng đầu trang {f.page_no}, số/ngày đóng dạng ảnh khi ký số)"
            warnings.append(f"«{label}» đọc bằng OCR từ ảnh đầu trang, nên kiểm lại trên ảnh trang.")
        return Answer("answered", text, kind="field", confidence=confidence,
                      reason=f"Lấy từ thẻ thông tin của {doc_id} (xác định văn bản qua {how}).",
                      citations=[cite], warnings=warnings, retrieved=retrieved or [])

    def _sentences(self, hits, tokens, strip, bigrams):
        """Mọi câu của các đoạn tìm được kèm điểm; câu trông như tiêm lệnh bị loại.

        Điểm câu = ½ độ phủ của câu + ½ độ phủ của đoạn chứa câu: câu hỏi thường có phần chỉ văn bản
        ("nghị định về kiểm soát TTHC") và phần chỉ vị trí ("phạm vi điều chỉnh") nằm ở hai câu khác nhau.
        """
        out, warnings = [], []
        for rank, h in enumerate(hits):
            c = h["chunk"]
            page_text = self.pages[(c.doc_id, c.page_no)]["text"]
            chunk_cov = self.coverage(tokens, strip, c.text, bigrams)
            for s, e in split_sentences(c):
                sent = page_text[s:e]
                if _INJECTION.search(sent):
                    warnings.append(f"Bỏ một câu trông như lệnh cho trợ lý ở {c.doc_id} trang {c.page_no}.")
                    continue
                cov = self.coverage(tokens, strip, sent, bigrams)
                out.append({"cov": chunk_cov, "score": (cov + chunk_cov) / 2, "rank": rank, "doc_id": c.doc_id,
                            "page_no": c.page_no, "start": s, "end": e, "len": len(sent)})
        return out, warnings

    def answer_passage(self, hits, tokens, strip, retrieved, bigrams, question: str = "") -> Answer:
        sents, warnings = self._sentences(hits, tokens, strip, bigrams)
        if not sents:
            return Answer("refused", "Không có câu nào dùng được làm căn cứ.",
                          reason="Mọi câu trong các đoạn tìm được đều bị loại. " + " ".join(warnings),
                          warnings=warnings, retrieved=retrieved)
        if self.index.dense is not None and question:
            self._add_dense_sentence_scores(sents, question)
        sents.sort(key=lambda x: (-x["score"], x["rank"], x["start"]))
        best = sents[0]
        picked = [best]
        # Câu ngắn (vd. tiêu đề "Điều 5. Thời hạn") thì lấy thêm câu kế tiếp trong cùng trang làm phần trả lời
        if best["len"] < 80:
            nxt = [s for s in sents if s["doc_id"] == best["doc_id"] and s["page_no"] == best["page_no"]
                   and s["start"] > best["start"]]
            if nxt:
                picked.append(min(nxt, key=lambda s: s["start"]))
        cites = [self.citation(s["doc_id"], s["page_no"], s["start"], s["end"]) for s in picked]
        card = self.cards.get(best["doc_id"])
        num = card.value("doc_number") if card else None
        source = f"{best['doc_id']}" + (f" (số {num})" if num else "") + f", trang {best['page_no']}"
        text = " ".join(f"{c['text']} [{i}]" for i, c in enumerate(cites, start=1))
        return Answer("answered", text, kind="passage", confidence=round(best["cov"], 3),
                      reason=f"Trích nguyên văn từ {source}.", citations=cites, warnings=warnings, retrieved=retrieved)

    def _add_dense_sentence_scores(self, sents: list[dict], question: str, limit: int = 60) -> None:
        """Điểm câu = ½ điểm từ khóa + ½ độ gần nghĩa (cosine e5 quy về [0, 1] trên dải 0,75–0,90), cho ≤ limit câu
        có điểm từ khóa cao nhất: câu hỏi diễn đạt khác chữ vẫn chọn được câu đúng ý."""
        sents.sort(key=lambda x: (-x["score"], x["rank"]))
        top = sents[:limit]
        texts = [self.pages[(s["doc_id"], s["page_no"])]["text"][s["start"]:s["end"]] for s in top]
        enc = self.index.encoder
        q = enc.encode([question], "query")[0]
        cos = enc.encode(texts, "passage") @ q
        for s, c in zip(top, cos):
            s["dense"] = float(c)
            s["score"] = 0.5 * s["score"] + 0.5 * float(np.clip((c - 0.75) / 0.15, 0, 1))
        for s in sents[limit:]:
            s["score"] *= 0.5

    def doc_label(self, doc_id: str) -> str:
        """Tên ngắn của văn bản để hiển thị/đưa vào prompt.

        "Nghị định 385/2026/NĐ-CP" nếu có số; "Báo cáo · Bao_cao_TTTN_07" nếu chỉ có loại; còn lại là mã văn bản
        (tệp tải lên bỏ tiền tố "up_<md5>_").
        """
        name = re.sub(r"^up_[0-9a-f]{8}_", "", doc_id)
        card = self.cards.get(doc_id)
        doc_type = card.value("doc_type") if card else None
        number = card.value("doc_number") if card else None
        if number and re.match(r"\w*\d", number):
            return f"{doc_type or 'Văn bản'} {number}"
        if doc_type:
            return f"{doc_type} · {name}"
        title = card.value("title") if card else None
        return (title[:70] + ("…" if len(title) > 70 else "")) if title else name

    def answer_llm(self, question, hits, retrieved, generator, extractive: Answer) -> Answer:
        """LLM diễn đạt từ ≤ MAX_SOURCES đoạn nguồn; câu không qua bộ kiểm bị cắt; cắt hết → trả `extractive`."""
        from src.llm import MAX_SOURCES, REFUSAL_MARK, build_messages, verify_answer

        sources, chosen = [], []
        for h, r in zip(hits, retrieved):
            if r["coverage"] < MIN_COVERAGE / 2 or len(sources) >= MAX_SOURCES:
                continue
            c = h["chunk"]
            text = " ".join(s for s in _SENT_SPLIT.split(c.text) if s and not _INJECTION.search(s))
            sources.append({"label": f"{self.doc_label(c.doc_id)}, trang {c.page_no}", "text": text})
            chosen.append(c)
        try:
            out = generator(build_messages(question, sources))
        except (RuntimeError, ValueError, OSError) as exc:
            detail = str(exc).strip()[:140]
            msg = f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__
            extractive.meta = {**extractive.meta, "fallback_extractive": True, "llm_error": str(exc)}
            extractive.warnings.append(f"Lỗi khi sinh câu trả lời bằng LLM ({msg}); hiển thị câu trích nguyên văn.")
            return extractive
        meta = {
            "model": out.get("model") or getattr(generator, "model_id", "?"),
            "seconds": out.get("seconds"),
            "new_tokens": out.get("new_tokens"),
            "tokens_per_sec": out.get("tokens_per_sec"),
            "vram_peak_mb": out.get("vram_peak_mb"),
            "raw": out["text"],
            "n_sources": len(sources),
        }
        if out.get("fallback_from") == "openrouter":
            meta["fallback_from"] = "openrouter"
            meta["fallback_reason"] = out.get("fallback_reason", "")
        if REFUSAL_MARK in out["text"].upper():
            meta["llm_refused"] = True
            meta["n_kept"] = 0
            meta["n_dropped"] = 0
            meta["fallback_extractive"] = True
            extractive.meta = {**extractive.meta, **meta}
            extractive.warnings.append("LLM cho rằng nguồn không đủ; hiển thị câu trích nguyên văn.")
            return extractive
        checked = verify_answer(out["text"], sources, _STOP[False])
        kept = [s for s in checked if s.kept]
        meta["dropped"] = [{"text": s.text, "reason": s.reason} for s in checked if not s.kept]
        meta["n_kept"] = len(kept)
        meta["n_dropped"] = len(meta["dropped"])
        meta["n_auto_cited"] = sum(s.auto_cited for s in kept)
        if not kept:
            meta["fallback_extractive"] = True
            extractive.meta = {**extractive.meta, **meta}
            extractive.warnings.append("Không câu nào của LLM qua bước kiểm nguồn; hiển thị câu trích nguyên văn.")
            return extractive
        meta["fallback_extractive"] = False
        # Đánh số lại theo thứ tự xuất hiện, chỉ giữ nguồn thật sự được dẫn
        order: dict[int, int] = {}
        for s in kept:
            for n in s.sources:
                order.setdefault(n, len(order) + 1)
        cites = []
        for n in sorted(order, key=order.get):
            c = chosen[n - 1]
            cites.append(self.citation(c.doc_id, c.page_no, c.start, c.end))
        text = " ".join(s.text.rstrip() + " " + "".join(f"[{order[n]}]" for n in s.sources) for s in kept)
        warnings = list(extractive.warnings)
        if out.get("fallback_from") == "openrouter":
            warnings.append(f"OpenRouter API lỗi; đã tự động chuyển sang LLM cục bộ ({meta['model'].split('/')[-1]}).")
        if meta["dropped"]:
            warnings.append(f"Đã cắt {len(meta['dropped'])} câu của LLM không khớp nguồn.")
        return Answer("answered", text, kind="llm", confidence=extractive.confidence,
                      reason=f"LLM {meta['model'].split('/')[-1]} diễn đạt từ {len(sources)} đoạn nguồn; "
                             "mỗi câu đã được kiểm lại theo nguồn.",
                      citations=cites, warnings=warnings, retrieved=retrieved, meta={**extractive.meta, **meta})

    def answer_list(self, hits, retrieved, min_cov: float | None = None) -> Answer:
        seen, cites, lines = set(), [], []
        threshold = min_cov if min_cov is not None else MIN_COVERAGE
        for h, r in zip(hits, retrieved):
            d = h["chunk"].doc_id
            if d in seen or r["coverage"] < threshold:
                continue
            seen.add(d)
            c = h["chunk"]
            cites.append(self.citation(d, c.page_no, c.start, c.end))
            card = self.cards.get(d)
            subj = card.value("subject") if card else None
            lines.append(f"- {self.doc_label(d)}" + (f": {subj}" if subj else "") + f" [{len(cites)}]")
            if len(seen) >= MAX_LIST_DOCS:
                break
        if not lines:       # qua cửa căn cứ nhờ vector nhưng không đoạn nào đủ độ phủ từ khóa → không liệt kê rỗng
            return Answer("refused", "Không tìm thấy văn bản nào đủ căn cứ để liệt kê.",
                          reason=f"Không đoạn nào chứa ≥ {threshold:.0%} trọng số từ khóa của câu hỏi.",
                          retrieved=retrieved)
        valid_covs = [r["coverage"] for r in retrieved if r["coverage"] >= threshold]
        conf = max(valid_covs) if valid_covs else threshold
        return Answer("answered", "\n".join(lines), kind="list",
                      confidence=conf,
                      reason=f"{len(lines)} văn bản có đoạn chứa ≥ {threshold:.0%} trọng số từ khóa.",
                      citations=cites, retrieved=retrieved)
