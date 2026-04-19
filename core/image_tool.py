import os
import unicodedata
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


GENERATION_PHRASES = [
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
    "fais moi une image",
    "fais-moi une image",
    "fait moi une image",
    "fait-moi une image",
    "fais moi un visuel",
    "fait moi un visuel",
    "dessine",
    "dessine moi",
    "dessine-moi",
    "image de",
    "photo de",
    "illustration de",
    "visuel de",
]

EDIT_PHRASES = [
    "modifie cette image",
    "modifie l image",
    "modifie l'image",
    "modifie le fond",
    "modifier le fond",
    "change le fond",
    "changer le fond",
    "retire le fond",
    "retirer le fond",
    "supprime le fond",
    "supprimer le fond",
    "enleve le fond",
    "enlève le fond",
    "mets un autre fond",
    "mettre un autre fond",
    "retouche cette image",
    "retouche la photo",
    "ameliore cette image",
    "améliore cette image",
    "corrige cette image",
    "transforme cette image",
]

VISUAL_WORDS = {
    "image",
    "photo",
    "visuel",
    "illustration",
    "dessin",
    "logo",
    "portrait",
    "fond",
    "voiture",
    "pochette",
}

ACTION_WORDS = {
    "genere",
    "génère",
    "cree",
    "crée",
    "dessine",
    "fais",
    "fait",
    "fabrique",
    "modifie",
    "modifier",
    "change",
    "changer",
    "retouche",
    "transforme",
}


def _normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""

    text = text.strip().lower()
    text = text.replace("’", "'").replace("`", "'").replace("´", "'")
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = " ".join(text.split())
    return text


def should_use_image_tool(message: str) -> bool:
    msg = _normalize(message)
    if not msg:
        return False

    for phrase in GENERATION_PHRASES:
        if phrase in msg:
            return True

    for phrase in EDIT_PHRASES:
        if phrase in msg:
            return True

    tokens = set(msg.split())

    if (tokens & VISUAL_WORDS) and (tokens & ACTION_WORDS):
        return True

    # Cas fréquents libres
    if "voiture rouge" in msg and ("fais" in tokens or "fait" in tokens or "genere" in tokens or "génère" in tokens):
        return True

    return False


def generate_image_reply(user_message: str, conversation=None) -> dict:
    try:
        prompt = user_message.strip()
        normalized = _normalize(prompt)

        # Si c'est clairement une demande d'édition
        if any(p in normalized for p in EDIT_PHRASES):
            return {
                "emotion": "positive",
                "precision": "precise",
                "topic": "image",
                "intent": "edit",
                "reply": "Modification d’image demandée.",
                "image_url": "",
                "image_base64": "",
            }

        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
        )

        image_url = ""
        image_base64 = ""

        if hasattr(result, "data") and result.data:
            item = result.data[0]

            if hasattr(item, "url") and item.url:
                image_url = item.url

            if hasattr(item, "b64_json") and item.b64_json:
                image_base64 = item.b64_json
                image_url = f"data:image/png;base64,{image_base64}"

        if not image_url:
            return {
                "emotion": "unknown",
                "precision": "precise",
                "topic": "image",
                "intent": "clarify",
                "reply": "Je n'ai pas reçu d'image exploitable après la génération.",
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
