import json
import os
import re
from typing import Any

from core.analyzer import normalize_text
from core.pdf.pdf_reader import PDFReadResult, read_pdf_source


PDF_ANALYSIS_PATTERNS = (
    "analyse ce pdf",
    "analyse le pdf",
    "analyse ce document pdf",
    "lis ce document pdf",
    "lis ce pdf",
    "resume le pdf",
    "resume ce pdf",
    "explique moi ce fichier pdf",
    "explique moi ce pdf",
    "dis moi ce qu il y a dans ce pdf",
    "qu est ce qu il y a dans ce pdf",
    "que dit ce pdf",
    "que contient ce pdf",
)

PDF_ANALYSIS_VERBS = (
    "analyse",
    "lis",
    "resume",
    "explique",
    "dis moi",
    "que dit",
    "que contient",
    "qu est ce qu il y a",
)

PDF_ANALYSIS_TARGETS = (
    "pdf",
    "document",
    "fichier",
    "piece jointe",
)

MAX_PDF_ANALYSIS_CHARS = 18000

PDF_ANALYSIS_STOPWORDS = {
    "analyse",
    "analyser",
    "ce",
    "cet",
    "cette",
    "le",
    "la",
    "les",
    "un",
    "une",
    "de",
    "du",
    "des",
    "dans",
    "sur",
    "moi",
    "pdf",
    "document",
    "fichier",
    "resum",
    "resume",
    "explique",
    "dis",
    "quel",
    "quelle",
    "quels",
    "quelles",
    "est",
    "sont",
    "qu",
    "il",
    "y",
    "a",
}


def should_use_pdf_analysis_tool(
    user_message: str,
    has_attached_pdf: bool,
) -> bool:
    text = _normalize_pdf_analysis_text(user_message)
    if not text:
        return False

    if any(pattern in text for pattern in PDF_ANALYSIS_PATTERNS):
        return True

    has_verb = any(term in text for term in PDF_ANALYSIS_VERBS)
    has_target = any(term in text for term in PDF_ANALYSIS_TARGETS)

    if has_verb and has_target:
        return True

    return has_attached_pdf and has_verb


def analyze_pdf_reply(
    user_message: str,
    pdf_url: str | None = None,
    pdf_path: str | None = None,
    pdf_name: str | None = None,
    pdf_mime_type: str | None = None,
    conversation: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    read_result = read_pdf_source(
        pdf_url=pdf_url,
        pdf_path=pdf_path,
        pdf_name=pdf_name,
        pdf_mime_type=pdf_mime_type,
    )

    if read_result.status == "missing_source":
        return _build_error_result(
            reply="Je peux analyser un PDF, mais j'ai besoin que tu m'en envoies un.",
            status="missing_source",
            source_name=read_result.source_name,
            page_count=read_result.page_count,
        )

    if read_result.status == "ocr_needed":
        return _build_ocr_limit_result(read_result)

    if not read_result.ok:
        return _build_error_result(
            reply=_map_read_error_to_reply(read_result),
            status=read_result.status,
            source_name=read_result.source_name,
            page_count=read_result.page_count,
        )

    analysis = _analyze_pdf_text(
        user_message=user_message,
        read_result=read_result,
        conversation=conversation,
    )

    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": "pdf",
        "intent": "reflect",
        "reply": _build_analysis_reply(
            summary=analysis["summary"],
            key_points=analysis["key_points"],
            page_count=read_result.page_count,
            analysis_status="ok",
            question_answer=analysis.get("question_answer", ""),
        ),
        "tool_type": "pdf",
        "pdf_analysis_status": "ok",
        "pdf_summary": analysis["summary"],
        "pdf_key_points": analysis["key_points"],
        "pdf_page_count": read_result.page_count,
        "pdf_source_name": read_result.source_name,
        "pdf_has_text": True,
        "pdf_question_answer": analysis.get("question_answer", ""),
    }


def _build_error_result(
    reply: str,
    status: str,
    source_name: str,
    page_count: int,
) -> dict[str, Any]:
    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": "pdf",
        "intent": "clarify",
        "reply": reply,
        "tool_type": "pdf",
        "pdf_analysis_status": status,
        "pdf_summary": "",
        "pdf_key_points": [],
        "pdf_page_count": page_count,
        "pdf_source_name": source_name,
        "pdf_has_text": False,
        "pdf_question_answer": "",
    }


def _build_ocr_limit_result(read_result: PDFReadResult) -> dict[str, Any]:
    source_label = read_result.source_name or "ce PDF"
    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": "pdf",
        "intent": "clarify",
        "reply": (
            f"Je n'ai pas detecte de vrai texte exploitable dans {source_label}. "
            "Le PDF semble vide ou surtout scanne en image. "
            "L'OCR n'est pas encore branche sur ce backend."
        ),
        "tool_type": "pdf",
        "pdf_analysis_status": "ocr_needed",
        "pdf_summary": "",
        "pdf_key_points": [],
        "pdf_page_count": read_result.page_count,
        "pdf_source_name": read_result.source_name,
        "pdf_has_text": False,
        "pdf_question_answer": "",
    }


def _map_read_error_to_reply(read_result: PDFReadResult) -> str:
    if read_result.status == "invalid_source":
        return "Je n'ai pas trouve le fichier PDF a analyser."
    if read_result.status == "download_error":
        return "Je n'ai pas reussi a recuperer le PDF distant pour l'analyse."
    if read_result.status == "invalid_pdf":
        return "Le fichier envoye ne semble pas etre un PDF lisible."
    if read_result.status == "empty_pdf":
        return "Le PDF est vide ou ne contient aucune page exploitable."
    return "Je n'ai pas reussi a lire ce PDF pour le moment."


def _normalize_pdf_analysis_text(message: str) -> str:
    return normalize_text(message).replace("'", " ").strip()


def _analyze_pdf_text(
    user_message: str,
    read_result: PDFReadResult,
    conversation: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    llm_analysis = _build_analysis_with_llm(
        user_message=user_message,
        read_result=read_result,
        conversation=conversation,
    )
    if llm_analysis is not None:
        return llm_analysis

    return _build_fallback_analysis(
        user_message=user_message,
        read_result=read_result,
    )


def _build_analysis_with_llm(
    user_message: str,
    read_result: PDFReadResult,
    conversation: list[dict[str, str]] | None = None,
) -> dict[str, Any] | None:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return None

    try:
        from core.llm_client import build_zoe_system_prompt, create_llm_client

        client = create_llm_client()
        result = client.ask(
            user_message=_build_pdf_analysis_prompt(
                user_message=user_message,
                read_result=read_result,
            ),
            system_prompt=(
                build_zoe_system_prompt()
                + " Tu analyses un document PDF."
                + " Tu reponds uniquement avec un JSON valide."
            ),
            conversation=conversation,
            temperature=0.2,
        )
    except Exception:
        return None

    if result.error or not result.text.strip():
        return None

    payload = _extract_json_payload(result.text)
    if payload is None:
        return None

    summary = str(payload.get("summary", "")).strip()
    if not summary:
        return None

    key_points = [
        str(item).strip()
        for item in payload.get("key_points", []) or []
        if str(item).strip()
    ][:5]

    question_answer = str(payload.get("question_answer", "")).strip()

    return {
        "summary": summary,
        "key_points": key_points,
        "question_answer": question_answer,
    }


def _build_pdf_analysis_prompt(
    user_message: str,
    read_result: PDFReadResult,
) -> str:
    pdf_text = read_result.extracted_text[:MAX_PDF_ANALYSIS_CHARS].strip()
    return (
        "Tu analyses un PDF pour Zoe.\n"
        "Retourne uniquement un JSON valide avec cette structure :\n"
        "{\n"
        '  "summary": "resume clair en francais",\n'
        '  "key_points": ["point 1", "point 2", "point 3"],\n'
        '  "question_answer": "reponse utile a la demande de l utilisateur ou vide si non pertinent"\n'
        "}\n"
        "Contraintes :\n"
        "- resume court et clair\n"
        "- 3 a 5 points importants maximum\n"
        "- si l utilisateur pose une question, reponds a partir du PDF\n"
        "- si la question n est pas precise, utilise question_answer vide\n\n"
        f"Nom du fichier : {read_result.source_name}\n"
        f"Nombre de pages : {read_result.page_count}\n"
        f"Demande utilisateur : {user_message.strip()}\n\n"
        f"Texte extrait du PDF :\n{pdf_text}"
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


def _build_fallback_analysis(
    user_message: str,
    read_result: PDFReadResult,
) -> dict[str, Any]:
    paragraphs = _extract_paragraphs(read_result.extracted_text)
    summary = paragraphs[0] if paragraphs else read_result.extracted_text[:400].strip()
    key_points = _extract_key_points(read_result.extracted_text)
    question_answer = _extract_answer_from_text(
        user_message=user_message,
        text=read_result.extracted_text,
    )

    return {
        "summary": summary or "Le PDF contient du texte exploitable, mais je n'ai pas pu produire un resume detaille.",
        "key_points": key_points,
        "question_answer": question_answer,
    }


def _extract_paragraphs(text: str) -> list[str]:
    cleaned = (text or "").replace("\r\n", "\n").strip()
    if not cleaned:
        return []

    return [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", cleaned)
        if paragraph.strip()
    ]


def _extract_key_points(text: str) -> list[str]:
    lines = [
        line.strip()
        for line in (text or "").replace("\r\n", "\n").split("\n")
        if line.strip()
    ]

    bullet_lines = [
        re.sub(r"^([-*•]|\d+[.)])\s+", "", line).strip()
        for line in lines
        if re.match(r"^([-*•]|\d+[.)])\s+", line)
    ]
    if bullet_lines:
        return bullet_lines[:5]

    sentences = re.split(r"(?<=[\.\!\?])\s+", " ".join(lines))
    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ][:5]


def _extract_answer_from_text(user_message: str, text: str) -> str:
    if "?" not in user_message and not any(
        marker in _normalize_pdf_analysis_text(user_message)
        for marker in {"explique", "dis moi", "que dit", "que contient", "qu est ce qu il y a"}
    ):
        return ""

    keywords = [
        token
        for token in _normalize_pdf_analysis_text(user_message).split()
        if len(token) > 2 and token not in PDF_ANALYSIS_STOPWORDS
    ]
    if not keywords:
        return ""

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[\.\!\?])\s+", " ".join(text.split()))
        if sentence.strip()
    ]

    best_sentence = ""
    best_score = 0

    for sentence in sentences:
        normalized_sentence = _normalize_pdf_analysis_text(sentence)
        score = sum(1 for keyword in keywords if keyword in normalized_sentence)
        if score > best_score:
            best_score = score
            best_sentence = sentence

    return best_sentence if best_score > 0 else ""


def _build_analysis_reply(
    summary: str,
    key_points: list[str],
    page_count: int,
    analysis_status: str,
    question_answer: str,
) -> str:
    parts = [
        f"Statut d'analyse : {analysis_status}",
        f"Nombre de pages : {page_count}",
        "",
        "Resume :",
        summary.strip(),
    ]

    if key_points:
        parts.append("")
        parts.append("Points importants :")
        for item in key_points[:5]:
            parts.append(f"- {item}")

    if question_answer.strip():
        parts.append("")
        parts.append("Reponse a ta demande :")
        parts.append(question_answer.strip())

    return "\n".join(parts).strip()
