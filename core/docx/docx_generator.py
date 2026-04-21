import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from core.config import DOCX_DIR, DOCX_DOWNLOAD_ROUTE_PREFIX


@dataclass
class DOCXSection:
    kind: str
    text: str = ""
    items: list[str] = field(default_factory=list)
    heading: str = ""


@dataclass
class DOCXDocumentContent:
    title: str
    subtitle: str = ""
    sections: list[DOCXSection] = field(default_factory=list)
    file_name_hint: str = ""


def sanitize_file_name_fragment(value: str, fallback: str = "document") -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_value = ascii_value.lower().strip()
    ascii_value = re.sub(r"[^a-z0-9]+", "_", ascii_value)
    ascii_value = ascii_value.strip("_")
    return ascii_value[:60] or fallback


def build_docx_filename(title_hint: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_title = sanitize_file_name_fragment(title_hint, fallback="zoe_document")
    return f"{timestamp}_{clean_title}.docx"


def build_docx_download_url(file_name: str) -> str:
    clean_name = Path(file_name).name
    return f"{DOCX_DOWNLOAD_ROUTE_PREFIX}/{clean_name}"


def generate_docx_file(
    document: DOCXDocumentContent,
    output_dir: Path | None = None,
) -> Path:
    target_dir = output_dir or DOCX_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    title_hint = document.file_name_hint or document.title or "document"
    file_name = build_docx_filename(title_hint)
    output_path = target_dir / file_name

    doc = Document()
    _configure_document(doc)
    doc.core_properties.title = document.title or "Document"
    doc.core_properties.subject = document.subtitle or ""

    _append_title(doc, document.title or "Document")
    if document.subtitle.strip():
        _append_subtitle(doc, document.subtitle)

    sections = document.sections or [DOCXSection(kind="paragraph", text="Document vide.")]

    for section in sections:
        if section.heading.strip():
            _append_heading(doc, section.heading)

        if section.kind == "list":
            _append_list_section(doc, section.items)
        else:
            _append_paragraph_section(doc, section.text)

    doc.save(output_path)
    return output_path


def _configure_document(doc: Document) -> None:
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(1.8)
        section.left_margin = Cm(2.0)
        section.right_margin = Cm(2.0)


def _append_title(doc: Document, title: str) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(4)
    run = paragraph.add_run((title or "").strip())
    run.bold = True
    run.font.name = "Calibri"
    run.font.size = Pt(18)


def _append_subtitle(doc: Document, subtitle: str) -> None:
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(14)
    run = paragraph.add_run((subtitle or "").strip())
    run.italic = True
    run.font.name = "Calibri"
    run.font.size = Pt(10.5)


def _append_heading(doc: Document, heading: str) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(8)
    paragraph.paragraph_format.space_after = Pt(3)
    run = paragraph.add_run((heading or "").strip())
    run.bold = True
    run.font.name = "Calibri"
    run.font.size = Pt(12)


def _append_paragraph_section(doc: Document, text: str) -> None:
    blocks = [block for block in _split_blocks(text) if block.strip()]
    if not blocks:
        return

    for block in blocks:
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(6)
        paragraph.paragraph_format.line_spacing = 1.2
        run = paragraph.add_run(block.strip())
        run.font.name = "Calibri"
        run.font.size = Pt(11)


def _append_list_section(doc: Document, items: Iterable[str]) -> None:
    normalized_items = [item.strip() for item in items if item and item.strip()]
    if not normalized_items:
        return

    for item in normalized_items:
        paragraph = doc.add_paragraph(style="List Bullet")
        paragraph.paragraph_format.space_after = Pt(2)
        run = paragraph.add_run(item)
        run.font.name = "Calibri"
        run.font.size = Pt(11)


def _split_blocks(text: str) -> list[str]:
    normalized = (text or "").replace("\r\n", "\n").strip()
    if not normalized:
        return []

    blocks = [block.strip() for block in re.split(r"\n\s*\n", normalized) if block.strip()]
    return blocks or [normalized]
