import json
import os
import re
from typing import Any

from core.analyzer import normalize_text
from core.docx.docx_generator import (
    DOCXDocumentContent,
    DOCXSection,
    build_docx_download_url,
    generate_docx_file,
)


DOCX_PATTERNS = (
    "fais moi un word",
    "cree un document word",
    "cree un fichier docx",
    "genere un fichier docx",
    "prepare un document a telecharger",
    "prepare un document word",
    "prepare un docx",
    "transforme ca en word",
    "transforme ceci en word",
    "transforme ce texte en word",
    "transforme ca en docx",
    "transforme ceci en docx",
    "transforme ce texte en docx",
    "convertis ca en word",
    "convertis ceci en word",
    "convertis ca en docx",
    "convertis ceci en docx",
    "fais moi une lettre en docx",
    "fais moi un document word",
    "cree un document a telecharger",
    "au format word",
    "au format docx",
    "exporte en word",
    "exporte en docx",
)

DOCX_ACTION_TERMS = (
    "fais",
    "cree",
    "genere",
    "prepare",
    "transforme",
    "convertis",
    "exporte",
)

DOCX_FORMAT_TERMS = (
    "word",
    "docx",
)

DOCX_DOCUMENT_TERMS = (
    "document",
    "lettre",
    "rapport",
    "fiche",
    "cv",
    "compte rendu",
    "resume",
)

DOCX_EXPORT_TERMS = (
    "telecharger",
    "exporter",
    "export",
)

DOCX_REFERENCE_TERMS = (
    "transforme ca en word",
    "transforme ceci en word",
    "transforme ce texte en word",
    "transforme ca en docx",
    "transforme ceci en docx",
    "transforme ce texte en docx",
    "convertis ca en word",
    "convertis ceci en word",
    "convertis ca en docx",
    "convertis ceci en docx",
    "mets ca en word",
    "mets ceci en word",
    "mets ca en docx",
    "mets ceci en docx",
)

DOCX_CONNECTOR_PREFIXES = (
    "sur ",
    "avec ",
    "de ",
    "pour ",
    "concernant ",
    "a propos de ",
    ":",
    "-",
)

DOCUMENT_KIND_TITLES = {
    "rapport": "Rapport",
    "lettre": "Lettre",
    "fiche": "Fiche",
    "cv": "CV",
    "compte rendu": "Compte rendu",
    "resume": "Resume",
    "document": "Document",
}


def should_use_docx_tool(user_message: str) -> bool:
    text = _normalize_docx_text(user_message)
    if not text:
        return False

    if "pdf" in text and not any(term in text for term in DOCX_FORMAT_TERMS):
        return False

    if any(pattern in text for pattern in DOCX_PATTERNS):
        return True

    has_action = any(term in text for term in DOCX_ACTION_TERMS)
    has_format = any(term in text for term in DOCX_FORMAT_TERMS)
    has_document_type = any(term in text for term in DOCX_DOCUMENT_TERMS)
    has_export = any(term in text for term in DOCX_EXPORT_TERMS)

    if has_format and (has_action or has_document_type or has_export):
        return True

    return has_action and has_document_type and has_export


def build_docx_reply(
    user_message: str,
    conversation: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    source_text = _extract_source_text(user_message, conversation)
    if not source_text.strip():
        return _build_error_result(
            reply="Je peux generer un document Word, mais j'ai besoin du contenu a mettre dedans.",
            intent="clarify",
        )

    try:
        document = _build_document_content(
            user_message=user_message,
            source_text=source_text,
            conversation=conversation,
        )

        docx_path = generate_docx_file(document)
        docx_file_name = docx_path.name

        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "docx",
            "intent": "reflect",
            "reply": "Ton document Word est pret.",
            "tool_type": "docx",
            "docx_path": str(docx_path),
            "docx_url": build_docx_download_url(docx_file_name),
            "docx_filename": docx_file_name,
            "docx_mime_type": (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            "docx_title": document.title,
        }

    except Exception:
        return _build_error_result(
            reply="Je n'ai pas reussi a generer le document Word pour le moment.",
            intent="clarify",
        )


def _build_error_result(reply: str, intent: str) -> dict[str, Any]:
    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": "docx",
        "intent": intent,
        "reply": reply,
        "tool_type": "docx",
        "docx_path": None,
        "docx_url": None,
        "docx_filename": None,
        "docx_mime_type": None,
        "docx_title": None,
    }


def _normalize_docx_text(message: str) -> str:
    return normalize_text(message).replace("'", " ").strip()


def _extract_source_text(
    user_message: str,
    conversation: list[dict[str, str]] | None = None,
) -> str:
    inline_source = _extract_inline_source_text(user_message)
    if inline_source.strip():
        return inline_source.strip()

    if _looks_like_reference_docx_request(user_message):
        return _extract_reference_content(conversation)

    return ""


def _extract_inline_source_text(user_message: str) -> str:
    raw_text = (user_message or "").strip()
    if not raw_text:
        return ""

    if "\n" in raw_text:
        first_line, remaining = raw_text.split("\n", 1)
        if should_use_docx_tool(first_line):
            cleaned_remaining = remaining.strip()
            if cleaned_remaining:
                return cleaned_remaining

    for marker in DOCX_FORMAT_TERMS:
        match = re.search(rf"\b{re.escape(marker)}\b", raw_text, flags=re.IGNORECASE)
        if not match:
            continue

        suffix = raw_text[match.end():].strip(" \n\t:;-")
        suffix = _strip_connectors(suffix)
        if suffix:
            return suffix

    for connector in ("sur", "avec", "de", "pour", "concernant", "a propos de"):
        match = re.search(
            rf"\b{re.escape(connector)}\b\s+(.+)$",
            raw_text,
            flags=re.IGNORECASE,
        )
        if not match:
            continue

        prefix = raw_text[:match.start()].strip()
        if not should_use_docx_tool(prefix):
            continue

        suffix = match.group(1).strip(" \n\t:;-")
        if suffix:
            return suffix

    return ""


def _strip_connectors(text: str) -> str:
    cleaned = (text or "").strip()
    lower_cleaned = cleaned.lower()

    for prefix in DOCX_CONNECTOR_PREFIXES:
        if lower_cleaned.startswith(prefix):
            return cleaned[len(prefix):].strip()

    return cleaned


def _looks_like_reference_docx_request(user_message: str) -> bool:
    text = _normalize_docx_text(user_message)
    return any(pattern in text for pattern in DOCX_REFERENCE_TERMS)


def _extract_reference_content(
    conversation: list[dict[str, str]] | None = None,
) -> str:
    if not conversation:
        return ""

    for item in reversed(conversation):
        role = str(item.get("role", "")).strip().lower()
        content = str(item.get("content", "")).strip()
        if not content:
            continue

        if role == "assistant":
            return content

    for item in reversed(conversation):
        content = str(item.get("content", "")).strip()
        if content:
            return content

    return ""


def _build_document_content(
    user_message: str,
    source_text: str,
    conversation: list[dict[str, str]] | None = None,
) -> DOCXDocumentContent:
    llm_document = _build_document_content_with_llm(
        user_message=user_message,
        source_text=source_text,
        conversation=conversation,
    )
    if llm_document is not None:
        return llm_document

    return _build_document_content_fallback(
        user_message=user_message,
        source_text=source_text,
    )


def _build_document_content_with_llm(
    user_message: str,
    source_text: str,
    conversation: list[dict[str, str]] | None = None,
) -> DOCXDocumentContent | None:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return None

    try:
        from core.llm_client import build_zoe_system_prompt, create_llm_client

        client = create_llm_client()
        result = client.ask(
            user_message=_build_docx_generation_prompt(
                user_message=user_message,
                source_text=source_text,
            ),
            system_prompt=(
                build_zoe_system_prompt()
                + " Tu prepares le contenu structure d'un document Word."
                + " Tu reponds uniquement avec un JSON valide."
            ),
            conversation=conversation,
            temperature=0.2,
        )
    except Exception:
        return None

    if result.error or not result.text.strip():
        return None

    parsed = _extract_json_payload(result.text)
    if parsed is None:
        return None

    return _build_document_from_payload(
        payload=parsed,
        user_message=user_message,
        source_text=source_text,
    )


def _build_docx_generation_prompt(
    user_message: str,
    source_text: str,
) -> str:
    return (
        "Tu prepares le contenu d'un document Word simple pour Zoe.\n"
        "Retourne uniquement un JSON valide avec cette structure :\n"
        "{\n"
        '  "title": "Titre court",\n'
        '  "subtitle": "Sous-titre court ou vide",\n'
        '  "file_name_hint": "nom de fichier court ou vide",\n'
        '  "sections": [\n'
        '    {"type": "paragraph", "heading": "", "text": "..."},\n'
        '    {"type": "list", "heading": "", "items": ["...", "..."]}\n'
        "  ]\n"
        "}\n"
        "Contraintes :\n"
        "- reponse en francais\n"
        "- pas de markdown\n"
        "- paragraphs clairs\n"
        "- listes simples si utile\n"
        "- si la demande parle d'une lettre, produis un vrai texte de lettre\n"
        "- si la demande parle d'un CV, propose une structure sobre et exploitable\n"
        "- si la demande parle d'un rapport, organise le contenu proprement\n\n"
        f"Demande utilisateur : {user_message.strip()}\n\n"
        f"Contenu de reference :\n{source_text.strip()}"
    )


def _extract_json_payload(text: str) -> dict[str, Any] | None:
    cleaned = (text or "").strip()
    if not cleaned:
        return None

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        payload = json.loads(cleaned[start:end + 1])
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    return payload


def _build_document_from_payload(
    payload: dict[str, Any],
    user_message: str,
    source_text: str,
) -> DOCXDocumentContent:
    title = str(payload.get("title", "")).strip() or _build_fallback_title(user_message, source_text)
    subtitle = str(payload.get("subtitle", "")).strip()
    file_name_hint = str(payload.get("file_name_hint", "")).strip() or title

    sections: list[DOCXSection] = []

    for item in payload.get("sections", []) or []:
        if not isinstance(item, dict):
            continue

        section_type = str(item.get("type", "paragraph")).strip().lower()
        heading = str(item.get("heading", "")).strip()

        if section_type == "list":
            raw_items = item.get("items", []) or []
            items = [
                str(list_item).strip()
                for list_item in raw_items
                if str(list_item).strip()
            ]
            if items:
                sections.append(DOCXSection(kind="list", heading=heading, items=items))
            continue

        text = str(item.get("text", "")).strip()
        if text:
            sections.append(DOCXSection(kind="paragraph", heading=heading, text=text))

    if not sections:
        sections = _build_sections_from_source(source_text)

    return DOCXDocumentContent(
        title=title,
        subtitle=subtitle,
        sections=sections,
        file_name_hint=file_name_hint,
    )


def _build_document_content_fallback(
    user_message: str,
    source_text: str,
) -> DOCXDocumentContent:
    title = _build_fallback_title(user_message, source_text)
    subtitle = _build_fallback_subtitle(user_message)
    sections = _build_sections_from_source(source_text)

    return DOCXDocumentContent(
        title=title,
        subtitle=subtitle,
        sections=sections,
        file_name_hint=title,
    )


def _build_fallback_title(user_message: str, source_text: str) -> str:
    normalized_message = _normalize_docx_text(user_message)
    document_kind = "document"

    for kind in DOCUMENT_KIND_TITLES:
        if kind in normalized_message:
            document_kind = kind
            break

    title = DOCUMENT_KIND_TITLES.get(document_kind, "Document")
    subject = _build_subject_hint(source_text)

    if subject:
        return f"{title} - {subject}"

    return title


def _build_fallback_subtitle(user_message: str) -> str:
    normalized_message = _normalize_docx_text(user_message)
    if "telecharger" in normalized_message:
        return "Document prepare pour export"
    return "Document Word genere par Zoe IA"


def _build_subject_hint(source_text: str) -> str:
    compact = " ".join((source_text or "").split()).strip(" .,:;!-")
    if not compact:
        return ""

    words = compact.split()
    return " ".join(words[:8]).strip()


def _build_sections_from_source(source_text: str) -> list[DOCXSection]:
    normalized = (source_text or "").replace("\r\n", "\n").strip()
    if not normalized:
        return [DOCXSection(kind="paragraph", text="Document vide.")]

    lines = normalized.split("\n")
    sections: list[DOCXSection] = []
    paragraph_buffer: list[str] = []
    list_buffer: list[str] = []

    def flush_paragraph_buffer() -> None:
        if paragraph_buffer:
            paragraph_text = "\n".join(paragraph_buffer).strip()
            if paragraph_text:
                sections.append(DOCXSection(kind="paragraph", text=paragraph_text))
            paragraph_buffer.clear()

    def flush_list_buffer() -> None:
        if list_buffer:
            sections.append(DOCXSection(kind="list", items=list_buffer.copy()))
            list_buffer.clear()

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            flush_paragraph_buffer()
            flush_list_buffer()
            continue

        if _is_list_item(line):
            flush_paragraph_buffer()
            list_buffer.append(_clean_list_item(line))
            continue

        flush_list_buffer()
        paragraph_buffer.append(line)

    flush_paragraph_buffer()
    flush_list_buffer()

    return sections or [DOCXSection(kind="paragraph", text=normalized)]


def _is_list_item(line: str) -> bool:
    return bool(re.match(r"^([-*]|\d+[.)])\s+", line))


def _clean_list_item(line: str) -> str:
    return re.sub(r"^([-*]|\d+[.)])\s+", "", line).strip()
