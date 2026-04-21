import json
import os
from copy import deepcopy
from datetime import datetime
from typing import Any

from core.config import HISTORY_LIMIT, MEMORY_FILE
from core.skills.skill_registry import get_default_skill_flags


DEFAULT_PROFILE = {
    "name": "",
    "city": "",
    "job": "",
    "likes": [],
    "dislikes": [],
    "projects": [],
    "goals": [],
    "important_people": [],
    "habits": [],
    "preferred_tone": "",
    "last_update": "",
}

DEFAULT_SESSION_CONTEXT = {
    "mood": "",
    "energy": "",
    "current_topic": "",
}

PROFILE_TEXT_FIELDS = {
    "name",
    "name_source",
    "app_user_name",
    "city",
    "job",
    "preferred_tone",
    "last_update",
}

PROFILE_LIST_FIELDS = {
    "likes",
    "dislikes",
    "projects",
    "goals",
    "important_people",
    "habits",
}

DEFAULT_MEMORY = {
    "history": [],
    "profile": deepcopy(DEFAULT_PROFILE),
    "last_emotion": "unknown",
    "last_topic": "general",
    "preferences": {},
    "skills_enabled": get_default_skill_flags(),
    "known_locations": [],
    "trusted_facts": {},
    "session_context": deepcopy(DEFAULT_SESSION_CONTEXT),
    "long_term_memory": [],
}


def ensure_memory_file() -> None:
    """
    Cree le fichier memoire si absent.
    """
    folder = os.path.dirname(MEMORY_FILE)

    if folder:
        os.makedirs(folder, exist_ok=True)

    if not os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(_build_default_memory(), f, ensure_ascii=False, indent=2)


def load_memory() -> dict:
    """
    Charge la memoire depuis memory.json
    """
    ensure_memory_file()

    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            return _build_default_memory()

        return _normalize_memory_payload(data)

    except Exception:
        return _build_default_memory()


def save_memory(memory: dict) -> None:
    """
    Sauvegarde memoire sur disque.
    """
    ensure_memory_file()
    normalized_memory = _normalize_memory_payload(memory if isinstance(memory, dict) else {})

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized_memory, f, ensure_ascii=False, indent=2)


def get_profile(memory: dict) -> dict:
    """
    Retourne le profil memorise.
    """
    profile = _normalize_profile(memory.get("profile"))
    memory["profile"] = profile
    return profile


def get_profile_snapshot(memory: dict) -> dict[str, Any]:
    """
    Retourne une vue nettoyee du profil utile pour les reponses.
    """
    profile = get_profile(memory)
    snapshot = deepcopy(DEFAULT_PROFILE)

    for field in DEFAULT_PROFILE:
        value = profile.get(field, deepcopy(DEFAULT_PROFILE[field]))

        if field in PROFILE_LIST_FIELDS:
            if isinstance(value, str):
                value = [value]
            elif not isinstance(value, list):
                value = []

            snapshot[field] = [
                _normalize_profile_text(item)
                for item in value
                if _normalize_profile_text(item)
            ][-20:]
            continue

        snapshot[field] = _normalize_profile_text(value)

    return snapshot


def get_preferences(memory: dict) -> dict:
    preferences = memory.get("preferences", {})
    if not isinstance(preferences, dict):
        preferences = {}
        memory["preferences"] = preferences
    return preferences


def get_skills_enabled(memory: dict) -> dict:
    skills_enabled = _normalize_skill_flags(memory.get("skills_enabled"))
    memory["skills_enabled"] = skills_enabled
    return skills_enabled


def get_session_context(memory: dict) -> dict:
    session_context = _normalize_session_context(memory.get("session_context"))
    memory["session_context"] = session_context
    return session_context


def set_session_value(memory: dict, key: str, value: Any) -> None:
    clean_key = (key or "").strip()
    if not clean_key:
        return

    session_context = get_session_context(memory)
    session_context[clean_key] = value
    memory["session_context"] = session_context


def add_trusted_fact(memory: dict, key: str, value: Any) -> None:
    clean_key = (key or "").strip()
    if not clean_key:
        return

    trusted_facts = memory.get("trusted_facts", {})
    if not isinstance(trusted_facts, dict):
        trusted_facts = {}

    trusted_facts[clean_key] = value
    memory["trusted_facts"] = trusted_facts


def get_trusted_fact(memory: dict, key: str, default: Any = None) -> Any:
    trusted_facts = memory.get("trusted_facts", {})
    if not isinstance(trusted_facts, dict):
        trusted_facts = {}
        memory["trusted_facts"] = trusted_facts

    clean_key = (key or "").strip()
    if not clean_key:
        return default

    return trusted_facts.get(clean_key, default)


def get_trusted_name(memory: dict) -> str:
    """
    Retourne le nom fiable memorise.
    Priorite au nom principal, puis au nom venant de l'application.
    """
    profile = get_profile(memory)

    name = profile.get("name", "")
    if isinstance(name, str) and name.strip():
        return name.strip()

    app_user_name = profile.get("app_user_name", "")
    if isinstance(app_user_name, str) and app_user_name.strip():
        return app_user_name.strip()

    return ""


def set_profile_name(memory: dict, name: str, source: str = "declared") -> None:
    """
    Enregistre un nom fiable dans le profil.
    """
    clean_name = (name or "").strip()
    if not clean_name:
        return

    profile = get_profile(memory)
    profile["name"] = clean_name
    profile["name_source"] = source
    profile["app_user_name"] = clean_name
    _mark_profile_updated(profile)
    memory["profile"] = profile
    add_trusted_fact(memory, "declared_name", clean_name)


def set_profile_city(memory: dict, city: str) -> None:
    clean_city = _normalize_profile_text(city)
    if not clean_city:
        return

    profile = get_profile(memory)
    profile["city"] = clean_city
    _mark_profile_updated(profile)
    memory["profile"] = profile
    add_trusted_fact(memory, "profile_city", clean_city)


def set_profile_job(memory: dict, job: str) -> None:
    clean_job = _normalize_profile_text(job)
    if not clean_job:
        return

    profile = get_profile(memory)
    profile["job"] = clean_job
    _mark_profile_updated(profile)
    memory["profile"] = profile
    add_trusted_fact(memory, "profile_job", clean_job)


def add_profile_like(memory: dict, like: str) -> None:
    add_profile_list_item(memory, "likes", like)
    profile = get_profile(memory)
    add_trusted_fact(memory, "profile_likes", profile.get("likes", []))


def add_profile_dislike(memory: dict, dislike: str) -> None:
    add_profile_list_item(memory, "dislikes", dislike)
    profile = get_profile(memory)
    add_trusted_fact(memory, "profile_dislikes", profile.get("dislikes", []))


def add_profile_project(memory: dict, project: str) -> None:
    add_profile_list_item(memory, "projects", project)


def add_profile_goal(memory: dict, goal: str) -> None:
    add_profile_list_item(memory, "goals", goal)


def add_profile_person(memory: dict, person_name: str) -> None:
    add_profile_list_item(memory, "important_people", person_name)


def add_profile_habit(memory: dict, habit: str) -> None:
    add_profile_list_item(memory, "habits", habit)


def set_preferred_tone(memory: dict, tone: str) -> None:
    clean_tone = _normalize_profile_text(tone)
    if not clean_tone:
        return

    profile = get_profile(memory)
    profile["preferred_tone"] = clean_tone
    _mark_profile_updated(profile)
    memory["profile"] = profile
    add_trusted_fact(memory, "preferred_tone", clean_tone)


def add_profile_list_item(memory: dict, field_name: str, value: str) -> None:
    if field_name not in PROFILE_LIST_FIELDS:
        return

    clean_value = _normalize_profile_text(value)
    if not clean_value:
        return

    profile = get_profile(memory)
    items = profile.get(field_name, [])

    if isinstance(items, str):
        items = [items.strip()] if items.strip() else []
    elif not isinstance(items, list):
        items = []

    normalized_value = clean_value.casefold()
    already_present = any(
        isinstance(item, str) and item.strip().casefold() == normalized_value
        for item in items
    )
    if not already_present:
        items.append(clean_value)

    profile[field_name] = [str(item).strip() for item in items if str(item).strip()][-20:]
    _mark_profile_updated(profile)
    memory["profile"] = profile


def clear_profile_name(memory: dict) -> None:
    """
    Supprime le nom memorise.
    """
    profile = get_profile(memory)
    profile["name"] = ""
    profile["name_source"] = ""
    profile["app_user_name"] = ""
    _mark_profile_updated(profile)
    memory["profile"] = profile


def forget_profile_field(memory: dict, field_name: str) -> bool:
    profile = get_profile(memory)

    if field_name == "name":
        clear_profile_name(memory)
        return True

    if field_name in PROFILE_LIST_FIELDS:
        profile[field_name] = []
    elif field_name in DEFAULT_PROFILE:
        profile[field_name] = deepcopy(DEFAULT_PROFILE[field_name])
    else:
        return False

    _mark_profile_updated(profile)
    memory["profile"] = profile
    return True


def apply_identity_context(
    memory: dict,
    account_key: str = "",
    user_name: str = "",
) -> None:
    """
    Applique le contexte d'identite venant de l'application.
    Le nom venant de l'app devient aussi le nom principal pour eviter
    les incoherences entre l'interface et les reponses de Zoe.
    """
    profile = get_profile(memory)

    clean_account_key = (account_key or "").strip()
    clean_user_name = (user_name or "").strip()

    if clean_account_key:
        profile["account_key"] = clean_account_key
        add_trusted_fact(memory, "account_key", clean_account_key)
        set_session_value(memory, "active_account_key", clean_account_key)

    if clean_user_name:
        profile["app_user_name"] = clean_user_name
        profile["name"] = clean_user_name
        profile["name_source"] = "identity_context"
        add_trusted_fact(memory, "app_user_name", clean_user_name)
        _mark_profile_updated(profile)

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
    Ajoute un echange a l'historique.
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
    history = history[-HISTORY_LIMIT:]

    memory["history"] = history
    memory["last_emotion"] = emotion
    memory["last_topic"] = topic


def update_profile_from_analysis(memory: dict, analysis: dict) -> None:
    """
    Met a jour un petit profil utilisateur.
    """
    profile = get_profile(memory)

    emotion = analysis.get("emotion", "unknown")
    topic = analysis.get("topic", "general")

    profile["last_detected_emotion"] = emotion
    profile["favorite_topic"] = topic

    emotion_counter = profile.get("emotion_counter", {})
    if not isinstance(emotion_counter, dict):
        emotion_counter = {}

    emotion_counter[emotion] = emotion_counter.get(emotion, 0) + 1
    profile["emotion_counter"] = emotion_counter

    memory["profile"] = profile
    update_session_context_from_analysis(memory, analysis)


def update_session_context_from_analysis(memory: dict, analysis: dict) -> None:
    session_context = get_session_context(memory)
    emotion = str(analysis.get("emotion", "unknown")).strip().lower()
    topic = str(analysis.get("topic", "general")).strip().lower()

    mood = ""
    energy = ""

    if emotion in {"negative", "sadness"}:
        mood = "sad"
        energy = "low"
    elif emotion == "stress":
        mood = "stressed"
        energy = "tense"
    elif emotion == "fatigue":
        mood = "tired"
        energy = "low"
    elif emotion == "anger":
        mood = "angry"
        energy = "high"
    elif emotion in {"positive", "joy"}:
        mood = "positive"
        energy = "high"

    if mood:
        session_context["mood"] = mood
    if energy:
        session_context["energy"] = energy
    if topic and topic != "general":
        session_context["current_topic"] = topic

    memory["session_context"] = session_context


def clear_memory(preserve_profile: bool = False) -> dict:
    """
    Reinitialise totalement la memoire.
    Si preserve_profile=True, conserve les informations durables.
    """
    current_memory = load_memory()

    fresh_memory = _build_default_memory()

    if preserve_profile:
        preserved_profile = current_memory.get("profile", {})
        preserved_preferences = current_memory.get("preferences", {})
        preserved_skills = current_memory.get("skills_enabled", {})
        preserved_locations = current_memory.get("known_locations", [])
        preserved_facts = current_memory.get("trusted_facts", {})
        preserved_long_term_memory = current_memory.get("long_term_memory", [])

        fresh_memory["profile"] = preserved_profile if isinstance(preserved_profile, dict) else {}
        fresh_memory["preferences"] = preserved_preferences if isinstance(preserved_preferences, dict) else {}
        fresh_memory["skills_enabled"] = _normalize_skill_flags(preserved_skills)
        fresh_memory["known_locations"] = preserved_locations if isinstance(preserved_locations, list) else []
        fresh_memory["trusted_facts"] = preserved_facts if isinstance(preserved_facts, dict) else {}
        fresh_memory["long_term_memory"] = (
            preserved_long_term_memory if isinstance(preserved_long_term_memory, list) else []
        )

        context_value = current_memory.get("context")
        if isinstance(context_value, dict):
            fresh_memory["context"] = context_value

    save_memory(fresh_memory)
    return fresh_memory


def get_last_messages(memory: dict, limit: int = 5) -> list:
    """
    Retourne les derniers echanges.
    """
    history = memory.get("history", [])
    if not isinstance(history, list):
        return []
    return history[-limit:]


def get_memory_stats(memory: dict) -> dict:
    """
    Retourne quelques statistiques simples sur la memoire.
    """
    history = memory.get("history", [])
    profile = memory.get("profile", {})
    trusted_facts = memory.get("trusted_facts", {})

    return {
        "history_count": len(history) if isinstance(history, list) else 0,
        "profile_keys": list(profile.keys()) if isinstance(profile, dict) else [],
        "last_emotion": memory.get("last_emotion", "unknown"),
        "last_topic": memory.get("last_topic", "general"),
        "has_context": isinstance(memory.get("context"), dict),
        "has_preferences": isinstance(memory.get("preferences"), dict),
        "trusted_facts_count": len(trusted_facts) if isinstance(trusted_facts, dict) else 0,
    }


def _build_default_memory() -> dict[str, Any]:
    return {
        "history": [],
        "profile": deepcopy(DEFAULT_PROFILE),
        "last_emotion": "unknown",
        "last_topic": "general",
        "preferences": {},
        "skills_enabled": get_default_skill_flags(),
        "known_locations": [],
        "trusted_facts": {},
        "session_context": deepcopy(DEFAULT_SESSION_CONTEXT),
        "long_term_memory": [],
    }


def _normalize_memory_payload(data: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(data)

    normalized["history"] = data.get("history", []) if isinstance(data.get("history"), list) else []
    normalized["profile"] = _normalize_profile(data.get("profile"))
    normalized["last_emotion"] = _normalize_string(data.get("last_emotion"), "unknown")
    normalized["last_topic"] = _normalize_string(data.get("last_topic"), "general")
    normalized["preferences"] = data.get("preferences", {}) if isinstance(data.get("preferences"), dict) else {}
    normalized["skills_enabled"] = _normalize_skill_flags(data.get("skills_enabled"))
    normalized["known_locations"] = data.get("known_locations", []) if isinstance(data.get("known_locations"), list) else []
    normalized["trusted_facts"] = data.get("trusted_facts", {}) if isinstance(data.get("trusted_facts"), dict) else {}
    normalized["session_context"] = _normalize_session_context(data.get("session_context"))
    normalized["long_term_memory"] = data.get("long_term_memory", []) if isinstance(data.get("long_term_memory"), list) else []

    context_value = data.get("context")
    if isinstance(context_value, dict):
        normalized["context"] = context_value

    return normalized


def _normalize_string(value: Any, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback

    cleaned = value.strip()
    return cleaned or fallback


def _normalize_skill_flags(raw_value: Any) -> dict[str, bool]:
    normalized = deepcopy(get_default_skill_flags())
    if not isinstance(raw_value, dict):
        return normalized

    for skill_name, skill_value in raw_value.items():
        clean_name = str(skill_name or "").strip()
        if not clean_name:
            continue
        normalized[clean_name] = _coerce_bool(skill_value, normalized.get(clean_name, True))

    return normalized


def _normalize_profile(raw_value: Any) -> dict[str, Any]:
    profile = deepcopy(DEFAULT_PROFILE)
    if not isinstance(raw_value, dict):
        return profile

    profile.update(raw_value)

    for field in PROFILE_TEXT_FIELDS:
        profile[field] = _normalize_profile_text(profile.get(field))

    for field in PROFILE_LIST_FIELDS:
        items = profile.get(field, [])
        if isinstance(items, str):
            items = [items]
        elif not isinstance(items, list):
            items = []

        deduped_items: list[str] = []
        seen: set[str] = set()
        for item in items:
            clean_item = _normalize_profile_text(item)
            if not clean_item:
                continue

            normalized_key = clean_item.casefold()
            if normalized_key in seen:
                continue

            seen.add(normalized_key)
            deduped_items.append(clean_item)

        profile[field] = deduped_items[-20:]

    return profile


def _normalize_session_context(raw_value: Any) -> dict[str, Any]:
    session_context = deepcopy(DEFAULT_SESSION_CONTEXT)
    if not isinstance(raw_value, dict):
        return session_context

    session_context.update(raw_value)
    for field in {"mood", "energy", "current_topic"}:
        session_context[field] = _normalize_profile_text(session_context.get(field))

    return session_context


def _normalize_profile_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    return value.strip()


def _mark_profile_updated(profile: dict[str, Any]) -> None:
    profile["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "enabled", "active"}:
            return True
        if normalized in {"0", "false", "no", "off", "disabled", "inactive"}:
            return False

    return default
