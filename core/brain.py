from core.analyzer import analyze_text
from core.thinker import think_about_message
from core.responder import build_final_response
from core.memory import (
    save_memory,
    add_message_to_history,
    update_profile_from_analysis,
)
from core.utils import current_datetime_string
from core.context import (
    ensure_context,
    start_riddle,
    close_riddle,
    set_last_bot_question,
    clear_waiting_flag,
    is_riddle_mode,
    get_riddle_answer,
    get_last_question_type,
)
from core.web_tool import should_use_web, build_web_reply
from core.code_tool import should_use_code_tool, build_code_result
from core.image_tool import should_use_image_tool, generate_image_reply
from core.llm_client import create_llm_client, build_zoe_system_prompt


def _get_name(memory: dict) -> str:
    profile = memory.get("profile", {})
    name = profile.get("name", "")
    if isinstance(name, str):
        return name.strip()
    return ""


def _save_name(memory: dict, name: str) -> None:
    profile = memory.get("profile", {})
    profile["name"] = name.strip().capitalize()
    memory["profile"] = profile
    save_memory(memory)


def _reply_with_name(memory: dict) -> str:
    name = _get_name(memory)

    if name:
        return f"Tu t'appelles {name}. Je m'en souviens."

    return "Je ne connais pas encore ton prénom. Tu peux me le dire si tu veux."


def _reply_memory(memory: dict) -> str:
    name = _get_name(memory)
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
        return "Je garde une mémoire légère de nos échanges, mais elle est encore en train de se construire."

    return " ".join(parts)


def _greeting_reply(memory: dict) -> str:
    name = _get_name(memory)
    last_emotion = memory.get("last_emotion", "unknown")

    if name and last_emotion in {"negative", "stress", "fatigue", "sadness"}:
        return f"Salut {name}. Je suis contente de te revoir. Ça va un peu mieux aujourd'hui ?"

    if name:
        return f"Salut {name}. Je suis contente de te revoir."

    return "Salut. Je suis contente de te revoir."


def _save_exchange(
    memory: dict,
    user_text: str,
    reply: str,
    emotion: str,
    topic: str,
    precision: str,
    intent: str
) -> None:
    add_message_to_history(
        memory=memory,
        user_message=user_text,
        zoe_reply=reply,
        emotion=emotion,
        topic=topic,
        precision=precision,
        intent=intent,
        timestamp=current_datetime_string(),
    )

    update_profile_from_analysis(
        memory=memory,
        analysis={
            "emotion": emotion,
            "topic": topic,
            "precision": precision,
            "intent": intent,
            "reply": reply,
        },
    )

    save_memory(memory)


def _build_conversation_history(memory: dict) -> list[dict[str, str]]:
    """
    Convertit l'historique local en format conversation pour le LLM.
    """
    history = memory.get("history", [])
    conversation: list[dict[str, str]] = []

    for item in history[-6:]:
        user_message = item.get("user_message", "").strip()
        zoe_reply = item.get("zoe_reply", "").strip()

        if user_message:
            conversation.append({
                "role": "user",
                "content": user_message,
            })

        if zoe_reply:
            conversation.append({
                "role": "assistant",
                "content": zoe_reply,
            })

    return conversation


def _call_llm_reply(user_input: str, memory: dict) -> dict | None:
    """
    Appelle le vrai moteur LLM pour une réponse libre.
    """
    try:
        user_name = _get_name(memory)
        conversation = _build_conversation_history(memory)

        client = create_llm_client()
        result = client.ask(
            user_message=user_input,
            system_prompt=build_zoe_system_prompt(user_name=user_name),
            conversation=conversation,
            temperature=0.7,
        )

        if result.error or not result.text.strip():
            return None

        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "llm",
            "intent": "reflect",
            "reply": result.text.strip(),
        }

    except Exception:
        return None


def _handle_contextual_reply(text: str, memory: dict) -> dict | None:
    """
    Comprend les petites réponses dans un contexte déjà ouvert.
    Exemple : 'je sais pas' après une devinette.
    """
    lower = text.lower().strip()
    ensure_context(memory)

    # =========================
    # MODE DEVINETTE
    # =========================
    if is_riddle_mode(memory):
        answer = get_riddle_answer(memory) or "un piano"

        if lower in {
            "je sais pas",
            "j'sais pas",
            "je ne sais pas",
            "jsais pas",
            "aucune idée",
            "j'abandonne",
            "abandon",
            "donne la réponse",
            "c'est quoi",
            "dis-moi",
        }:
            reply = f"La réponse était : {answer}. Tu en veux une autre ?"
            set_last_bot_question(memory, reply, "riddle_followup")
            _save_exchange(memory, text, reply, "unknown", "fun", "precise", "reflect")
            return {
                "emotion": "unknown",
                "precision": "precise",
                "topic": "fun",
                "intent": "reflect",
                "reply": reply,
            }

        if lower in {
            "encore",
            "oui",
            "oui encore",
            "une autre",
            "vas-y",
        }:
            question = "Je commence sans voix, je finis sans air, et pourtant je peux être très chère. Qui suis-je ?"
            answer = "une bague"
            start_riddle(memory, question, answer)
            reply = f"D'accord. Nouvelle devinette : {question}"
            _save_exchange(memory, text, reply, "positive", "fun", "precise", "encourage")
            return {
                "emotion": "positive",
                "precision": "precise",
                "topic": "fun",
                "intent": "encourage",
                "reply": reply,
            }

        if lower in {
            "non",
            "non merci",
            "stop",
            "arrête",
            "pas une autre",
        }:
            close_riddle(memory)
            reply = "D'accord, j'arrête les devinettes pour le moment."
            _save_exchange(memory, text, reply, "unknown", "fun", "precise", "reflect")
            return {
                "emotion": "unknown",
                "precision": "precise",
                "topic": "fun",
                "intent": "reflect",
                "reply": reply,
            }

    # =========================
    # RÉPONSE À UNE QUESTION ÉMOTIONNELLE
    # =========================
    qtype = get_last_question_type(memory)

    if qtype in {"emotional_followup", "general_followup"}:
        if lower in {"oui", "oui un peu", "un peu", "ça va un peu mieux", "mieux"}:
            clear_waiting_flag(memory)
            reply = "Je suis contente de lire ça. Qu'est-ce qui t'aide le plus en ce moment ?"
            _save_exchange(memory, text, reply, "positive", "general", "precise", "encourage")
            return {
                "emotion": "positive",
                "precision": "precise",
                "topic": "general",
                "intent": "encourage",
                "reply": reply,
            }

        if lower in {"non", "pas trop", "toujours pas", "non pas vraiment"}:
            clear_waiting_flag(memory)
            reply = "D'accord. On peut prendre le temps. Qu'est-ce qui te pèse le plus maintenant ?"
            _save_exchange(memory, text, reply, "negative", "general", "precise", "support")
            return {
                "emotion": "negative",
                "precision": "precise",
                "topic": "general",
                "intent": "support",
                "reply": reply,
            }

    return None


def _direct_rules(text: str, memory: dict) -> dict | None:
    lower = text.lower().strip()
    ensure_context(memory)

    # Nom de Zoe
    if lower in {
        "comment tu t'appelles",
        "tu t'appelles comment",
        "quel est ton nom",
        "c'est quoi ton prénom",
        "qui es-tu",
        "tu es qui",
        "tu es quoi",
    }:
        reply = "Je m'appelle Zoé. Je suis une intelligence artificielle."
        _save_exchange(memory, text, reply, "positive", "identity", "precise", "reflect")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    # Questions naturelles de conversation
    if lower in {"et toi", "et toi ?", "toi ?", "et toi alors"}:
        reply = "Moi ça va bien. Merci de me le demander."
        _save_exchange(memory, text, reply, "positive", "conversation", "precise", "reflect")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "conversation",
            "intent": "reflect",
            "reply": reply,
        }

    if lower in {
        "et toi comment tu t'appelles",
        "toi comment tu t'appelles",
        "et toi tu t'appelles comment",
        "toi tu t'appelles comment",
        "et toi comment tu t'appelle",
        "toi comment tu t'appelle",
    }:
        reply = "Je m'appelle Zoé. Je suis une intelligence artificielle."
        _save_exchange(memory, text, reply, "positive", "identity", "precise", "reflect")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    if lower in {
        "fais-moi une devinette",
        "donne-moi une devinette",
        "une devinette",
    }:
        question = "Qu'est-ce qui a des clés mais n'ouvre aucune porte ?"
        answer = "un piano"
        start_riddle(memory, question, answer)
        reply = f"Avec plaisir. {question}"
        _save_exchange(memory, text, reply, "positive", "fun", "precise", "encourage")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "fun",
            "intent": "encourage",
            "reply": reply,
        }

    # Salutations
    if lower in {"salut", "salut zoe", "bonjour", "hello", "coucou"}:
        reply = _greeting_reply(memory)

        if "Ça va un peu mieux" in reply:
            set_last_bot_question(memory, reply, "emotional_followup")
        else:
            clear_waiting_flag(memory)

        _save_exchange(memory, text, reply, "positive", "general", "vague", "encourage")
        return {
            "emotion": "positive",
            "precision": "vague",
            "topic": "general",
            "intent": "encourage",
            "reply": reply,
        }

    # Question sur le prénom utilisateur
    if lower in {
        "comment je m'appelle",
        "comment je m'appelles",
        "tu connais mon prénom",
        "tu te souviens de mon prénom",
        "c'est quoi mon prénom",
    }:
        reply = _reply_with_name(memory)
        _save_exchange(memory, text, reply, "unknown", "identity", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    # Question mémoire globale
    if "tu te souviens de moi" in lower or "tu te souviens de nos échanges" in lower:
        reply = _reply_memory(memory)
        _save_exchange(memory, text, reply, "unknown", "memory", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "memory",
            "intent": "reflect",
            "reply": reply,
        }

    # Prénom utilisateur
    if lower.startswith("je m'appelle "):
        try:
            name = text.split("je m'appelle", 1)[1].strip().split(" ")[0]
            if name:
                _save_name(memory, name)
                reply = f"Enchantée {name.capitalize()}. Je retiens ton prénom."
                _save_exchange(memory, text, reply, "positive", "identity", "precise", "encourage")
                return {
                    "emotion": "positive",
                    "precision": "precise",
                    "topic": "identity",
                    "intent": "encourage",
                    "reply": reply,
                }
        except Exception:
            pass

    if lower.startswith("mon prénom c'est "):
        try:
            name = text.split("mon prénom c'est", 1)[1].strip().split(" ")[0]
            if name:
                _save_name(memory, name)
                reply = f"Merci {name.capitalize()}. Je retiens ton prénom."
                _save_exchange(memory, text, reply, "positive", "identity", "precise", "encourage")
                return {
                    "emotion": "positive",
                    "precision": "precise",
                    "topic": "identity",
                    "intent": "encourage",
                    "reply": reply,
                }
        except Exception:
            pass

    # Petite conversation
    if lower in {"cava", "ça va", "ca va", "ça va ?", "ca va ?"}:
        name = _get_name(memory)
        if name:
            reply = f"Oui, ça va bien. Merci {name}. Et toi, comment tu te sens aujourd'hui ?"
        else:
            reply = "Oui, ça va bien. Merci. Et toi, comment tu te sens aujourd'hui ?"

        set_last_bot_question(memory, reply, "general_followup")
        _save_exchange(memory, text, reply, "positive", "conversation", "vague", "ask_open_question")
        return {
            "emotion": "positive",
            "precision": "vague",
            "topic": "conversation",
            "intent": "ask_open_question",
            "reply": reply,
        }

    # Tests version
    if lower == "brain thinker":
        reply = "Mon cerveau avec réflexion est bien actif."
        _save_exchange(memory, text, reply, "positive", "system", "precise", "encourage")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "system",
            "intent": "encourage",
            "reply": reply,
        }

    if lower == "brain v5":
        reply = "Mon cerveau V5 simple est bien actif."
        _save_exchange(memory, text, reply, "positive", "system", "precise", "encourage")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "system",
            "intent": "encourage",
            "reply": reply,
        }

    return None


def process_user_message(user_input: str, memory: dict) -> dict:
    text = user_input.strip()
    ensure_context(memory)

    # 0. Contexte vivant
    contextual_result = _handle_contextual_reply(text, memory)
    if contextual_result is not None:
        return contextual_result

    # 1. Règles directes
    direct_result = _direct_rules(text, memory)
    if direct_result is not None:
        return direct_result

    # 2. Outil image
    if should_use_image_tool(text):
        conversation = _build_conversation_history(memory)
        image_result = generate_image_reply(
            user_message=text,
            conversation=conversation,
        )

        reply = image_result["reply"]

        result = {
            "emotion": image_result.get("emotion", "positive"),
            "precision": image_result.get("precision", "precise"),
            "topic": image_result.get("topic", "image"),
            "intent": image_result.get("intent", "create"),
            "reply": reply,
            "image_url": image_result.get("image_url", ""),
            "thought_summary": "mode image activé",
            "strategy": "image_generation",
            "tone": "creative",
        }

        _save_exchange(
            memory=memory,
            user_text=text,
            reply=reply,
            emotion=result["emotion"],
            topic=result["topic"],
            precision=result["precision"],
            intent=result["intent"],
        )

        return result

    # 3. Outil code
    if should_use_code_tool(text):
        conversation = _build_conversation_history(memory)
        code_result = build_code_result(
            user_message=text,
            conversation=conversation,
        )

        reply = code_result["reply"]

        result = {
            "emotion": code_result.get("emotion", "positive"),
            "precision": code_result.get("precision", "precise"),
            "topic": code_result.get("topic", "code"),
            "intent": code_result.get("intent", "reflect"),
            "reply": reply,
            "thought_summary": "mode code activé",
            "strategy": "code_generation",
            "tone": "technical",
        }

        _save_exchange(
            memory=memory,
            user_text=text,
            reply=reply,
            emotion=result["emotion"],
            topic=result["topic"],
            precision=result["precision"],
            intent=result["intent"],
        )

        return result

    # 4. Outil web
    if should_use_web(text):
        user_name = _get_name(memory)
        conversation = _build_conversation_history(memory)
        web_result = build_web_reply(
            user_message=text,
            user_name=user_name,
            conversation=conversation,
        )

        reply = web_result["reply"]

        result = {
            "emotion": web_result.get("emotion", "unknown"),
            "precision": web_result.get("precision", "precise"),
            "topic": web_result.get("topic", "web"),
            "intent": web_result.get("intent", "clarify"),
            "reply": reply,
            "thought_summary": web_result.get("thought_summary", ""),
            "strategy": web_result.get("strategy", "web_search"),
            "tone": web_result.get("tone", "informative"),
        }

        _save_exchange(
            memory=memory,
            user_text=text,
            reply=reply,
            emotion=result["emotion"],
            topic=result["topic"],
            precision=result["precision"],
            intent=result["intent"],
        )

        return result

    # 5. Analyse locale
    analysis = analyze_text(text, memory)
    thought_summary = think_about_message(text, memory, analysis)
    reply = build_final_response(text, memory, analysis, thought_summary)

    # 6. Fallback LLM si la réponse locale semble trop faible
    llm_result = _call_llm_reply(text, memory)
    if llm_result is not None:
        reply = llm_result["reply"]
        analysis["emotion"] = llm_result.get("emotion", analysis.get("emotion", "unknown"))
        analysis["topic"] = llm_result.get("topic", analysis.get("topic", "general"))
        analysis["precision"] = llm_result.get("precision", analysis.get("precision", "vague"))
        analysis["intent"] = llm_result.get("intent", analysis.get("intent", "reflect"))

    result = {
        "emotion": analysis.get("emotion", "unknown"),
        "precision": analysis.get("precision", "vague"),
        "topic": analysis.get("topic", "general"),
        "intent": analysis.get("intent", "reflect"),
        "reply": reply,
        "thought_summary": thought_summary,
        "strategy": analysis.get("strategy", ""),
        "tone": analysis.get("tone", ""),
    }

    _save_exchange(
        memory=memory,
        user_text=text,
        reply=reply,
        emotion=result["emotion"],
        topic=result["topic"],
        precision=result["precision"],
        intent=result["intent"],
    )

    return result 
