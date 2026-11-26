"""Trợ lý ảo Hỏi - Đáp nghiệp vụ Lưu trữ số hóa tỉnh Thái Nguyên.

Hỗ trợ:
1. Quản lý phiên hội thoại đa vòng (Multi-turn conversational memory).
2. Tự động liên kết ngữ cảnh (Anaphora resolution: "văn bản đó", "hồ sơ này").
3. Nhận diện ý định chuyên sâu:
   - Tra cứu cơ cấu Phông - Hồ sơ lưu trữ theo Thông tư 02/2019/TT-BNV.
   - Hướng dẫn thủ tục hành chính, nộp lưu & trích lục hồ sơ lưu trữ tỉnh Thái Nguyên.
   - Hỏi đáp nội dung văn bản cụ thể có dẫn nguồn kép (Phông + Hồ sơ + Trang PDF).
"""
from __future__ import annotations

from collections import OrderedDict
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from src.archive import ArchiveManager, get_archive_manager, is_access_allowed
from src.archive_search import extract_year
from src.qa import _DOC_REF, _SUMMARY_INTENT, Answer, Assistant, detect_field
from src.text import normalize_text, remove_diacritics

# Tri thức nghiệp vụ Lưu trữ tỉnh Thái Nguyên (Chuẩn hóa từ Sở Nội vụ & Thông tư 02/2019/TT-BNV)
THAI_NGUYEN_ARCHIVE_KNOWLEDGE = {
    "trich_luc": """Thủ tục xin cấp bản sao / trích lục tài liệu lưu trữ tại tỉnh Thái Nguyên:
1. Cơ quan thực hiện: Trung tâm Lưu trữ Lịch sử tỉnh Thái Nguyên (trực thuộc Sở Nội vụ tỉnh Thái Nguyên).
2. Đối tượng: Các cơ quan, tổ chức và công dân có nhu cầu chính đáng khai thác tài liệu lưu trữ lịch sử.
3. Hồ sơ yêu cầu:
   - Phiếu yêu cầu khai thác, sử dụng tài liệu lưu trữ (theo mẫu quy định).
   - Xuất trình Căn cước công dân hoặc giấy tờ tùy thân hợp lệ.
   - Giấy giới thiệu hoặc văn bản đề nghị của cơ quan, tổ chức (nếu là đại diện cơ quan).
4. Thời hạn giải quyết:
   - Cung cấp tài liệu đọc tại chỗ: Trong ngày làm việc hoặc không quá 01 ngày.
   - Cấp bản sao, trích lục tài liệu: Không quá 03 ngày làm việc kể từ khi nhận đủ hồ sơ hợp lệ.
5. Lệ phí khai thác: Thực hiện theo Thông tư số 156/2026/TT-BTC của Bộ Tài chính.""",

    "nop_luu": """Quy trình nộp lưu tài liệu điện tử và tài liệu số hóa vào Lưu trữ lịch sử tỉnh Thái Nguyên:
1. Thời hạn nộp lưu: Trong thời hạn 01 năm kể từ ngày công việc kết thúc, các cơ quan thuộc nguồn nộp lưu có trách nhiệm nộp lưu hồ sơ vào Trung tâm Lưu trữ Lịch sử tỉnh.
2. Tiêu chuẩn hồ sơ nộp lưu (Thông tư 02/2019/TT-BNV & Nghị định 30/2020/NĐ-CP):
   - Hồ sơ phải được chỉnh lý hoàn chỉnh, phân loại theo mục lục, có tiêu đề và thời hạn bảo quản rõ ràng.
   - Tài liệu số hóa phải ở định dạng chuẩn PDF/A hoặc PDF scan rõ nét (độ phân giải tối thiểu 300 DPI), đầy đủ các trang và lớp chữ OCR bóc tách.
   - Kèm theo siêu dữ liệu (Metadata) cấp Hồ sơ và cấp Văn bản đảm bảo nguyên tắc «Đúng - Đủ - Sạch - Sống».
3. Phương thức nộp lưu: Nộp lưu trực tiếp qua Cổng Quản lý Tài liệu Lưu trữ Số hóa tỉnh Thái Nguyên hoặc chuyển giao qua mạng truyền số liệu chuyên dùng.""",

    "tieu_chuan_so_hoa": """Tiêu chuẩn số hóa tài liệu lưu trữ theo Thông tư 02/2019/TT-BNV và tỉnh Thái Nguyên:
1. Định dạng tệp: Định dạng PDF hoặc PDF/A, chuẩn nén ISO 19005.
2. Độ phân giải quét (Scan Resolution): Tối thiểu 300 DPI, tỷ lệ quét 1:1.
3. Chế độ màu:
   - Quét màu (Color): Đối với văn bản có chữ ký tươi, con dấu đỏ hoặc tài liệu ảnh.
   - Quét xám (Grayscale) hoặc đen trắng: Đối với văn bản chữ thông thường.
4. Bóc tách siêu dữ liệu (OCR & Metadata): Tỷ lệ nhận dạng ký tự quang học (OCR) đạt yêu cầu, tự động trích xuất các trường Số hiệu, Ngày tháng, Người ký, Trích yếu theo Nghị định 30/2020/NĐ-CP.""",
}


@dataclass
class ChatMessage:
    role: str       # "user" | "assistant"
    content: str
    citations: list[dict] = field(default_factory=list)
    kind: str = "text"
    timestamp: str = ""


@dataclass
class ChatSession:
    session_id: str
    messages: list[ChatMessage] = field(default_factory=list)
    active_doc_id: str | None = None
    active_file_code: str | None = None
    last_role: str | None = None
    last_seen: float = field(default_factory=time.time)

    def add_message(self, role: str, content: str, citations: list[dict] | None = None, kind: str = "text") -> None:
        self.last_seen = time.time()
        self.messages.append(ChatMessage(role=role, content=content, citations=citations or [], kind=kind))
        if len(self.messages) > 30:
            self.messages = self.messages[-30:]


class SessionManager:
    """Quản lý phiên hội thoại đa vòng cho Chatbot (có giới hạn LRU + TTL và an toàn đa luồng)."""

    def __init__(self, max_sessions: int = 500, ttl_seconds: int = 86_400):
        self._lock = threading.RLock()
        self.sessions: OrderedDict[str, ChatSession] = OrderedDict()
        self.max_sessions = max(1, int(max_sessions))
        self.ttl_seconds = max(60, int(ttl_seconds))

    def _cleanup_unlocked(self, now: float) -> None:
        expired = [sid for sid, sess in self.sessions.items() if now - sess.last_seen > self.ttl_seconds]
        for sid in expired:
            self.sessions.pop(sid, None)
        while len(self.sessions) >= self.max_sessions:
            self.sessions.popitem(last=False)

    def get_or_create(self, session_id: str | None = None) -> ChatSession:
        with self._lock:
            now = time.time()
            s_id = (session_id or "").strip()[:120] or str(uuid.uuid4())
            if s_id in self.sessions:
                sess = self.sessions[s_id]
                if now - sess.last_seen > self.ttl_seconds:
                    self.sessions.pop(s_id, None)
                else:
                    sess.last_seen = now
                    self.sessions.move_to_end(s_id)
                    return sess
            self._cleanup_unlocked(now)
            sess = ChatSession(session_id=s_id, last_seen=now)
            self.sessions[s_id] = sess
            return sess


_session_mgr = SessionManager()


def get_session_manager() -> SessionManager:
    return _session_mgr


def resolve_anaphora(question: str, session: ChatSession, assistant: Assistant) -> tuple[str, list[str] | None]:
    """Liên kết đại từ chỉ xuất ('văn bản này', 'văn bản đó', 'ai ký') với ngữ cảnh trước đó.

    Chỉ thu hẹp doc_ids khi câu hỏi KHÔNG nêu đích danh văn bản mới, và không ghép thêm chuỗi
    vào question để tránh làm sai lệch độ phủ từ khóa trong Assistant.ask.
    """
    q_norm = remove_diacritics(question).lower()
    if (
        _DOC_REF.search(question)
        or re.search(r"\b(quyet dinh|nghi dinh|chi thi|cong van|thong bao|thong tu|luat|nghi quyet)\s+\d+", q_norm)
        or assistant.find_doc(question) is not None
    ):
        return question, None

    anaphora_patterns = [
        r"\b(van ban nay|van ban do|vb nay|vb do|tai lieu nay|tai lieu do)\b",
        r"\b(ai ky no|ngay ban hanh cua no|do ai ban hanh)\b",
        r"\b(tom tat no|tom tat van ban nay|tom tat van ban do)\b",
    ]
    has_anaphora = any(re.search(p, q_norm) for p in anaphora_patterns)

    # Nếu câu hỏi quá ngắn như "Ai ký?", "Ban hành khi nào?", "Gửi cho ai?"
    is_short_field_question = len(question.strip().split()) <= 4 and bool(
        re.search(r"\b(ai ky|ngay nao|khi nao|co quan nao|noi nhan)\b", q_norm)
    )

    if (has_anaphora or is_short_field_question) and session.active_doc_id:
        return question, [session.active_doc_id]

    return question, None


def _access_denied_response(
    raw_question: str,
    session: ChatSession,
    blocked_modes: list[str],
    user_role: str,
) -> dict[str, Any]:
    """Tạo phản hồi từ chối khi tất cả văn bản ứng viên bị chặn bởi mức tiếp cận mô phỏng."""
    modes_str = ", ".join(blocked_modes) if blocked_modes else "Hạn chế"
    reply_text = (
        f"Từ chối trả lời: Tất cả văn bản ứng viên đều thuộc mức tiếp cận hạn chế ({modes_str}), "
        f"vai trò '{user_role}' không có quyền truy cập (mức tiếp cận mô phỏng)."
    )
    session.add_message("user", raw_question)
    session.add_message("assistant", reply_text, kind="access_denied")
    return {
        "status": "refused",
        "kind": "access_denied",
        "text": reply_text,
        "reason": f"Tất cả văn bản ứng viên bị chặn bởi mức tiếp cận mô phỏng ({modes_str}).",
        "access_denied": True,
        "blocked_usage_modes": blocked_modes,
        "simulated": True,
        "citations": [],
        "warnings": [],
        "retrieved": [],
        "meta": {},
        "session_id": session.session_id,
    }


def _make_reply(
    session: ChatSession,
    raw_question: str,
    text: str,
    kind: str,
    reason: str,
    citations: list[dict] | None = None,
    suggestions: list[str] | None = None,
    status: str = "answered",
) -> dict[str, Any]:
    """Chuẩn hóa phản hồi hội thoại và lưu vào lịch sử phiên."""
    cites = citations or []
    session.add_message("user", raw_question)
    session.add_message("assistant", text, citations=cites, kind=kind)
    return {
        "status": status,
        "text": text,
        "kind": kind,
        "reason": reason,
        "citations": cites,
        "warnings": [],
        "retrieved": [],
        "meta": {},
        "suggestions": suggestions or [],
        "session_id": session.session_id,
    }


def _build_live_stats_reply(assistant: Assistant, archive_mgr: ArchiveManager) -> str:
    """Tổng hợp số liệu trực tiếp từ kho lưu trữ và chỉ mục văn bản hiện hành."""
    n_fonds = len(archive_mgr.fonds)
    n_dossiers = len(archive_mgr.dossiers)
    n_docs = len(assistant.doc_pages)
    n_pages = sum(len(ps) for ps in assistant.doc_pages.values())

    fond_lines = []
    for f in archive_mgr.fonds.values():
        doc_total = sum(len(d.doc_ids) for d in f.dossiers)
        fond_lines.append(f"- **{f.fond_name}** (`{f.fond_id}`): {len(f.dossiers)} hồ sơ · {doc_total} lượt văn bản")

    mode_counts: dict[str, int] = {}
    for dos in archive_mgr.dossiers.values():
        mode = dos.usage_mode or "Công khai"
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
    mode_summary = ", ".join(f"**{k}**: {v} hồ sơ" for k, v in mode_counts.items()) or "Chưa phân loại"

    return (
        f"### Thống kê Kho lưu trữ Số hóa hiện tại\n"
        f"- **Tổng số Phông lưu trữ:** {n_fonds} phông\n"
        f"- **Tổng số Hồ sơ quản lý:** {n_dossiers} hồ sơ ({mode_summary})\n"
        f"- **Tổng số Văn bản số hóa đã lập chỉ mục:** {n_docs} văn bản ({n_pages} trang tài liệu)\n\n"
        f"**Phân bổ theo từng Phông lưu trữ:**\n"
        + "\n".join(fond_lines)
    )


_HEADING_LINE_RE = re.compile(
    r"^\s*((?i:Điều\s+\d+[a-z]?|Chương\s+[IVXLC\d]+|Mục\s+\d+|Phần\s+[IVXLC\d]+)|[IVXLC]{1,5})\s*[.:)]\s+(.+)$"
)
_BOILERPLATE_HEADING_RE = re.compile(
    r"\b(điều khoản thi hành|hiệu lực thi hành|trách nhiệm thi hành|tổ chức thực hiện|giải thích từ ngữ|nơi nhận)\b",
    re.IGNORECASE,
)
_ACRONYMS = {"UBND", "TTHC", "CNTT", "CCHC", "GD&ĐT", "GDTX", "PDF", "AI", "VN", "TW", "QH", "NĐ", "TT", "HĐND"}
_HEADING_STOP = set("va cua trong cho voi ve tai cac nhung quy dinh nay hoac theo tren duoi sau truoc".split())


def _format_heading_title(title: str) -> str:
    clean = re.sub(r"\s+", " ", title).strip(" .:;,-")
    if clean.isupper():
        words = [w if w.strip("(),/") in _ACRONYMS else w.lower() for w in clean.split()]
        clean = " ".join(words)
    return clean[:1].upper() + clean[1:] if clean else clean


def _extract_doc_headings(assistant: Any, doc_id: str) -> list[tuple[str, str]]:
    """Trích các đề mục cấu trúc có nghĩa (Điều/Chương/Mục/I...) từ các đoạn của một văn bản."""
    primary: list[tuple[str, str]] = []
    secondary: list[tuple[str, str]] = []
    seen_titles: set[str] = set()
    for c in getattr(assistant, "chunks", []):
        if getattr(c, "doc_id", None) != doc_id:
            continue
        for raw_line in (getattr(c, "text", "") or "").splitlines():
            line = raw_line.strip()
            if not line or "|" in line or "nơi nhận" in line.lower():
                continue
            m = _HEADING_LINE_RE.match(line)
            if not m:
                continue
            marker = re.sub(r"\s+", " ", m.group(1)).strip()
            title_raw = m.group(2).strip()
            if ";" in title_raw or len(title_raw) < 6 or len(title_raw) > 76 or len(title_raw.split()) > 13:
                continue
            title = _format_heading_title(title_raw)
            title_norm = remove_diacritics(title).lower()
            if title_norm in seen_titles or re.match(r"^(nay|co hieu luc|cac ong|truong hop)\b", title_norm):
                continue
            seen_titles.add(title_norm)
            if _BOILERPLATE_HEADING_RE.search(title):
                secondary.append((marker, title))
            else:
                primary.append((marker, title))
    return primary + secondary


def _heading_to_question(marker: str, title: str, label: str) -> str | None:
    low = title.lower()
    if low.startswith((
        "quy định ", "yêu cầu ", "nguyên tắc ", "thẩm quyền ", "trách nhiệm ",
        "đối tượng ", "phạm vi ", "mục tiêu ", "quan điểm ", "giải pháp ",
        "nhiệm vụ ", "chế độ ", "tiêu chuẩn ", "điều kiện ", "sửa đổi", "bổ sung", "thay thế",
    )):
        q = f"{title} trong {label} được quy định như thế nào?"
    elif marker.lower().startswith("điều"):
        q = f"{marker} ({title}) của {label} quy định những gì?"
    else:
        q = f"{title} trong {label} được nêu như thế nào?"
    q_norm = remove_diacritics(q).lower()
    if detect_field(q) is not None or _SUMMARY_INTENT.search(q_norm):
        return None
    return q


def _keywords_norm(text: str) -> set[str]:
    toks = re.findall(r"[a-z0-9]+", remove_diacritics(text).lower())
    return {t for t in toks if len(t) >= 2 and t not in _HEADING_STOP}


def _build_contextual_suggestions(
    raw_question: str,
    out: dict[str, Any],
    session: ChatSession,
    assistant: Any,
    archive_mgr: ArchiveManager,
    unique_cited: list[str],
) -> list[str]:
    """Sinh tối đa 4 câu hỏi gợi ý động bám sát đề mục văn bản, trường chưa hỏi và tài liệu liên quan."""
    asked_texts = [m.content for m in getattr(session, "messages", []) if getattr(m, "role", "") == "user"]
    asked_texts.append(raw_question)
    asked_norms = [remove_diacritics(t).lower().strip() for t in asked_texts]
    asked_joined = " \n ".join(asked_norms)
    q_cur_norm = asked_norms[-1]

    candidates: list[str] = []
    seen_q: set[str] = set()

    def _add(q: str | None) -> bool:
        if not q:
            return False
        qn = remove_diacritics(q).lower().strip()
        if qn in seen_q or any(qn == a for a in asked_norms):
            return False
        seen_q.add(qn)
        candidates.append(q)
        return True

    def _topic_already_asked(title: str) -> bool:
        tn = remove_diacritics(title).lower()
        if tn and tn in asked_joined:
            return True
        kws = _keywords_norm(title)
        if len(kws) >= 2 and all(k in q_cur_norm for k in kws):
            return True
        return False

    cards = getattr(assistant, "cards", {}) or {}
    retrieved = out.get("retrieved") or []

    if out.get("status") == "answered" and len(unique_cited) == 1:
        main_doc = unique_cited[0]
        label = assistant.doc_label(main_doc)
        card = cards.get(main_doc)
        headings = _extract_doc_headings(assistant, main_doc)

        # 1. Tối đa 2 câu hỏi đào sâu vào các đề mục khác trong cùng văn bản
        deep_added = 0
        for marker, title in headings:
            if deep_added >= 2:
                break
            if _topic_already_asked(title):
                continue
            if _add(_heading_to_question(marker, title, label)):
                deep_added += 1

        # 2. Trường siêu dữ liệu / hồ sơ / tóm tắt còn chưa hỏi
        cur_field = detect_field(raw_question)
        cur_summary = bool(_SUMMARY_INTENT.search(q_cur_norm))
        cur_dossier = bool(re.search(r"\b(ho so|phong)\b", q_cur_norm))

        if not cur_dossier:
            _add("Văn bản này thuộc hồ sơ lưu trữ nào?")
        if cur_field != "signer" and card and card.value("signer"):
            _add("Ai ký văn bản đó?")
        if cur_field != "issue_date" and card and card.value("issue_date") and len(candidates) < 3:
            _add(f"{label} ban hành ngày nào?")
        if not cur_summary and len(candidates) < 3:
            _add("Tóm tắt văn bản này")

        # 3. Nếu chưa đủ 4 gợi ý (hoặc thêm 1 gợi ý mở rộng), liên kết sang văn bản liên quan cùng truy hồi/hồ sơ
        if len(candidates) < 4:
            rel_docs: list[str] = []
            for r in retrieved:
                d_id = r.get("doc_id")
                if d_id and d_id != main_doc and d_id not in rel_docs:
                    rel_docs.append(d_id)
            if not rel_docs:
                arch_info = archive_mgr.get_doc_archive_info(main_doc)
                fc = arch_info.get("file_code")
                dos = archive_mgr.dossiers.get(fc) if fc else None
                if dos:
                    rel_docs = [d_id for d_id in dos.doc_ids if d_id != main_doc and d_id in assistant.doc_pages]
            for rd in rel_docs:
                if len(candidates) >= 4:
                    break
                r_label = assistant.doc_label(rd)
                r_headings = _extract_doc_headings(assistant, rd)
                picked_q = None
                for marker, title in r_headings:
                    if not _topic_already_asked(title):
                        picked_q = _heading_to_question(marker, title, r_label)
                        if picked_q:
                            break
                if picked_q is None:
                    picked_q = f"Tóm tắt {r_label}"
                _add(picked_q)

    elif out.get("status") == "answered" and len(unique_cited) > 1:
        q_kws = _keywords_norm(raw_question)
        for d_id in unique_cited[:3]:
            if len(candidates) >= 3:
                break
            d_label = assistant.doc_label(d_id)
            d_headings = _extract_doc_headings(assistant, d_id)
            ranked = sorted(
                d_headings,
                key=lambda ht: -len(_keywords_norm(ht[1]) & q_kws),
            )
            picked_q = None
            for marker, title in ranked:
                if not _topic_already_asked(title):
                    picked_q = _heading_to_question(marker, title, d_label)
                    if picked_q:
                        break
            _add(picked_q or f"Tóm tắt {d_label}")
        if unique_cited:
            arch_info = archive_mgr.get_doc_archive_info(unique_cited[0])
            fc = arch_info.get("file_code")
            dos = archive_mgr.dossiers.get(fc) if fc else None
            if dos and dos.title:
                dos_label = dos.title if dos.title.lower().startswith("hồ sơ") else f"Hồ sơ {dos.title}"
                _add(f"{dos_label} gồm những văn bản nào?")

    else:
        near_docs = []
        for r in retrieved:
            d_id = r.get("doc_id")
            if d_id and d_id not in near_docs and float(r.get("coverage", 0.0)) >= 0.2:
                near_docs.append(d_id)
        for d_id in near_docs[:2]:
            d_label = assistant.doc_label(d_id)
            d_headings = _extract_doc_headings(assistant, d_id)
            picked_q = None
            for marker, title in d_headings:
                if not _topic_already_asked(title):
                    picked_q = _heading_to_question(marker, title, d_label)
                    if picked_q:
                        break
            _add(picked_q or f"Tóm tắt {d_label}")
        _add("Thống kê kho lưu trữ hiện có gì?")
        _add("Có những phông lưu trữ nào?")

    return candidates[:4]


_ARCHIVE_REG_NORM_RE = re.compile(
    r"\b(?:thong tu\s*(?:so\s*)?02(?:/2019(?:/tt-bnv)?)?|02/2019/tt-bnv|"
    r"nghi dinh\s*(?:so\s*)?30(?:/2020(?:/nd-cp)?)?|30/2020/nd-cp|156/2026/tt-btc)\b"
)
_ARCHIVE_REG_RAW_RE = re.compile(
    r"\b(?:02/2019/TT-BNV|30/2020/N[ĐD]-CP|156/2026/TT-BTC)\b",
    re.IGNORECASE,
)


def handle_archive_query(
    question: str,
    session: ChatSession,
    assistant: Assistant,
    archive_mgr: ArchiveManager,
    generator: Any = None,
    doc_ids: list[str] | None = None,
    user_role: str = "public",
    file_code: str | None = None,
    year: str | None = None,
    usage_mode: str | None = None,
) -> dict[str, Any]:
    """Xử lý câu hỏi nghiệp vụ Lưu trữ số hóa đa vòng."""
    if session.last_role is not None and session.last_role != user_role:
        session.messages.clear()
        session.active_doc_id = None
        session.active_file_code = None
    session.last_role = user_role

    raw_question = question.strip()
    resolved_q, auto_doc_ids = resolve_anaphora(raw_question, session, assistant)
    effective_doc_ids = doc_ids if doc_ids is not None else auto_doc_ids

    q_norm = remove_diacritics(resolved_q).lower()
    q_clean = re.sub(r"[^\w\s/]", " ", q_norm).strip()
    q_clean = re.sub(r"\s+", " ", q_clean)
    q_doc_check = _ARCHIVE_REG_NORM_RE.sub(" ", q_norm)
    raw_doc_check = _ARCHIVE_REG_RAW_RE.sub(" ", raw_question)
    is_specific_doc_q = bool(
        assistant.find_doc(raw_question) is not None
        or re.search(r"\b\d+\s*/|\b(quyet dinh|nghi dinh|chi thi|cong van|thong bao|thong tu|nghi quyet)\s+\d+", q_doc_check)
        or _DOC_REF.search(raw_doc_check)
    )

    default_suggestions = [
        "Có những phông lưu trữ nào?",
        "Thống kê kho lưu trữ hiện có gì?",
        "Hồ sơ Chuyển đổi số gồm những văn bản nào?",
        "Thủ tục xin trích lục hồ sơ thế nào?",
    ]

    # --- 0. GIAO TIẾP HỘI THOẠI, HƯỚNG DẪN & THỐNG KÊ HỆ THỐNG ---
    if not is_specific_doc_q:
        if re.fullmatch(r"(ok|oke|okay|tot lam|tuyet voi|hay qua|duoc roi|hieu roi)", q_clean) or (
            len(q_clean.split()) <= 8 and re.search(r"\b(cam on|thank|thanks|tam biet|bye|goodbye)\b", q_clean)
        ):
            return _make_reply(
                session,
                raw_question,
                "Rất vui được hỗ trợ bạn! Nếu bạn cần tra cứu thêm nội dung văn bản, kiểm tra hồ sơ theo Thông tư 02/2019/TT-BNV hoặc hỏi thủ tục nộp lưu/trích lục, hãy nhắn cho tôi bất cứ lúc nào nhé.",
                kind="conversation",
                reason="Phản hồi hội thoại tự nhiên.",
                suggestions=default_suggestions[:3],
            )

        is_greeting = bool(
            re.match(r"^(xin chao|chao ban|chao|hello|hi|hey|alo|chao tro ly|chao ai)(\b|$)", q_clean)
            or re.search(r"\b(ban la ai|ban ten gi|tu gioi thieu|gioi thieu ve ban)\b", q_clean)
        )
        if is_greeting and len(q_clean.split()) <= 12:
            n_docs = len(assistant.doc_pages)
            n_dos = len(archive_mgr.dossiers)
            reply_text = (
                "Xin chào! Tôi là **Trợ lý Số Lưu trữ tỉnh Thái Nguyên**. "
                f"Hiện tôi đang kết nối trực tiếp với **{n_dos} hồ sơ** và **{n_docs} văn bản số hóa** trong kho.\n\n"
                "Bạn có thể trò chuyện hoặc nhờ tôi thực hiện:\n"
                "- **Hỏi đáp nội dung văn bản:** Kèm trích dẫn `[1]` trỏ thẳng tới trang PDF có tô vàng (hỗ trợ hỏi nối tiếp như *“Ai ký?”*, *“Ban hành khi nào?”*).\n"
                "- **Tra cứu Phông & Hồ sơ:** Xem cấu trúc Phông lưu trữ, danh sách văn bản thuộc từng mã hồ sơ.\n"
                "- **Thống kê kho trực tiếp:** Kiểm tra nhanh số lượng hồ sơ, văn bản, trang số hóa theo từng Phông.\n"
                "- **Tư vấn quy trình nghiệp vụ:** Thủ tục trích lục, nộp lưu, tiêu chuẩn số hóa PDF/A theo NĐ 30/2020/NĐ-CP & TT 02/2019/TT-BNV."
            )
            return _make_reply(
                session,
                raw_question,
                reply_text,
                kind="conversation",
                reason="Chào hỏi và giới thiệu khả năng trợ lý.",
                suggestions=default_suggestions,
            )

        if re.search(r"\b(ban lam duoc gi|lam duoc gi|co chuc nang gi|huong dan su dung|huong dan dung|cach dung|cach su dung|giup do|tro giup|help)\b", q_clean):
            reply_text = (
                "### Hướng dẫn tương tác với Trợ lý AI Lưu trữ\n"
                "Tôi hỗ trợ tra cứu và giải đáp dựa trên kho tài liệu số hóa thật theo nguyên tắc **chỉ trả lời khi có căn cứ**:\n"
                "- **Hỏi chi tiết văn bản:** Ví dụ `Ai ký Nghị định 385/2026/NĐ-CP?` hoặc `Mục tiêu chuyển đổi số tỉnh Thái Nguyên là gì?`\n"
                "- **Hỏi nối tiếp ngữ cảnh:** Sau khi hỏi một văn bản, bạn có thể hỏi ngắn gọn `Ban hành khi nào?` hoặc `Tóm tắt văn bản này`.\n"
                "- **Tra cứu danh mục & số liệu:** Hỏi `Có những phông lưu trữ nào?` hoặc `Thống kê kho lưu trữ`.\n"
                "- **Xem nguồn gốc:** Nhấp vào thẻ số `[1]` trong câu trả lời để mở trang PDF gốc có tô vàng đúng đoạn căn cứ."
            )
            return _make_reply(
                session,
                raw_question,
                reply_text,
                kind="conversation",
                reason="Hướng dẫn sử dụng trợ lý AI.",
                suggestions=default_suggestions,
            )

        is_stats_q = bool(
            re.search(r"\b(thong ke kho|thong ke he thong|thong ke luu tru|tong quan kho|kho co gi|kho luu tru co gi|bao nhieu van ban|bao nhieu ho so|bao nhieu trang|bao nhieu phong)\b", q_clean)
            or (len(q_clean.split()) <= 4 and "thong ke" in q_clean)
        )
        if is_stats_q:
            reply_text = _build_live_stats_reply(assistant, archive_mgr)
            return _make_reply(
                session,
                raw_question,
                reply_text,
                kind="archive_stats",
                reason="Thống kê số liệu trực tiếp từ kho lưu trữ và chỉ mục hiện hành.",
                suggestions=[
                    "Có những phông lưu trữ nào?",
                    "Hồ sơ Chuyển đổi số gồm những văn bản nào?",
                    "Tiêu chuẩn số hóa tài liệu theo Thông tư 02?",
                ],
            )

    # --- 1. NHẬN DIỆN Ý ĐỊNH: THỦ TỤC & QUY TRÌNH LƯU TRỮ THÁI NGUYÊN ---
    if not is_specific_doc_q and re.search(r"\b(trich luc|xin cap ban sao|khai thac tai lieu|muon doc)\b", q_norm):
        return _make_reply(
            session,
            raw_question,
            THAI_NGUYEN_ARCHIVE_KNOWLEDGE["trich_luc"],
            kind="procedure",
            reason="Quy chế khai thác và cấp trích lục hồ sơ của Trung tâm Lưu trữ Lịch sử tỉnh Thái Nguyên.",
            citations=[
                {
                    "doc_id": "GUIDE_TRICH_LUC",
                    "label": "Quy chế Khai thác Lưu trữ Lịch sử Thái Nguyên",
                    "page_no": 1,
                    "text": "Thủ tục xin cấp bản sao, trích lục tài liệu lưu trữ tại tỉnh Thái Nguyên.",
                }
            ],
            suggestions=[
                "Quy trình nộp lưu tài liệu theo Thông tư 02/2019/TT-BNV?",
                "Tiêu chuẩn số hóa scan 300 DPI là gì?",
                "Có những phông lưu trữ nào?",
            ],
        )

    if not is_specific_doc_q and re.search(r"\b(nop luu|giao nop|thoi han nop luu)\b", q_norm):
        return _make_reply(
            session,
            raw_question,
            THAI_NGUYEN_ARCHIVE_KNOWLEDGE["nop_luu"],
            kind="procedure",
            reason="Quy định nộp lưu tài liệu điện tử theo Thông tư 02/2019/TT-BNV và tỉnh Thái Nguyên.",
            citations=[
                {
                    "doc_id": "GUIDE_NOP_LUU",
                    "label": "Hướng dẫn nộp lưu tài liệu số hóa tỉnh Thái Nguyên",
                    "page_no": 1,
                    "text": "Quy trình nộp lưu hồ sơ tài liệu vào Lưu trữ lịch sử tỉnh.",
                }
            ],
            suggestions=[
                "Tiêu chuẩn số hóa scan PDF/A theo Thông tư 02?",
                "Thủ tục xin cấp bản sao trích lục hồ sơ lưu trữ thế nào?",
                "Có những phông lưu trữ nào?",
            ],
        )

    if not is_specific_doc_q and re.search(r"\b(tieu chuan so hoa|scan|do phan giai|dpi|pdf/a)\b", q_norm):
        return _make_reply(
            session,
            raw_question,
            THAI_NGUYEN_ARCHIVE_KNOWLEDGE["tieu_chuan_so_hoa"],
            kind="procedure",
            reason="Tiêu chuẩn kỹ thuật số hóa tài liệu theo Thông tư 02/2019/TT-BNV.",
            citations=[
                {
                    "doc_id": "GUIDE_SCAN_STD",
                    "label": "Thông tư số 02/2019/TT-BNV",
                    "page_no": 1,
                    "text": "Quy định tiêu chuẩn dữ liệu thông tin đầu vào và quản lý CSDL lưu trữ điện tử.",
                }
            ],
            suggestions=[
                "Quy trình nộp lưu tài liệu theo Thông tư 02/2019/TT-BNV?",
                "Thống kê kho lưu trữ hiện có gì?",
            ],
        )

    # --- 1b. HỎI VĂN BẢN THUỘC HỒ SƠ LƯU TRỮ NÀO ---
    if re.search(r"\b(thuoc ho so( luu tru)? nao|nam trong ho so nao)\b", q_norm):
        target_doc_id = assistant.find_doc(raw_question)
        if target_doc_id is None and effective_doc_ids and len(effective_doc_ids) == 1:
            target_doc_id = effective_doc_ids[0]
        if target_doc_id is None and session.active_doc_id and (
            effective_doc_ids is None or session.active_doc_id in effective_doc_ids
        ):
            target_doc_id = session.active_doc_id
        if target_doc_id:
            arch_info = archive_mgr.get_doc_archive_info(target_doc_id)
            if not is_access_allowed(arch_info.get("usage_mode"), user_role):
                return _access_denied_response(raw_question, session, [arch_info.get("usage_mode", "Nội bộ")], user_role)
            session.active_doc_id = target_doc_id
            session.active_file_code = arch_info.get("file_code")
            label = assistant.doc_label(target_doc_id)
            reply_text = (
                f"**{label}** hiện được phân loại vào hồ sơ lưu trữ:\n"
                f"- **Phông:** {arch_info.get('fond_name')}\n"
                f"- **Mã hồ sơ:** `{arch_info.get('file_code')}`\n"
                f"- **Tiêu đề hồ sơ:** {arch_info.get('dossier_title')}\n"
                f"- **Thời hạn bảo quản:** {arch_info.get('retention_period')} | **Chế độ:** {arch_info.get('usage_mode')}"
            )
            return _make_reply(
                session,
                raw_question,
                reply_text,
                kind="dossier_detail",
                reason=f"Tra cứu phân loại Phông và Hồ sơ của văn bản {target_doc_id}.",
                suggestions=[f"Tóm tắt {label}", f"Ai ký {label}?"],
            )

    # --- 2. NHẬN DIỆN Ý ĐỊNH: TRA CỨU DANH MỤC PHÔNG & HỒ SƠ ---
    # Ví dụ: "Phông UBND tỉnh có những hồ sơ nào?", "Có những phông lưu trữ nào?"
    if not is_specific_doc_q and re.search(r"\b(phong luu tru|danh sach phong|cac phong luu tru|co nhung phong|thong tin phong)\b", q_norm):
        fonds_list = []
        for f in archive_mgr.fonds.values():
            fonds_list.append(f"• **{f.fond_name}** (`{f.fond_id}`): {f.description} (gồm {len(f.dossiers)} hồ sơ)")
        reply_text = "Hiện tại kho lưu trữ số hóa tỉnh Thái Nguyên đang quản lý các Phông lưu trữ sau:\n\n" + "\n".join(fonds_list)
        return _make_reply(
            session,
            raw_question,
            reply_text,
            kind="archive_catalog",
            reason="Tra cứu danh mục Phông lưu trữ theo Thông tư 02/2019/TT-BNV.",
            citations=[],
            suggestions=[
                "Thống kê kho lưu trữ hiện có gì?",
                "Hồ sơ chỉ đạo triển khai Chuyển đổi số gồm những văn bản nào?",
                "Hồ sơ kiểm soát thủ tục hành chính gồm những văn bản nào?",
            ],
        )

    # Kiểm tra hỏi về hồ sơ cụ thể qua từ khóa (vd: "hồ sơ chuyển đổi số", "hồ sơ quy hoạch")
    if not is_specific_doc_q and re.search(r"\b(ho so.*gom|ho so.*co nhung|danh sach van ban|cac ho so|ho so luu tru)\b", q_norm):
        # Tìm hồ sơ phù hợp nhất: ưu tiên khớp đúng mã hồ sơ trước, sau đó mới xét trùng từ tiêu đề
        matched_dos = next(
            (dos for dos in archive_mgr.dossiers.values() if dos.file_code.lower() in q_norm),
            None,
        )
        if matched_dos is None:
            q_words = set(q_norm.split()) - {"ho", "so", "nam", "cac", "van", "ban", "gom", "co", "nhung", "nao"}
            best_overlap = 1
            for dos in archive_mgr.dossiers.values():
                dos_words = set(remove_diacritics(dos.title).lower().split())
                overlap = len(dos_words & q_words)
                if overlap > best_overlap:
                    best_overlap = overlap
                    matched_dos = dos

        if matched_dos:
            if not is_access_allowed(matched_dos.usage_mode, user_role):
                return _access_denied_response(raw_question, session, [matched_dos.usage_mode], user_role)

            session.active_file_code = matched_dos.file_code
            docs_summary = []
            for d_id in matched_dos.doc_ids:
                c = assistant.cards.get(d_id)
                subj = (c.value("subject") or c.value("title") or "") if c else ""
                label = assistant.doc_label(d_id)
                if subj:
                    docs_summary.append(f"• **{label}**: {subj[:100]}...")
                else:
                    docs_summary.append(f"• **{label}**")

            reply_text = (
                f"**Hồ sơ:** {matched_dos.title}\n"
                f"- **Mã hồ sơ:** `{matched_dos.file_code}`\n"
                f"- **Phông:** {matched_dos.fond_name}\n"
                f"- **Thời hạn bảo quản:** {matched_dos.retention_period} | **Chế độ:** {matched_dos.usage_mode}\n"
                f"- **Đơn vị lập hồ sơ:** {matched_dos.creator_unit}\n\n"
                f"**Các văn bản trong hồ sơ ({len(matched_dos.doc_ids)} văn bản):**\n"
                + "\n".join(docs_summary)
            )
            dos_suggestions = ["Có những phông lưu trữ nào?", "Thủ tục xin trích lục hồ sơ thế nào?"]
            if matched_dos.doc_ids:
                first_lbl = assistant.doc_label(matched_dos.doc_ids[0])
                dos_suggestions.insert(0, f"Tóm tắt nội dung chính của {first_lbl}?")
            return _make_reply(
                session,
                raw_question,
                reply_text,
                kind="dossier_detail",
                reason=f"Tra cứu mục lục hồ sơ {matched_dos.file_code}.",
                citations=[],
                suggestions=dos_suggestions,
            )

    # --- 3. Ý ĐỊNH RAG NỘI DUNG VĂN BẢN (GỌI CỐT LÕI ASSISTANT CÓ DẪN NGUỒN KÉP) ---
    base_ids = set(effective_doc_ids) if effective_doc_ids is not None else set(assistant.doc_pages.keys())
    has_filter = any([effective_doc_ids is not None, file_code, year, usage_mode])

    if file_code or usage_mode:
        arch_filtered = archive_mgr.filter_doc_ids(file_code=file_code, usage_mode=usage_mode)
        if arch_filtered is not None:
            base_ids &= arch_filtered

    if year:
        target_year = year.strip()
        year_matched = set()
        for d_id in base_ids:
            card = assistant.cards.get(d_id)
            c_year = extract_year(card.value("issue_date") if card else None)
            if c_year == target_year:
                year_matched.add(d_id)
        base_ids = year_matched

    if base_ids:
        allowed_ids = [
            d_id
            for d_id in sorted(base_ids)
            if is_access_allowed(archive_mgr.get_doc_archive_info(d_id).get("usage_mode"), user_role)
        ]
        if not allowed_ids:
            blocked_modes = sorted(
                {archive_mgr.get_doc_archive_info(d_id).get("usage_mode", "Nội bộ") for d_id in base_ids}
            )
            return _access_denied_response(raw_question, session, blocked_modes, user_role)
        qa_doc_ids = allowed_ids if (has_filter or len(allowed_ids) < len(assistant.doc_pages)) else None
    else:
        qa_doc_ids = [] if has_filter else None

    ans: Answer = assistant.ask(resolved_q, doc_ids=qa_doc_ids, generator=generator)
    out = asdict(ans)

    # Đính kèm thông tin Phông và Hồ sơ vào từng trích dẫn citations
    cited_docs: list[str] = []
    for c in out["citations"]:
        doc_id = c.get("doc_id")
        c["label"] = assistant.doc_label(doc_id)
        if doc_id:
            cited_docs.append(doc_id)
            arch_info = archive_mgr.get_doc_archive_info(doc_id)
            c["fond_name"] = arch_info.get("fond_name", "")
            c["file_code"] = arch_info.get("file_code", "")
            c["dossier_title"] = arch_info.get("dossier_title", "")
            c["retention_period"] = arch_info.get("retention_period", "")
    unique_cited = list(dict.fromkeys(cited_docs))
    if len(unique_cited) == 1:
        session.active_doc_id = unique_cited[0]
    elif out.get("kind") == "list" and len(unique_cited) > 1:
        session.active_doc_id = None

    out["suggestions"] = _build_contextual_suggestions(
        raw_question=raw_question,
        out=out,
        session=session,
        assistant=assistant,
        archive_mgr=archive_mgr,
        unique_cited=unique_cited,
    )

    out["session_id"] = session.session_id

    # Lưu lại lịch sử hội thoại
    session.add_message("user", raw_question)
    session.add_message("assistant", out["text"], citations=out["citations"], kind=out.get("kind", "rag"))

    return out
