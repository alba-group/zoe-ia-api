from typing import Any


def think_about_message(
    user_input: str,
    analysis: dict[str, Any],
    memory: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    Fait réfléchir Zoe avant la réponse.
    Retourne une décision structurée.
    """

    memory = memory or {}

    emotion = analysis.get("emotion", "unknown")
    precision = analysis.get("precision", "vague")
    topic = analysis.get("topic", "general")
    intent = analysis.get("intent", "clarify")

    last_emotion = memory.get("last_emotion", "unknown")
    last_topic = memory.get("last_topic", "general")

    profile = memory.get("profile", {})
    user_name = profile.get("name", "")

    thought = []
    strategy = "listen"
    tone = "calm"
    priority = "understand"

    # =========================
    # BASE DE RÉFLEXION
    # =========================
    thought.append(f"émotion détectée: {emotion}")
    thought.append(f"précision: {precision}")
    thought.append(f"sujet: {topic}")

    if user_name:
        thought.append(f"utilisateur connu: {user_name}")

    if last_emotion != "unknown":
        thought.append(f"dernière émotion connue: {last_emotion}")

    if last_topic != "general":
        thought.append(f"dernier sujet connu: {last_topic}")

    # =========================
    # STRATÉGIE
    # =========================
    if emotion in {"negative", "sadness"}:
        tone = "gentle"
        priority = "support"

        if precision == "vague":
            strategy = "open_emotional_question"
            thought.append("message négatif mais flou, il faut ouvrir la discussion doucement")
        else:
            strategy = "clarify_event"
            thought.append("message négatif précis, il faut comprendre ce qui s'est passé")

    elif emotion == "stress":
        tone = "calm"
        priority = "relieve"

        if precision == "vague":
            strategy = "find_source_of_stress"
            thought.append("stress détecté, chercher la source")
        else:
            strategy = "understand_pressure"
            thought.append("stress précis, comprendre ce qui pèse le plus")

    elif emotion == "fatigue":
        tone = "soft"
        priority = "understand"

        if precision == "vague":
            strategy = "find_cause_of_fatigue"
            thought.append("fatigue floue, demander d'où ça vient")
        else:
            strategy = "separate_body_and_mind"
            thought.append("fatigue précise, distinguer corps, moral ou journée")

    elif emotion == "anger":
        tone = "steady"
        priority = "de-escalate"

        if precision == "vague":
            strategy = "find_trigger"
            thought.append("colère floue, identifier ce qui a déclenché")
        else:
            strategy = "identify_hurt"
            thought.append("colère précise, comprendre ce qui a blessé")

    elif emotion in {"positive", "joy"}:
        tone = "warm"
        priority = "encourage"

        if last_emotion in {"negative", "sadness", "stress", "fatigue"}:
            strategy = "highlight_improvement"
            thought.append("amélioration par rapport à l'état précédent, valoriser le positif")
        elif precision == "vague":
            strategy = "ask_positive_detail"
            thought.append("positif mais flou, demander ce qui a fait du bien")
        else:
            strategy = "expand_positive_moment"
            thought.append("positif précis, approfondir le bon moment")

    else:
        tone = "neutral"
        priority = "understand"

        if intent == "reflect":
            strategy = "reflective_question"
            thought.append("intention réflexive, poser une question qui aide à développer")
        elif intent == "encourage":
            strategy = "gentle_encouragement"
            thought.append("encourager et ouvrir")
        else:
            strategy = "generic_clarify"
            thought.append("manque d'informations, demander plus de détails")

    # =========================
    # CONTINUITÉ MÉMOIRE
    # =========================
    memory_hint = None

    if topic != "general" and topic == last_topic:
        memory_hint = f"Le sujet revient encore autour de {topic}."
        thought.append("le sujet revient, garder de la continuité")

    elif last_emotion in {"negative", "stress", "fatigue"} and emotion in {"positive", "joy"}:
        memory_hint = "L'utilisateur semble aller un peu mieux qu'avant."
        thought.append("évolution émotionnelle positive détectée")

    elif last_emotion in {"positive", "joy"} and emotion in {"negative", "sadness"}:
        memory_hint = "Le ton semble plus lourd qu'au message précédent."
        thought.append("baisse émotionnelle détectée")

    return {
        "strategy": strategy,
        "tone": tone,
        "priority": priority,
        "memory_hint": memory_hint,
        "thought_summary": " | ".join(thought),
        "user_name": user_name,
        "emotion": emotion,
        "precision": precision,
        "topic": topic,
    } 
