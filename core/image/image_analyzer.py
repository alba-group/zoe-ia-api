import logging
from typing import Any

from core.analyzer import normalize_text
from core.llm_client import build_zoe_system_prompt, create_llm_client


logger = logging.getLogger("zoe.image.analyzer")

IMAGE_ANALYSIS_PATTERNS = (
    "analyse la photo",
    "analyse cette photo",
    "analyse la capture",
    "analyse l image",
    "analyse cette image",
    "decris la photo",
    "decris cette photo",
    "decris l image",
    "decris cette image",
    "decris moi cette image",
    "qu est ce qu il y a sur cette photo",
    "qu est ce qu il y a sur la photo",
    "qu est ce qu il y a sur cette image",
    "qu est ce qu il y a sur l image",
    "que vois tu sur cette photo",
    "que vois tu sur cette image",
    "que contient cette image",
    "que contient cette photo",
    "lis ce qu il y a sur l image",
    "lis ce qu il y a sur la photo",
    "lis ce qui est ecrit sur l image",
    "lis le texte de l image",
    "lis le texte sur l image",
    "lis le texte sur la photo",
    "explique moi cette photo",
    "explique moi cette image",
    "explique cette photo",
    "explique cette image",
)

IMAGE_ANALYSIS_VERBS = (
    "analyse",
    "decris",
    "explique",
    "lis",
    "identifie",
    "reconnait",
    "que vois tu",
    "qu est ce qu il y a",
    "que contient",
)

IMAGE_ANALYSIS_OBJECTS = (
    "image",
    "photo",
    "capture",
    "dessus",
    "dedans",
    "ecrit",
    "texte",
)

SHORT_IMAGE_ANALYSIS_REQUESTS = {
    "analyse",
    "analyse l image",
    "analyse la photo",
    "analyse cette image",
    "analyse cette photo",
    "decris",
    "decris l image",
    "decris la photo",
    "decris cette image",
    "decris cette photo",
    "explique",
    "explique cette image",
    "explique cette photo",
    "lis l image",
    "lis la photo",
    "lis le texte",
}


def _normalize_image_analysis_text(message: str) -> str:
    text = normalize_text(message).replace("'", " ")
    return " ".join(text.split()).strip()


def should_use_image_analysis_tool(message: str, has_attached_image: bool) -> bool:
    text = _normalize_image_analysis_text(message)
    if not has_attached_image or not text:
        return False

    if text in SHORT_IMAGE_ANALYSIS_REQUESTS:
        return True

    if any(pattern in text for pattern in IMAGE_ANALYSIS_PATTERNS):
        return True

    has_analysis_verb = any(verb in text for verb in IMAGE_ANALYSIS_VERBS)
    has_image_object = any(item in text for item in IMAGE_ANALYSIS_OBJECTS)

    return has_analysis_verb and (has_image_object or len(text.split()) <= 6)


def _build_error_result(reply: str, intent: str = "clarify") -> dict[str, Any]:
    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": "image",
        "intent": intent,
        "reply": reply,
    }


def _build_image_analysis_system_prompt() -> str:
    return (
        build_zoe_system_prompt()
        + " Tu peux analyser une image envoyee par l'utilisateur."
        + " Decris seulement ce qui est visible et n'invente pas les details."
        + " Si du texte est present et lisible, recopie-le fidelement."
        + " Si un element est incertain, dis-le clairement."
        + " Adapte la reponse a la demande reelle de l'utilisateur : description, explication visuelle ou lecture du texte."
        + " Reponds en francais naturel, clairement et sans JSON."
    )


def _map_analysis_error(error: str | None) -> dict[str, Any]:
    normalized_error = normalize_text(error or "")

    if not normalized_error:
        return _build_error_result("Je n'ai pas reussi a analyser l'image pour le moment.")

    if "aucune image exploitable" in normalized_error or "aucune image" in normalized_error:
        return _build_error_result("Je n'ai pas recu d'image exploitable pour l'analyse.")

    if any(
        marker in normalized_error
        for marker in {
            "format d image invalide",
            "image_base64 vide",
            "invalid image",
            "invalid value",
            "unsupported image",
            "base64",
        }
    ):
        return _build_error_result("L'image jointe semble invalide ou non prise en charge.")

    if any(
        marker in normalized_error
        for marker in {
            "timeout",
            "timed out",
            "deadline exceeded",
            "504",
        }
    ):
        return _build_error_result("L'analyse de l'image a pris trop de temps. Reessaie dans un instant.")

    return _build_error_result("Je n'ai pas reussi a analyser l'image pour le moment.")


def analyze_image_reply(
    user_message: str,
    image_url: str | None = None,
    image_base64: str | None = None,
    image_mime_type: str | None = None,
    conversation: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    if not (image_url or "").strip() and not (image_base64 or "").strip():
        return _build_error_result("Je n'ai pas recu d'image exploitable pour l'analyse.")

    try:
        client = create_llm_client()
        result = client.analyze_image(
            user_message=user_message,
            image_url=image_url,
            image_base64=image_base64,
            image_mime_type=image_mime_type,
            system_prompt=_build_image_analysis_system_prompt(),
            conversation=conversation,
            temperature=0.2,
        )

        if result.error:
            logger.warning("image-analysis llm error=%s", result.error)
            return _map_analysis_error(result.error)

        reply = result.text.strip()
        if not reply:
            return _build_error_result("Je n'ai pas reussi a analyser l'image pour le moment.")

        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "image",
            "intent": "reflect",
            "reply": reply,
        }

    except Exception as error:
        logger.exception("image-analysis failure: %s", error)
        return _map_analysis_error(str(error))
