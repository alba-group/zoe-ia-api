import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from core.config import PDF_DIR, PDF_DOWNLOAD_ROUTE_PREFIX


@dataclass
class PDFSection:
    kind: str
    text: str = ""
    items: list[str] = field(default_factory=list)
    heading: str = ""


@dataclass
class PDFDocumentContent:
    title: str
    subtitle: str = ""
    sections: list[PDFSection] = field(default_factory=list)
    file_name_hint: str = ""


def sanitize_file_name_fragment(value: str, fallback: str = "document") -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.lower().strip()
    ascii_value = re.sub(r"[^a-z0-9]+", "_", ascii_value)
    ascii_value = ascii_value.strip("_")
    return ascii_value[:60] or fallback


def build_pdf_filename(title_hint: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_title = sanitize_file_name_fragment(title_hint, fallback="zoe_document")
    return f"{timestamp}_{clean_title}.pdf"


def build_pdf_download_url(file_name: str) -> str:
    clean_name = Path(file_name).name
    return f"{PDF_DOWNLOAD_ROUTE_PREFIX}/{clean_name}"


def generate_pdf_file(
    document: PDFDocumentContent,
    output_dir: Path | None = None,
) -> Path:
    target_dir = output_dir or PDF_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    title_hint = document.file_name_hint or document.title or "document"
    file_name = build_pdf_filename(title_hint)
    output_path = target_dir / file_name

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title=document.title,
    )

    styles = _build_styles()
    story: list = []

    story.append(Paragraph(_to_markup(document.title or "Document"), styles["title"]))

    if document.subtitle.strip():
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(_to_markup(document.subtitle), styles["subtitle"]))

    story.append(Spacer(1, 8 * mm))

    sections = document.sections or [PDFSection(kind="paragraph", text="Document vide.")]

    for section in sections:
        if section.heading.strip():
            story.append(Paragraph(_to_markup(section.heading), styles["heading"]))
            story.append(Spacer(1, 2 * mm))

        if section.kind == "list":
            _append_list_section(story, section.items, styles["body"])
        else:
            _append_paragraph_section(story, section.text, styles["body"])

        story.append(Spacer(1, 4 * mm))

    doc.build(story)
    return output_path


def _build_styles() -> dict[str, ParagraphStyle]:
    base_styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ZoePdfTitle",
        parent=base_styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=23,
        textColor=colors.HexColor("#111827"),
        spaceAfter=0,
    )

    subtitle_style = ParagraphStyle(
        "ZoePdfSubtitle",
        parent=base_styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=0,
    )

    heading_style = ParagraphStyle(
        "ZoePdfHeading",
        parent=base_styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=0,
    )

    body_style = ParagraphStyle(
        "ZoePdfBody",
        parent=base_styles["BodyText"],
        fontName="Helvetica",
        fontSize=11,
        leading=16,
        textColor=colors.black,
        spaceAfter=0,
    )

    return {
        "title": title_style,
        "subtitle": subtitle_style,
        "heading": heading_style,
        "body": body_style,
    }


def _append_paragraph_section(
    story: list,
    text: str,
    style: ParagraphStyle,
) -> None:
    blocks = [block for block in _split_blocks(text) if block.strip()]
    if not blocks:
        return

    for block in blocks:
        story.append(Paragraph(_to_markup(block), style))
        story.append(Spacer(1, 2 * mm))


def _append_list_section(
    story: list,
    items: Iterable[str],
    style: ParagraphStyle,
) -> None:
    normalized_items = [item.strip() for item in items if item and item.strip()]
    if not normalized_items:
        return

    flowable = ListFlowable(
        [
            ListItem(Paragraph(_to_markup(item), style))
            for item in normalized_items
        ],
        bulletType="bullet",
        leftIndent=14,
    )
    story.append(flowable)


def _split_blocks(text: str) -> list[str]:
    normalized = (text or "").replace("\r\n", "\n").strip()
    if not normalized:
        return []

    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    return blocks or [normalized]


def _to_markup(text: str) -> str:
    safe_text = escape((text or "").strip())
    return safe_text.replace("\n", "<br/>")
