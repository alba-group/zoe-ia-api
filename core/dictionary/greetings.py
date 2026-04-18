# Salutations et formulations d'accueil pour Zoe IA

GREETING_WORDS = {
    "salut",
    "bonjour",
    "bonsoir",
    "coucou",
    "hello",
    "hey",
    "yo",
    "slt",
    "bjr",
    "re",
    "rebonjour",
    "rebonjour",
}

GREETING_PHRASES = {
    "salut zoe",
    "bonjour zoe",
    "bonsoir zoe",
    "coucou zoe",
    "hello zoe",
    "hey zoe",
    "yo zoe",
    "re zoe",
}

POLITE_GREETINGS = {
    "bonjour à toi",
    "salut à toi",
    "bonsoir à toi",
}

ALL_GREETINGS = GREETING_WORDS | GREETING_PHRASES | POLITE_GREETINGS


def is_greeting(text: str) -> bool:
    """
    Vérifie si le texte ressemble à une salutation simple.
    """
    if not isinstance(text, str):
        return False

    cleaned = text.strip().lower()
    return cleaned in ALL_GREETINGS


def build_greeting_reply(user_name: str = "", last_emotion: str = "unknown", last_topic: str = "general") -> str:
    """
    Construit une réponse de salutation naturelle.
    """
    safe_name = user_name.strip() if isinstance(user_name, str) else ""

    if safe_name and last_emotion in {"negative", "stress", "fatigue", "sadness"}:
        return f"Salut {safe_name}. Je suis contente de te revoir. Ça va un peu mieux aujourd'hui ?"

    if safe_name and last_topic not in {"general", "identity", "memory"}:
        return f"Salut {safe_name}. Je suis contente de te revoir. Tu veux qu'on reprenne là où on s'était arrêtés ?"

    if safe_name:
        return f"Salut {safe_name}. Je suis contente de te revoir."

    return "Salut. Je suis contente de te revoir." 
