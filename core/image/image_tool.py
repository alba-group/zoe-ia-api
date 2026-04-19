import base64
import logging
import mimetypes
import tempfile
from pathlib import Path
from typing import Any

import requests

from core.analyzer import normalize_text
from core.config import IMAGE_MODEL_NAME, IMAGE_SIZE, OPENAI_API_KEY, OPENAI_TIMEOUT_SECONDS
from core.image.firebase_storage import upload_generated_image_bytes


logger = logging.getLogger("zoe.image")
OPENAI_IMAGE_GENERATIONS_URL = "https://api.openai.com/v1/images/generations"
OPENAI_IMAGE_EDITS_URL = "https://api.openai.com/v1/images/edits"


IMAGE_REQUEST_PATTERNS = (
    "genere moi une image de",
    "genere moi une image",
    "genere une image de",
    "genere une image",
    "cree une image de",
    "cree une image",
    "cree moi une image de",
    "cree moi une image",
    "fais une image de",
    "fais une image",
    "fais moi une image de",
    "fais moi une image",
    "dessine",
    "photo de",
    "illustration de",
    "image de",
    "portrait de",
    "affiche une image de",
    "visuel de",
    "imagine en image",
    "rendu de",
)

LOOSE_IMAGE_REQUEST_PREFIXES = (
    "fais moi ",
    "fais-moi ",
    "genere moi ",
    "genere-moi ",
    "cree moi ",
    "cree-moi ",
    "genere une ",
    "cree une ",
    "imagine ",
    "visualise ",
)

NON_VISUAL_CREATION_TERMS = {
    "script",
    "code",
    "fonction",
    "programme",
    "fichier",
    "liste",
    "note",
    "message",
    "sms",
    "mail",
    "quiz",
    "devinette",
    "jeu",
    "menu",
    "texte",
    "resume",
    "explication",
    "poeme",
    "idee",
    "reponse",
    "analyse",
    "paroles",
    "chanson",
    "musique",
    "rappel",
    "evenement",
    "rendez vous",
    "contact",
    "appel",
}

IMAGE_PROMPT_PREFIXES = (
    "de ",
    "d ",
    "du ",
    "des ",
    "une ",
    "un ",
)

IMAGE_EDIT_PATTERNS = (
    "modifie l image",
    "modifie cette image",
    "modifie la photo",
    "retouche l image",
    "retouche la photo",
    "change le fond",
    "change l arriere plan",
    "change l image",
    "mets la voiture en rouge",
    "mets le fond en",
    "change la couleur",
)

IMAGE_EDIT_VERBS = (
    "modifie",
    "retouche",
    "change",
    "mets",
    "remplace",
    "ajoute",
    "supprime",
    "transforme",
    "ameliore",
    "retire",
    "retravaille",
    "recolorie",
)

IMAGE_EDIT_OBJECTS = (
    "image",
    "photo",
    "fond",
    "decor",
    "arriere plan",
    "couleur",
    "voiture",
    "visage",
    "style",
)


def _build_error_result(reply: str, prompt: str | None = None) -> dict[str, Any]:
    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": "image",
        "intent": "clarify",
        "reply": reply,
        "image_url": "",
        "image_base64": None,
        "image_mime_type": None,
        "image_prompt": prompt,
    }


def _looks_like_loose_visual_request(text: str) -> bool:
    if any(pattern in text for pattern in IMAGE_REQUEST_PATTERNS):
        return True
    if not any(text.startswith(prefix) for prefix in LOOSE_IMAGE_REQUEST_PREFIXES):
        return False
    return not any(term in text for term in NON_VISUAL_CREATION_TERMS)


def should_use_image_tool(message: str) -> bool:
    text = normalize_text(message)
    if not text:
        return False
    return any(pattern in text for pattern in IMAGE_REQUEST_PATTERNS) or _looks_like_loose_visual_request(text)


def should_use_image_edit_tool(message: str, has_attached_image: bool) -> bool:
    text = normalize_text(message)
    if not has_attached_image or not text:
        return False
    if any(pattern in text for pattern in IMAGE_EDIT_PATTERNS):
        return True
    has_edit_verb = any(verb in text for verb in IMAGE_EDIT_VERBS)
    has_image_object = any(item in text for item in IMAGE_EDIT_OBJECTS)
    return has_edit_verb and (has_image_object or len(text.split()) <= 12)


def _strip_prompt_prefix(prompt: str) -> str:
    for prefix in IMAGE_PROMPT_PREFIXES:
        if prompt.startswith(prefix):
            return prompt[len(prefix):].strip()
    return prompt.strip()


def extract_image_prompt(message: str) -> str:
    normalized_message = normalize_text(message)
    for pattern in IMAGE_REQUEST_PATTERNS:
        if pattern in normalized_message:
            prompt = normalized_message.split(pattern, 1)[1].strip(" :,-")
            prompt = _strip_prompt_prefix(prompt)
            if prompt:
                return prompt
    for prefix in LOOSE_IMAGE_REQUEST_PREFIXES:
        if normalized_message.startswith(prefix):
            prompt = normalized_message[len(prefix):].strip(" :,-")
            prompt = _strip_prompt_prefix(prompt)
            if prompt:
                return prompt
    return normalized_message or "une image originale et soignee"


def extract_image_edit_prompt(message: str) -> str:
    prompt = normalize_text(message).strip(" :,-")
    return prompt or "modifie cette image proprement"


def _decode_image_bytes(image_base64: str | None, image_url: str | None) -> bytes:
    if image_base64:
        clean_base64 = image_base64.split(",", 1)[-1]
        return base64.b64decode(clean_base64)
    if image_url:
        response = requests.get(image_url, timeout=OPENAI_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.content
    raise ValueError("Aucune image exploitable recue.")


def _upload_and_build_result(
    image_bytes: bytes,
    prompt: str,
    user_uid: str | None,
    account_key: str | None,
    success_reply: str,
    intent: str,
    flow_label: str,
) -> dict[str, Any]:
    upload_result = upload_generated_image_bytes(
        image_bytes=image_bytes,
        user_uid=user_uid,
        account_key=account_key,
        prompt=prompt,
    )
    download_url = upload_result.get("download_url", "")
    if not download_url:
        raise ValueError("Firebase Storage n'a pas renvoye d'URL de telechargement.")

    logger.info(
        "%s upload firebase ok path=%s",
        flow_label,
        upload_result.get("storage_path", ""),
    )
    logger.info("%s download url ok has_url=%s", flow_label, bool(download_url))
    return {
        "emotion": "positive",
        "precision": "precise",
        "topic": "image",
        "intent": intent,
        "reply": success_reply,
        "image_url": download_url,
        "image_base64": None,
        "image_mime_type": "image/png",
        "image_prompt": prompt,
    }


def _openai_headers(*, json_request: bool) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    if json_request:
        headers["Content-Type"] = "application/json"
    return headers


def _extract_image_payload(
    payload: dict[str, Any],
    prompt: str,
    flow_label: str,
) -> tuple[bytes, str]:
    data_items = payload.get("data", [])
    logger.info("%s openai response ok items=%s", flow_label, len(data_items))
    if not data_items:
        raise ValueError("OpenAI n'a renvoye aucune image.")

    first = data_items[0] if isinstance(data_items[0], dict) else {}
    image_base64 = (
        first.get("b64_json")
        or first.get("image_base64")
        or first.get("result")
    )
    image_url = first.get("url") or first.get("image_url")
    revised_prompt = str(first.get("revised_prompt") or prompt).strip() or prompt

    logger.info(
        "%s openai payload ok has_b64=%s has_url=%s",
        flow_label,
        bool(image_base64),
        bool(image_url),
    )

    image_bytes = _decode_image_bytes(image_base64=image_base64, image_url=image_url)
    logger.info("%s image decoded ok bytes=%s", flow_label, len(image_bytes))
    return image_bytes, revised_prompt


def generate_image_reply(
    user_message: str,
    conversation: list[dict[str, str]] | None = None,
    user_uid: str | None = None,
    account_key: str | None = None,
) -> dict[str, Any]:
    del conversation
    prompt = extract_image_prompt(user_message)
    logger.info(
        "image-create requested prompt=%s uid_present=%s account_key_present=%s",
        prompt,
        bool((user_uid or "").strip()),
        bool((account_key or "").strip()),
    )

    if not OPENAI_API_KEY:
        return _build_error_result(
            reply="Je n'ai pas reussi a generer l'image pour le moment.",
            prompt=prompt,
        )

    if not (user_uid or "").strip() and not str(account_key or "").strip().startswith("user_"):
        logger.warning("image-create missing authenticated user identity")
        return _build_error_result(
            reply="Connecte-toi pour enregistrer et afficher cette image dans ton espace Zoe IA.",
            prompt=prompt,
        )

    try:
        payload_with_b64 = {
            "model": IMAGE_MODEL_NAME,
            "prompt": prompt,
            "size": IMAGE_SIZE,
            "response_format": "b64_json",
        }
        response = requests.post(
            OPENAI_IMAGE_GENERATIONS_URL,
            headers=_openai_headers(json_request=True),
            json=payload_with_b64,
            timeout=OPENAI_TIMEOUT_SECONDS,
        )

        if not response.ok and response.status_code == 400:
            logger.warning(
                "openai-image-create retry without response_format status=%s body=%s",
                response.status_code,
                response.text[:400],
            )
            response = requests.post(
                OPENAI_IMAGE_GENERATIONS_URL,
                headers=_openai_headers(json_request=True),
                json={
                    "model": IMAGE_MODEL_NAME,
                    "prompt": prompt,
                    "size": IMAGE_SIZE,
                },
                timeout=OPENAI_TIMEOUT_SECONDS,
            )

        response.raise_for_status()
        payload = response.json()
        image_bytes, revised_prompt = _extract_image_payload(
            payload=payload,
            prompt=prompt,
            flow_label="image-create",
        )
        return _upload_and_build_result(
            image_bytes=image_bytes,
            prompt=revised_prompt,
            user_uid=user_uid,
            account_key=account_key,
            success_reply="Image generee avec succes.",
            intent="create",
            flow_label="image-create",
        )
    except Exception as error:
        logger.exception("image-create failure: %s", error)
        return _build_error_result(
            reply="Je n'ai pas reussi a generer l'image pour le moment.",
            prompt=prompt,
        )


def _download_source_image(source_image_url: str, source_image_mime_type: str | None) -> tuple[Path, str]:
    response = requests.get(source_image_url, timeout=OPENAI_TIMEOUT_SECONDS)
    response.raise_for_status()
    content_type = (
        source_image_mime_type
        or response.headers.get("Content-Type", "").strip()
        or "image/jpeg"
    )
    if not content_type.startswith("image/"):
        content_type = "image/jpeg"
    extension = mimetypes.guess_extension(content_type) or ".jpg"
    if extension == ".jpe":
        extension = ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as file:
        file.write(response.content)
        path = Path(file.name)
    logger.info(
        "image-edit source downloaded content_type=%s bytes=%s file=%s",
        content_type,
        len(response.content),
        path.name,
    )
    return path, content_type


def edit_image_reply(
    user_message: str,
    source_image_url: str | None,
    source_image_mime_type: str | None = None,
    conversation: list[dict[str, str]] | None = None,
    user_uid: str | None = None,
    account_key: str | None = None,
) -> dict[str, Any]:
    del conversation
    prompt = extract_image_edit_prompt(user_message)
    logger.info(
        "image-edit requested source_image_provided=%s prompt=%s uid_present=%s account_key_present=%s",
        bool((source_image_url or "").strip()),
        prompt,
        bool((user_uid or "").strip()),
        bool((account_key or "").strip()),
    )

    if not OPENAI_API_KEY:
        return _build_error_result(
            reply="Je n'ai pas reussi a modifier l'image pour le moment.",
            prompt=prompt,
        )

    if not source_image_url:
        return _build_error_result(
            reply="Je n'ai pas recu d'image source exploitable pour faire la modification.",
            prompt=prompt,
        )

    if not (user_uid or "").strip() and not str(account_key or "").strip().startswith("user_"):
        logger.warning("image-edit missing authenticated user identity")
        return _build_error_result(
            reply="Connecte-toi pour enregistrer et afficher cette image dans ton espace Zoe IA.",
            prompt=prompt,
        )

    source_path: Path | None = None
    try:
        source_path, detected_mime_type = _download_source_image(
            source_image_url=source_image_url,
            source_image_mime_type=source_image_mime_type,
        )
        headers = _openai_headers(json_request=False)
        data = {
            "model": IMAGE_MODEL_NAME,
            "prompt": prompt,
            "size": IMAGE_SIZE,
        }
        with source_path.open("rb") as image_file:
            files = {
                "image": (source_path.name, image_file, detected_mime_type),
            }
            response = requests.post(
                OPENAI_IMAGE_EDITS_URL,
                headers=headers,
                data=data,
                files=files,
                timeout=OPENAI_TIMEOUT_SECONDS,
            )
        response.raise_for_status()
        payload = response.json()
        image_bytes, revised_prompt = _extract_image_payload(
            payload=payload,
            prompt=prompt,
            flow_label="image-edit",
        )
        return _upload_and_build_result(
            image_bytes=image_bytes,
            prompt=revised_prompt,
            user_uid=user_uid,
            account_key=account_key,
            success_reply="Image modifiee avec succes.",
            intent="edit",
            flow_label="image-edit",
        )

    except Exception as error:
        logger.exception("image-edit failure: %s", error)
        return _build_error_result(
            reply="Je n'ai pas reussi a modifier l'image pour le moment.",
            prompt=prompt,
        )
    finally:
        if source_path and source_path.exists():
            try:
                source_path.unlink()
            except OSError:
                logger.warning("temp-image-cleanup failed file=%s", source_path)
