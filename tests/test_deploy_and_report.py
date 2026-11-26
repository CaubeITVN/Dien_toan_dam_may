"""Kiểm thử đóng gói tách dữ liệu (deploy_cloud.py), khóa LLM mặc định, hồ sơ SpecKit và báo cáo ĐTĐM."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

from scripts.deploy_cloud import collect_space_files, collect_storage_files
from src.llm import LocalLLM

ROOT = Path(__file__).resolve().parent.parent


def test_decoupled_deployment_package_is_small_and_clean():
    space_files = collect_space_files(ROOT, mode="decoupled")
    storage_files = collect_storage_files(ROOT)

    total_space_bytes = sum(src.stat().st_size for src, _ in space_files)
    assert total_space_bytes < 5 * 1024 * 1024, f"Gói Space quá lớn: {total_space_bytes} bytes"

    space_rels = {rel for _, rel in space_files}
    assert "Dockerfile" in space_rels
    assert "requirements-deploy.txt" in space_rels
    assert "src/cloud_store.py" in space_rels
    assert "src/telemetry.py" in space_rels
    assert "web/static/cloud.html" in space_rels
    assert not any(rel.startswith("data/") or rel.startswith("models/") for rel in space_rels)

    storage_rels = {rel for _, rel in storage_files}
    assert "state/archive_structure.json" in storage_rels
    assert "data/manifest.csv" in storage_rels
    assert any(rel.startswith("raw/") and rel.endswith(".pdf") for rel in storage_rels)

    for _, rel in space_files + storage_files:
        assert not rel.endswith((".pt", ".pth", ".pyc", ".env"))
        assert "__pycache__" not in rel


def test_speckit_artifacts_exist():
    required = [
        ROOT / ".specify" / "memory" / "constitution.md",
        ROOT / "specs" / "001-cloud-native-rag-archive" / "spec.md",
        ROOT / "specs" / "001-cloud-native-rag-archive" / "research.md",
        ROOT / "specs" / "001-cloud-native-rag-archive" / "data-model.md",
        ROOT / "specs" / "001-cloud-native-rag-archive" / "contracts" / "cloud-api.md",
        ROOT / "specs" / "001-cloud-native-rag-archive" / "plan.md",
        ROOT / "specs" / "001-cloud-native-rag-archive" / "quickstart.md",
        ROOT / "specs" / "001-cloud-native-rag-archive" / "tasks.md",
    ]
    for path in required:
        assert path.is_file() and path.stat().st_size > 100, f"Thiếu tệp SpecKit: {path}"


def test_default_openrouter_api_key_ready_and_masked():
    llm = LocalLLM()
    assert llm.provider == "openrouter"
    assert llm.has_api_key is True
    st = llm.status()
    assert st["has_api_key"] is True
    assert "••••" in st["api_key_masked"]
    assert "c251fb75" not in st["api_key_masked"]

    nb_html = (ROOT / "web" / "static" / "notebooklm.html").read_text(encoding="utf-8")
    assert 'class="llm-cfg-btn hidden" id="btnLlmConfig"' in nb_html
    assert 'id="llmToggle" checked' in nb_html


def _assert_clean_academic_text(text: str) -> None:
    forbidden_literals = (
        "cloud_store.py",
        "telemetry.py",
        "deploy_cloud.py",
        "Dockerfile",
        "docker-compose.yml",
        "HF_TOKEN",
        "OPENROUTER_API_KEY",
        "APP_ADMIN_PASSWORD",
        "/healthz",
        "/readyz",
        "/api/cloud/",
        "doc_ids",
        "use_llm",
        "sk-or-v1-",
        "KHUNG CẬP NHẬT",
        "[...]",
    )
    for token in forbidden_literals:
        assert token not in text, f"Báo cáo vi phạm quy tắc AGENTS.md (chứa {token!r})"

    assert "TÀI LIỆU THAM KHẢO" not in text.upper()
    assert not re.search(r"\[\d+\]", text), "Báo cáo không được chứa trích dẫn [n]"
    assert not re.search(r"\b(?:US\d+|FR-\d+|SC-\d+|T\d{3})\b", text)


def test_academic_report_three_chapters_and_compliance():
    md_path = ROOT / "reports" / "BAO_CAO_DIEN_TOAN_DAM_MAY.md"
    assert md_path.is_file()
    md_text = md_path.read_text(encoding="utf-8")

    for heading in (
        "## MỞ ĐẦU",
        "## CHƯƠNG 1.",
        "## CHƯƠNG 2.",
        "## CHƯƠNG 3.",
        "## KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN",
    ):
        assert heading in md_text, f"Thiếu mục chính {heading!r} trong báo cáo Markdown"
    _assert_clean_academic_text(md_text)

    docx_path = ROOT / "reports" / "BAO CAO DU AN _DTDM_NHOM 4_2026,09mm,25.docx"
    assert docx_path.is_file() and docx_path.stat().st_size > 1_000_000
    with zipfile.ZipFile(docx_path, "r") as zf:
        media_imgs = [n for n in zf.namelist() if n.startswith("word/media/") and n.lower().endswith((".png", ".jpg", ".jpeg"))]
        assert len(media_imgs) >= 26, f"Kỳ vọng tối thiểu 26 ảnh (1 logo bìa + 25 hình minh họa), hiện có {len(media_imgs)}"
        doc_xml = zf.read("word/document.xml").decode("utf-8")
        assert "No table of contents entries found." not in doc_xml
        plain_text = "".join(ET.fromstring(doc_xml).itertext())

    for required_title in (
        "TỔNG QUAN BÀI TOÁN VÀ DỊCH VỤ ĐÁM MÂY CÔNG CỘNG",
        "QUY TRÌNH TRIỂN KHAI HỆ THỐNG LÊN NỀN TẢNG ĐÁM MÂY",
        "KẾT QUẢ TRIỂN KHAI VÀ ĐÁNH GIÁ SẢN PHẨM",
        "KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN",
    ):
        assert required_title in plain_text, f"Thiếu chương {required_title!r} trong báo cáo Word"
    _assert_clean_academic_text(plain_text)
