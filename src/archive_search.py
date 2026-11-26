"""Công cụ tra cứu nghiệp vụ đa tiêu chí và Tra cứu chuyên sâu Nội dung Văn bản (Deep Content Search).

Kết hợp lọc siêu dữ liệu Thông tư 02/2019/TT-BNV + Nghị định 30/2020/NĐ-CP
với truy hồi toàn văn và ngữ nghĩa (BM25 + e5 qua RRF).
"""
from __future__ import annotations

import html
import re
from dataclasses import asdict, dataclass
from typing import Any

from src.archive import ArchiveManager, get_archive_manager, is_access_allowed
from src.qa import Assistant
from src.text import normalize_text, remove_diacritics


def extract_year(date_str: str | None) -> str | None:
    if not date_str:
        return None
    m = re.search(r"\b(19\d{2}|20\d{2})\b", date_str)
    return m.group(1) if m else None


def _parse_date_tuple(date_str: str | None) -> tuple[int, int, int]:
    """Đổi ngày dd/mm/yyyy (hoặc yyyy) sang bộ (year, month, day) để sắp xếp đúng thứ tự thời gian."""
    if not date_str:
        return (0, 0, 0)
    m = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})", date_str)
    if m:
        return (int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m_vn = re.search(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", date_str, re.IGNORECASE)
    if m_vn:
        return (int(m_vn.group(3)), int(m_vn.group(2)), int(m_vn.group(1)))
    y = extract_year(date_str)
    return (int(y), 0, 0) if y else (0, 0, 0)


def highlight_keywords(text: str, query: str) -> str:
    """Tô sáng (bôi đậm <mark>) các từ khóa của câu hỏi trong đoạn văn bản."""
    clean_text = html.escape(text)
    if not query.strip():
        return clean_text

    # Tách các từ khóa có nghĩa
    words = [re.escape(w) for w in query.strip().split() if len(w) >= 2]
    if not words:
        return clean_text

    pattern = re.compile(r"(" + "|".join(words) + r")", re.IGNORECASE)
    return pattern.sub(r"<mark class='kw-highlight'>\1</mark>", clean_text)


@dataclass
class SearchFilter:
    query: str = ""
    fond_id: str | None = None
    file_code: str | None = None
    doc_type: str | None = None
    year: str | None = None
    issuer: str | None = None
    signer: str | None = None
    retention_period: str | None = None
    usage_mode: str | None = None
    user_role: str = "public"
    search_mode: str = "content"   # "content" (tra cứu đoạn nội dung) | "doc" (tra cứu văn bản)
    page: int = 1
    page_size: int = 10


def search_content_passages(
    assistant: Assistant,
    filters: SearchFilter,
    candidate_doc_ids: set[str],
    mgr: ArchiveManager,
) -> dict[str, Any]:
    """Tra cứu chuyên sâu theo từng đoạn nội dung văn bản (Passage-level Retrieval)."""
    query_str = (filters.query or "").strip()
    matches = []

    if query_str and candidate_doc_ids:
        # Tìm kiếm bằng HybridIndex (BM25 + TF-IDF + e5 qua RRF)
        hits = assistant.index.search(query_str, k=150, doc_ids=candidate_doc_ids)

        for hit in hits:
            chunk = hit["chunk"]
            card = assistant.cards.get(chunk.doc_id)
            arch_info = mgr.get_doc_archive_info(chunk.doc_id)
            pages = assistant.doc_pages.get(chunk.doc_id, [])

            snippet_raw = chunk.text.strip()
            if len(snippet_raw) > 350:
                snippet_raw = snippet_raw[:350] + "..."

            snippet_html = highlight_keywords(snippet_raw, query_str)

            matches.append({
                "doc_id": chunk.doc_id,
                "label": assistant.doc_label(chunk.doc_id),
                "doc_number": card.value("doc_number") if card else None,
                "doc_type": card.value("doc_type") if card else None,
                "issue_date": card.value("issue_date") if card else None,
                "issuer": card.value("issuer") if card else None,
                "signer": card.value("signer") if card else None,
                "fond_id": arch_info.get("fond_id"),
                "fond_name": arch_info.get("fond_name"),
                "file_code": arch_info.get("file_code"),
                "dossier_title": arch_info.get("dossier_title"),
                "retention_period": arch_info.get("retention_period"),
                "usage_mode": arch_info.get("usage_mode"),
                "page_no": chunk.page_no,
                "n_pages": len(pages),
                "start": chunk.start,
                "end": chunk.end,
                "snippet": snippet_raw,
                "snippet_html": snippet_html,
                "score": round(hit.get("rrf", 0.0), 4),
            })
    else:
        # Nếu không có query: Lấy đoạn đầu trang 1 của các văn bản phù hợp
        sorted_docs = sorted(candidate_doc_ids)
        for doc_id in sorted_docs:
            card = assistant.cards.get(doc_id)
            arch_info = mgr.get_doc_archive_info(doc_id)
            pages = assistant.doc_pages.get(doc_id, [])
            p1_text = pages[0]["text"] if pages else ""
            snippet_raw = (p1_text[:300] + "...") if len(p1_text) > 300 else p1_text

            matches.append({
                "doc_id": doc_id,
                "label": assistant.doc_label(doc_id),
                "doc_number": card.value("doc_number") if card else None,
                "doc_type": card.value("doc_type") if card else None,
                "issue_date": card.value("issue_date") if card else None,
                "issuer": card.value("issuer") if card else None,
                "signer": card.value("signer") if card else None,
                "fond_id": arch_info.get("fond_id"),
                "fond_name": arch_info.get("fond_name"),
                "file_code": arch_info.get("file_code"),
                "dossier_title": arch_info.get("dossier_title"),
                "retention_period": arch_info.get("retention_period"),
                "usage_mode": arch_info.get("usage_mode"),
                "page_no": 1,
                "n_pages": len(pages),
                "start": 0,
                "end": min(200, len(p1_text)),
                "snippet": snippet_raw,
                "snippet_html": html.escape(snippet_raw),
                "score": 0.0,
            })

    # Phân trang
    total_matches = len(matches)
    unique_docs = len({m["doc_id"] for m in matches})
    start_idx = (filters.page - 1) * filters.page_size
    end_idx = start_idx + filters.page_size

    return {
        "total": total_matches,
        "total_docs": unique_docs,
        "page": filters.page,
        "page_size": filters.page_size,
        "items": matches[start_idx:end_idx],
    }


def faceted_search(
    assistant: Assistant,
    filters: SearchFilter,
    archive_mgr: ArchiveManager | None = None,
) -> dict[str, Any]:
    """Tìm kiếm kết hợp lọc đa tiêu chí và xếp hạng toàn văn / ngữ nghĩa."""
    mgr = archive_mgr or get_archive_manager()

    # 1. Thu thập ứng viên theo siêu dữ liệu lưu trữ
    archive_candidates = mgr.filter_doc_ids(
        fond_id=filters.fond_id,
        file_code=filters.file_code,
        retention_period=filters.retention_period,
        usage_mode=filters.usage_mode,
    )

    all_doc_ids = set(assistant.doc_pages.keys())
    if archive_candidates is not None:
        matched_ids = all_doc_ids & archive_candidates
    else:
        matched_ids = set(all_doc_ids)

    # 2. Lọc theo siêu dữ liệu văn bản (thẻ thông tin DocCard)
    has_card_filters = any([filters.doc_type, filters.year, filters.issuer, filters.signer])
    final_candidates = set()
    for doc_id in matched_ids:
        card = assistant.cards.get(doc_id)
        if not card:
            if not has_card_filters:
                final_candidates.add(doc_id)
            continue

        c_type = card.value("doc_type") or ""
        c_date = card.value("issue_date") or ""
        c_year = extract_year(c_date)
        c_issuer = card.value("issuer") or ""
        c_signer = card.value("signer") or ""

        if filters.doc_type and filters.doc_type.strip().lower() not in c_type.lower():
            continue
        if filters.year and filters.year.strip() != c_year:
            continue
        if filters.issuer:
            clean_filter_iss = remove_diacritics(filters.issuer).lower()
            clean_c_iss = remove_diacritics(c_issuer).lower()
            if clean_filter_iss not in clean_c_iss:
                continue
        if filters.signer:
            clean_filter_sig = remove_diacritics(filters.signer).lower()
            clean_c_sig = remove_diacritics(c_signer).lower()
            if clean_filter_sig not in clean_c_sig:
                continue

        final_candidates.add(doc_id)

    # 2b. Kiểm tra quyền tiếp cận mô phỏng theo usage_mode của hồ sơ
    if final_candidates:
        allowed_candidates = {
            doc_id
            for doc_id in final_candidates
            if is_access_allowed(mgr.get_doc_archive_info(doc_id).get("usage_mode"), filters.user_role)
        }
        if not allowed_candidates:
            blocked_modes = sorted(
                {mgr.get_doc_archive_info(d).get("usage_mode", "Nội bộ") for d in final_candidates}
            )
            modes_str = ", ".join(blocked_modes)
            return {
                "status": "access_denied",
                "access_denied": True,
                "message": (
                    f"Từ chối truy cập: Tất cả {len(final_candidates)} văn bản phù hợp thuộc mức tiếp cận "
                    f"hạn chế ({modes_str}), không khả dụng cho vai trò '{filters.user_role}' (mô phỏng)."
                ),
                "blocked_usage_modes": blocked_modes,
                "simulated": True,
                "total": 0,
                "total_docs": 0,
                "page": filters.page,
                "page_size": filters.page_size,
                "items": [],
                "facets": {
                    "fonds": {},
                    "doc_types": {},
                    "years": {},
                    "retention_periods": {},
                    "usage_modes": {},
                },
            }
        final_candidates = allowed_candidates

    # 3. Tính toán các khía cạnh thống kê (Facets count) trên tập ứng viên phù hợp
    facet_fonds: dict[str, int] = {}
    facet_doc_types: dict[str, int] = {}
    facet_years: dict[str, int] = {}
    facet_retentions: dict[str, int] = {}
    facet_usages: dict[str, int] = {}

    for doc_id in final_candidates:
        arch_info = mgr.get_doc_archive_info(doc_id)
        card = assistant.cards.get(doc_id)
        d_type = card.value("doc_type") if card else None
        d_date = card.value("issue_date") if card else None
        d_year = extract_year(d_date)

        f_name = arch_info.get("fond_name") or "Khác"
        facet_fonds[f_name] = facet_fonds.get(f_name, 0) + 1

        if d_type:
            facet_doc_types[d_type] = facet_doc_types.get(d_type, 0) + 1

        if d_year:
            facet_years[d_year] = facet_years.get(d_year, 0) + 1

        ret = arch_info.get("retention_period") or "Chưa rõ"
        facet_retentions[ret] = facet_retentions.get(ret, 0) + 1

        usage = arch_info.get("usage_mode") or "Công khai"
        facet_usages[usage] = facet_usages.get(usage, 0) + 1

    facets_dict = {
        "fonds": dict(sorted(facet_fonds.items(), key=lambda x: -x[1])),
        "doc_types": dict(sorted(facet_doc_types.items(), key=lambda x: -x[1])),
        "years": dict(sorted(facet_years.items(), key=lambda x: -x[1])),
        "retention_periods": dict(sorted(facet_retentions.items(), key=lambda x: -x[1])),
        "usage_modes": dict(sorted(facet_usages.items(), key=lambda x: -x[1])),
    }

    # 4. Nếu chế độ là tra cứu đoạn nội dung (content search)
    if filters.search_mode == "content":
        res = search_content_passages(assistant, filters, final_candidates, mgr)
        res["facets"] = facets_dict
        return res

    # 5. Chế độ tra cứu cấp độ văn bản (doc search)
    query_str = (filters.query or "").strip()
    ranked_doc_ids: list[tuple[str, str, float]] = []

    if query_str and final_candidates:
        hits = assistant.index.search(query_str, k=200, doc_ids=final_candidates)
        seen_docs: set[str] = set()
        for hit in hits:
            chunk = hit["chunk"]
            if chunk.doc_id in seen_docs:
                continue
            seen_docs.add(chunk.doc_id)
            snippet = chunk.text[:220] + ("..." if len(chunk.text) > 220 else "")
            ranked_doc_ids.append((chunk.doc_id, snippet, hit.get("rrf", 0.0)))
    else:
        def sort_key(d_id: str):
            c = assistant.cards.get(d_id)
            date_s = (c.value("issue_date") or "") if c else ""
            return (_parse_date_tuple(date_s), d_id)

        sorted_docs = sorted(final_candidates, key=sort_key, reverse=True)
        for doc_id in sorted_docs:
            card = assistant.cards.get(doc_id)
            subj = (card.value("subject") or card.value("title") or "") if card else ""
            ranked_doc_ids.append((doc_id, subj[:200], 0.0))

    total = len(ranked_doc_ids)
    page_no = max(1, filters.page)
    start_idx = (page_no - 1) * filters.page_size
    end_idx = start_idx + filters.page_size
    page_slice = ranked_doc_ids[start_idx:end_idx]

    items = []
    for doc_id, snippet, score in page_slice:
        card = assistant.cards.get(doc_id)
        arch_info = mgr.get_doc_archive_info(doc_id)
        pages = assistant.doc_pages.get(doc_id, [])

        items.append({
            "doc_id": doc_id,
            "label": assistant.doc_label(doc_id),
            "doc_type": card.value("doc_type") if card else None,
            "doc_number": card.value("doc_number") if card else None,
            "issue_date": card.value("issue_date") if card else None,
            "issuer": card.value("issuer") if card else None,
            "signer": card.value("signer") if card else None,
            "subject": (card.value("subject") or card.value("title")) if card else None,
            "fond_id": arch_info.get("fond_id"),
            "fond_name": arch_info.get("fond_name"),
            "file_code": arch_info.get("file_code"),
            "dossier_title": arch_info.get("dossier_title"),
            "retention_period": arch_info.get("retention_period"),
            "usage_mode": arch_info.get("usage_mode"),
            "n_pages": len(pages),
            "snippet": snippet,
            "snippet_html": highlight_keywords(snippet, query_str),
            "score": round(score, 4),
            "search_score": round(score, 4),
        })

    return {
        "total": total,
        "total_docs": total,
        "page": filters.page,
        "page_size": filters.page_size,
        "items": items,
        "facets": facets_dict,
    }
