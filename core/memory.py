import json
import os

from core.config import MEMORY_FILE, HISTORY_LIMIT


DEFAULT_MEMORY = {
    "history": [],
    "profile": {},
    "last_emotion": "unknown",
    "last_topic": "general"
}


def _safe_default_memory() -> dict:
    return {
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
            json.dump(_safe_default_memory(), f, ensure_ascii=False, indent=2)


def _sanitize_memory(data: dict) -> dict:
    """
    Nettoie la structure mémoire pour éviter les valeurs invalides
    ou les profils partiellement cassés.
    """
    if not isinstance(data, dict):
        return _safe_default_memory()

    memory = _safe_default_memory()

    history = data.get("history", [])
    if isinstance(history, list):
        memory["history"] = history[-HISTORY_LIMIT:]

    profile = data.get("profile", {})
    if isinstance(profile, dict):
        clean_profile = dict(profile)

        # Nettoyage du champ name si présent
        name = clean_profile.get("name", "")
        if not isinstance(name, str):
            clean_profile["name"] = ""
        else:
            clean_profile["name"] = name.strip()

        # Nettoyage du champ emotion_counter
        emotion_counter = clean_profile.get("emotion_counter", {})
        if not isinstance(emotion_counter, dict):
            clean_profile["emotion_counter"] = {}
        else:
            clean_profile["emotion_counter"] = emotion_counter

        memory["profile"] = clean_profile

    last_emotion = data.get("last_emotion", "unknown")
    if isinstance(last_emotion, str) and last_emotion.strip():
        memory["last_emotion"] = last_emotion.strip()

    last_topic = data.get("last_topic", "general")
    if isinstance(last_topic, str) and last_topic.strip():
        memory["last_topic"] = last_topic.strip()

    return memory


def load_memory() -> dict:
    """
    Charge la mémoire depuis memory.json
    """
    ensure_memory_file()

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        return _sanitize_memory(data)

    except Exception:
        return _safe_default_memory()


def save_memory(memory: dict) -> None:
    """
    Sauvegarde mémoire sur disque.
    """
    ensure_memory_file()
    clean_memory = _sanitize_memory(memory)

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(clean_memory, f, ensure_ascii=False, indent=2)


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
    if not isinstance(history, list):
        history = []

    history.append(item)
    history = history[-HISTORY_LIMIT:]

    memory["history"] = history
    memory["last_emotion"] = emotion
    memory["last_topic"] = topic


def update_profile_from_analysis(memory: dict, analysis: dict) -> None:
    """
    Met à jour un petit profil utilisateur.
    """
    profile = memory.get("profile", {})
    if not isinstance(profile, dict):
        profile = {}

    emotion = analysis.get("emotion", "unknown")
    topic = analysis.get("topic", "general")

    profile["last_detected_emotion"] = emotion
    profile["favorite_topic"] = topic

    emotion_counter = profile.get("emotion_counter", {})
    if not isinstance(emotion_counter, dict):
        emotion_counter = {}

    emotion_counter[emotion] = emotion_counter.get(emotion, 0) + 1
    profile["emotion_counter"] = emotion_counter

    # Nettoyage du prénom si jamais il existe
    if "name" in profile and isinstance(profile["name"], str):
        profile["name"] = profile["name"].strip()

    memory["profile"] = profile


def clear_memory() -> dict:
    """
    Réinitialise totalement la mémoire.
    """
    clean = _safe_default_memory()
    save_memory(clean)
    return clean


def get_last_messages(memory: dict, limit: int = 5) -> list:
    """
    Retourne les derniers échanges.
    """
    history = memory.get("history", [])
    if not isinstance(history, list):
        return []
    return history[-limit:]


def get_profile(memory: dict) -> dict:
    """
    Retourne le profil mémorisé.
    """
    profile = memory.get("profile", {})
    if not isinstance(profile, dict):
        return {}
    return profile 
