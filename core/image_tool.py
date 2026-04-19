import os
import base64
import unicodedata
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


IMAGE_GENERATION_KEYWORDS = [
    "genere une image",
    "génère une image",
    "genere moi une image",
    "génère moi une image",
    "genere-moi une image",
    "génère-moi une image",
    "cree une image",
    "crée une image",
    "cree moi une image",
    "crée moi une image",
    "dessine",
    "dessine moi",
    "dessine-moi",
    "photo de",
    "illustration de",
    "image de",
    "visuel de",
    "fais moi une image",
    "fais-moi une image",
    "fais moi un visuel",
    "fais-moi un visuel",
    "fais moi une voiture",
    "fais-moi une voiture",
    "fais moi une voiture rouge",
    "fais-moi une voiture rouge",
    "cree un logo",
    "crée un logo",
    "fais moi un logo",
    "fais-moi un logo",
]

IMAGE_EDIT_KEYWORDS = [
    "modifie cette image",
    "modifie l image",
    "modifie l'image",
    "modifie la photo",
    "retouche cette image",
    "retouche la photo",
    "edite cette image",
    "édite cette image",
    "ameliore cette image",
    "améliore cette image",
    "corrige cette image",
    "transforme cette image",
    "change le fond",
    "change l arriere plan",
    "change l arrière plan",
    "enleve le fond",
    "enlève le fond",
    "supprime le fond",
]

VISUAL_OBJECT_WORDS = {
    "image",
    "photo",
    "visuel",
    "illustration",
    "dessin",
    "logo",
    "affiche",
    "portrait",
    "voiture",
    "pochette",
}

VISUAL_ACTION_WORDS = {
    "genere",
    "génère",
    "cree",
    "crée",
    "dessine",
    "fais",
    "fabrique",
    "montre",
    "imagine",
}


def _normalize_text(text: str) -> str:
    if not isinstance(text, str):
        return ""

    cleaned = text.strip().lower()
    cleaned = cleaned.replace("’", "'")
    cleaned = cleaned.replace("`", "'")
    cleaned = cleaned.replace("´", "'")

    cleaned = unicodedata.normalize("NFD", cleaned)
    cleaned = "".join(ch for ch in cleaned if unicodedata.category(ch) != "Mn")
    cleaned = " ".join(cleaned.split())
    return cleaned


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _looks_like_generation_request(msg: str) -> bool:
    if _contains_any(msg, IMAGE_GENERATION_KEYWORDS):
        return True

    tokens = set(msg.split())

    if (tokens & VISUAL_OBJECT_WORDS) and (tokens & VISUAL_ACTION_WORDS):
        return True

    return False


def _looks_like_edit_request(msg: str) -> bool:
    return _contains_any(msg, IMAGE_EDIT_KEYWORDS)


def should_use_image_tool(message: str) -> bool:
    msg = _normalize_text(message)

    if not msg:
        return False

    if _looks_like_edit_request(msg):
        return True

    if _looks_like_generation_request(msg):
        return True

    return False


def _extract_image_payload(result) -> tuple[str, str]:
    """
    Retourne :
    - image_url_or_data_url
    - raw_base64
    """
    image_url = ""
    image_base64 = ""

    if not hasattr(result, "data") or not result.data:
        return image_url, image_base64

    first = result.data[0]

    # Cas URL directe
    if hasattr(first, "url") and first.url:
        image_url = first.url

    # Cas base64 (fréquent avec gpt-image-1)
    if hasattr(first, "b64_json") and first.b64_json:
        image_base64 = first.b64_json
        image_url = f"data:image/png;base64,{image_base64}"

    return image_url, image_base64


def generate_image_reply(user_message: str, conversation=None) -> dict:
    try:
        prompt = user_message.strip()
        normalized = _normalize_text(prompt)

        # Cas modification d'image :
        # ce fichier ne reçoit pas encore l'image jointe réellement.
        # Donc on renvoie une réponse claire plutôt qu'une fausse réussite.
        if _looks_like_edit_request(normalized):
            return {
                "emotion": "unknown",
                "precision": "precise",
                "topic": "image",
                "intent": "edit",
                "reply": "J’ai besoin de l’image à modifier pour faire cette retouche.",
                "image_url": "",
                "image_base64": "",
            }

        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
        )

        image_url, image_base64 = _extract_image_payload(result)

        if not image_url and not image_base64:
            return {
                "emotion": "unknown",
                "precision": "precise",
                "topic": "image",
                "intent": "clarify",
                "reply": "L’image a été demandée, mais je n’ai pas reçu de résultat exploitable.",
                "image_url": "",
                "image_base64": "",
            }

        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "image",
            "intent": "create",
            "reply": "Image générée avec succès.",
            "image_url": image_url,
            "image_base64": image_base64,
        }

    except Exception as e:
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "image",
            "intent": "clarify",
            "reply": f"Je n'ai pas réussi à générer l'image pour le moment : {str(e)}",
            "image_url": "",
            "image_base64": "",
        } 
