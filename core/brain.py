import re
import unicodedata

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

from core.dictionary import (
    ALL_SYMBOLS,
    SPACE_SYMBOLS,
    ALL_EMOJIS,
    is_greeting,
    build_greeting_reply,
    build_identity_reply,
    build_unknown_name_reply,
    build_wrong_name_reply,
    build_memory_empty_reply,
)


IDENTITY_HINTS = {
    "nom",
    "prenom",
    "prénom",
    "appelle",
    "appelles",
}

ASSISTANT_IDENTITY_PATTERNS = {
    "qui es tu",
    "tu es qui",
    "tu es quoi",
    "quel est ton nom",
    "c est quoi ton prenom",
    "c est quoi ton prénom",
    "tu t appelles comment",
    "comment tu t appelles",
    "et toi comment tu t appelles",
    "et toi tu t appelles comment",
    "toi comment tu t appelles",
}

USER_NAME_PATTERNS = {
    "comment je m appelle",
    "comment je m appelles",
    "tu connais mon prenom",
    "tu connais mon prénom",
    "tu te souviens de mon prenom",
    "tu te souviens de mon prénom",
    "c est quoi mon prenom",
    "c est quoi mon prénom",
    "quel est mon prenom",
    "quel est mon prénom",
}

NEGATIVE_NAME_PATTERNS = {
    "je m appelle pas",
    "je ne m appelle pas",
    "ce n est pas mon prenom",
    "ce n est pas mon prénom",
    "c est pas mon prenom",
    "c est pas mon prénom",
    "tu te trompes de prenom",
    "tu te trompes de prénom",
}

RIDDLE_REQUEST_PATTERNS = {
    "fais moi une devinette",
    "donne moi une devinette",
    "une devinette",
}

HOW_ARE_YOU_PATTERNS = {
    "ca va",
    "ça va",
    "ca va ?",
    "ça va ?",
    "cava",
}

SIMPLE_CHAT_PATTERNS = {
    "merci",
    "merci zoe",
    "et toi",
    "et toi ?",
    "toi ?",
    "et toi alors",
    "je suis triste",
    "je t aime",
    "j ai besoin de parler",
    "j'ai besoin de parler",
}

PROTECTED_CHAT_PREFIXES = (
    "comment tu t",
    "tu t appelles",
    "qui es tu",
    "salut",
    "bonjour",
    "bonsoir",
    "coucou",
    "merci",
    "comment je m appelle",
    "quel est mon prenom",
    "quel est mon prénom",
    "je m appelle ",
    "je m appelle pas",
    "je ne m appelle pas",
    "mon prenom c est",
    "mon prénom c est",
    "mon prenom est",
    "mon prénom est",
    "moi c est",
    "moi c'est",
)


def _collapse_spaces(text: str) -> str:
    return " ".join(text.split())


def _normalize_user_text(text: str) -> str:
    """
    Normalise un texte utilisateur :
    - minuscules
    - suppression des emojis
    - remplacement ponctuation/symboles par espaces
    - compactage des espaces
    """
    if not isinstance(text, str):
        return ""

    cleaned = text

    for space_symbol in SPACE_SYMBOLS:
        cleaned = cleaned.replace(space_symbol, " ")

    for emoji in ALL_EMOJIS:
        cleaned = cleaned.replace(emoji, " ")

    for symbol in ALL_SYMBOLS:
        cleaned = cleaned.replace(symbol, " ")

    cleaned = cleaned.lower()
    cleaned = _collapse_spaces(cleaned)
    return cleaned.strip()


def _normalize_for_name(text: str) -> str:
    if not isinstance(text, str):
        return ""

    cleaned = text.strip().lower()
    cleaned = cleaned.replace("’", "'")
    cleaned = cleaned.replace("`", "'")
    cleaned = cleaned.replace("´", "'")
    cleaned = unicodedata.normalize("NFD", cleaned)
    cleaned = "".join(ch for ch in cleaned if unicodedata.category(ch) != "Mn")
    cleaned = _collapse_spaces(cleaned)
    return cleaned


def _safe_split_name(raw_value: str) -> str:
    if not isinstance(raw_value, str):
        return ""

    candidate = raw_value.strip()
    if not candidate:
        return ""

    candidate = candidate.split(" ")[0].strip()
    candidate = candidate.strip(" .,!?:;\"'`()[]{}")
    return candidate


def _extract_name_from_message(text: str) -> str:
    normalized = _normalize_for_name(text)

    patterns = [
        r"^je m'appelle\s+([a-zA-ZÀ-ÿ\-]+)$",
        r"^je m appelle\s+([a-zA-ZÀ-ÿ\-]+)$",
        r"^mon prenom c'est\s+([a-zA-ZÀ-ÿ\-]+)$",
        r"^mon prenom c est\s+([a-zA-ZÀ-ÿ\-]+)$",
        r"^mon prenom est\s+([a-zA-ZÀ-ÿ\-]+)$",
        r"^moi c'est\s+([a-zA-ZÀ-ÿ\-]+)$",
        r"^moi c est\s+([a-zA-ZÀ-ÿ\-]+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, normalized, re.IGNORECASE)
        if match:
            return _safe_split_name(match.group(1))

    return ""


def _is_invalid_name_candidate(name: str) -> bool:
    forbidden = {
        "quel",
        "quelle",
        "quels",
        "quelles",
        "et",
        "toi",
        "comment",
        "mon",
        "prenom",
        "prénom",
        "nom",
        "bonjour",
        "bonsoir",
        "salut",
        "merci",
        "temps",
        "meteo",
        "météo",
        "donne",
        "pourquoi",
        "ou",
        "où",
        "quand",
    }
    return _normalize_user_text(name) in forbidden


def _contains_any_phrase(text: str, phrases: set[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def _looks_like_assistant_identity_question(text: str) -> bool:
    if text in ASSISTANT_IDENTITY_PATTERNS:
        return True

    tokens = set(text.split())

    if "qui" in tokens and "tu" in tokens:
        return True

    if IDENTITY_HINTS & tokens and "tu" in tokens:
        return True

    return False


def _looks_like_user_name_question(text: str) -> bool:
    if text in USER_NAME_PATTERNS:
        return True

    question_markers = {
        "comment",
        "quel",
        "quoi",
        "connais",
        "souviens",
    }

    tokens = set(text.split())

    if ("prenom" in tokens or "prénom" in tokens) and question_markers & tokens:
        return True

    if "appelle" in tokens and ("comment" in tokens or "quel" in tokens):
        return True

    return False


def _is_protected_chat_message(text: str) -> bool:
    if not text:
        return False

    if is_greeting(text):
        return True

    if text in SIMPLE_CHAT_PATTERNS:
        return True

    if _looks_like_assistant_identity_question(text):
        return True

    if _looks_like_user_name_question(text):
        return True

    if _contains_any_phrase(text, NEGATIVE_NAME_PATTERNS):
        return True

    return any(text.startswith(prefix) for prefix in PROTECTED_CHAT_PREFIXES)


def _get_name(memory: dict) -> str:
    """
    Retourne uniquement un prénom explicitement mémorisé.
    Aucun fallback automatique.
    """
    profile = memory.get("profile", {})
    name = profile.get("name", "")

    if isinstance(name, str):
        return name.strip()

    return ""


def _clear_name(memory: dict) -> None:
    profile = memory.get("profile", {})
    profile["name"] = ""
    memory["profile"] = profile
    save_memory(memory)


def _save_name(memory: dict, name: str) -> None:
    clean_name = _safe_split_name(name)

    if not clean_name:
        return

    profile = memory.get("profile", {})
    profile["name"] = clean_name.capitalize()
    memory["profile"] = profile
    save_memory(memory)


def _reply_with_name(memory: dict) -> str:
    name = _get_name(memory)

    if name:
        return f"Tu t'appelles {name}. Je m'en souviens."

    return build_unknown_name_reply()


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
        return build_memory_empty_reply()

    return " ".join(parts)


def _greeting_reply(memory: dict) -> str:
    name = _get_name(memory)
    last_emotion = memory.get("last_emotion", "unknown")
    last_topic = memory.get("last_topic", "general")

    return build_greeting_reply(
        user_name=name,
        last_emotion=last_emotion,
        last_topic=last_topic,
    )


def _save_exchange(
    memory: dict,
    user_text: str,
    reply: str,
    emotion: str,
    topic: str,
    precision: str,
    intent: str,
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
    lower = _normalize_user_text(text)
    ensure_context(memory)

    if is_riddle_mode(memory):
        answer = get_riddle_answer(memory) or "un piano"

        if lower in {
            "je sais pas",
            "j sais pas",
            "je ne sais pas",
            "jsais pas",
            "aucune idee",
            "aucune idée",
            "j abandonne",
            "abandon",
            "donne la reponse",
            "donne la réponse",
            "c est quoi",
            "dis moi",
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
            "vas y",
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
            "arrete",
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

    qtype = get_last_question_type(memory)

    if qtype == "ask_name":
        extracted_name = _extract_name_from_message(text)

        if not extracted_name:
            raw_candidate = text.strip()
            normalized_candidate = _normalize_user_text(raw_candidate)

            words = normalized_candidate.split()

            if (
                raw_candidate
                and len(words) == 1
                and words[0].isalpha()
                and len(words[0]) >= 2
            ):
                extracted_name = _safe_split_name(raw_candidate)

        if extracted_name and _is_invalid_name_candidate(extracted_name):
            extracted_name = ""

        if extracted_name:
            _save_name(memory, extracted_name)
            clear_waiting_flag(memory)
            reply = f"Enchantée, {extracted_name.capitalize()}. Je retiens ton prénom."
            _save_exchange(memory, text, reply, "positive", "identity", "precise", "encourage")
            return {
                "emotion": "positive",
                "precision": "precise",
                "topic": "identity",
                "intent": "encourage",
                "reply": reply,
            }

        # Si la réponse n'est pas un prénom, on coupe le mode ask_name
        clear_waiting_flag(memory)

    if qtype in {"emotional_followup", "general_followup"}:
        if lower in {"oui", "oui un peu", "un peu", "ca va un peu mieux", "ça va un peu mieux", "mieux"}:
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
    lower = _normalize_user_text(text)
    ensure_context(memory)

    if _contains_any_phrase(lower, NEGATIVE_NAME_PATTERNS):
        _clear_name(memory)
        reply = build_wrong_name_reply()
        _save_exchange(memory, text, reply, "unknown", "identity", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    if _looks_like_assistant_identity_question(lower):
        reply = build_identity_reply()
        _save_exchange(memory, text, reply, "positive", "identity", "precise", "reflect")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    if lower in {"et toi", "toi", "et toi alors"}:
        reply = "Moi ça va bien. Merci de me le demander."
        _save_exchange(memory, text, reply, "positive", "conversation", "precise", "reflect")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "conversation",
            "intent": "reflect",
            "reply": reply,
        }

    if lower in RIDDLE_REQUEST_PATTERNS:
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

    if is_greeting(lower):
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

    extracted_name = _extract_name_from_message(text)
    if extracted_name and not _is_invalid_name_candidate(extracted_name):
        _save_name(memory, extracted_name)
        clear_waiting_flag(memory)
        reply = f"Enchantée, {extracted_name.capitalize()}. Je retiens ton prénom."
        _save_exchange(memory, text, reply, "positive", "identity", "precise", "encourage")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "identity",
            "intent": "encourage",
            "reply": reply,
        }

    if _looks_like_user_name_question(lower):
        reply = _reply_with_name(memory)

        if reply == build_unknown_name_reply():
            set_last_bot_question(memory, reply, "ask_name")

        _save_exchange(memory, text, reply, "unknown", "identity", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    if "tu te souviens de moi" in lower or "tu te souviens de nos echanges" in lower or "tu te souviens de nos échanges" in lower:
        reply = _reply_memory(memory)
        _save_exchange(memory, text, reply, "unknown", "memory", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "memory",
            "intent": "reflect",
            "reply": reply,
        }

    if lower in HOW_ARE_YOU_PATTERNS:
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
    normalized_text = _normalize_user_text(text)
    ensure_context(memory)

    # 1. Règles directes prioritaires
    direct_result = _direct_rules(text, memory)
    if direct_result is not None:
        return direct_result

    # 2. Image prioritaire
    if should_use_image_tool(normalized_text):
        clear_waiting_flag(memory)

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

    # 3. Web prioritaire
    if should_use_web(normalized_text):
        clear_waiting_flag(memory)

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

    # 4. Code prioritaire
    if not _is_protected_chat_message(normalized_text) and should_use_code_tool(normalized_text):
        clear_waiting_flag(memory)

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

    # 5. Contexte vivant après les priorités
    contextual_result = _handle_contextual_reply(text, memory)
    if contextual_result is not None:
        return contextual_result

    # 6. Analyse générale
    analysis = analyze_text(text, memory)
    thought = think_about_message(text, memory, analysis)

    thought_payload = thought if isinstance(thought, dict) else None

    reply = build_final_response(
        analysis=analysis,
        memory=memory,
        thought=thought_payload,
    )

    llm_result = _call_llm_reply(text, memory)
    if llm_result is not None:
        reply = build_final_response(
            analysis=analysis,
            model_reply=llm_result["reply"],
            memory=memory,
            thought=thought_payload,
        )
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
        "thought_summary": thought if isinstance(thought, str) else "",
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
