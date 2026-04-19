import json
import os

from core.config import MEMORY_FILE, HISTORY_LIMIT


DEFAULT_MEMORY = {
    "history": [],
    "profile": {},
    "last_emotion": "unknown",
    "last_topic": "general",
}


def ensure_memory_file() -> None:
    """
    Crée le fichier mémoire si absent.
    """
    folder = os.path.dirname(MEMORY_FILE)

    if folder:
        os.makedirs(folder, exist_ok=True)

    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_MEMORY, f, ensure_ascii=False, indent=2)


def load_memory() -> dict:
    """
    Charge la mémoire depuis memory.json
    """
    ensure_memory_file()

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return DEFAULT_MEMORY.copy()

        data.setdefault("history", [])
        data.setdefault("profile", {})
        data.setdefault("last_emotion", "unknown")
        data.setdefault("last_topic", "general")

        return data

    except Exception:
        return DEFAULT_MEMORY.copy()


def save_memory(memory: dict) -> None:
    """
    Sauvegarde mémoire sur disque.
    """
    ensure_memory_file()

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def get_profile(memory: dict) -> dict:
    """
    Retourne le profil mémorisé.
    """
    profile = memory.get("profile", {})
    if isinstance(profile, dict):
        return profile
    return {}


def get_trusted_name(memory: dict) -> str:
    """
    Retourne le prénom utilisateur s'il existe.
    """
    profile = get_profile(memory)
    name = profile.get("name", "")

    if isinstance(name, str):
        return name.strip()

    return ""


def set_profile_name(memory: dict, name: str, source: str = "declared") -> None:
    """
    Enregistre un prénom utilisateur.
    """
    clean_name = (name or "").strip()

    if not clean_name:
        return

    profile = get_profile(memory)
    profile["name"] = clean_name
    profile["name_source"] = source
    memory["profile"] = profile


def clear_profile_name(memory: dict) -> None:
    """
    Supprime le prénom mémorisé.
    """
    profile = get_profile(memory)
    profile["name"] = ""
    profile["name_source"] = ""
    memory["profile"] = profile


def apply_identity_context(
    memory: dict,
    account_key: str = "",
    user_name: str = "",
) -> None:
    """
    Applique le contexte d'identité venant de l'application.
    """
    profile = get_profile(memory)

    clean_account_key = (account_key or "").strip()
    clean_user_name = (user_name or "").strip()

    if clean_account_key:
        profile["account_key"] = clean_account_key

    if clean_user_name:
        profile["app_user_name"] = clean_user_name

        # On peut l'utiliser comme prénom si aucun prénom fiable n'est encore mémorisé
        current_name = str(profile.get("name", "")).strip()
        if not current_name:
            profile["name"] = clean_user_name
            profile["name_source"] = "identity_context"

    memory["profile"] = profile


def add_message_to_history(
    memory: dict,
    user_message: str,
    zoe_reply: str,
    emotion: str,
    topic: str,
    precision: str,
    intent: str,
    timestamp: str,
) -> None:
    """
    Ajoute un échange à l'historique.
    """
    item = {
        "timestamp": timestamp,
        "user_message": user_message,
        "zoe_reply": zoe_reply,
        "emotion": emotion,
        "topic": topic,
        "precision": precision,
        "intent": intent,
    }

    history = memory.get("history", [])
    if not isinstance(history, list):
        history = []

    history.append(item)

    # limite mémoire courte
    history = history[-HISTORY_LIMIT:]

    memory["history"] = history
    memory["last_emotion"] = emotion
    memory["last_topic"] = topic


def update_profile_from_analysis(memory: dict, analysis: dict) -> None:
    """
    Met à jour un petit profil utilisateur.
    """
    profile = get_profile(memory)

    emotion = analysis.get("emotion", "unknown")
    topic = analysis.get("topic", "general")

    profile["last_detected_emotion"] = emotion
    profile["favorite_topic"] = topic

    # compteur émotion
    emotion_counter = profile.get("emotion_counter", {})
    if not isinstance(emotion_counter, dict):
        emotion_counter = {}

    emotion_counter[emotion] = emotion_counter.get(emotion, 0) + 1
    profile["emotion_counter"] = emotion_counter

    memory["profile"] = profile


def clear_memory() -> dict:
    """
    Réinitialise totalement la mémoire.
    """
    save_memory(DEFAULT_MEMORY.copy())
    return DEFAULT_MEMORY.copy()


def get_last_messages(memory: dict, limit: int = 5) -> list:
    """
    Retourne les derniers échanges.
    """
    history = memory.get("history", [])
    if not isinstance(history, list):
        return []
    return history[-limit:] 
