import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


IMAGE_KEYWORDS = [
    "génère une image",
    "génère-moi une image",
    "crée une image",
    "dessine",
    "photo de",
    "illustration de",
    "image de",
]


def should_use_image_tool(message: str) -> bool:
    msg = message.lower().strip()

    for keyword in IMAGE_KEYWORDS:
        if keyword in msg:
            return True

    return False


def generate_image_reply(user_message: str, conversation=None) -> dict:
    try:
        prompt = user_message.strip()

        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )

        image_url = ""

        if hasattr(result, "data") and len(result.data) > 0:
            if hasattr(result.data[0], "url"):
                image_url = result.data[0].url

        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "image",
            "intent": "create",
            "reply": "Image générée avec succès.",
            "image_url": image_url
        }

    except Exception as e:
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "image",
            "intent": "clarify",
            "reply": "Je n'ai pas réussi à générer l'image pour le moment.",
            "image_url": ""
        } 
