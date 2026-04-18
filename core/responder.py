from typing import Any


def _safe_name(name: str) -> str:
    if isinstance(name, str):
        return name.strip()
    return ""


def _prefix_with_name(text: str, user_name: str) -> str:
    user_name = _safe_name(user_name)
    if not user_name:
        return text

    if text.startswith("Je suis là"):
        return text.replace("Je suis là", f"Je suis là, {user_name}", 1)

    if text.startswith("Salut"):
        return text.replace("Salut", f"Salut {user_name}", 1)

    return text


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
        return "Je vois. Tu veux m'expliquer un peu plus ce qui s'est passé ?"

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
        return "Ça fait plaisir à entendre. Qu'est-ce qui t'a fait du bien aujourd'hui ?"

    if strategy == "ask_positive_detail":
        return "C'est une bonne nouvelle. Qu'est-ce qui t'a rendu content aujourd'hui ?"

    if strategy == "expand_positive_moment":
        return "Ça fait plaisir à entendre. Quel moment t'a fait le plus de bien ?"

    if strategy == "reflective_question":
        return "Je vois. Qu'est-ce qui te semble le plus important dans tout ça ?"

    if strategy == "gentle_encouragement":
        return "Tu peux prendre ton temps. Je t'écoute."

    if strategy == "generic_clarify":
        if user_name:
            return f"Je t'écoute, {user_name}. Tu peux m'en dire un peu plus ?"
        return "Je t'écoute. Tu peux m'en dire un peu plus ?"

    if user_name:
        return f"Je t'écoute, {user_name}. Tu peux m'en dire un peu plus ?"

    return "Je t'écoute. Tu peux m'en dire un peu plus ?"


def _apply_tone(text: str, tone: str) -> str:
    """
    Ajuste légèrement le ton sans rendre la réponse artificielle.
    """
    if tone == "gentle" and not text.startswith("Je suis là"):
        return f"Je suis là. {text}"

    if tone == "warm" and not text.startswith("Ça fait plaisir"):
        if "bonne nouvelle" in text.lower():
            return text
        return f"Ça fait plaisir à entendre. {text}"

    if tone == "soft" and not text.startswith("Je vois"):
        if "fatigué" in text.lower() or "fatigue" in text.lower():
            return text
        return f"Je vois. {text}"

    return text


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

    reply = _apply_tone(reply, tone)

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

    if emotion in {"negative", "sadness"}:
        if precision == "vague":
            return _prefix_with_name("Je suis là. Qu'est-ce qui ne va pas aujourd'hui ?", user_name)
        return "Je vois. Tu veux m'expliquer un peu plus ce qui s'est passé ?"

    if emotion == "stress":
        if precision == "vague":
            return "Tu sembles stressé. Tu sais ce qui te met dans cet état ?"
        return "Je comprends. Qu'est-ce qui te pèse le plus dans cette situation ?"

    if emotion == "fatigue":
        if precision == "vague":
            return "Tu as l'air fatigué. Tu sais d'où ça vient aujourd'hui ?"
        return "Je vois. Cette fatigue vient plutôt du corps, du moral ou de ta journée ?"

    if emotion == "anger":
        if precision == "vague":
            return "Je sens de la colère dans ce que tu dis. Qu'est-ce qui t'a énervé ?"
        return "Je comprends. Qu'est-ce qui t'a le plus blessé ou agacé dans cette situation ?"

    if emotion in {"positive", "joy"}:
        if precision == "vague":
            return "C'est une bonne nouvelle. Qu'est-ce qui t'a rendu content aujourd'hui ?"
        return "Ça fait plaisir à entendre. Quel moment t'a fait le plus de bien ?"

    return _prefix_with_name("Je t'écoute. Tu peux m'en dire un peu plus ?", user_name)


def build_greeting(memory: dict[str, Any] | None = None) -> str:
    memory = memory or {}
    name = memory.get("profile", {}).get("name", "")
    last_emotion = memory.get("last_emotion", "unknown")
    last_topic = memory.get("last_topic", "general")

    name = _safe_name(name)

    if name and last_emotion in {"negative", "stress", "fatigue", "sadness"}:
        return f"Salut {name}. Je suis contente de te revoir. Ça va un peu mieux aujourd'hui ?"

    if name and last_topic not in {"general", "identity", "memory"}:
        return f"Salut {name}. Je suis contente de te revoir. Tu veux qu'on reprenne là où on s'était arrêtés ?"

    if name:
        return f"Salut {name}. Je suis contente de te revoir."

    return "Salut. Je suis contente de te revoir."


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
        return "Je garde une trace légère de nos échanges, mais ma mémoire est encore en train de se construire."

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
        return model_reply.strip()

    if thought:
        return build_response_from_thought(thought, memory)

    return build_response_from_analysis(analysis or {}, memory) 
