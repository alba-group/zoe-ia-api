from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from docx import Document

from core.config import OPENAI_TIMEOUT_SECONDS


DOCX_SOURCE_TIMEOUT_SECONDS = max(float(OPENAI_TIMEOUT_SECONDS), 30.0)


@dataclass
class DOCXReadResult:
    ok: bool
    status: str
    source_name: str = ""
    source_type: str = ""
    paragraph_count: int = 0
    extracted_text: str = ""
    paragraphs: list[str] = field(default_factory=list)
    heading_titles: list[str] = field(default_factory=list)
    has_text: bool = False
    error: str | None = None


def read_docx_source(
    docx_url: str | None = None,
    docx_path: str | None = None,
    docx_name: str | None = None,
    docx_mime_type: str | None = None,
) -> DOCXReadResult:
    del docx_mime_type

    if (docx_path or "").strip():
        return _read_docx_from_path(
            docx_path=str(docx_path or "").strip(),
            docx_name=docx_name,
        )

    if (docx_url or "").strip():
        return _read_docx_from_url(
            docx_url=str(docx_url or "").strip(),
            docx_name=docx_name,
        )

    return DOCXReadResult(
        ok=False,
        status="missing_source",
        source_name=(docx_name or "").strip(),
        source_type="none",
        error="Aucun DOCX fourni.",
    )


def _read_docx_from_path(docx_path: str, docx_name: str | None = None) -> DOCXReadResult:
    path = Path(docx_path).expanduser()
    if not path.is_absolute():
        path = path.resolve()

    if not path.exists() or not path.is_file():
        return DOCXReadResult(
            ok=False,
            status="invalid_source",
            source_name=(docx_name or path.name).strip(),
            source_type="path",
            error="Le fichier DOCX est introuvable.",
        )

    try:
        docx_bytes = path.read_bytes()
    except Exception as error:
        return DOCXReadResult(
            ok=False,
            status="read_error",
            source_name=(docx_name or path.name).strip(),
            source_type="path",
            error=str(error),
        )

    return _extract_docx_text(
        docx_bytes=docx_bytes,
        source_name=(docx_name or path.name).strip(),
        source_type="path",
    )


def _read_docx_from_url(docx_url: str, docx_name: str | None = None) -> DOCXReadResult:
    try:
        with urlopen(docx_url, timeout=DOCX_SOURCE_TIMEOUT_SECONDS) as response:
            docx_bytes = response.read()
    except Exception as error:
        parsed = urlparse(docx_url)
        fallback_name = Path(parsed.path).name
        return DOCXReadResult(
            ok=False,
            status="download_error",
            source_name=(docx_name or fallback_name).strip(),
            source_type="url",
            error=str(error),
        )

    parsed = urlparse(docx_url)
    source_name = (docx_name or Path(parsed.path).name or "document.docx").strip()

    return _extract_docx_text(
        docx_bytes=docx_bytes,
        source_name=source_name,
        source_type="url",
    )


def _extract_docx_text(
    docx_bytes: bytes,
    source_name: str,
    source_type: str,
) -> DOCXReadResult:
    if not docx_bytes:
        return DOCXReadResult(
            ok=False,
            status="empty_docx",
            source_name=source_name,
            source_type=source_type,
            error="Le document DOCX est vide.",
        )

    try:
        document = Document(BytesIO(docx_bytes))
    except Exception as error:
        return DOCXReadResult(
            ok=False,
            status="invalid_docx",
            source_name=source_name,
            source_type=source_type,
            error=str(error),
        )

    paragraphs: list[str] = []
    heading_titles: list[str] = []

    for paragraph in document.paragraphs:
        text = _clean_text(paragraph.text)
        if not text:
            continue

        paragraphs.append(text)
        if _looks_like_heading(paragraph.style.name if paragraph.style else ""):
            heading_titles.append(text)

    for table in document.tables:
        for row in table.rows:
            cell_values = [
                _clean_text(cell.text)
                for cell in row.cells
                if _clean_text(cell.text)
            ]
            if cell_values:
                paragraphs.append(" | ".join(cell_values))

    extracted_text = "\n\n".join(paragraphs).strip()
    if not extracted_text:
        return DOCXReadResult(
            ok=False,
            status="empty_docx",
            source_name=source_name,
            source_type=source_type,
            paragraph_count=0,
            paragraphs=[],
            heading_titles=[],
            has_text=False,
            error="Le document Word ne contient pas de texte exploitable.",
        )

    return DOCXReadResult(
        ok=True,
        status="ok",
        source_name=source_name,
        source_type=source_type,
        paragraph_count=len(paragraphs),
        extracted_text=extracted_text,
        paragraphs=paragraphs,
        heading_titles=_deduplicate_preserve_order(heading_titles),
        has_text=True,
        error=None,
    )


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\r", " ").replace("\n", " ").split()).strip()


def _looks_like_heading(style_name: str) -> bool:
    normalized = _clean_text(style_name).lower()
    if not normalized:
        return False

    return (
        normalized.startswith("heading")
        or normalized.startswith("titre")
        or normalized == "title"
        or normalized.startswith("heading ")
        or normalized.startswith("titre ")
    )


def _deduplicate_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value)

    return result
