"""Lắp ráp báo cáo Word hoàn chỉnh (~40 trang, 3 chương + Kết luận, không trích dẫn)
theo bố cục biểu mẫu ICTU và phong cách trình bày học thuật chuẩn mực.

Chạy từ thư mục `Dien_toan_dam_may/`:
    python scripts/build_dtdm_docx.py
"""
from __future__ import annotations

import copy
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dtdm_content_part1 import FRONT_MATTER, build_chapter_1  # noqa: E402
from scripts.dtdm_content_part2 import build_chapters_part2  # noqa: E402

BACKUP_DOCX = ROOT / "reports" / "backup_original_DTDM_NHOM4.docx"
OUT_DOCX_CLOUD = ROOT / "reports" / "BAO CAO DU AN _DTDM_NHOM 4_2026,09mm,25.docx"
FIG_DIR = ROOT / "reports" / "figures"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

EMU_PER_CM = 360000


def wtag(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def rtag(name: str) -> str:
    return f"{{{R_NS}}}{name}"


def _register_namespaces(xml_text: str) -> None:
    pairs = re.findall(r'xmlns:([a-zA-Z0-9_]+)="([^"]+)"', xml_text)
    seen: set[str] = set()
    for prefix, uri in pairs:
        if prefix not in seen:
            seen.add(prefix)
            ET.register_namespace(prefix, uri)


def _restore_root_attrs(serialized_xml: str, original_xml: str, root_tag: str) -> str:
    orig_start = original_xml.find(f"<{root_tag}")
    orig_end = original_xml.find(">", orig_start)
    new_start = serialized_xml.find(f"<{root_tag}")
    new_end = serialized_xml.find(">", new_start)
    if -1 in (orig_start, orig_end, new_start, new_end):
        return serialized_xml
    orig_open = original_xml[orig_start : orig_end + 1]
    new_open = serialized_xml[new_start : new_end + 1]
    orig_prefixes = set(re.findall(r'xmlns:([a-zA-Z0-9_]+)="[^"]+"', orig_open))
    extra = [
        f'xmlns:{p}="{u}"'
        for p, u in re.findall(r'xmlns:([a-zA-Z0-9_]+)="([^"]+)"', new_open)
        if p not in orig_prefixes
    ]
    merged_open = orig_open[:-1] + (" " + " ".join(extra) if extra else "") + ">"
    return serialized_xml[:new_start] + merged_open + serialized_xml[new_end + 1 :]


def _make_rpr(*, size_half_pt: int = 26, bold: bool = False, italic: bool = False, color: str | None = None) -> ET.Element:
    rpr = ET.Element(wtag("rPr"))
    ET.SubElement(
        rpr,
        wtag("rFonts"),
        {
            wtag("ascii"): "Times New Roman",
            wtag("eastAsia"): "Times New Roman",
            wtag("hAnsi"): "Times New Roman",
            wtag("cs"): "Times New Roman",
        },
    )
    if bold:
        ET.SubElement(rpr, wtag("b"))
    if italic:
        ET.SubElement(rpr, wtag("i"))
    if color:
        ET.SubElement(rpr, wtag("color"), {wtag("val"): color})
    ET.SubElement(rpr, wtag("sz"), {wtag("val"): str(size_half_pt)})
    ET.SubElement(rpr, wtag("szCs"), {wtag("val"): str(size_half_pt)})
    return rpr


def _make_run(text: str, *, size_half_pt: int = 26, bold: bool = False, italic: bool = False, color: str | None = None) -> ET.Element:
    r = ET.Element(wtag("r"))
    r.append(_make_rpr(size_half_pt=size_half_pt, bold=bold, italic=italic, color=color))
    t = ET.SubElement(r, wtag("t"))
    t.set(XML_SPACE, "preserve")
    t.text = text
    return r


def make_para(
    text: str = "",
    *,
    style: str | None = None,
    jc: str | None = None,
    bold: bool = False,
    italic: bool = False,
    size_half_pt: int = 26,
    color: str | None = None,
    disable_num: bool = False,
    page_break_before: bool = False,
    keep_next: bool = False,
    first_line: int | None = None,
    before: int | None = None,
    after: int | None = None,
    line: int | None = None,
) -> ET.Element:
    p = ET.Element(wtag("p"))
    ppr = ET.SubElement(p, wtag("pPr"))
    if style:
        ET.SubElement(ppr, wtag("pStyle"), {wtag("val"): style})
    if keep_next:
        ET.SubElement(ppr, wtag("keepNext"))
    if page_break_before:
        ET.SubElement(ppr, wtag("pageBreakBefore"))
    if disable_num:
        numpr = ET.SubElement(ppr, wtag("numPr"))
        ET.SubElement(numpr, wtag("ilvl"), {wtag("val"): "0"})
        ET.SubElement(numpr, wtag("numId"), {wtag("val"): "0"})
    if before is not None or after is not None or line is not None:
        sp_attrs = {wtag("lineRule"): "auto"}
        if before is not None:
            sp_attrs[wtag("before")] = str(before)
        if after is not None:
            sp_attrs[wtag("after")] = str(after)
        if line is not None:
            sp_attrs[wtag("line")] = str(line)
        ET.SubElement(ppr, wtag("spacing"), sp_attrs)
    if first_line is not None:
        ET.SubElement(ppr, wtag("ind"), {wtag("firstLine"): str(first_line)})
    if jc:
        ET.SubElement(ppr, wtag("jc"), {wtag("val"): jc})
    if text:
        for idx, line_part in enumerate(text.split("\n")):
            if idx > 0:
                r_br = ET.Element(wtag("r"))
                ET.SubElement(r_br, wtag("br"))
                p.append(r_br)
            p.append(_make_run(line_part, size_half_pt=size_half_pt, bold=bold, italic=italic, color=color))
    return p


def make_toc_field(instr: str, placeholder_text: str) -> ET.Element:
    """Chèn trường Word tự động (TOC / LOF / LOT) dùng tên hiển thị style của template."""
    p = ET.Element(wtag("p"))
    ppr = ET.SubElement(p, wtag("pPr"))
    ET.SubElement(ppr, wtag("pStyle"), {wtag("val"): "Normal"})
    ET.SubElement(ppr, wtag("spacing"), {wtag("before"): "60", wtag("after"): "120", wtag("line"): "320", wtag("lineRule"): "auto"})

    def _fld(ftype: str) -> ET.Element:
        r = ET.Element(wtag("r"))
        r.append(_make_rpr(size_half_pt=26))
        ET.SubElement(r, wtag("fldChar"), {wtag("fldCharType"): ftype})
        return r

    r_instr = ET.Element(wtag("r"))
    r_instr.append(_make_rpr(size_half_pt=26))
    it = ET.SubElement(r_instr, wtag("instrText"))
    it.set(XML_SPACE, "preserve")
    it.text = f" {instr} "

    p.append(_fld("begin"))
    p.append(r_instr)
    p.append(_fld("separate"))
    p.append(_make_run(placeholder_text, size_half_pt=26, italic=True, color="475569"))
    p.append(_fld("end"))
    return p


def make_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    booktabs: bool = True,
    col_widths: list[int] | None = None,
    center_cols: set[int] | None = None,
    font_half_pt: int = 22,
    header_fill: str | None = None,
) -> ET.Element:
    tbl = ET.Element(wtag("tbl"))
    tblpr = ET.SubElement(tbl, wtag("tblPr"))
    ET.SubElement(tblpr, wtag("tblStyle"), {wtag("val"): "TableGrid"})
    total_w = sum(col_widths) if col_widths else 8788
    ET.SubElement(tblpr, wtag("tblW"), {wtag("w"): str(total_w), wtag("type"): "dxa"})
    ET.SubElement(tblpr, wtag("tblLayout"), {wtag("type"): "fixed" if col_widths else "autofit"})
    ET.SubElement(tblpr, wtag("jc"), {wtag("val"): "center"})

    borders = ET.SubElement(tblpr, wtag("tblBorders"))
    if booktabs:
        ET.SubElement(borders, wtag("top"), {wtag("val"): "single", wtag("sz"): "10", wtag("space"): "0", wtag("color"): "1E293B"})
        ET.SubElement(borders, wtag("bottom"), {wtag("val"): "single", wtag("sz"): "10", wtag("space"): "0", wtag("color"): "1E293B"})
        ET.SubElement(borders, wtag("left"), {wtag("val"): "none"})
        ET.SubElement(borders, wtag("right"), {wtag("val"): "none"})
        ET.SubElement(borders, wtag("insideV"), {wtag("val"): "none"})
        ET.SubElement(borders, wtag("insideH"), {wtag("val"): "single", wtag("sz"): "4", wtag("space"): "0", wtag("color"): "E2E8F0"})
    else:
        for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
            ET.SubElement(borders, wtag(side), {wtag("val"): "single", wtag("sz"): "6", wtag("space"): "0", wtag("color"): "334155"})

    tbl_mar = ET.SubElement(tblpr, wtag("tblCellMar"))
    for side, val in (("top", "55"), ("left", "100"), ("bottom", "55"), ("right", "100")):
        ET.SubElement(tbl_mar, wtag(side), {wtag("w"): val, wtag("type"): "dxa"})

    if col_widths:
        tbl_grid = ET.SubElement(tbl, wtag("tblGrid"))
        for cw in col_widths:
            ET.SubElement(tbl_grid, wtag("gridCol"), {wtag("w"): str(cw)})

    def _add_row(cells: list[str], *, is_header: bool) -> None:
        tr = ET.SubElement(tbl, wtag("tr"))
        trpr = ET.SubElement(tr, wtag("trPr"))
        ET.SubElement(trpr, wtag("cantSplit"))
        if is_header:
            ET.SubElement(trpr, wtag("tblHeader"))
        for c_idx, cell_txt in enumerate(cells):
            tc = ET.SubElement(tr, wtag("tc"))
            tcpr = ET.SubElement(tc, wtag("tcPr"))
            if col_widths and c_idx < len(col_widths):
                ET.SubElement(tcpr, wtag("tcW"), {wtag("w"): str(col_widths[c_idx]), wtag("type"): "dxa"})
            if is_header:
                if booktabs:
                    tc_borders = ET.SubElement(tcpr, wtag("tcBorders"))
                    ET.SubElement(tc_borders, wtag("bottom"), {wtag("val"): "single", wtag("sz"): "8", wtag("space"): "0", wtag("color"): "1E293B"})
                if header_fill:
                    ET.SubElement(tcpr, wtag("shd"), {wtag("val"): "clear", wtag("color"): "auto", wtag("fill"): header_fill})
                ET.SubElement(tcpr, wtag("vAlign"), {wtag("val"): "center"})
            align = "center" if (is_header or (center_cols and c_idx in center_cols)) else "left"
            p = make_para(
                cell_txt,
                jc=align,
                bold=is_header,
                size_half_pt=font_half_pt,
                first_line=0,
                before=20,
                after=20,
                line=236,
            )
            tc.append(p)

    _add_row(headers, is_header=True)
    for row in rows:
        _add_row(row, is_header=False)
    return tbl


def make_image_para(rid: str, img_path: Path, width_cm: float, doc_pr_id: int) -> ET.Element:
    with Image.open(img_path) as im:
        px_w, px_h = im.size
    cx = int(round(width_cm * EMU_PER_CM))
    cy = int(round(cx * (px_h / max(1, px_w))))

    p = ET.Element(wtag("p"))
    ppr = ET.SubElement(p, wtag("pPr"))
    ET.SubElement(ppr, wtag("keepNext"))
    ET.SubElement(ppr, wtag("spacing"), {wtag("before"): "100", wtag("after"): "60", wtag("line"): "240", wtag("lineRule"): "auto"})
    ET.SubElement(ppr, wtag("jc"), {wtag("val"): "center"})

    r = ET.SubElement(p, wtag("r"))
    drawing = ET.SubElement(r, wtag("drawing"))
    inline = ET.SubElement(drawing, f"{{{WP_NS}}}inline", {"distT": "0", "distB": "0", "distL": "0", "distR": "0"})
    ET.SubElement(inline, f"{{{WP_NS}}}extent", {"cx": str(cx), "cy": str(cy)})
    ET.SubElement(inline, f"{{{WP_NS}}}effectExtent", {"l": "0", "t": "0", "r": "0", "b": "0"})
    ET.SubElement(inline, f"{{{WP_NS}}}docPr", {"id": str(doc_pr_id), "name": img_path.stem})
    c_nv = ET.SubElement(inline, f"{{{WP_NS}}}cNvGraphicFramePr")
    ET.SubElement(c_nv, f"{{{A_NS}}}graphicFrameLocks", {"noChangeAspect": "1"})

    graphic = ET.SubElement(inline, f"{{{A_NS}}}graphic")
    gdata = ET.SubElement(graphic, f"{{{A_NS}}}graphicData", {"uri": PIC_NS})
    pic = ET.SubElement(gdata, f"{{{PIC_NS}}}pic")

    nv_pic = ET.SubElement(pic, f"{{{PIC_NS}}}nvPicPr")
    ET.SubElement(nv_pic, f"{{{PIC_NS}}}cNvPr", {"id": str(doc_pr_id), "name": img_path.name})
    ET.SubElement(nv_pic, f"{{{PIC_NS}}}cNvPicPr")

    blip_fill = ET.SubElement(pic, f"{{{PIC_NS}}}blipFill")
    ET.SubElement(blip_fill, f"{{{A_NS}}}blip", {rtag("embed"): rid})
    stretch = ET.SubElement(blip_fill, f"{{{A_NS}}}stretch")
    ET.SubElement(stretch, f"{{{A_NS}}}fillRect")

    sp_pr = ET.SubElement(pic, f"{{{PIC_NS}}}spPr")
    xfrm = ET.SubElement(sp_pr, f"{{{A_NS}}}xfrm")
    ET.SubElement(xfrm, f"{{{A_NS}}}off", {"x": "0", "y": "0"})
    ET.SubElement(xfrm, f"{{{A_NS}}}ext", {"cx": str(cx), "cy": str(cy)})
    prst = ET.SubElement(sp_pr, f"{{{A_NS}}}prstGeom", {"prst": "rect"})
    ET.SubElement(prst, f"{{{A_NS}}}avLst")
    return p


def make_section_break_para(
    *,
    footer_rid: str,
    header_rid: str | None = None,
    num_fmt: str = "lowerRoman",
    start_at_one: bool = True,
) -> ET.Element:
    p = ET.Element(wtag("p"))
    ppr = ET.SubElement(p, wtag("pPr"))
    sect = ET.SubElement(ppr, wtag("sectPr"))
    if header_rid:
        ET.SubElement(sect, wtag("headerReference"), {wtag("type"): "default", rtag("id"): header_rid})
    ET.SubElement(sect, wtag("footerReference"), {wtag("type"): "default", rtag("id"): footer_rid})
    ET.SubElement(sect, wtag("pgSz"), {wtag("w"): "11907", wtag("h"): "16840"})
    ET.SubElement(
        sect,
        wtag("pgMar"),
        {
            wtag("top"): "1701",
            wtag("right"): "1134",
            wtag("bottom"): "1701",
            wtag("left"): "1985",
            wtag("header"): "851",
            wtag("footer"): "1134",
            wtag("gutter"): "0",
        },
    )
    pg_num = {wtag("fmt"): num_fmt}
    if start_at_one:
        pg_num[wtag("start")] = "1"
    ET.SubElement(sect, wtag("pgNumType"), pg_num)
    ET.SubElement(sect, wtag("cols"), {wtag("space"): "720"})
    return p


def _normalize_styles_xml(raw_styles: bytes) -> bytes:
    txt = raw_styles.decode("utf-8")
    _register_namespaces(txt)
    root = ET.fromstring(txt)

    def _set_p_spacing_and_rpr(
        style_id: str,
        *,
        sz: str,
        line: str,
        before: str,
        after: str,
        first_line: str | None,
        outline: str | None = None,
    ):
        el = root.find(f"{{{W_NS}}}style[@{{{W_NS}}}styleId='{style_id}']")
        if el is None:
            return
        ppr = el.find(wtag("pPr"))
        if ppr is None:
            ppr = ET.SubElement(el, wtag("pPr"))
        sp = ppr.find(wtag("spacing"))
        if sp is None:
            sp = ET.SubElement(ppr, wtag("spacing"))
        sp.set(wtag("before"), before)
        sp.set(wtag("after"), after)
        sp.set(wtag("line"), line)
        sp.set(wtag("lineRule"), "auto")
        if first_line is not None:
            ind = ppr.find(wtag("ind"))
            if ind is None:
                ind = ET.SubElement(ppr, wtag("ind"))
            ind.set(wtag("firstLine"), first_line)
        if outline is not None:
            ol = ppr.find(wtag("outlineLvl"))
            if ol is None:
                ol = ET.SubElement(ppr, wtag("outlineLvl"))
            ol.set(wtag("val"), outline)
        rpr = el.find(wtag("rPr"))
        if rpr is None:
            rpr = ET.SubElement(el, wtag("rPr"))
        rf = rpr.find(wtag("rFonts"))
        if rf is None:
            rf = ET.SubElement(rpr, wtag("rFonts"))
        for attr in ("ascii", "eastAsia", "hAnsi", "cs"):
            rf.set(wtag(attr), "Times New Roman")
        for tag_sz in ("sz", "szCs"):
            s_el = rpr.find(wtag(tag_sz))
            if s_el is None:
                s_el = ET.SubElement(rpr, wtag(tag_sz))
            s_el.set(wtag("val"), sz)

    _set_p_spacing_and_rpr("Normal", sz="26", line="264", before="20", after="40", first_line=None)
    _set_p_spacing_and_rpr("0TEXTc1", sz="26", line="264", before="20", after="40", first_line="567")
    _set_p_spacing_and_rpr("1Chapterc5", sz="30", line="264", before="40", after="100", first_line="0", outline="0")
    _set_p_spacing_and_rpr("21Level2c2", sz="28", line="264", before="70", after="35", first_line="0", outline="1")
    _set_p_spacing_and_rpr("311Level3c3", sz="26", line="264", before="45", after="25", first_line="0", outline="2")
    _set_p_spacing_and_rpr("4Figuresc6", sz="24", line="240", before="20", after="50", first_line="0")
    _set_p_spacing_and_rpr("5Tablesc7", sz="24", line="240", before="55", after="25", first_line="0")
    for toc_sid in ("TOC1", "TOC2", "TOC3", "TOC4", "TOC5"):
        _set_p_spacing_and_rpr(toc_sid, sz="24", line="252", before="0", after="25", first_line=None)

    out_xml = _restore_root_attrs(ET.tostring(root, encoding="unicode"), txt, "w:styles")
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + out_xml).encode("utf-8")


def _validate_academic_text(texts: list[str]) -> None:
    joined = "\n".join(texts)
    # Cho phép ký hiệu [1] chỉ khi mô tả ví dụ nút trích dẫn giao diện? Không dùng [n] để bảo đảm không có trích dẫn!
    if re.search(r"\[\d+\]", joined):
        raise ValueError("Phát hiện ký hiệu trích dẫn [n] trong nội dung báo cáo.")
    if "TÀI LIỆU THAM KHẢO" in joined.upper():
        raise ValueError("Báo cáo không được chứa mục TÀI LIỆU THAM KHẢO.")
    if "KHUNG CẬP NHẬT" in joined or "[...]" in joined:
        raise ValueError("Phát hiện nội dung giữ chỗ chưa hoàn thiện.")
    if "sk-or-v1-" in joined.lower():
        raise ValueError("Phát hiện khóa API thô trong nội dung báo cáo.")
    forbidden = (
        "cloud_store.py", "telemetry.py", "deploy_cloud.py", "Dockerfile",
        "docker-compose", "HF_TOKEN", "OPENROUTER_API_KEY", "APP_ADMIN_PASSWORD",
        "Keycloak", "Terraform", "archive-core", "ocr-worker", "MinIO",
        "/healthz", "/readyz", "/api/cloud", "doc_ids", "use_llm",
        "chúng em", "của mình",
    )
    for tok in forbidden:
        if tok.lower() in joined.lower():
            raise ValueError(f"Nội dung báo cáo vi phạm quy tắc AGENTS.md (chứa {tok!r}).")


def build_docx() -> Path:
    if not BACKUP_DOCX.is_file():
        raise FileNotFoundError(f"Không tìm thấy tệp sao lưu gốc: {BACKUP_DOCX}")

    ch1 = build_chapter_1()
    ch2_and_3, conclusion = build_chapters_part2()
    chapters = [ch1] + ch2_and_3

    all_texts: list[str] = []
    for k in ("loi_cam_doan", "loi_cam_on"):
        all_texts.extend(FRONT_MATTER[k])
    for row in FRONT_MATTER["phan_cong"] + FRONT_MATTER["tu_viet_tat"] + FRONT_MATTER["nhan_xet_diem"]:
        all_texts.extend(row)
    for heading, paras in FRONT_MATTER["mo_dau"]:
        all_texts.append(heading)
        all_texts.extend(paras)
    for ch in chapters:
        all_texts.append(ch["title"])
        for sec in ch["sections"]:
            all_texts.append(sec["title"])
            for sub in sec["subs"]:
                all_texts.append(sub[0])
                all_texts.extend(sub[1])
                if len(sub) > 2:
                    for item in sub[2]:
                        all_texts.append(item["caption"])
                        if item["type"] == "table":
                            all_texts.extend(item["headers"])
                            for row in item["rows"]:
                                all_texts.extend(row)
    all_texts.append(conclusion["title"])
    for h, paras in conclusion["subsections"]:
        all_texts.append(h)
        all_texts.extend(paras)
    _validate_academic_text(all_texts)

    with zipfile.ZipFile(BACKUP_DOCX, "r") as zin:
        doc_xml_raw = zin.read("word/document.xml").decode("utf-8")
        rels_raw = zin.read("word/_rels/document.xml.rels").decode("utf-8")
        styles_raw = zin.read("word/styles.xml")
        orig_entries = {name: zin.read(name) for name in zin.namelist()}

    _register_namespaces(doc_xml_raw)
    doc_root = ET.fromstring(doc_xml_raw)
    body = doc_root.find(wtag("body"))
    orig_children = list(body)

    # Giữ nguyên trang bìa ICTU gốc (bảng [0] và đoạn cuối [1] chứa viền đôi & sectPr[0])
    cover_tbl = copy.deepcopy(orig_children[0])
    cover_end_p = copy.deepcopy(orig_children[1])
    final_sect = copy.deepcopy(orig_children[-1])
    pg_mar = final_sect.find(wtag("pgMar"))
    if pg_mar is not None:
        pg_mar.set(wtag("top"), "1701")
        pg_mar.set(wtag("bottom"), "1701")
        pg_mar.set(wtag("left"), "1985")
        pg_mar.set(wtag("right"), "1134")
    pg_num_type = final_sect.find(wtag("pgNumType"))
    if pg_num_type is None:
        pg_num_type = ET.SubElement(final_sect, wtag("pgNumType"))
    pg_num_type.set(wtag("fmt"), "decimal")
    pg_num_type.set(wtag("start"), "1")

    rels_root = ET.fromstring(rels_raw)
    removed_targets: set[str] = set()
    for rel in list(rels_root):
        rid = rel.attrib.get("Id", "")
        target = rel.attrib.get("Target", "")
        if "image" in rel.attrib.get("Type", "") and rid != "rId10":
            removed_targets.add("word/" + target.lstrip("/"))
            rels_root.remove(rel)

    fig_files = sorted(FIG_DIR.glob("fig_*.png"))
    next_rid_num = 30
    fig_rids: dict[str, str] = {}
    new_media_files: dict[str, bytes] = {}
    for fp in fig_files:
        rid = f"rId{next_rid_num}"
        next_rid_num += 1
        media_name = f"media/{fp.name}"
        fig_rids[fp.name] = rid
        new_media_files[f"word/{media_name}"] = fp.read_bytes()
        ET.SubElement(
            rels_root,
            f"{{{REL_NS}}}Relationship",
            {
                "Id": rid,
                "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
                "Target": media_name,
            },
        )

    for child in list(body):
        body.remove(child)

    # Trang bìa gốc
    body.append(cover_tbl)
    body.append(cover_end_p)

    # =========================================================================
    # PHẦN ĐẦU (Số trang La Mã i, ii, iii...) — Theo bố cục bản mẫu chuẩn mực
    # =========================================================================

    # Trang i: NHẬN XÉT CỦA GIẢNG VIÊN (không đưa vào Mục lục giống bản mẫu)
    body.append(make_para("NHẬN XÉT CỦA GIẢNG VIÊN", style="Normal", jc="center", bold=True, size_half_pt=30, before=40, after=200, keep_next=True))
    dot_line = ". " * 52
    for title_txt, n_dots in (
        ("1. Về hình thức và bố cục báo cáo:", 3),
        ("2. Về nội dung và kết quả triển khai:", 4),
        ("3. Về tinh thần, thái độ làm việc của nhóm:", 3),
    ):
        body.append(make_para(title_txt, style="0TEXTc1", first_line=0, before=120, after=60, line=300, keep_next=True))
        for _ in range(n_dots):
            body.append(make_para(dot_line.strip(), style="0TEXTc1", first_line=0, before=40, after=80, line=320))
    body.append(make_para("4. Điểm đánh giá:", style="0TEXTc1", first_line=0, before=120, after=80, line=300, keep_next=True))
    body.append(make_table(
        ["STT", "Họ và tên sinh viên", "Điểm số", "Điểm chữ"],
        FRONT_MATTER["nhan_xet_diem"],
        booktabs=False,
        col_widths=[900, 4200, 1800, 1888],
        center_cols={0, 2, 3},
        font_half_pt=24,
        header_fill="F1F5F9",
    ))
    body.append(make_para("Thái Nguyên, ngày …… tháng …… năm 2026", style="0TEXTc1", jc="right", italic=True, first_line=0, before=220, after=20))
    body.append(make_para("Giảng viên", style="0TEXTc1", jc="right", bold=True, first_line=0, before=0, after=10))
    body.append(make_para("(Ký và ghi rõ họ tên)", style="0TEXTc1", jc="right", italic=True, first_line=0, before=0, after=260))
    body.append(make_para("", style="Normal", before=120, after=120))
    body.append(make_para("TS. Nguyễn Đức Bình", style="0TEXTc1", jc="right", bold=True, first_line=0, before=120, after=0))

    # Trang ii: LỜI CAM ĐOAN
    body.append(make_para("LỜI CAM ĐOAN", style="1Chapterc5", disable_num=True, page_break_before=True))
    for p_txt in FRONT_MATTER["loi_cam_doan"][:-1]:
        body.append(make_para(p_txt, style="0TEXTc1"))
    body.append(make_para(FRONT_MATTER["loi_cam_doan"][-1], style="0TEXTc1", jc="right", italic=True, first_line=0, before=180, after=20))
    body.append(make_para("Nhóm trưởng", style="0TEXTc1", jc="right", bold=True, first_line=0, before=0, after=10))
    body.append(make_para("(Ký và ghi rõ họ tên)", style="0TEXTc1", jc="right", italic=True, first_line=0, before=0, after=240))
    body.append(make_para("", style="Normal", before=100, after=100))
    body.append(make_para("Nông Thị Hương", style="0TEXTc1", jc="right", bold=True, first_line=0))

    # Trang iii: LỜI CẢM ƠN
    body.append(make_para("LỜI CẢM ƠN", style="1Chapterc5", disable_num=True, page_break_before=True))
    for p_txt in FRONT_MATTER["loi_cam_on"][:-1]:
        body.append(make_para(p_txt, style="0TEXTc1"))
    body.append(make_para(FRONT_MATTER["loi_cam_on"][-1], style="0TEXTc1", jc="right", italic=True, first_line=0, before=180, after=20))
    body.append(make_para("Nhóm sinh viên thực hiện", style="0TEXTc1", jc="right", bold=True, first_line=0, before=0, after=20))
    body.append(make_para("Nông Thị Hương – Lê Xuân Nhất", style="0TEXTc1", jc="right", first_line=0))

    # Trang iv: BẢNG PHÂN CÔNG NHIỆM VỤ
    body.append(make_para("BẢNG PHÂN CÔNG NHIỆM VỤ", style="1Chapterc5", disable_num=True, page_break_before=True))
    body.append(make_table(
        ["STT", "Họ và tên", "Nhiệm vụ phụ trách", "Mức độ hoàn thành"],
        FRONT_MATTER["phan_cong"],
        booktabs=False,
        col_widths=[700, 1950, 4750, 1388],
        center_cols={0, 3},
        font_half_pt=24,
        header_fill="F1F5F9",
    ))

    # Trang v: MỤC LỤC (Normal in đậm căn giữa để không tự liệt kê chính mình vào Mục lục)
    body.append(make_para("MỤC LỤC", style="Normal", jc="center", bold=True, size_half_pt=30, page_break_before=True, before=40, after=180, keep_next=True))
    body.append(make_toc_field(
        'TOC \\h \\z \\t "1_Chapter_c5,1,2_1_Level2_c2,2,3_1_1_Level3_c3,3"',
        "[Mục lục tự động sẽ được cập nhật đầy đủ số trang]",
    ))

    # Trang vii: DANH MỤC HÌNH ẢNH
    body.append(make_para("DANH MỤC HÌNH ẢNH", style="1Chapterc5", disable_num=True, page_break_before=True))
    body.append(make_toc_field(
        'TOC \\h \\z \\t "4_Figures_c6,4"',
        "[Danh mục hình ảnh sẽ được cập nhật tự động]",
    ))

    # Trang ix: DANH MỤC BẢNG
    body.append(make_para("DANH MỤC BẢNG", style="1Chapterc5", disable_num=True, page_break_before=True))
    body.append(make_toc_field(
        'TOC \\h \\z \\t "5_Tables_c7,5"',
        "[Danh mục bảng sẽ được cập nhật tự động]",
    ))

    # Trang x: DANH MỤC TỪ VIẾT TẮT
    body.append(make_para("DANH MỤC TỪ VIẾT TẮT", style="1Chapterc5", disable_num=True, page_break_before=True))
    body.append(make_table(
        ["STT", "Viết tắt", "Ý nghĩa"],
        FRONT_MATTER["tu_viet_tat"],
        booktabs=False,
        col_widths=[750, 1750, 6288],
        center_cols={0},
        font_half_pt=23,
        header_fill="F1F5F9",
    ))

    # Ngắt phần cuối Phần đầu (đánh số La Mã i, ii, iii... cho toàn bộ Phần đầu)
    body.append(make_section_break_para(footer_rid="rId13", header_rid="rId12", num_fmt="lowerRoman", start_at_one=True))

    # =========================================================================
    # PHẦN NỘI DUNG CHÍNH (Số trang Ả Rập 1, 2, 3...)
    # =========================================================================

    # MỞ ĐẦU (bắt đầu trang 1)
    body.append(make_para("MỞ ĐẦU", style="1Chapterc5", disable_num=True))
    for heading, paras in FRONT_MATTER["mo_dau"]:
        body.append(make_para(heading, style="0TEXTc1", bold=True, keep_next=True, first_line=0, before=120, after=60))
        for p_txt in paras:
            body.append(make_para(p_txt, style="0TEXTc1"))

    # CHƯƠNG 1, CHƯƠNG 2, CHƯƠNG 3
    doc_pr_id = 100
    for ch in chapters:
        body.append(make_para(ch["title"], style="1Chapterc5", page_break_before=True))
        for sec in ch["sections"]:
            body.append(make_para(sec["title"], style="21Level2c2"))
            for sub in sec["subs"]:
                sub_title = sub[0]
                sub_paras = sub[1]
                extras = sub[2] if len(sub) > 2 else []
                body.append(make_para(sub_title, style="311Level3c3"))
                for p_txt in sub_paras:
                    body.append(make_para(p_txt, style="0TEXTc1"))
                for item in extras:
                    if item["type"] == "table":
                        body.append(make_para(item["caption"], style="5Tablesc7", bold=True, jc="center", keep_next=True))
                        body.append(make_table(item["headers"], item["rows"], booktabs=True, font_half_pt=21))
                        body.append(make_para("", style="Normal", before=0, after=25, line=240))
                    elif item["type"] == "figure":
                        fname = item["path"]
                        rid = fig_rids[fname]
                        body.append(make_image_para(rid, FIG_DIR / fname, round(item.get("width_cm", 15.0) * 0.64, 2), doc_pr_id))
                        doc_pr_id += 1
                        body.append(make_para(item["caption"], style="4Figuresc6", bold=False, italic=True, jc="center"))

    # KẾT LUẬN VÀ HƯỚNG PHÁT TRIỂN (cấp chương không đánh số)
    body.append(make_para(conclusion["title"], style="1Chapterc5", disable_num=True, page_break_before=True))
    for h_txt, paras in conclusion["subsections"]:
        body.append(make_para(h_txt, style="0TEXTc1", bold=True, keep_next=True, first_line=0, before=120, after=60))
        for p_txt in paras:
            body.append(make_para(p_txt, style="0TEXTc1"))

    body.append(final_sect)

    new_doc_xml = _restore_root_attrs(ET.tostring(doc_root, encoding="unicode"), doc_xml_raw, "w:document")
    new_doc_bytes = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n' + new_doc_xml).encode("utf-8")
    new_rels_bytes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        + ET.tostring(rels_root, encoding="unicode")
    ).encode("utf-8")
    new_styles_bytes = _normalize_styles_xml(styles_raw)

    OUT_DOCX_CLOUD.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = OUT_DOCX_CLOUD.with_suffix(".tmp.docx")
    with zipfile.ZipFile(tmp_out, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for name, data in orig_entries.items():
            if name in removed_targets:
                continue
            if name == "word/document.xml":
                zout.writestr(name, new_doc_bytes)
            elif name == "word/_rels/document.xml.rels":
                zout.writestr(name, new_rels_bytes)
            elif name == "word/styles.xml":
                zout.writestr(name, new_styles_bytes)
            else:
                zout.writestr(name, data)
        for mname, mbytes in new_media_files.items():
            zout.writestr(mname, mbytes)

    shutil.move(str(tmp_out), str(OUT_DOCX_CLOUD))
    word_count = sum(len(t.split()) for t in all_texts)
    print(f"Built {OUT_DOCX_CLOUD} | words={word_count} | figures={len(fig_files)} | size={OUT_DOCX_CLOUD.stat().st_size} bytes")
    return OUT_DOCX_CLOUD


if __name__ == "__main__":
    build_docx()
