import logging
import re
from difflib import SequenceMatcher
from typing import Any

from core.analyzer import analyze_text, normalize_text
from core.code_tool import build_code_result, should_use_code_tool
from core.config import LLM_HISTORY_LIMIT, OPENAI_API_KEY
from core.context import (
    clear_waiting_flag,
    close_riddle,
    ensure_context,
    get_last_question_type,
    get_riddle_answer,
    is_riddle_mode,
    set_last_bot_question,
    start_riddle,
) 

from core.image.image_tool import (
    edit_image_reply,
    generate_image_reply,
    should_use_image_edit_tool,
    should_use_image_tool,
)

from core.llm_client import build_zoe_system_prompt, create_llm_client
from core.memory import (
    add_message_to_history,
    apply_identity_context,
    clear_profile_name,
    get_last_messages,
    get_trusted_name,
    save_memory,
    set_profile_name,
    update_profile_from_analysis,
)

from core.responder import build_final_response
from core.thinker import think_about_message
from core.utils import current_datetime_string
from core.web_tool import build_web_reply, should_use_web


INTENT_PHONE_ACTION = "PHONE_ACTION"
INTENT_MESSAGE_ACTION = "MESSAGE_ACTION"
INTENT_NOTES_ACTION = "NOTES_ACTION"
INTENT_GAME = "GAME"
INTENT_IMAGE_EDIT_REQUEST = "IMAGE_EDIT_REQUEST"
INTENT_IMAGE_REQUEST = "IMAGE_REQUEST"
INTENT_WEB_SEARCH = "WEB_SEARCH"
INTENT_CODE_REQUEST = "CODE_REQUEST"
INTENT_CHAT = "CHAT"


logger = logging.getLogger("zoe.brain")

SIMPLE_INTENT_AI_NAME = "simple_ai_name"
SIMPLE_INTENT_USER_NAME = "simple_user_name"
SIMPLE_INTENT_WRONG_NAME = "simple_wrong_name"
SIMPLE_INTENT_GREETING = "simple_greeting"
SIMPLE_INTENT_THANKS = "simple_thanks"
SIMPLE_INTENT_HOW_ARE_YOU = "simple_how_are_you"

PROTECTED_CHAT_EXACT = {
    "salut",
    "salut zoe",
    "bonjour",
    "bonjour zoe",
    "hello",
    "coucou",
    "merci",
    "merci zoe",
    "merci beaucoup",
    "comment ca va",
    "comment Ã§a va",
    "qui es tu",
    "tu es qui",
    "ca va",
    "et toi",
}

PROTECTED_CHAT_CONTAINS = {
    "comment tu t'appelles",
    "comment tu t appelles",
    "tu t'appelles comment",
    "tu t appelles comment",
    "quel est ton nom",
    "comment je m'appelle",
    "comment je m appelle",
    "tu connais mon prenom",
    "tu connais mon prÃ©nom",
    "tu te souviens de mon prenom",
    "tu te souviens de mon prÃ©nom",
    "je m'appelle pas",
    "je m appelle pas",
    "ce n'est pas mon prenom",
    "ce n est pas mon prenom",
    "ce n'est pas mon prÃ©nom",
    "ce n est pas mon prÃ©nom",
    "tu te trompes de prenom",
    "tu te trompes de prÃ©nom",
    "rappelle toi de mon vrai nom",
    "rappelle-toi de mon vrai nom",
    "je suis triste",
    "je t'aime",
    "je t aime",
    "tu me manques",
    "j'ai besoin de parler",
    "j ai besoin de parler",
    "je vais mal",
}


PHONE_ACTION_EXPRESSIONS = {
    "cherche dans mes contacts",
    "dans mes contacts",
    "ouvre le contact",
    "ouvre ce contact",
    "ajoute au calendrier",
    "ajoute dans mon calendrier",
    "cree un evenement",
    "creer un evenement",
    "cree un rendez vous",
    "creer un rendez vous",
    "programme un rappel",
    "programme une alarme",
    "prepare un appel",
}

PHONE_ACTION_VERBS = {
    "appel",
    "appelle",
    "appeler",
    "contacte",
    "contacter",
    "telephone",
    "telephoner",
    "ouvre",
    "ouvrir",
    "ajoute",
    "ajouter",
    "cree",
    "creer",
    "programme",
    "programmer",
    "planifie",
    "planifier",
    "cherche",
    "chercher",
    "trouve",
    "trouver",
}

PHONE_ACTION_OBJECTS = {
    "contact",
    "contacts",
    "telephone",
    "numero",
    "appel",
    "calendrier",
    "evenement",
    "rendez vous",
    "rappel",
    "alarme",
    "anniversaire",
}

PHONE_ACTION_PREFIXES = (
    "appel ",
    "appelle ",
    "appeler ",
    "contacte ",
    "contacter ",
    "telephone ",
    "telephoner ",
    "numero de ",
    "ouvre le contact ",
    "ouvre contact ",
)

MESSAGE_ACTION_PATTERNS = {
    "envoie un message",
    "envoie un sms",
    "sms a",
    "ecris a",
    "message a",
    "texto a",
}

NOTES_ACTION_PATTERNS = {
    "note",
    "notes",
    "bloc notes",
    "bloc note",
    "blocnotes",
    "keep",
    "google keep",
    "mets dans mes notes",
    "mets ca dans mes notes",
    "cree une note",
    "ajoute une note",
    "liste de courses",
}

SIMPLE_AI_NAME_VARIANTS = {
    "comment tu t appelles",
    "tu t appelles comment",
    "c est quoi ton nom",
    "quel est ton nom",
    "qui es tu",
    "tu es qui",
    "tes qui",
    "t ki",
    "tki",
    "coman tu tapel",
    "comment tu tapel",
}

SIMPLE_USER_NAME_VARIANTS = {
    "comment je m appelle",
    "tu connais mon prenom",
    "tu te souviens de mon prenom",
    "c est quoi mon prenom",
    "quel est mon prenom",
}

SIMPLE_WRONG_NAME_VARIANTS = {
    "je m appelle pas",
    "ce n est pas mon prenom",
    "tu te trompes de prenom",
    "c est pas mon prenom",
}

SIMPLE_GREETING_VARIANTS = {
    "salut",
    "bonjour",
    "hello",
    "coucou",
    "slt",
    "bjr",
}

SIMPLE_THANKS_VARIANTS = {
    "merci",
    "merci beaucoup",
    "mercii",
    "merciii",
}

SIMPLE_HOW_ARE_YOU_VARIANTS = {
    "comment ca va",
    "ca va",
    "et toi",
    "toi ca va",
}

GAME_RIDDLE_PATTERNS = {
    "devinette",
    "propose moi une devinette",
    "propose-moi une devinette",
    "donne moi une devinette",
    "donne-moi une devinette",
    "fais moi une devinette",
    "fais-moi une devinette",
}

GAME_QUIZ_PATTERNS = {
    "quiz",
    "quiz rapide",
    "fais moi un quiz",
    "fais-moi un quiz",
    "jeu de questions",
    "question reponse",
    "question reponse amusante",
}

GAME_GENERAL_PATTERNS = {
    "lance un jeu",
    "jeu amusant",
    "mini jeu",
    "mini-jeu",
    "jeu fun",
    "jeu rapide",
    "surprends moi avec un jeu",
}

RIDDLE_FOLLOWUP_YES = {
    "oui",
    "oui encore",
    "encore",
    "une autre",
    "vas y",
    "vas-y",
    "ok",
    "d accord",
}

RIDDLE_FOLLOWUP_NO = {
    "non",
    "non merci",
    "stop",
    "arrete",
    "pas une autre",
}

RIDDLE_GIVE_UP_PATTERNS = {
    "je sais pas",
    "j sais pas",
    "je ne sais pas",
    "jsais pas",
    "aucune idee",
    "j abandonne",
    "abandon",
    "donne la reponse",
    "donne moi la reponse",
    "dis moi",
}

RIDDLE_BANK = [
    {
        "question": "Je suis leger comme une plume, mais meme le plus fort des hommes ne peut pas me tenir longtemps. Que suis-je ?",
        "answer": "le souffle",
        "accepted_answers": ["le souffle", "souffle", "ton souffle", "la respiration", "respiration"],
    },
    {
        "question": "Je suis toujours devant toi, mais tu ne peux jamais me rattraper. Qui suis-je ?",
        "answer": "le futur",
        "accepted_answers": ["le futur", "futur", "l avenir", "l'avenir", "avenir"],
    },
    {
        "question": "Qu'est-ce qui a des cles mais n'ouvre aucune porte ?",
        "answer": "un piano",
        "accepted_answers": ["un piano", "piano", "le piano"],
    },
    {
        "question": "Plus tu m'en prends, plus tu en laisses derriere toi. Qui suis-je ?",
        "answer": "des pas",
        "accepted_answers": ["des pas", "les pas", "pas", "tes pas"],
    },
]

QUIZ_QUESTION_BANK = [
    {
        "question": "Quel animal peut sauter plus haut qu'un immeuble ?",
        "choices": {
            "A": "Un kangourou",
            "B": "Un chat",
            "C": "Aucun, les immeubles ne sautent pas",
        },
        "answer": "C",
    },
    {
        "question": "Quel mois de l'annee compte 28 jours ?",
        "choices": {
            "A": "Fevrier seulement",
            "B": "Tous les mois",
            "C": "Janvier et fevrier",
        },
        "answer": "B",
    },
    {
        "question": "Que peux-tu casser sans jamais le toucher ?",
        "choices": {
            "A": "Le silence",
            "B": "Une vitre",
            "C": "Une chaise",
        },
        "answer": "A",
    },
    {
        "question": "Combien y a-t-il de lettres dans le mot 'alphabet' ?",
        "choices": {
            "A": "7",
            "B": "8",
            "C": "9",
        },
        "answer": "B",
    },
    {
        "question": "Qu'est-ce qui monte, mais ne redescend jamais ?",
        "choices": {
            "A": "L'age",
            "B": "La pluie",
            "C": "Une echelle",
        },
        "answer": "A",
    },
]


def _looks_like_riddle_request(text: str) -> bool:
    if should_use_code_tool(text):
        return False
    return _contains_any(text, GAME_RIDDLE_PATTERNS)


def _looks_like_quiz_request(text: str) -> bool:
    if should_use_code_tool(text):
        return False
    return _contains_any(text, GAME_QUIZ_PATTERNS)


def _looks_like_game_request(text: str) -> bool:
    if should_use_code_tool(text):
        return False
    return (
        _looks_like_riddle_request(text)
        or _looks_like_quiz_request(text)
        or _contains_any(text, GAME_GENERAL_PATTERNS)
    )


def _pick_riddle(memory: dict) -> dict[str, str | list[str]]:
    recent_count = len(get_last_messages(memory, limit=max(len(RIDDLE_BANK), 1)))
    return RIDDLE_BANK[recent_count % len(RIDDLE_BANK)]


def _format_riddle_prompt(question: str) -> str:
    return f"Voici ta devinette :\n{question}"


def _format_quiz_question(title: str, question: dict[str, Any], display_index: int, total: int) -> str:
    choice_lines = []
    for key, value in question.get("choices", {}).items():
        choice_lines.append(f"{key}. {value}")

    return (
        f"{title} - Question {display_index}/{total}\n"
        f"{question.get('question', '')}\n"
        + "\n".join(choice_lines)
    ).strip()


def _build_game_result(reply: str, intent: str = "encourage") -> dict[str, Any]:
    return {
        "emotion": "positive",
        "precision": "precise",
        "topic": "fun",
        "intent": intent,
        "reply": reply,
        "tool_type": "game",
    }


def _start_riddle_session(memory: dict) -> dict[str, Any]:
    riddle = _pick_riddle(memory)
    question = str(riddle.get("question", "")).strip()
    answer = str(riddle.get("answer", "")).strip()
    accepted_answers = [
        item
        for item in riddle.get("accepted_answers", [])
        if isinstance(item, str) and item.strip()
    ] or [answer]
    start_riddle(memory, question, answer, accepted_answers)
    return _build_game_result(_format_riddle_prompt(question))


def _start_quiz_session(memory: dict) -> dict[str, Any]:
    questions = []
    for item in QUIZ_QUESTION_BANK:
        if not isinstance(item, dict):
            continue
        questions.append(
            {
                "question": str(item.get("question", "")).strip(),
                "choices": dict(item.get("choices", {})),
                "answer": str(item.get("answer", "")).strip().upper(),
            }
        )

    title = "Quiz rapide"
    start_quiz(memory, title, questions)
    first_question = get_quiz_question(memory) or {}
    reply = _format_quiz_question(
        title=title,
        question=first_question,
        display_index=1,
        total=get_quiz_total(memory),
    )
    return _build_game_result(reply)


def _normalize_game_answer(text: str) -> str:
    cleaned = _normalize_simple_text(text)
    prefixes = (
        "c est ",
        "cest ",
        "je dirais ",
        "je pense que c est ",
        "je pense que c est la ",
        "la reponse est ",
        "la reponse c est ",
        "reponse ",
    )

    for prefix in prefixes:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()

    return cleaned


def _matches_expected_answer(user_message: str, accepted_answers: list[str]) -> bool:
    guess = _normalize_game_answer(user_message)
    if not guess:
        return False

    for accepted in accepted_answers:
        normalized_answer = _normalize_game_answer(accepted)
        if not normalized_answer:
            continue
        if guess == normalized_answer:
            return True
        if guess.endswith(f" {normalized_answer}"):
            return True
        if normalized_answer.endswith(f" {guess}") and len(guess.split()) >= 2:
            return True

    return False


def _extract_quiz_choice(user_message: str, question: dict[str, Any]) -> str | None:
    guess = _normalize_game_answer(user_message).upper()
    if not guess:
        return None

    choices = question.get("choices", {})
    if not isinstance(choices, dict):
        return None

    tokens = guess.split()
    if tokens:
        first_token = tokens[0].strip(" .)!?:;,-")
        if first_token in choices:
            return first_token

    for key, value in choices.items():
        normalized_choice = _normalize_game_answer(str(value))
        if guess.lower() == normalized_choice:
            return str(key).upper()
        if guess.lower().endswith(normalized_choice):
            return str(key).upper()

    return None


def _contains_any(text: str, patterns: set[str]) -> bool:
    return any(pattern in text for pattern in patterns)


def _normalize_simple_text(text: str) -> str:
    cleaned = normalize_text(text)
    cleaned = cleaned.replace("'", " ").replace("â€™", " ")
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _compact_simple_text(text: str) -> str:
    return _normalize_simple_text(text).replace(" ", "")


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _has_token_like(tokens: list[str], variants: set[str], threshold: float = 0.72) -> bool:
    for token in tokens:
        for variant in variants:
            if token == variant:
                return True
            if len(token) >= 2 and len(variant) >= 2:
                if token.startswith(variant) or variant.startswith(token):
                    return True
                if _similarity(token, variant) >= threshold:
                    return True
    return False


def _matches_variant_family(text: str, variants: set[str], threshold: float = 0.78) -> bool:
    compact_text = _compact_simple_text(text)
    if not compact_text:
        return False

    for variant in variants:
        if compact_text == variant.replace(" ", ""):
            return True
        if _similarity(compact_text, variant.replace(" ", "")) >= threshold:
            return True
    return False


def _detect_simple_intent(text: str) -> str | None:
    normalized = _normalize_simple_text(text)
    if not normalized:
        return None

    tokens = normalized.split()

    if _matches_variant_family(normalized, SIMPLE_WRONG_NAME_VARIANTS, threshold=0.76):
        return SIMPLE_INTENT_WRONG_NAME

    if (
        _matches_variant_family(normalized, SIMPLE_AI_NAME_VARIANTS, threshold=0.72)
        or (
            _has_token_like(tokens, {"comment", "coman", "komen", "koment"}, threshold=0.62)
            and _has_token_like(tokens, {"tu", "toi", "t"}, threshold=0.8)
            and _has_token_like(tokens, {"appelle", "appelles", "apelle", "apel", "tapel", "tappelle"}, threshold=0.62)
        )
        or (
            _has_token_like(tokens, {"nom", "prenom", "name"}, threshold=0.72)
            and _has_token_like(tokens, {"ton", "ta", "tes"}, threshold=0.72)
        )
        or (
            _has_token_like(tokens, {"qui", "ki"}, threshold=0.6)
            and _has_token_like(tokens, {"tu", "toi", "t", "tes", "es"}, threshold=0.6)
            and len(tokens) <= 4
        )
    ):
        return SIMPLE_INTENT_AI_NAME

    if (
        _matches_variant_family(normalized, SIMPLE_USER_NAME_VARIANTS, threshold=0.76)
        or (
            _has_token_like(tokens, {"comment", "quel", "quoi"}, threshold=0.68)
            and (
                _has_token_like(tokens, {"prenom", "nom"}, threshold=0.72)
                or (
                    _has_token_like(tokens, {"appelle", "apelle", "apel"}, threshold=0.62)
                    and _has_token_like(tokens, {"je", "m", "mon"}, threshold=0.72)
                )
            )
        )
    ):
        return SIMPLE_INTENT_USER_NAME

    if (
        _matches_variant_family(normalized, SIMPLE_GREETING_VARIANTS, threshold=0.82)
        or (len(tokens) <= 3 and _has_token_like(tokens, SIMPLE_GREETING_VARIANTS, threshold=0.7))
    ):
        return SIMPLE_INTENT_GREETING

    if (
        _matches_variant_family(normalized, SIMPLE_THANKS_VARIANTS, threshold=0.82)
        or (len(tokens) <= 4 and _has_token_like(tokens, {"merci", "mercii", "merciii"}, threshold=0.7))
    ):
        return SIMPLE_INTENT_THANKS

    if (
        _matches_variant_family(normalized, SIMPLE_HOW_ARE_YOU_VARIANTS, threshold=0.78)
        or (
            _has_token_like(tokens, {"comment", "ca", "sa", "et"}, threshold=0.72)
            and _has_token_like(tokens, {"va", "toi"}, threshold=0.72)
        )
    ):
        return SIMPLE_INTENT_HOW_ARE_YOU

    return None


def _looks_like_phone_action(text: str) -> bool:
    if any(text.startswith(prefix) for prefix in PHONE_ACTION_PREFIXES):
        return True

    if _contains_any(text, PHONE_ACTION_EXPRESSIONS):
        return True

    has_phone_verb = _contains_any(text, PHONE_ACTION_VERBS)
    has_phone_object = _contains_any(text, PHONE_ACTION_OBJECTS)

    if has_phone_verb and has_phone_object:
        return True

    return False


def _looks_like_message_action(text: str) -> bool:
    return any(pattern in text for pattern in MESSAGE_ACTION_PATTERNS)


def _looks_like_notes_action(text: str) -> bool:
    return any(pattern in text for pattern in NOTES_ACTION_PATTERNS)


def _looks_like_protected_chat(text: str) -> bool:
    compact_text = text.strip(" .!?;,:")
    return (
        _detect_simple_intent(compact_text) is not None
        or
        compact_text in PROTECTED_CHAT_EXACT
        or any(pattern in compact_text for pattern in PROTECTED_CHAT_CONTAINS)
    )


def _get_name(memory: dict) -> str:
    return get_trusted_name(memory)


def _save_name(memory: dict, name: str) -> None:
    set_profile_name(memory, name, source="declared")


def _reply_with_name(memory: dict) -> str:
    name = _get_name(memory)

    if name:
        return f"Tu t'appelles {name}. Je m'en souviens."

    return "Je ne connais pas encore ton prenom. Tu peux me le dire si tu veux."


def _reply_memory(memory: dict) -> str:
    name = _get_name(memory)
    last_emotion = memory.get("last_emotion", "unknown")
    last_topic = memory.get("last_topic", "general")
    parts: list[str] = []

    if name:
        parts.append(f"Je me souviens que tu t'appelles {name}.")

    if last_emotion != "unknown":
        parts.append(f"La derniere emotion que j'ai retenue, c'est {last_emotion}.")

    if last_topic != "general":
        parts.append(f"Le dernier sujet important que j'ai retenu, c'est {last_topic}.")

    if not parts:
        return "Je garde une memoire legere de nos echanges, mais elle est encore en train de se construire."

    return " ".join(parts)


def _greeting_reply(memory: dict) -> str:
    name = _get_name(memory)
    last_emotion = memory.get("last_emotion", "unknown")

    if name and last_emotion in {"negative", "stress", "fatigue", "sadness"}:
        return f"Salut {name}. Je suis contente de te revoir. Ca va un peu mieux aujourd'hui ?"

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
    conversation: list[dict[str, str]] = []

    for item in get_last_messages(memory, limit=LLM_HISTORY_LIMIT):
        user_message = item.get("user_message", "").strip()
        zoe_reply = item.get("zoe_reply", "").strip()

        if user_message:
            conversation.append({"role": "user", "content": user_message})

        if zoe_reply:
            conversation.append({"role": "assistant", "content": zoe_reply})

    return conversation


def classify_intent(
    user_message: str,
    attached_image_url: str | None = None,
) -> str:
    text = normalize_text(user_message)
    has_attached_image = bool((attached_image_url or "").strip())
    image_edit_detected = should_use_image_edit_tool(
        message=text,
        has_attached_image=has_attached_image,
    )
    image_create_detected = should_use_image_tool(text)
    routed_preview = (
        "image_edit"
        if image_edit_detected
        else "image_create"
        if image_create_detected
        else "text"
    )

    logger.info(
        "image-routing attached_image=%s image_create=%s image_edit=%s route=%s source_image_provided=%s",
        has_attached_image,
        image_create_detected,
        image_edit_detected,
        routed_preview,
        has_attached_image,
    )

    if _looks_like_protected_chat(text):
        return INTENT_CHAT

    if _looks_like_phone_action(text):
        return INTENT_PHONE_ACTION

    if _looks_like_message_action(text):
        return INTENT_MESSAGE_ACTION

    if _looks_like_notes_action(text):
        return INTENT_NOTES_ACTION

    if _looks_like_game_request(text):
        return INTENT_GAME

    if image_edit_detected:
        return INTENT_IMAGE_EDIT_REQUEST

    if image_create_detected:
        return INTENT_IMAGE_REQUEST

    if should_use_web(text):
        return INTENT_WEB_SEARCH

    if should_use_code_tool(text):
        return INTENT_CODE_REQUEST

    return INTENT_CHAT


def _is_deep_emotional_message(text: str, analysis: dict) -> bool:
    lower = normalize_text(text)
    topic = analysis.get("topic", "general")

    if topic in {"affection", "gratitude", "support", "solitude", "couple"}:
        return True

    return any(
        marker in lower
        for marker in {
            "je t'aime",
            "je t aime",
            "tu me manques",
            "j'ai besoin de parler",
            "j ai besoin de parler",
            "je vais mal",
            "j'ai peur",
            "j ai peur",
            "je suis perdu",
            "je suis perdue",
            "merci zoe",
        }
    )


def _should_attempt_llm(user_input: str, analysis: dict) -> bool:
    if not OPENAI_API_KEY:
        return False

    text = user_input.strip()
    lower = normalize_text(text)
    word_count = len(text.split())
    emotion = analysis.get("emotion", "unknown")
    precision = analysis.get("precision", "vague")
    topic = analysis.get("topic", "general")

    if _is_deep_emotional_message(text, analysis):
        return True

    if word_count <= 4 and emotion != "unknown":
        return False

    if "?" in text:
        return True

    if any(
        marker in lower
        for marker in {
            "pourquoi",
            "comment",
            "peux tu",
            "tu peux",
            "que penses tu",
            "qu est ce que tu penses",
        }
    ):
        return True

    if emotion == "unknown" or topic in {"affection", "gratitude", "support"}:
        return True

    return precision == "precise" and word_count >= 8


def _call_llm_reply(user_input: str, memory: dict) -> dict | None:
    try:
        user_name = _get_name(memory)
        conversation = _build_conversation_history(memory)
        client = create_llm_client()
        result = client.ask(
            user_message=user_input,
            system_prompt=build_zoe_system_prompt(user_name=user_name),
            conversation=conversation,
            temperature=0.8,
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


def _alternative_reply_from_analysis(memory: dict, analysis: dict) -> str:
    emotion = analysis.get("emotion", "unknown")
    topic = analysis.get("topic", "general")
    name = _get_name(memory)

    if topic == "affection":
        return "C'est touchant a lire. Je suis la avec toi, avec beaucoup de douceur."

    if topic == "gratitude":
        return "Merci a toi. Si ma presence te fait du bien, j'en suis contente."

    if topic == "support":
        return f"Je suis la{', ' + name if name else ''}. Tu peux me dire les choses a ton rythme."

    if emotion in {"negative", "sadness"}:
        return f"Je suis la{', ' + name if name else ''}. Tu veux me dire ce qui te pese le plus ?"

    if emotion == "stress":
        return "On peut poser ca calmement. Qu'est-ce qui te met le plus sous pression ?"

    if emotion == "fatigue":
        return "On peut prendre ca doucement. Cette fatigue vient plutot du corps ou du mental ?"

    if emotion in {"positive", "joy"}:
        return "Ca fait plaisir a lire. Quel moment t'a fait le plus de bien ?"

    return f"Je t'ecoute{', ' + name if name else ''}. Quel point te semble le plus important ?"


def _avoid_repetitive_reply(reply: str, memory: dict, analysis: dict) -> str:
    recent_replies = {
        item.get("zoe_reply", "").strip().lower()
        for item in get_last_messages(memory, limit=3)
        if isinstance(item, dict)
    }

    if reply.strip().lower() not in recent_replies:
        return reply

    alternative = _alternative_reply_from_analysis(memory, analysis)
    if alternative.strip().lower() not in recent_replies:
        return alternative

    return reply


def _handle_contextual_reply(text: str, memory: dict) -> dict | None:
    lower = normalize_text(text)
    plain_lower = _normalize_simple_text(text)
    ensure_context(memory)

    if is_riddle_mode(memory):
        answer = get_riddle_answer(memory) or "un piano"
        accepted_answers = get_riddle_answers(memory) or [answer]

        if plain_lower in RIDDLE_GIVE_UP_PATTERNS:
            close_riddle(memory)
            reply = f"Pas grave.\nLa bonne reponse etait : {answer}.\nTu veux une autre devinette ?"
            set_last_bot_question(memory, reply, "riddle_followup")
            _save_exchange(memory, text, reply, "unknown", "fun", "precise", "reflect")
            return _build_game_result(reply, intent="reflect")

        if _matches_expected_answer(text, accepted_answers):
            close_riddle(memory)
            reply = f"Bravo, bonne reponse.\nLa bonne reponse etait bien : {answer}.\nTu veux une autre devinette ?"
            set_last_bot_question(memory, reply, "riddle_followup")
            _save_exchange(memory, text, reply, "positive", "fun", "precise", "encourage")
            return _build_game_result(reply)

        close_riddle(memory)
        reply = f"Pas cette fois.\nLa bonne reponse etait : {answer}.\nTu veux une autre devinette ?"
        set_last_bot_question(memory, reply, "riddle_followup")
        _save_exchange(memory, text, reply, "unknown", "fun", "precise", "reflect")
        return _build_game_result(reply, intent="reflect")

    if is_quiz_mode(memory):
        current_question = get_quiz_question(memory)
        if current_question is None:
            close_quiz(memory)
            return None

        selected_choice = _extract_quiz_choice(text, current_question)
        if selected_choice is None:
            reply = "Reponds simplement par A, B, C ou D. Tu peux aussi ecrire la reponse choisie."
            _save_exchange(memory, text, reply, "unknown", "fun", "precise", "clarify")
            return _build_game_result(reply, intent="clarify")

        correct_choice = str(current_question.get("answer", "")).upper()
        choices = current_question.get("choices", {})
        correct_label = f"{correct_choice}. {choices.get(correct_choice, '')}".strip()
        answered_correctly = selected_choice == correct_choice
        next_question = advance_quiz(memory, answered_correctly)

        if next_question is None:
            score = get_quiz_score(memory)
            total = get_quiz_total(memory)
            close_quiz(memory)
            lead = "Bonne reponse." if answered_correctly else f"Incorrect.\nLa bonne reponse etait : {correct_label}."
            reply = f"{lead}\n\nQuiz termine.\nTon score : {score}/{total}"
            _save_exchange(memory, text, reply, "positive", "fun", "precise", "encourage")
            return _build_game_result(reply)

        next_index = get_quiz_index(memory) + 1
        total = get_quiz_total(memory)
        next_block = _format_quiz_question(
            title=get_quiz_title(memory) or "Quiz rapide",
            question=next_question,
            display_index=next_index,
            total=total,
        )
        lead = "Bonne reponse." if answered_correctly else f"Incorrect.\nLa bonne reponse etait : {correct_label}."
        reply = f"{lead}\n\n{next_block}"
        _save_exchange(memory, text, reply, "positive", "fun", "precise", "encourage")
        return _build_game_result(reply)

    qtype = get_last_question_type(memory)

    if qtype == "riddle_followup":
        if plain_lower in RIDDLE_FOLLOWUP_YES:
            result = _start_riddle_session(memory)
            _save_exchange(memory, text, result["reply"], "positive", "fun", "precise", "encourage")
            return result

        if plain_lower in RIDDLE_FOLLOWUP_NO:
            clear_waiting_flag(memory)
            reply = "D'accord, j'arrete les devinettes pour le moment."
            _save_exchange(memory, text, reply, "unknown", "fun", "precise", "reflect")
            return _build_game_result(reply, intent="reflect")

        clear_waiting_flag(memory)

    if qtype in {"emotional_followup", "general_followup"}:
        if lower in {"oui", "oui un peu", "un peu", "ca va un peu mieux", "mieux"}:
            clear_waiting_flag(memory)
            reply = "Je suis contente de lire ca. Qu'est-ce qui t'aide le plus en ce moment ?"
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
            reply = "D'accord. On peut prendre le temps. Qu'est-ce qui te pese le plus maintenant ?"
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
    lower = normalize_text(text)
    plain_lower = lower.strip(" .!?;,:")
    ensure_context(memory)
    simple_intent = _detect_simple_intent(text)

    if simple_intent == SIMPLE_INTENT_WRONG_NAME:
        wrong_name = text.split("pas", 1)[-1].strip(" .,!?:;")
        clear_profile_name(memory)
        reply = "D'accord, merci de me l'avoir dit. Je ne vais plus utiliser ce prenom."
        if wrong_name and wrong_name.lower() != text.lower():
            reply = f"D'accord, merci de me l'avoir dit. Je ne vais plus utiliser {wrong_name}."
        _save_exchange(memory, text, reply, "unknown", "identity", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    if simple_intent == SIMPLE_INTENT_AI_NAME:
        reply = "Je m'appelle Zoe. Je suis une intelligence artificielle."
        _save_exchange(memory, text, reply, "positive", "identity", "precise", "reflect")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    if simple_intent == SIMPLE_INTENT_USER_NAME:
        reply = _reply_with_name(memory)
        _save_exchange(memory, text, reply, "unknown", "identity", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    if simple_intent == SIMPLE_INTENT_GREETING:
        reply = _greeting_reply(memory)

        if "ca va un peu mieux" in normalize_text(reply):
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

    if simple_intent == SIMPLE_INTENT_THANKS:
        reply = "Avec plaisir."
        _save_exchange(memory, text, reply, "positive", "conversation", "precise", "reflect")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "conversation",
            "intent": "reflect",
            "reply": reply,
        }

    if simple_intent == SIMPLE_INTENT_HOW_ARE_YOU:
        reply = "Moi ca va bien. Merci de me le demander."
        _save_exchange(memory, text, reply, "positive", "conversation", "precise", "reflect")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "conversation",
            "intent": "reflect",
            "reply": reply,
        }

    if plain_lower.startswith("je m'appelle pas ") or plain_lower.startswith("je m appelle pas "):
        wrong_name = text.split("pas", 1)[-1].strip(" .,!?:;")
        clear_profile_name(memory)
        reply = "D'accord, merci de me l'avoir dit. Je ne vais plus utiliser ce prenom."
        if wrong_name:
            reply = (
                f"D'accord, merci de me l'avoir dit. Je ne vais plus utiliser {wrong_name}."
            )
        _save_exchange(memory, text, reply, "unknown", "identity", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    if plain_lower in {
        "ce n'est pas mon prenom",
        "ce n est pas mon prenom",
        "ce n'est pas mon prÃ©nom",
        "ce n est pas mon prÃ©nom",
        "tu te trompes de prenom",
        "tu te trompes de prÃ©nom",
    }:
        clear_profile_name(memory)
        reply = "D'accord, merci de me l'avoir dit. Je ne vais plus utiliser ce prenom."
        _save_exchange(memory, text, reply, "unknown", "identity", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    if plain_lower in {
        "comment tu t'appelles",
        "comment tu t appelles",
        "tu t'appelles comment",
        "tu t appelles comment",
        "quel est ton nom",
        "c'est quoi ton prenom",
        "c est quoi ton prenom",
        "qui es tu",
        "tu es qui",
        "tu es quoi",
    }:
        reply = "Je m'appelle Zoe. Je suis une intelligence artificielle."
        _save_exchange(memory, text, reply, "positive", "identity", "precise", "reflect")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    if plain_lower in {"et toi", "toi", "et toi alors"}:
        reply = "Moi ca va bien. Merci de me le demander."
        _save_exchange(memory, text, reply, "positive", "conversation", "precise", "reflect")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "conversation",
            "intent": "reflect",
            "reply": reply,
        }

    if plain_lower in {
        "et toi comment tu t'appelles",
        "et toi comment tu t appelles",
        "toi comment tu t'appelles",
        "toi comment tu t appelles",
        "et toi tu t'appelles comment",
        "et toi tu t appelles comment",
        "toi tu t'appelles comment",
        "toi tu t appelles comment",
    }:
        reply = "Je m'appelle Zoe. Je suis une intelligence artificielle."
        _save_exchange(memory, text, reply, "positive", "identity", "precise", "reflect")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    if _looks_like_riddle_request(plain_lower):
        result = _start_riddle_session(memory)
        _save_exchange(memory, text, result["reply"], "positive", "fun", "precise", "encourage")
        return result

    if _looks_like_quiz_request(plain_lower):
        result = _start_quiz_session(memory)
        _save_exchange(memory, text, result["reply"], "positive", "fun", "precise", "encourage")
        return result

    if plain_lower in {"salut", "salut zoe", "bonjour", "hello", "coucou"}:
        reply = _greeting_reply(memory)

        if "ca va un peu mieux" in normalize_text(reply):
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

    if plain_lower in {
        "comment je m'appelle",
        "comment je m appelles",
        "tu connais mon prenom",
        "tu te souviens de mon prenom",
        "c'est quoi mon prenom",
        "c est quoi mon prenom",
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

    if "tu te souviens de moi" in plain_lower or "tu te souviens de nos echanges" in plain_lower:
        reply = _reply_memory(memory)
        _save_exchange(memory, text, reply, "unknown", "memory", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "memory",
            "intent": "reflect",
            "reply": reply,
        }

    if plain_lower.startswith("je m'appelle ") or plain_lower.startswith("je m appelle "):
        name = text.split(" ", 3)[-1].strip().split(" ")[0]
        if name:
            _save_name(memory, name)
            stored_name = _get_name(memory) or name.strip()
            reply = f"Enchantee {stored_name}. Je retiens ton prenom."
            _save_exchange(memory, text, reply, "positive", "identity", "precise", "encourage")
            return {
                "emotion": "positive",
                "precision": "precise",
                "topic": "identity",
                "intent": "encourage",
                "reply": reply,
            }

    if plain_lower.startswith("mon prenom c'est ") or plain_lower.startswith("mon prenom c est "):
        name = text.split(" ", 4)[-1].strip().split(" ")[0]
        if name:
            _save_name(memory, name)
            stored_name = _get_name(memory) or name.strip()
            reply = f"Merci {stored_name}. Je retiens ton prenom."
            _save_exchange(memory, text, reply, "positive", "identity", "precise", "encourage")
            return {
                "emotion": "positive",
                "precision": "precise",
                "topic": "identity",
                "intent": "encourage",
                "reply": reply,
            }

    if plain_lower in {"cava", "ca va"}:
        name = _get_name(memory)
        if name:
            reply = f"Oui, ca va bien. Merci {name}. Et toi, comment tu te sens aujourd'hui ?"
        else:
            reply = "Oui, ca va bien. Merci. Et toi, comment tu te sens aujourd'hui ?"

        set_last_bot_question(memory, reply, "general_followup")
        _save_exchange(memory, text, reply, "positive", "conversation", "vague", "ask_open_question")
        return {
            "emotion": "positive",
            "precision": "vague",
            "topic": "conversation",
            "intent": "ask_open_question",
            "reply": reply,
        }

    if plain_lower == "brain thinker":
        reply = "Mon cerveau avec reflexion est bien actif."
        _save_exchange(memory, text, reply, "positive", "system", "precise", "encourage")
        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "system",
            "intent": "encourage",
            "reply": reply,
        }

    if plain_lower == "brain v5":
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


def _build_phone_action_result(user_input: str) -> dict:
    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": "phone_action",
        "intent": "clarify",
        "reply": (
            "Cette demande correspond a une action telephone. "
            "Dans l'application Zoe IA, elle doit etre geree par les outils Android locaux."
        ),
        "thought_summary": "intention d'action telephone detectee",
        "strategy": "phone_action",
        "tone": "practical",
        "tool_type": "phone_action",
        "tool_input": user_input,
    }


def _build_android_local_action_result(
    user_input: str,
    topic: str,
    tool_type: str,
    thought_summary: str,
    reply: str,
) -> dict:
    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": topic,
        "intent": "clarify",
        "reply": reply,
        "thought_summary": thought_summary,
        "strategy": tool_type,
        "tone": "practical",
        "tool_type": tool_type,
        "tool_input": user_input,
    }


def process_user_message(
    user_input: str,
    memory: dict,
    identity: dict | None = None,
    attached_image_url: str | None = None,
    attached_image_mime_type: str | None = None,
) -> dict:
    text = user_input.strip()
    ensure_context(memory)
    identity = identity or {}
    apply_identity_context(
        memory=memory,
        account_key=str(identity.get("account_key", "")).strip(),
        user_name=str(identity.get("user_name", "")).strip(),
    )
    user_uid = str(identity.get("user_uid", "")).strip()
    logger.info(
        "identity-context uid_present=%s account_key_present=%s attached_image=%s",
        bool(user_uid),
        bool(str(identity.get("account_key", "")).strip()),
        bool((attached_image_url or "").strip()),
    )

    contextual_result = _handle_contextual_reply(text, memory)
    if contextual_result is not None:
        return contextual_result

    direct_result = _direct_rules(text, memory)
    if direct_result is not None:
        return direct_result

    detected_intent = classify_intent(
        text,
        attached_image_url=attached_image_url,
    )
    logger.info(
        "intent-selected intent=%s attached_image=%s source_image_provided=%s",
        detected_intent,
        bool((attached_image_url or "").strip()),
        bool((attached_image_url or "").strip()),
    )

    if detected_intent == INTENT_PHONE_ACTION:
        result = _build_phone_action_result(text)
        _save_exchange(
            memory=memory,
            user_text=text,
            reply=result["reply"],
            emotion=result["emotion"],
            topic=result["topic"],
            precision=result["precision"],
            intent=result["intent"],
        )
        return result

    if detected_intent == INTENT_MESSAGE_ACTION:
        result = _build_android_local_action_result(
            user_input=text,
            topic="message_action",
            tool_type="message_action",
            thought_summary="intention d'envoi de message detectee",
            reply=(
                "Cette demande correspond a un message a preparer. "
                "Dans l'application Zoe IA, elle doit etre geree par les outils Android locaux."
            ),
        )
        _save_exchange(
            memory=memory,
            user_text=text,
            reply=result["reply"],
            emotion=result["emotion"],
            topic=result["topic"],
            precision=result["precision"],
            intent=result["intent"],
        )
        return result

    if detected_intent == INTENT_NOTES_ACTION:
        result = _build_android_local_action_result(
            user_input=text,
            topic="notes_action",
            tool_type="notes_action",
            thought_summary="intention de note detectee",
            reply=(
                "Cette demande correspond a une note a preparer. "
                "Dans l'application Zoe IA, elle doit etre geree par les outils Android locaux."
            ),
        )
        _save_exchange(
            memory=memory,
            user_text=text,
            reply=result["reply"],
            emotion=result["emotion"],
            topic=result["topic"],
            precision=result["precision"],
            intent=result["intent"],
        )
        return result

    if detected_intent == INTENT_GAME:
        if _looks_like_quiz_request(normalize_text(text)):
            result = _start_quiz_session(memory)
        else:
            result = _start_riddle_session(memory)

        _save_exchange(
            memory=memory,
            user_text=text,
            reply=result["reply"],
            emotion=result["emotion"],
            topic=result["topic"],
            precision=result["precision"],
            intent=result["intent"],
        )
        return result

    if detected_intent == INTENT_IMAGE_EDIT_REQUEST:
        image_result = edit_image_reply(
            user_message=text,
            source_image_url=attached_image_url,
            source_image_mime_type=attached_image_mime_type,
            conversation=_build_conversation_history(memory),
            user_uid=user_uid,
            account_key=str(identity.get("account_key", "")).strip(),
        )
        result = {
            "emotion": image_result.get("emotion", "unknown"),
            "precision": image_result.get("precision", "precise"),
            "topic": image_result.get("topic", "image"),
            "intent": image_result.get("intent", "edit"),
            "reply": image_result["reply"],
            "thought_summary": "modification d'image activee",
            "strategy": "image_edit",
            "tone": "creative",
            "tool_type": "image",
            "image_base64": image_result.get("image_base64"),
            "image_url": image_result.get("image_url"),
            "image_mime_type": image_result.get("image_mime_type"),
            "image_prompt": image_result.get("image_prompt"),
        }
        _save_exchange(
            memory=memory,
            user_text=text,
            reply=result["reply"],
            emotion=result["emotion"],
            topic=result["topic"],
            precision=result["precision"],
            intent=result["intent"],
        )
        return result

    if detected_intent == INTENT_IMAGE_REQUEST:
        image_result = generate_image_reply(
            user_message=text,
            conversation=_build_conversation_history(memory),
            user_uid=user_uid,
            account_key=str(identity.get("account_key", "")).strip(),
        )
        result = {
            "emotion": image_result.get("emotion", "unknown"),
            "precision": image_result.get("precision", "precise"),
            "topic": image_result.get("topic", "image"),
            "intent": image_result.get("intent", "create"),
            "reply": image_result["reply"],
            "thought_summary": "generation d'image activee",
            "strategy": "image_create",
            "tone": "creative",
            "tool_type": "image",
            "image_base64": image_result.get("image_base64"),
            "image_url": image_result.get("image_url"),
            "image_mime_type": image_result.get("image_mime_type"),
            "image_prompt": image_result.get("image_prompt"),
        }
        _save_exchange(
            memory=memory,
            user_text=text,
            reply=result["reply"],
            emotion=result["emotion"],
            topic=result["topic"],
            precision=result["precision"],
            intent=result["intent"],
        )
        return result

    if detected_intent == INTENT_WEB_SEARCH:
        user_name = _get_name(memory)
        conversation = _build_conversation_history(memory)
        web_result = build_web_reply(
            user_message=text,
            user_name=user_name,
            conversation=conversation,
        )
        result = {
            "emotion": web_result.get("emotion", "unknown"),
            "precision": web_result.get("precision", "precise"),
            "topic": web_result.get("topic", "web"),
            "intent": web_result.get("intent", "clarify"),
            "reply": web_result["reply"],
            "thought_summary": "mode recherche web active",
            "strategy": "web_search",
            "tone": "informative",
            "tool_type": "web",
        }
        _save_exchange(
            memory=memory,
            user_text=text,
            reply=result["reply"],
            emotion=result["emotion"],
            topic=result["topic"],
            precision=result["precision"],
            intent=result["intent"],
        )
        return result

    if detected_intent == INTENT_CODE_REQUEST:
        conversation = _build_conversation_history(memory)
        code_result = build_code_result(
            user_message=text,
            conversation=conversation,
        )
        result = {
            "emotion": code_result.get("emotion", "positive"),
            "precision": code_result.get("precision", "precise"),
            "topic": code_result.get("topic", "code"),
            "intent": code_result.get("intent", "reflect"),
            "reply": code_result["reply"],
            "thought_summary": "mode code active",
            "strategy": "code_generation",
            "tone": "technical",
            "tool_type": "code",
            "language": code_result.get("language"),
        }
        _save_exchange(
            memory=memory,
            user_text=text,
            reply=result["reply"],
            emotion=result["emotion"],
            topic=result["topic"],
            precision=result["precision"],
            intent=result["intent"],
        )
        return result

    analysis = analyze_text(text)
    thought = think_about_message(
        user_input=text,
        analysis=analysis,
        memory=memory,
    )

    llm_result = None
    if _should_attempt_llm(text, analysis):
        llm_result = _call_llm_reply(text, memory)

    llm_reply = llm_result["reply"] if llm_result and llm_result.get("reply") else None

    reply = build_final_response(
        analysis=analysis,
        model_reply=llm_reply,
        memory=memory,
        thought=thought,
    )
    reply = _avoid_repetitive_reply(reply, memory, analysis)

    if reply.endswith("?"):
        set_last_bot_question(memory, reply, "general_followup")
    else:
        clear_waiting_flag(memory)

    result = {
        "emotion": analysis.get("emotion", "unknown"),
        "precision": analysis.get("precision", "vague"),
        "topic": analysis.get("topic", "general"),
        "intent": analysis.get("intent", "clarify"),
        "reply": reply,
        "thought_summary": thought.get("thought_summary", ""),
        "strategy": thought.get("strategy", ""),
        "tone": thought.get("tone", ""),
        "tool_type": "chat",
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
