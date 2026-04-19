import base64
import re
import uuid
from typing import Optional


IMAGE_CREATE_KEYWORDS = [
    "génère une image",
    "génère-moi une image",
    "genere une image",
    "genere-moi une image",
    "crée une image",
    "cree une image",
    "dessine",
    "fais-moi une image",
    "fais moi une image",
    "fait moi une image",
    "image de",
    "photo de",
    "illustration de",
]

IMAGE_EDIT_KEYWORDS = [
    "modifie cette image",
    "modifier l'image",
    "modifier cette image",
    "change le fond",
    "modifie le fond",
    "retouche cette image",
    "améliore cette image",
    "ameliore cette image",
]


def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return " ".join(text.lower().strip().split())


def should_create_image(message: str) -> bool:
    msg = normalize_text(message)
    return any(keyword in msg for keyword in IMAGE_CREATE_KEYWORDS)


def should_edit_image(message: str) -> bool:
    msg = normalize_text(message)
    return any(keyword in msg for keyword in IMAGE_EDIT_KEYWORDS)


def should_handle_image(message: str) -> bool:
    return should_create_image(message) or should_edit_image(message)


def decode_base64_image(image_base64: str) -> bytes:
    if not image_base64:
        raise ValueError("image_base64 vide")

    try:
        return base64.b64decode(image_base64)
    except Exception as exc:
        raise ValueError(f"Impossible de décoder le base64 image : {exc}") from exc


def safe_filename_from_prompt(prompt: str, prefix: str = "zoe_image") -> str:
    raw = (prompt or "").strip().lower()
    raw = re.sub(r"[^a-zA-Z0-9àâäéèêëîïôöùûüç\-_\s]", "", raw)
    raw = re.sub(r"\s+", "_", raw).strip("_")

    if not raw:
        raw = prefix

    raw = raw[:40]
    return f"{raw}_{uuid.uuid4().hex[:12]}.png"


def content_type_for_png() -> str:
    return "image/png"


def build_image_prompt(user_message: str, conversation=None) -> str:
    prompt = (user_message or "").strip()

    if not prompt:
        raise ValueError("Prompt image vide")

    return prompt


def build_edit_prompt(user_message: str, conversation=None) -> str:
    prompt = (user_message or "").strip()

    if not prompt:
        raise ValueError("Prompt modification vide")

    return prompt


def extract_first_non_empty_text(*values: Optional[str]) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "" 