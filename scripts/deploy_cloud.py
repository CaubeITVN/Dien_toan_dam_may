"""Đóng gói và triển khai hệ thống lên Public Cloud (Hugging Face Spaces + Private Dataset Storage).

Hỗ trợ 2 chế độ:
  - ``decoupled`` (mặc định): Tách mã nguồn nhẹ (< 5 MB) lên Docker Space và tách dữ liệu
    (archive_structure, manifest, processed, ocr, raw PDF, dense cache, uploads) lên
    Hugging Face Hub Dataset riêng tư (``private=True``).
  - ``standalone``: Đóng gói tất cả vào một Docker Space duy nhất.

Ví dụ chạy từ thư mục `Dien_toan_dam_may/`:
    python scripts/deploy_cloud.py --mode decoupled --dry-run
    python scripts/deploy_cloud.py --mode standalone --dry-run
    python scripts/deploy_cloud.py --mode decoupled --token hf_xxx --sync-secrets
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import secrets
import shutil
import tempfile

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"

SPACE_ROOT_FILES = (
    "Dockerfile",
    "requirements-deploy.txt",
    ".dockerignore",
)
STORAGE_DATA_FILES = (
    ("data/archive_structure.json", "state/archive_structure.json"),
    ("data/manifest.csv", "data/manifest.csv"),
)
STORAGE_MODEL_FILES = (
    ("models/refusal_threshold.json", "models/refusal_threshold.json"),
    ("models/spellfix_lm.pkl", "models/spellfix_lm.pkl"),
)
DEFAULT_SPACE_NAME = "tra-cuu-luu-tru-so-cloud"
DEFAULT_STORAGE_NAME = "tra-cuu-luu-tru-so-storage"
FORBIDDEN_PATTERN = re.compile(r"(^|/)\.env($|\.)|\.pt$|\.pth$|data/(gold|external)|__pycache__")
SECRET_KEYS = (
    "OPENROUTER_API_KEY",
    "OPENROUTER_MODEL",
    "LLM_PROVIDER",
    "APP_ADMIN_PASSWORD",
    "APP_SECRET_KEY",
)


def _strip_quotes(val: str) -> str:
    s = val.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def read_dotenv(path: Path = ENV_PATH) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k:
            out[k] = _strip_quotes(v)
    return out


def _iter_clean_dir(base: Path, root: Path, prefix: str | None = None) -> list[tuple[Path, str]]:
    out: list[tuple[Path, str]] = []
    if not base.is_dir():
        return out
    for p in sorted(base.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix() if prefix is None else f"{prefix}/{p.relative_to(base).as_posix()}"
        if "/__pycache__/" in f"/{rel}/" or p.suffix in {".pyc", ".pyo"}:
            continue
        if p.name.startswith(".env") or p.name.startswith("tmp_"):
            continue
        out.append((p, rel))
    return out


def collect_space_files(
    root: Path = ROOT,
    *,
    mode: str = "decoupled",
    include_uploads: bool = True,
) -> list[tuple[Path, str]]:
    """Thu thập tệp đẩy lên Hugging Face Docker Space theo chế độ `decoupled` hoặc `standalone`."""
    if mode not in ("decoupled", "standalone"):
        raise ValueError(f"Chế độ deploy không hợp lệ: {mode!r}")

    files: list[tuple[Path, str]] = []
    for name in SPACE_ROOT_FILES:
        src = root / name
        if src.is_file():
            files.append((src, name))
    readme_src = root / "hf_space_readme.md"
    if readme_src.is_file():
        files.append((readme_src, "README.md"))

    files.extend(_iter_clean_dir(root / "src", root))
    files.extend(_iter_clean_dir(root / "web", root))

    if mode == "standalone":
        for rel in ("data/manifest.csv", "data/archive_structure.json"):
            p = root / rel
            if p.is_file():
                files.append((p, rel))
        for rel in ("data/processed", "data/ocr", "data/raw"):
            files.extend(_iter_clean_dir(root / rel, root))
        if include_uploads:
            files.extend(_iter_clean_dir(root / "data/uploads", root))
        for rel in ("models/refusal_threshold.json", "models/spellfix_lm.pkl"):
            p = root / rel
            if p.is_file():
                files.append((p, rel))
        files.extend(_iter_clean_dir(root / "models/dense", root))

    return files


def collect_storage_files(
    root: Path = ROOT,
    *,
    raw_dir: Path | None = None,
    include_uploads: bool = True,
) -> list[tuple[Path, str]]:
    """Thu thập tệp dữ liệu và chỉ mục đẩy lên kho Private Dataset (`HF_STORAGE_REPO`)."""
    files: list[tuple[Path, str]] = []
    for src_rel, dst_rel in STORAGE_DATA_FILES + STORAGE_MODEL_FILES:
        p = root / src_rel
        if p.is_file():
            files.append((p, dst_rel))

    files.extend(_iter_clean_dir(root / "data/processed", root, prefix="data/processed"))
    files.extend(_iter_clean_dir(root / "models/dense", root, prefix="models/dense"))
    files.extend(_iter_clean_dir(root / "data/ocr", root, prefix="ocr"))
    raw_base = Path(raw_dir) if raw_dir is not None else (root / "data/raw")
    files.extend(_iter_clean_dir(raw_base, raw_base, prefix="raw"))
    if include_uploads:
        files.extend(_iter_clean_dir(root / "data/uploads", root, prefix="uploads"))
    return files


def _validate_no_forbidden(files: list[tuple[Path, str]]) -> None:
    bad = [rel for _, rel in files if FORBIDDEN_PATTERN.search(rel)]
    if bad:
        raise RuntimeError(f"Phát hiện tệp cấm trong gói triển khai: {bad[:5]}")


def _resolve_secrets(
    dotenv: dict[str, str],
    *,
    admin_password: str | None = None,
    storage_repo: str | None = None,
    hf_token: str | None = None,
) -> dict[str, str]:
    out: dict[str, str] = {}
    for k in SECRET_KEYS:
        val = (os.environ.get(k) or dotenv.get(k) or "").strip()
        if val:
            out[k] = val
    if admin_password is not None and admin_password.strip():
        out["APP_ADMIN_PASSWORD"] = admin_password.strip()
    out.setdefault("LLM_PROVIDER", "openrouter")
    out.setdefault("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")
    out.setdefault("CLOUD_STATELESS_ENV", "1")
    if "APP_SECRET_KEY" not in out:
        out["APP_SECRET_KEY"] = secrets.token_urlsafe(32)
    if storage_repo:
        out["HF_STORAGE_REPO"] = storage_repo
    if hf_token:
        out["HF_TOKEN"] = hf_token
    return out


def _print_summary(title: str, files: list[tuple[Path, str]]) -> float:
    total_bytes = sum(src.stat().st_size for src, _ in files)
    mb = total_bytes / (1024 * 1024)
    print(f"[{title}] Tổng số tệp: {len(files)} ({mb:.2f} MB)")
    by_top: dict[str, list[int]] = {}
    for src, rel in files:
        top = rel.split("/", 1)[0]
        stat = by_top.setdefault(top, [0, 0])
        stat[0] += 1
        stat[1] += src.stat().st_size
    for top, (cnt, sz) in sorted(by_top.items()):
        print(f"  - {top}: {cnt} tệp ({sz / (1024 * 1024):.2f} MB)")
    return mb


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Đóng gói & triển khai Cloud-Native RAG lên Hugging Face.")
    parser.add_argument("--mode", choices=("decoupled", "standalone"), default="decoupled", help="Chế độ đóng gói")
    parser.add_argument("--space", help="ID Docker Space đích, vd username/tra-cuu-luu-tru-so-cloud")
    parser.add_argument("--storage-repo", help="ID Dataset lưu trữ riêng tư, vd username/tra-cuu-luu-tru-so-storage")
    parser.add_argument("--raw-dir", type=Path, help="Thư mục PDF nguồn tùy chọn khi đồng bộ kho Dataset")
    parser.add_argument("--token", help="Hugging Face Write Token (hoặc dùng biến môi trường HF_TOKEN)")
    parser.add_argument("--private", action="store_true", help="Tạo Docker Space ở chế độ Private")
    parser.add_argument("--no-uploads", action="store_true", help="Không đính kèm thư mục data/uploads")
    parser.add_argument("--sync-secrets", action="store_true", help="Đồng bộ cấu hình lên Space Secrets")
    parser.add_argument("--admin-password", help="Đặt APP_ADMIN_PASSWORD khi đồng bộ Secrets")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ kiểm tra tệp và dung lượng, không tải lên")
    args = parser.parse_args(argv)

    space_files = collect_space_files(ROOT, mode=args.mode, include_uploads=not args.no_uploads)
    _validate_no_forbidden(space_files)

    storage_files: list[tuple[Path, str]] = []
    if args.mode == "decoupled":
        storage_files = collect_storage_files(ROOT, raw_dir=args.raw_dir, include_uploads=not args.no_uploads)
        _validate_no_forbidden(storage_files)

    space_mb = _print_summary(f"Docker Space ({args.mode})", space_files)
    if args.mode == "decoupled":
        _print_summary("Private Dataset Storage", storage_files)
        if space_mb >= 5.0:
            raise RuntimeError(f"Gói mã nguồn decoupled vượt ngưỡng 5 MB ({space_mb:.2f} MB).")

    dotenv = read_dotenv(ENV_PATH)
    token = (args.token or os.environ.get("HF_TOKEN") or "").strip() or None
    preview_secrets = _resolve_secrets(
        dotenv,
        admin_password=args.admin_password,
        storage_repo=args.storage_repo or ("<username>/" + DEFAULT_STORAGE_NAME if args.mode == "decoupled" else None),
        hf_token=token,
    )
    print("Space Secrets sẽ đồng bộ:", sorted(preview_secrets.keys()))

    if args.dry_run:
        return 0

    from huggingface_hub import HfApi

    api = HfApi(token=token)
    try:
        who = api.whoami()
    except Exception as exc:
        raise SystemExit(
            "Chưa đăng nhập Hugging Face hoặc thiếu Write Token.\n"
            "Tạo Write Token tại https://huggingface.co/settings/tokens rồi chạy:\n"
            "  python scripts/deploy_cloud.py --mode decoupled --token <HF_WRITE_TOKEN> --sync-secrets"
        ) from exc

    username = who["name"]
    space_repo = args.space or f"{username}/{DEFAULT_SPACE_NAME}"
    if "/" not in space_repo:
        space_repo = f"{username}/{space_repo}"

    storage_repo = None
    if args.mode == "decoupled":
        storage_repo = args.storage_repo or os.environ.get("HF_STORAGE_REPO") or f"{username}/{DEFAULT_STORAGE_NAME}"
        if "/" not in storage_repo:
            storage_repo = f"{username}/{storage_repo}"
        print(f"Đang tạo/kiểm tra Private Dataset Storage: {storage_repo} (private=True)...")
        api.create_repo(repo_id=storage_repo, repo_type="dataset", private=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="hf_storage_stage_") as tmp_ds:
            ds_stage = Path(tmp_ds)
            for src, rel in storage_files:
                dst = ds_stage / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            print(f"Đang đẩy {len(storage_files)} tệp dữ liệu lên {storage_repo}...")
            api.upload_folder(
                folder_path=str(ds_stage),
                repo_id=storage_repo,
                repo_type="dataset",
                commit_message="Sync durable archive storage layer",
            )

    print(f"Đang tạo/kiểm tra Docker Space: {space_repo} (private={args.private})...")
    api.create_repo(
        repo_id=space_repo,
        repo_type="space",
        space_sdk="docker",
        private=args.private,
        exist_ok=True,
    )

    if args.sync_secrets:
        final_secrets = _resolve_secrets(
            dotenv,
            admin_password=args.admin_password,
            storage_repo=storage_repo,
            hf_token=token,
        )
        for k, v in final_secrets.items():
            api.add_space_secret(repo_id=space_repo, key=k, value=v)
        print("Đã đồng bộ Space Secrets:", sorted(final_secrets.keys()))

    with tempfile.TemporaryDirectory(prefix="hf_space_stage_") as tmp_sp:
        sp_stage = Path(tmp_sp)
        for src, rel in space_files:
            dst = sp_stage / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        print(f"Đang đẩy {len(space_files)} tệp mã nguồn lên {space_repo}...")
        api.upload_folder(
            folder_path=str(sp_stage),
            repo_id=space_repo,
            repo_type="space",
            commit_message=f"Deploy Cloud-Native Digital Archive RAG ({args.mode})",
        )

    print(f"Hoàn tất! Truy cập Space tại: https://huggingface.co/spaces/{space_repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
