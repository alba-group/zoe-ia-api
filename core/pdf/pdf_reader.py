from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any
import unicodedata
from urllib.parse import urlparse
from urllib.request import urlopen

from pypdf import PdfReader

from core.config import OPENAI_TIMEOUT_SECONDS


PDF_SOURCE_TIMEOUT_SECONDS = max(float(OPENAI_TIMEOUT_SECONDS), 30.0)


@dataclass
class PDFReadResult:
    ok: bool
    status: str
    source_name: str = ""
    source_type: str = ""
    page_count: int = 0
    extracted_text: str = ""
    page_texts: list[str] = field(default_factory=list)
    pages_with_text: int = 0
    has_text: bool = False
    scanned_like: bool = False
    error: str | None = None


def read_pdf_source(
    pdf_url: str | None = None,
    pdf_path: str | None = None,
    pdf_name: str | None = None,
    pdf_mime_type: str | None = None,
) -> PDFReadResult:
    del pdf_mime_type

    if (pdf_path or "").strip():
        return _read_pdf_from_path(
            pdf_path=str(pdf_path or "").strip(),
            pdf_name=pdf_name,
        )

    if (pdf_url or "").strip():
        return _read_pdf_from_url(
            pdf_url=str(pdf_url or "").strip(),
            pdf_name=pdf_name,
        )

    return PDFReadResult(
        ok=False,
        status="missing_source",
        source_name=(pdf_name or "").strip(),
        source_type="none",
        error="Aucun PDF fourni.",
    )


def _read_pdf_from_path(pdf_path: str, pdf_name: str | None = None) -> PDFReadResult:
    path = Path(pdf_path).expanduser()
    if not path.is_absolute():
        path = path.resolve()

    if not path.exists() or not path.is_file():
        return PDFReadResult(
            ok=False,
            status="invalid_source",
            source_name=(pdf_name or path.name).strip(),
            source_type="path",
            error="Le fichier PDF est introuvable.",
        )

    try:
        pdf_bytes = path.read_bytes()
    except Exception as error:
        return PDFReadResult(
            ok=False,
            status="read_error",
            source_name=(pdf_name or path.name).strip(),
            source_type="path",
            error=str(error),
        )

    return _extract_pdf_text(
        pdf_bytes=pdf_bytes,
        source_name=(pdf_name or path.name).strip(),
        source_type="path",
    )


def _read_pdf_from_url(pdf_url: str, pdf_name: str | None = None) -> PDFReadResult:
    try:
        with urlopen(pdf_url, timeout=PDF_SOURCE_TIMEOUT_SECONDS) as response:
            pdf_bytes = response.read()
    except Exception as error:
        parsed = urlparse(pdf_url)
        fallback_name = Path(parsed.path).name
        return PDFReadResult(
            ok=False,
            status="download_error",
            source_name=(pdf_name or fallback_name).strip(),
            source_type="url",
            error=str(error),
        )

    parsed = urlparse(pdf_url)
    source_name = (pdf_name or Path(parsed.path).name or "document.pdf").strip()

    return _extract_pdf_text(
        pdf_bytes=pdf_bytes,
        source_name=source_name,
        source_type="url",
    )


def _extract_pdf_text(
    pdf_bytes: bytes,
    source_name: str,
    source_type: str,
) -> PDFReadResult:
    if not pdf_bytes:
        return PDFReadResult(
            ok=False,
            status="empty_pdf",
            source_name=source_name,
            source_type=source_type,
            error="Le PDF est vide.",
        )

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except Exception as error:
        return PDFReadResult(
            ok=False,
            status="invalid_pdf",
            source_name=source_name,
            source_type=source_type,
            error=str(error),
        )

    page_texts: list[str] = []
    pages_with_text = 0

    for page in reader.pages:
        page_text = _extract_page_text(page)
        page_texts.append(page_text)
        if page_text.strip():
            pages_with_text += 1

    page_count = len(reader.pages)
    extracted_text = "\n\n".join(
        text.strip()
        for text in page_texts
        if text.strip()
    ).strip()
    has_text = bool(extracted_text)
    scanned_like = page_count > 0 and not has_text

    if page_count == 0:
        return PDFReadResult(
            ok=False,
            status="empty_pdf",
            source_name=source_name,
            source_type=source_type,
            page_count=0,
            error="Le PDF ne contient aucune page.",
        )

    if not has_text:
        return PDFReadResult(
            ok=False,
            status="ocr_needed",
            source_name=source_name,
            source_type=source_type,
            page_count=page_count,
            page_texts=page_texts,
            pages_with_text=pages_with_text,
            has_text=False,
            scanned_like=scanned_like,
            error="Aucun texte exploitable n'a ete detecte dans le PDF.",
        )

    return PDFReadResult(
        ok=True,
        status="ok",
        source_name=source_name,
        source_type=source_type,
        page_count=page_count,
        extracted_text=extracted_text,
        page_texts=page_texts,
        pages_with_text=pages_with_text,
        has_text=True,
        scanned_like=False,
        error=None,
    )


def _extract_page_text(page: Any) -> str:
    try:
        text = page.extract_text() or ""
    except Exception:
        return ""

    cleaned = "".join(
        char
        for char in text
        if (
            char in {"\n", "\r", "\t"}
            or (ord(char) >= 32 and not unicodedata.category(char).startswith("C"))
        )
    )

    return cleaned.strip()
