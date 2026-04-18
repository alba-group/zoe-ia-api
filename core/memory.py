import json
import os

from core.config import MEMORY_FILE, HISTORY_LIMIT


DEFAULT_MEMORY = {
    "history": [],
    "profile": {},
    "last_emotion": "unknown",
    "last_topic": "general"
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


def add_message_to_history(
    memory: dict,
    user_message: str,
    zoe_reply: str,
    emotion: str,
    topic: str,
    precision: str,
    intent: str,
    timestamp: str
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
        "intent": intent
    }

    history = memory.get("history", [])
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

    profile = memory.get("profile", {})

    emotion = analysis.get("emotion", "unknown")
    topic = analysis.get("topic", "general")

    profile["last_detected_emotion"] = emotion
    profile["favorite_topic"] = topic

    # compteur émotion
    emotion_counter = profile.get("emotion_counter", {})
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
    return history[-limit:]


def get_profile(memory: dict) -> dict:
    """
    Retourne le profil mémorisé.
    """
    return memory.get("profile", {})
