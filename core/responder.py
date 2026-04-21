from typing import Any

from core.dictionary.greetings import build_greeting_reply
from core.dictionary.emotions import build_emotion_reply
from core.dictionary.tones import apply_tone
from core.dictionary.sentences import (
    build_identity_reply,
    build_unknown_name_reply,
    build_wrong_name_reply,
    build_listening_reply,
    build_memory_empty_reply,
    build_riddle_stop_reply,
    GENERAL_POSITIVE_REPLY,
    GENERAL_SUPPORT_REPLY,
    GENERAL_CLARIFY_REPLY,
)


def _safe_name(name: str) -> str:
    if isinstance(name, str):
        return name.strip()
    return ""


def _looks_like_code_block(text: str) -> bool:
    if not isinstance(text, str):
        return False

    stripped = text.strip().lower()
    if stripped.startswith("```"):
        return True

    code_markers = (
        "def ",
        "class ",
        "import ",
        "from ",
        "public class ",
        "fun ",
        "val ",
        "var ",
        "<html",
        "console.log(",
    )
    return any(marker in stripped for marker in code_markers)


def _should_prefer_plain_text(analysis: dict[str, Any] | None = None) -> bool:
    if not isinstance(analysis, dict):
        return False

    topic = str(analysis.get("topic", "")).strip().lower()

    return topic in {
        "musique",
        "écriture",
        "ecriture",
        "joie",
        "fatigue",
        "famille",
        "couple",
        "solitude",
        "quotidien",
        "général",
        "general",
        "image",
        "projet",
        "conversation",
        "support",
        "gratitude",
        "affection",
        "memory",
        "identite",
        "identity",
    }


def _build_from_strategy(
    strategy: str,
    tone: str,
    user_name: str,
    memory_hint: str | None = None
) -> str:
    """
    Construit la réponse principale à partir de la stratégie réfléchie.
    """
    user_name = _safe_name(user_name)

    if strategy == "open_emotional_question":
        if user_name:
            return f"Je suis là, {user_name}. Qu'est-ce qui te pèse le plus aujourd'hui ?"
        return "Je suis là. Qu'est-ce qui te pèse le plus aujourd'hui ?"

    if strategy == "clarify_event":
        return GENERAL_CLARIFY_REPLY

    if strategy == "find_source_of_stress":
        return "Tu sembles sous pression. Tu sais ce qui te met dans cet état ?"

    if strategy == "understand_pressure":
        return "Je comprends. Qu'est-ce qui te prend le plus d'énergie dans cette situation ?"

    if strategy == "find_cause_of_fatigue":
        return "Tu as l'air fatigué. Tu sais d'où ça vient aujourd'hui ?"

    if strategy == "separate_body_and_mind":
        return "Je vois. Cette fatigue vient plutôt du corps, du moral ou de ta journée ?"

    if strategy == "find_trigger":
        return "Je sens de la colère dans ce que tu dis. Qu'est-ce qui a déclenché ça ?"

    if strategy == "identify_hurt":
        return "Je comprends. Qu'est-ce qui t'a le plus touché ou blessé dans cette situation ?"

    if strategy == "highlight_improvement":
        if memory_hint:
            return f"{memory_hint} Qu'est-ce qui t'a fait du bien aujourd'hui ?"
        return f"{GENERAL_POSITIVE_REPLY} Qu'est-ce qui t'a fait du bien aujourd'hui ?"

    if strategy == "ask_positive_detail":
        return "C'est une bonne nouvelle. Qu'est-ce qui t'a rendu content aujourd'hui ?"

    if strategy == "expand_positive_moment":
        return "Ça fait plaisir à entendre. Quel moment t'a fait le plus de bien ?"

    if strategy == "reflective_question":
        return "Je vois. Qu'est-ce qui te semble le plus important dans tout ça ?"

    if strategy == "gentle_encouragement":
        return "Tu peux prendre ton temps. Je t'écoute."

    if strategy == "generic_clarify":
        return build_listening_reply(user_name)

    return build_listening_reply(user_name)


def build_response_from_thought(
    thought: dict[str, Any],
    memory: dict[str, Any] | None = None
) -> str:
    """
    Construit une réponse à partir de la réflexion de Zoe.
    """
    memory = memory or {}

    strategy = thought.get("strategy", "generic_clarify")
    tone = thought.get("tone", "neutral")
    user_name = thought.get("user_name", "")
    memory_hint = thought.get("memory_hint", None)

    reply = _build_from_strategy(
        strategy=strategy,
        tone=tone,
        user_name=user_name,
        memory_hint=memory_hint
    )

    reply = apply_tone(reply, tone)

    return reply


def build_response_from_analysis(
    analysis: dict[str, Any],
    memory: dict[str, Any] | None = None
) -> str:
    """
    Fallback simple si la réflexion n'est pas disponible.
    """
    emotion = analysis.get("emotion", "unknown")
    precision = analysis.get("precision", "vague")
    user_name = ""

    if memory:
        user_name = memory.get("profile", {}).get("name", "")

    return build_emotion_reply(
        emotion=emotion,
        precision=precision,
        user_name=user_name,
    )


def build_greeting(memory: dict[str, Any] | None = None) -> str:
    memory = memory or {}
    name = memory.get("profile", {}).get("name", "")
    last_emotion = memory.get("last_emotion", "unknown")
    last_topic = memory.get("last_topic", "general")

    return build_greeting_reply(
        user_name=name,
        last_emotion=last_emotion,
        last_topic=last_topic,
    )


def build_memory_reply(memory: dict[str, Any] | None = None) -> str:
    memory = memory or {}
    profile = memory.get("profile", {})
    name = _safe_name(profile.get("name", ""))
    last_emotion = memory.get("last_emotion", "unknown")
    last_topic = memory.get("last_topic", "general")

    parts = []

    if name:
        parts.append(f"Je me souviens que tu t'appelles {name}.")

    if last_emotion != "unknown":
        parts.append(f"La dernière émotion que j'ai retenue, c'est {last_emotion}.")

    if last_topic != "general":
        parts.append(f"Le dernier sujet important que j'ai retenu, c'est {last_topic}.")

    if not parts:
        return build_memory_empty_reply()

    return " ".join(parts)


def build_final_response(
    analysis: dict[str, Any] | None = None,
    model_reply: str | None = None,
    memory: dict[str, Any] | None = None,
    thought: dict[str, Any] | None = None
) -> str:
    """
    Priorité :
    1. réponse du modèle si disponible
    2. réponse construite depuis la réflexion
    3. fallback simple depuis l'analyse
    """
    if model_reply and model_reply.strip():
        clean_reply = model_reply.strip()

        # Petit garde-fou :
        # si le sujet attendu est plutôt textuel / créatif / conversationnel,
        # on évite de faire confiance à une réponse qui ressemble visiblement à du code.
        if _should_prefer_plain_text(analysis) and _looks_like_code_block(clean_reply):
            if thought:
                return build_response_from_thought(thought, memory)
            return build_response_from_analysis(analysis or {}, memory)

        return clean_reply

    if thought:
        return build_response_from_thought(thought, memory)

    return build_response_from_analysis(analysis or {}, memory)