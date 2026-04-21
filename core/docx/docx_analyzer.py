import json
import os
import re
from typing import Any

from core.analyzer import normalize_text
from core.docx.docx_reader import DOCXReadResult, read_docx_source


DOCX_ANALYSIS_PATTERNS = (
    "analyse ce word",
    "analyse le word",
    "analyse ce document word",
    "analyse ce docx",
    "lis ce document word",
    "lis ce fichier word",
    "lis ce docx",
    "resume ce docx",
    "resume ce word",
    "resume le document word",
    "explique moi ce fichier word",
    "explique moi ce document word",
    "explique moi ce docx",
    "dis moi ce qu il y a dans ce document",
    "dis moi ce qu il y a dans ce word",
    "qu est ce qu il y a dans ce document",
    "que contient ce docx",
    "que dit ce document word",
)

DOCX_ANALYSIS_VERBS = (
    "analyse",
    "lis",
    "resume",
    "explique",
    "dis moi",
    "que dit",
    "que contient",
    "qu est ce qu il y a",
)

DOCX_ANALYSIS_TARGETS = (
    "word",
    "docx",
    "document",
    "fichier",
    "piece jointe",
)

MAX_DOCX_ANALYSIS_CHARS = 18000

DOCX_ANALYSIS_STOPWORDS = {
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
    "word",
    "docx",
    "document",
    "fichier",
    "piece",
    "jointe",
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


def should_use_docx_analysis_tool(
    user_message: str,
    has_attached_docx: bool,
) -> bool:
    text = _normalize_docx_analysis_text(user_message)
    if not text:
        return False

    if any(pattern in text for pattern in DOCX_ANALYSIS_PATTERNS):
        return True

    has_verb = any(term in text for term in DOCX_ANALYSIS_VERBS)
    has_target = any(term in text for term in DOCX_ANALYSIS_TARGETS)

    if has_verb and has_target:
        return True

    return has_attached_docx and has_verb


def analyze_docx_reply(
    user_message: str,
    docx_url: str | None = None,
    docx_path: str | None = None,
    docx_name: str | None = None,
    docx_mime_type: str | None = None,
    conversation: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    read_result = read_docx_source(
        docx_url=docx_url,
        docx_path=docx_path,
        docx_name=docx_name,
        docx_mime_type=docx_mime_type,
    )

    if read_result.status == "missing_source":
        return _build_error_result(
            reply="Je peux analyser un document Word, mais j'ai besoin que tu m'en envoies un.",
            status="missing_source",
            source_name=read_result.source_name,
            paragraph_count=read_result.paragraph_count,
        )

    if not read_result.ok:
        return _build_error_result(
            reply=_map_read_error_to_reply(read_result),
            status=read_result.status,
            source_name=read_result.source_name,
            paragraph_count=read_result.paragraph_count,
        )

    analysis = _analyze_docx_text(
        user_message=user_message,
        read_result=read_result,
        conversation=conversation,
    )

    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": "docx",
        "intent": "reflect",
        "reply": _build_analysis_reply(
            summary=analysis["summary"],
            key_points=analysis["key_points"],
            analysis_status="ok",
            question_answer=analysis.get("question_answer", ""),
            paragraph_count=read_result.paragraph_count,
            heading_titles=read_result.heading_titles,
        ),
        "tool_type": "docx",
        "docx_analysis_status": "ok",
        "docx_summary": analysis["summary"],
        "docx_key_points": analysis["key_points"],
        "docx_source_name": read_result.source_name,
        "docx_has_text": True,
        "docx_question_answer": analysis.get("question_answer", ""),
        "docx_heading_titles": read_result.heading_titles,
        "docx_paragraph_count": read_result.paragraph_count,
    }


def _build_error_result(
    reply: str,
    status: str,
    source_name: str,
    paragraph_count: int,
) -> dict[str, Any]:
    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": "docx",
        "intent": "clarify",
        "reply": reply,
        "tool_type": "docx",
        "docx_analysis_status": status,
        "docx_summary": "",
        "docx_key_points": [],
        "docx_source_name": source_name,
        "docx_has_text": False,
        "docx_question_answer": "",
        "docx_heading_titles": [],
        "docx_paragraph_count": paragraph_count,
    }


def _map_read_error_to_reply(read_result: DOCXReadResult) -> str:
    if read_result.status == "invalid_source":
        return "Je n'ai pas trouve le fichier Word a analyser."
    if read_result.status == "download_error":
        return "Je n'ai pas reussi a recuperer le document Word distant pour l'analyse."
    if read_result.status == "invalid_docx":
        return "Le fichier envoye ne semble pas etre un document Word / DOCX lisible."
    if read_result.status == "empty_docx":
        return "Le document Word est vide ou ne contient pas de texte exploitable."
    return "Je n'ai pas reussi a lire ce document Word pour le moment."


def _normalize_docx_analysis_text(message: str) -> str:
    return normalize_text(message).replace("'", " ").strip()


def _analyze_docx_text(
    user_message: str,
    read_result: DOCXReadResult,
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
    read_result: DOCXReadResult,
    conversation: list[dict[str, str]] | None = None,
) -> dict[str, Any] | None:
    if not os.getenv("OPENAI_API_KEY", "").strip():
        return None

    try:
        from core.llm_client import build_zoe_system_prompt, create_llm_client

        client = create_llm_client()
        result = client.ask(
            user_message=_build_docx_analysis_prompt(
                user_message=user_message,
                read_result=read_result,
            ),
            system_prompt=(
                build_zoe_system_prompt()
                + " Tu analyses un document Word."
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


def _build_docx_analysis_prompt(
    user_message: str,
    read_result: DOCXReadResult,
) -> str:
    docx_text = read_result.extracted_text[:MAX_DOCX_ANALYSIS_CHARS].strip()
    headings = "\n".join(f"- {item}" for item in read_result.heading_titles[:10])
    return (
        "Tu analyses un document Word / DOCX pour Zoe.\n"
        "Retourne uniquement un JSON valide avec cette structure :\n"
        "{\n"
        '  "summary": "resume clair en francais",\n'
        '  "key_points": ["point 1", "point 2", "point 3"],\n'
        '  "question_answer": "reponse utile a la demande de l utilisateur ou vide si non pertinent"\n'
        "}\n"
        "Contraintes :\n"
        "- resume court et clair\n"
        "- 3 a 5 points importants maximum\n"
        "- tiens compte des titres si presents\n"
        "- si l utilisateur pose une question, reponds a partir du document\n"
        "- si la question n est pas precise, utilise question_answer vide\n\n"
        f"Nom du fichier : {read_result.source_name}\n"
        f"Nombre de paragraphes : {read_result.paragraph_count}\n"
        f"Demande utilisateur : {user_message.strip()}\n\n"
        f"Titres reperes :\n{headings or '- aucun'}\n\n"
        f"Texte extrait du document :\n{docx_text}"
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
    read_result: DOCXReadResult,
) -> dict[str, Any]:
    summary = _build_fallback_summary(read_result)
    key_points = _extract_key_points(read_result)
    question_answer = _extract_answer_from_text(
        user_message=user_message,
        text=read_result.extracted_text,
    )

    return {
        "summary": summary or "Le document Word contient du texte exploitable, mais je n'ai pas pu produire un resume detaille.",
        "key_points": key_points,
        "question_answer": question_answer,
    }


def _build_fallback_summary(read_result: DOCXReadResult) -> str:
    paragraphs = read_result.paragraphs
    headings = read_result.heading_titles

    if headings and paragraphs:
        first_heading = headings[0]
        for paragraph in paragraphs:
            if paragraph != first_heading:
                return f"{first_heading} : {paragraph}"

    if paragraphs:
        return paragraphs[0]

    return read_result.extracted_text[:400].strip()


def _extract_key_points(read_result: DOCXReadResult) -> list[str]:
    key_points: list[str] = []

    for heading in read_result.heading_titles[:5]:
        if heading not in key_points:
            key_points.append(heading)

    bullet_lines = [
        re.sub(r"^([-*]|\d+[.)])\s+", "", line).strip()
        for line in read_result.extracted_text.replace("\r\n", "\n").split("\n")
        if re.match(r"^([-*]|\d+[.)])\s+", line.strip())
    ]
    for line in bullet_lines:
        if line and line not in key_points:
            key_points.append(line)
        if len(key_points) >= 5:
            return key_points[:5]

    sentences = re.split(r"(?<=[\.\!\?])\s+", " ".join(read_result.extracted_text.split()))
    for sentence in sentences:
        cleaned = sentence.strip()
        if cleaned and cleaned not in key_points:
            key_points.append(cleaned)
        if len(key_points) >= 5:
            break

    return key_points[:5]


def _extract_answer_from_text(user_message: str, text: str) -> str:
    normalized_message = _normalize_docx_analysis_text(user_message)
    if "?" not in user_message and not any(
        marker in normalized_message
        for marker in {"explique", "dis moi", "que dit", "que contient", "qu est ce qu il y a"}
    ):
        return ""

    keywords = [
        token
        for token in normalized_message.split()
        if len(token) > 2 and token not in DOCX_ANALYSIS_STOPWORDS
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
        normalized_sentence = _normalize_docx_analysis_text(sentence)
        score = sum(1 for keyword in keywords if keyword in normalized_sentence)
        if score > best_score:
            best_score = score
            best_sentence = sentence

    return best_sentence if best_score > 0 else ""


def _build_analysis_reply(
    summary: str,
    key_points: list[str],
    analysis_status: str,
    question_answer: str,
    paragraph_count: int,
    heading_titles: list[str],
) -> str:
    parts = [
        f"Statut d'analyse : {analysis_status}",
        f"Nombre de paragraphes : {paragraph_count}",
        "",
        "Resume :",
        summary.strip(),
    ]

    if heading_titles:
        parts.append("")
        parts.append("Titres reperes :")
        for item in heading_titles[:5]:
            parts.append(f"- {item}")

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
