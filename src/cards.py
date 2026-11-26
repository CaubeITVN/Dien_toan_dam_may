"""Dựng thẻ thông tin cho cả kho và chấm luật so với nhãn bạc của cổng vanban.chinhphu.vn.

Nhãn `ref_*` trong data/sources.csv lấy từ trang chi tiết của cổng, độc lập với luật (không rò rỉ nhãn),
nhưng vẫn là BẠC: chưa người duyệt, và PDF bản đăng cổng đôi khi để trống số/ngày.
Chấm theo slide 9/46: số ký hiệu và ngày khớp sau chuẩn hóa, cơ quan F1 âm tiết ≥ 0,7, trích yếu độ phủ ≥ 0,7.

Chạy từ gốc Du_an/:  python -m src.cards [--split dev]
"""
import argparse
import csv
import json
import sys
from collections import defaultdict

from src.config import DATA_DIR, EVAL_TEST, RESULTS_DIR
from src.extract_rules import DocCard, extract_card, normalize_doc_number
from src.ingest import PAGES_PATH, PROCESSED_DIR, read_jsonl, read_manifest, write_jsonl
from src.metrics import keyword_coverage, keyword_f1
from src.text import normalize_text

CARDS_PATH = PROCESSED_DIR / "cards.jsonl"
SOURCES_PATH = DATA_DIR / "sources.csv"
EVAL_FIELDS = ["doc_type", "doc_number", "issue_date", "issuer", "signer", "subject"]
KEYWORD_THRESHOLD = 0.7


def pages_by_doc(pages: list[dict]) -> dict[str, list[dict]]:
    out = defaultdict(list)
    for p in pages:
        out[p["doc_id"]].append(p)
    return out


def build_cards(pages: list[dict]) -> list[DocCard]:
    return [extract_card(doc_id, ps) for doc_id, ps in pages_by_doc(pages).items()]


def load_cards(path=CARDS_PATH) -> dict[str, DocCard]:
    return {d["doc_id"]: DocCard.from_dict(d) for d in read_jsonl(path)}


def portal_refs() -> dict[str, dict]:
    """Nhãn bạc của cổng cho các VB cp_*; ngày "19-10-2026" đổi về "19/10/2026"."""
    with open(SOURCES_PATH, encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["source"] == "chinhphu"]
    refs = {}
    for r in rows:
        refs[r["doc_id"]] = {
            "doc_type": r["ref_doc_type"], "doc_number": r["ref_doc_number"],
            "issue_date": r["ref_issue_date"].replace("-", "/"), "issuer": r["ref_issuer"],
            "signer": r["ref_signer"], "subject": r["ref_subject"],
        }
    return refs


def field_correct(name: str, ref: str, hyp) -> bool:
    if hyp is None:
        return False
    if name == "doc_number":
        return normalize_doc_number(ref) == normalize_doc_number(hyp)
    if name == "issuer":
        return keyword_f1(ref, hyp) >= KEYWORD_THRESHOLD
    if name == "subject":
        return keyword_coverage(ref, hyp) >= KEYWORD_THRESHOLD
    return normalize_text(ref).lower() == normalize_text(str(hyp)).lower()


def evaluate(cards: dict[str, DocCard], doc_ids: list[str], refs: dict[str, dict],
             has_text: dict[str, bool]) -> list[dict]:
    """Mỗi trường: số VB có nhãn, tỉ lệ đúng trên mọi VB và trên VB có chữ ở trang 1, mức "luôn rỗng" (= 0)."""
    rows = []
    for name in EVAL_FIELDS:
        ids = [d for d in doc_ids if refs.get(d, {}).get(name)]
        ok = {d: field_correct(name, refs[d][name], cards[d].value(name)) for d in ids}
        texted = [d for d in ids if has_text[d]]
        rows.append({
            "field": name, "n": len(ids), "n_text": len(texted),
            "acc_all": sum(ok.values()) / len(ids) if ids else None,
            "acc_text": sum(ok[d] for d in texted) / len(texted) if texted else None,
            "floor_empty": 0.0,
            "errors": [{"doc_id": d, "ref": refs[d][name], "hyp": cards[d].value(name)}
                       for d in texted if not ok[d]],
        })
    return rows


def print_table(rows: list[dict], split: str) -> None:
    print(f"Luật so với nhãn bạc cổng chinhphu · tập {split}")
    print(f"{'trường':<12}{'n':>4}{'đúng/tất cả':>13}{'n có chữ':>10}{'đúng/có chữ':>13}{'luôn rỗng':>11}")
    for r in rows:
        a = "—" if r["acc_all"] is None else f"{r['acc_all']:.3f}"
        t = "—" if r["acc_text"] is None else f"{r['acc_text']:.3f}"
        print(f"{r['field']:<12}{r['n']:>4}{a:>13}{r['n_text']:>10}{t:>13}{r['floor_empty']:>11.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Dựng thẻ thông tin và chấm luật")
    ap.add_argument("--split", default="dev", choices=["train", "dev", "test"])
    args = ap.parse_args()
    if args.split == "test" and not EVAL_TEST:
        sys.exit("Tập test chỉ đo sau điểm dừng C2 (EVAL_TEST = True)")
    pages = read_jsonl(PAGES_PATH)
    cards = build_cards(pages)
    write_jsonl([c.to_dict() for c in cards], CARDS_PATH)
    cards_by_id = {c.doc_id: c for c in cards}
    first_page_text = {d: bool(ps[0]["text"]) for d, ps in pages_by_doc(pages).items()}
    doc_ids = [r["doc_id"] for r in read_manifest() if r["split"] == args.split]
    rows = evaluate(cards_by_id, doc_ids, portal_refs(), first_page_text)
    print_table(rows, args.split)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"extract_rules_{args.split}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"split": args.split, "label": "silver_portal", "rows": rows}, f, ensure_ascii=False, indent=1)
    print(f"Đã ghi {len(cards)} thẻ vào {CARDS_PATH.name}; kết quả: {out.relative_to(RESULTS_DIR.parent.parent)}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
