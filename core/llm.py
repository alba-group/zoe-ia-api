import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from core.config import (
    LLM_HISTORY_LIMIT,
    MODEL_NAME,
    OPENAI_MAX_RETRIES,
    OPENAI_TIMEOUT_SECONDS,
)
from core.memory import get_last_messages, get_profile, get_session_context


load_dotenv()

LLM_TEMPORARY_FAILURE_REPLY = "Je n'ai pas reussi a repondre pour le moment. Reessaie dans un instant."
LLM_UNAVAILABLE_REPLY = "Le service de reponse est temporairement indisponible."


def build_memory_context(memory: dict) -> str:
    profile = get_profile(memory)
    session_context = get_session_context(memory)
    trusted_facts = memory.get("trusted_facts", {})

    parts: list[str] = []

    name = str(profile.get("name", "")).strip()
    city = str(profile.get("city", "")).strip()
    job = str(profile.get("job", "")).strip()
    preferred_tone = str(profile.get("preferred_tone", "")).strip()

    if name:
        parts.append(f"Nom utilisateur : {name}.")
    if city:
        parts.append(f"Ville : {city}.")
    if job:
        parts.append(f"Metier : {job}.")

    for field_name, label in (
        ("likes", "Aime"),
        ("dislikes", "N'aime pas"),
        ("projects", "Projets"),
        ("goals", "Objectifs"),
    ):
        values = _clean_list(profile.get(field_name))
        if values:
            parts.append(f"{label} : {', '.join(values[:4])}.")

    important_people = _clean_list(profile.get("important_people"))
    if important_people:
        parts.append(f"Personnes importantes : {', '.join(important_people[:3])}.")

    habits = _clean_list(profile.get("habits"))
    if habits:
        parts.append(f"Habitudes : {', '.join(habits[:3])}.")

    if preferred_tone:
        parts.append(f"Ton prefere : {preferred_tone}.")

    session_bits: list[str] = []
    mood = str(session_context.get("mood", "")).strip()
    energy = str(session_context.get("energy", "")).strip()
    current_topic = str(session_context.get("current_topic", "")).strip()
    if mood:
        session_bits.append(f"humeur={mood}")
    if energy:
        session_bits.append(f"energie={energy}")
    if current_topic:
        session_bits.append(f"sujet={current_topic}")
    if session_bits:
        parts.append("Contexte session : " + ", ".join(session_bits) + ".")

    if isinstance(trusted_facts, dict) and trusted_facts:
        trusted_parts: list[str] = []
        for key, value in list(trusted_facts.items())[:5]:
            clean_key = str(key).strip()
            clean_value = _stringify_fact(value)
            if clean_key and clean_value:
                trusted_parts.append(f"{clean_key}={clean_value}")
        if trusted_parts:
            parts.append("Faits fiables : " + "; ".join(trusted_parts) + ".")

    recent_lines: list[str] = []
    for item in get_last_messages(memory, limit=min(LLM_HISTORY_LIMIT, 4)):
        if not isinstance(item, dict):
            continue

        user_message = str(item.get("user_message", "")).strip()
        zoe_reply = str(item.get("zoe_reply", "")).strip()

        if user_message:
            recent_lines.append(f"Utilisateur : {user_message}")
        if zoe_reply:
            recent_lines.append(f"Zoe : {zoe_reply}")

    if recent_lines:
        parts.append("Derniers echanges utiles :\n" + "\n".join(recent_lines))

    return "\n".join(parts).strip()


def generate_fallback_reply() -> str:
    return LLM_TEMPORARY_FAILURE_REPLY


def generate_llm_reply(user_message: str, memory: dict, system_prompt: str) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return LLM_UNAVAILABLE_REPLY

    try:
        client = OpenAI(
            api_key=api_key,
            timeout=OPENAI_TIMEOUT_SECONDS,
            max_retries=OPENAI_MAX_RETRIES,
        )

        messages = _build_chat_messages(
            user_message=user_message,
            memory=memory,
            system_prompt=system_prompt,
        )

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.6,
        )

        content = response.choices[0].message.content if response.choices else ""
        if isinstance(content, str) and content.strip():
            return content.strip()

        return generate_fallback_reply()

    except Exception:
        return generate_fallback_reply()


def _build_chat_messages(
    user_message: str,
    memory: dict,
    system_prompt: str,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []

    clean_system_prompt = str(system_prompt or "").strip()
    if clean_system_prompt:
        messages.append({"role": "system", "content": clean_system_prompt})

    memory_context = build_memory_context(memory)
    if memory_context:
        messages.append(
            {
                "role": "system",
                "content": (
                    "Contexte memoire utile a respecter. "
                    "Ne pas inventer d'information absente.\n"
                    f"{memory_context}"
                ),
            }
        )

    for item in get_last_messages(memory, limit=min(LLM_HISTORY_LIMIT, 4)):
        if not isinstance(item, dict):
            continue

        user_text = str(item.get("user_message", "")).strip()
        zoe_text = str(item.get("zoe_reply", "")).strip()

        if user_text:
            messages.append({"role": "user", "content": user_text})
        if zoe_text:
            messages.append({"role": "assistant", "content": zoe_text})

    messages.append({"role": "user", "content": user_message.strip()})
    return messages


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    elif not isinstance(value, list):
        return []

    return [str(item).strip() for item in value if str(item).strip()]


def _stringify_fact(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item).strip() for item in value[:3] if str(item).strip())

    if isinstance(value, dict):
        pairs: list[str] = []
        for key, inner_value in list(value.items())[:3]:
            clean_key = str(key).strip()
            clean_value = str(inner_value).strip()
            if clean_key and clean_value:
                pairs.append(f"{clean_key}={clean_value}")
        return ", ".join(pairs)

    return str(value).strip()
