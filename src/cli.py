"""Dòng lệnh của dự án, chạy từ gốc Du_an/:

  python -m src.cli ingest              # PDF → chữ từng trang đã làm sạch (data/processed/pages.jsonl)
  python -m src.cli extract [--split dev]   # thẻ thông tin + chấm với nhãn bạc cổng
  python -m src.cli ask "Ai ký Nghị định 385/2026/NĐ-CP?"
  python -m src.cli uploads [--delete DOC_ID]   # PDF đã tải lên qua web
  python -m src.cli serve [--port 8000] [--host 0.0.0.0]   # web demo (0.0.0.0: mở cho LAN)
"""
import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m src.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ingest")
    ex = sub.add_parser("extract")
    ex.add_argument("--split", default="dev", choices=["train", "dev", "test"])
    ask = sub.add_parser("ask")
    ask.add_argument("question")
    up = sub.add_parser("uploads", help="liệt kê / xóa PDF đã tải lên qua web (data/uploads)")
    up.add_argument("--delete", metavar="DOC_ID")
    sv = sub.add_parser("serve")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--host", default="127.0.0.1", help="0.0.0.0 để máy khác cùng mạng LAN truy cập")
    args = ap.parse_args(argv)

    if args.cmd == "ingest":
        from src.ingest import PAGES_PATH, build_pages, summarize, write_jsonl
        pages = build_pages()
        write_jsonl(pages, PAGES_PATH)
        summarize(pages)
    elif args.cmd == "extract":
        from src import cards
        sys.argv = ["cards", "--split", args.split]
        cards.main()
    elif args.cmd == "ask":
        from src.dense import default_encoder
        from src.ingest import PAGES_PATH, read_jsonl
        from src.qa import Assistant
        ans = Assistant(read_jsonl(PAGES_PATH), encoder=default_encoder()).ask(args.question)
        print(("TRẢ LỜI" if ans.status == "answered" else "TỪ CHỐI") + f": {ans.text}")
        print(f"Lý do: {ans.reason}")
        if ans.confidence is not None:
            print(f"Độ phủ căn cứ: {ans.confidence:.2f}")
        for c in ans.citations:
            print(f"  ↳ {c['doc_id']}, trang {c['page_no']}: {c['text'][:120]}")
        for w in ans.warnings:
            print(f"  ⚠ {w}")
    elif args.cmd == "uploads":
        from src import uploads
        if args.delete:
            print("Đã xóa" if uploads.delete_upload(args.delete) else "Không có", args.delete)
            return
        items = uploads.list_uploads()
        print(f"{len(items)} tệp trong {uploads.UPLOAD_DIR}")
        for doc_id, _pdf, _pages, m in items:
            print(f"  {doc_id}  ·  {m.get('original_name')}  ·  {m.get('uploaded_at')}  ·  "
                  f"{m.get('size_bytes', 0) / 1048576:.1f} MB  ·  {m.get('n_pages')} trang, {m.get('n_missing')} chưa OCR")
    elif args.cmd == "serve":
        import uvicorn
        uvicorn.run("web.app:app", host=args.host, port=args.port)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
