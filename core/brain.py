import logging
import re
from difflib import SequenceMatcher
from typing import Any

from core.analyzer import analyze_text, normalize_text
from core.code_tool import build_code_result, should_use_code_tool
from core.config import LLM_HISTORY_LIMIT
from core.context import (
    advance_quiz,
    clear_waiting_flag,
    close_quiz,
    close_riddle,
    ensure_context,
    get_last_question_type,
    get_riddle_answer,
    get_riddle_answers,
    get_quiz_index,
    get_quiz_question,
    get_quiz_score,
    get_quiz_title,
    get_quiz_total,
    is_quiz_mode,
    is_riddle_mode,
    set_last_bot_question,
    start_quiz,
    start_riddle,
)
from core.docx.docx_analyzer import analyze_docx_reply, should_use_docx_analysis_tool
from core.docx.docx_service import build_docx_reply, should_use_docx_tool
from core.image.image_analyzer import (
    analyze_image_reply,
    should_use_image_analysis_tool,
)
from core.image.image_tool import (
    edit_image_reply,
    generate_image_reply,
    should_use_image_edit_tool,
    should_use_image_tool,
)
from core.knowledge.knowledge_loader import load_zoe_identity
from core.knowledge.knowledge_router import route_local_knowledge
from core.llm import generate_llm_reply
from core.llm_client import build_zoe_system_prompt
from core.location.proximity_service import (
    build_proximity_reply,
    should_use_proximity_search,
)
from core.memory import (
    add_message_to_history,
    add_profile_dislike,
    add_profile_goal,
    add_profile_like,
    add_profile_person,
    add_profile_project,
    add_profile_habit,
    apply_identity_context,
    add_trusted_fact,
    clear_profile_name,
    forget_profile_field,
    get_last_messages,
    get_profile,
    get_profile_snapshot,
    get_session_context,
    get_trusted_name,
    save_memory,
    set_preferred_tone,
    set_profile_city,
    set_profile_job,
    set_session_value,
    set_profile_name,
    update_profile_from_analysis,
)
from core.pdf.pdf_analyzer import analyze_pdf_reply, should_use_pdf_analysis_tool
from core.pdf.pdf_service import build_pdf_reply, should_use_pdf_tool
from core.responder import build_final_response
from core.skills.skill_registry import get_enabled_skills
from core.thinker import think_about_message
from core.utils import current_datetime_string
from core.web_tool import build_web_reply, should_use_web


INTENT_PHONE_ACTION = "PHONE_ACTION"
INTENT_MESSAGE_ACTION = "MESSAGE_ACTION"
INTENT_NOTES_ACTION = "NOTES_ACTION"
INTENT_GAME = "GAME"
INTENT_IMAGE_EDIT_REQUEST = "IMAGE_EDIT_REQUEST"
INTENT_IMAGE_ANALYSIS_REQUEST = "IMAGE_ANALYSIS_REQUEST"
INTENT_IMAGE_REQUEST = "IMAGE_REQUEST"
INTENT_PROXIMITY_SEARCH = "PROXIMITY_SEARCH"
INTENT_DOCX_ANALYSIS_REQUEST = "DOCX_ANALYSIS_REQUEST"
INTENT_DOCX_REQUEST = "DOCX_REQUEST"
INTENT_PDF_ANALYSIS_REQUEST = "PDF_ANALYSIS_REQUEST"
INTENT_PDF_REQUEST = "PDF_REQUEST"
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
    "tu connais mon nom",
    "tu connais mon nom",
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
    "c est quoi ton prenom",
    "qui es tu",
    "tu es qui",
    "tes qui",
    "t ki",
    "tki",
    "coman tu tapel",
    "comment tu tapel",
    "comment t appelles tu",
}

SIMPLE_USER_NAME_VARIANTS = {
    "comment je m appelle",
    "comment je mappelle",
    "quel est mon nom",
    "c est quoi mon nom",
    "cest quoi mon nom",
    "quel est mon prenom",
    "c est quoi mon prenom",
    "cest quoi mon prenom",
    "tu connais mon prenom",
    "tu te souviens de mon prenom",
    "qui je suis",
    "qui suis je",
    "tu sais qui je suis",
    "tu sais mon nom",
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

TEXT_CREATIVE_TERMS = {
    "musique",
    "chanson",
    "rap",
    "paroles",
    "refrain",
    "couplet",
    "couplets",
    "intro",
    "outro",
    "pont",
    "bridge",
    "suno",
    "prompt",
    "bio",
    "description",
    "texte",
    "poeme",
    "poesie",
    "poésie",
    "histoire",
    "scenario",
    "scénario",
    "clip",
    "video",
    "vidéo",
    "narration",
    "storytelling",
    "youtube",
    "publication",
    "post",
    "commentaire",
    "message",
}

TEXT_SCRIPT_EXPRESSIONS = {
    "script de musique",
    "script musical",
    "script de chanson",
    "script de rap",
    "script de clip",
    "script video",
    "script vidéo",
    "script narratif",
    "script de presentation",
    "script de présentation",
    "ecris des paroles",
    "écris des paroles",
    "fais des paroles",
    "cree des paroles",
    "crée des paroles",
    "prompt suno",
    "description youtube",
    "bio youtube",
}

TECHNICAL_CODE_TERMS = {
    "python",
    "javascript",
    "js",
    "kotlin",
    "java",
    "html",
    "css",
    "sql",
    "json",
    "api",
    "bot",
    "fonction",
    "classe",
    "methode",
    "méthode",
    "variable",
    "algorithme",
    "algorithm",
    "script python",
    "script js",
    "script javascript",
    "application",
    "appli",
    "programme",
    "coder",
    "code source",
    "backend",
    "frontend",
    "fastapi",
    "android",
    "compose",
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


def _looks_like_creative_text_request(text: str) -> bool:
    if not text:
        return False

    if any(expr in text for expr in TEXT_SCRIPT_EXPRESSIONS):
        return True

    return any(term in text for term in TEXT_CREATIVE_TERMS)


def _looks_like_explicit_technical_code_request(text: str) -> bool:
    if not text:
        return False

    return any(term in text for term in TECHNICAL_CODE_TERMS)


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


def _is_wrong_name_statement(normalized: str, compact: str) -> bool:
    explicit_variants = {variant.replace(" ", "") for variant in SIMPLE_WRONG_NAME_VARIANTS}
    if compact in explicit_variants:
        return True

    return normalized.startswith("je m appelle pas ") or normalized in {
        "je m appelle pas",
        "ce n est pas mon prenom",
        "tu te trompes de prenom",
        "c est pas mon prenom",
    }


def _is_user_name_question(normalized: str, compact: str, tokens: list[str]) -> bool:
    user_name_markers = {
        "comment je m appelle",
        "comment je mappelle",
        "quel est mon nom",
        "c est quoi mon nom",
        "c est quoi mon prenom",
        "quel est mon prenom",
        "tu connais mon prenom",
        "tu connais mon nom",
        "tu te souviens de mon prenom",
        "qui je suis",
        "qui suis je",
        "tu sais qui je suis",
        "tu sais mon nom",
    }

    if normalized in user_name_markers:
        return True

    if compact in {
        "commentjemappelle",
        "quelestmonnom",
        "cestquoimonnom",
        "cestquoimonprenom",
        "quelestmonprenom",
        "quijesuis",
        "quisuisje",
    }:
        return True

    has_user_reference = "je" in tokens or "mon" in tokens or "m" in tokens or "moi" in tokens
    has_name_keyword = "nom" in tokens or "prenom" in tokens
    has_question_marker = (
        "comment" in tokens
        or "quel" in tokens
        or "quoi" in tokens
        or "connais" in tokens
        or "souviens" in tokens
        or "sais" in tokens
        or "qui" in tokens
    )

    if has_user_reference and has_name_keyword and has_question_marker:
        return True

    return "qui" in tokens and "suis" in tokens and "je" in tokens


def _detect_simple_intent(text: str) -> str | None:
    normalized = _normalize_simple_text(text)
    if not normalized:
        return None

    compact = normalized.replace(" ", "")
    tokens = normalized.split()

    if _is_wrong_name_statement(normalized, compact):
        return SIMPLE_INTENT_WRONG_NAME

    ai_name_markers = {
        "comment tu t appelles",
        "tu t appelles comment",
        "quel est ton nom",
        "c est quoi ton nom",
        "c est quoi ton prenom",
        "qui es tu",
        "tu es qui",
        "comment t appelles tu",
    }

    if (
        normalized in ai_name_markers
        or compact in {
            "commenttutappelles",
            "tutappellescomment",
            "quelesttonnom",
            "cestquoitonnom",
            "cestquoitonprenom",
            "quiestu",
            "tuesqui",
        }
        or (
            ("tu" in tokens or "toi" in tokens or "ton" in tokens or "ta" in tokens or "tes" in tokens)
            and (
                "appelles" in tokens
                or "appelle" in tokens
                or "nom" in tokens
                or "prenom" in tokens
            )
        )
    ):
        return SIMPLE_INTENT_AI_NAME

    if _is_user_name_question(normalized, compact, tokens):
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
        or compact_text in PROTECTED_CHAT_EXACT
        or any(pattern in compact_text for pattern in PROTECTED_CHAT_CONTAINS)
    )


def _get_name(memory: dict) -> str:
    return get_trusted_name(memory)


def _save_name(memory: dict, name: str) -> None:
    set_profile_name(memory, name, source="declared")
    save_memory(memory)


def _clean_profile_statement_value(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").strip(" .,!?:;"))
    return cleaned.strip()


def _strip_leading_article(value: str) -> str:
    cleaned_value = _clean_profile_statement_value(value)
    if not cleaned_value:
        return ""

    cleaned_value = re.sub(
        r"^(?:le|la|les|un|une|des|du|de la|de l'|de l’|d'|d’|l'|l’)\s+",
        "",
        cleaned_value,
        flags=re.IGNORECASE,
    )
    return _clean_profile_statement_value(cleaned_value)


def _extract_declared_name(text: str, fallback_index: int) -> str:
    raw_name = text.split(" ", fallback_index)[-1].strip()
    if not raw_name:
        return ""

    first_token = raw_name.split(" ")[0].strip(" .,!?:;\"'()[]{}")
    return first_token


def _reply_with_name(memory: dict) -> str:
    profile = get_profile(memory)
    name = str(profile.get("name", "")).strip()

    if name:
        return f"Tu m'as dit t'appeler {name}."

    return "Je ne connais pas encore ton prenom. Tu peux me le dire si tu veux."


def _reply_with_city(memory: dict) -> str:
    profile = get_profile(memory)
    city = str(profile.get("city", "")).strip()
    if city:
        return f"Tu habites {city} si je me souviens bien."
    return "Je n'ai pas encore retenu ta ville. Tu peux me la redire si tu veux."


def _reply_with_job(memory: dict) -> str:
    profile = get_profile(memory)
    job = str(profile.get("job", "")).strip()
    if job:
        return f"Tu m'avais parle de ton travail dans {job}."
    return "Je n'ai pas encore retenu ton metier. Tu peux me le dire si tu veux."


def _reply_with_likes(memory: dict) -> str:
    profile = get_profile(memory)
    likes = profile.get("likes", [])
    if isinstance(likes, list):
        cleaned_likes = [str(item).strip() for item in likes if str(item).strip()]
        if cleaned_likes:
            if len(cleaned_likes) == 1:
                return f"Tu m'avais dit aimer {cleaned_likes[0]}."
            return "Tu m'avais dit aimer " + ", ".join(cleaned_likes[:-1]) + f" et {cleaned_likes[-1]}."

    return "Je n'ai pas encore retenu ce que tu aimes. Tu peux me le dire si tu veux."


def _join_profile_parts(parts: list[str]) -> str:
    clean_parts = [str(part).strip() for part in parts if str(part).strip()]
    if not clean_parts:
        return ""
    if len(clean_parts) == 1:
        return clean_parts[0]
    if len(clean_parts) == 2:
        return f"{clean_parts[0]} et {clean_parts[1]}"
    return ", ".join(clean_parts[:-1]) + f" et {clean_parts[-1]}"


def _format_like_summary_value(value: str) -> str:
    clean_value = str(value).strip()
    normalized_value = normalize_text(clean_value)
    if normalized_value == "rap":
        return "le rap"
    return clean_value


def _reply_with_self_summary(memory: dict) -> str:
    profile = get_profile_snapshot(memory)
    name = str(profile.get("name", "")).strip()
    city = str(profile.get("city", "")).strip()
    likes = profile.get("likes", [])

    clean_likes = (
        [_format_like_summary_value(item) for item in likes if str(item).strip()]
        if isinstance(likes, list)
        else []
    )

    parts: list[str] = []
    if name:
        parts.append(f"Tu t'appelles {name}")
    if city:
        parts.append(f"tu habites {city}")
    if clean_likes:
        parts.append(f"tu aimes {_join_profile_parts(clean_likes)}")

    if not parts:
        return "Je n'ai pas encore assez d'informations sur toi. Tu peux me parler de ton prenom, de ta ville ou de ce que tu aimes."

    sentence = _join_profile_parts(parts)
    return sentence[:1].upper() + sentence[1:] + "."


def _build_profile_summary(memory: dict) -> str:
    profile = get_profile(memory)

    def _format_list(field_name: str) -> str:
        values = profile.get(field_name, [])
        if not isinstance(values, list):
            return "-"
        clean_values = [str(item).strip() for item in values if str(item).strip()]
        return ", ".join(clean_values) if clean_values else "-"

    return "\n".join(
        [
            f"Nom : {str(profile.get('name', '')).strip() or '-'}",
            f"Ville : {str(profile.get('city', '')).strip() or '-'}",
            f"Metier : {str(profile.get('job', '')).strip() or '-'}",
            f"Gouts : {_format_list('likes')}",
            f"Je n'aime pas : {_format_list('dislikes')}",
            f"Projets : {_format_list('projects')}",
            f"Objectifs : {_format_list('goals')}",
            f"Personnes importantes : {_format_list('important_people')}",
            f"Habitudes : {_format_list('habits')}",
            f"Style prefere : {str(profile.get('preferred_tone', '')).strip() or '-'}",
        ]
    )


def _normalize_forget_field(field_name: str) -> str:
    normalized_field = normalize_text(field_name).replace(" ", "")
    aliases = {
        "name": "name",
        "prenom": "name",
        "nom": "name",
        "city": "city",
        "ville": "city",
        "job": "job",
        "metier": "job",
        "likes": "likes",
        "gouts": "likes",
        "gout": "likes",
        "dislikes": "dislikes",
        "projects": "projects",
        "projets": "projects",
        "goals": "goals",
        "objectif": "goals",
        "objectifs": "goals",
        "importantpeople": "important_people",
        "personnesimportantes": "important_people",
        "habits": "habits",
        "habitude": "habits",
        "habitudes": "habits",
        "tone": "preferred_tone",
        "style": "preferred_tone",
        "preferredtone": "preferred_tone",
    }
    return aliases.get(normalized_field, "")


def _handle_profile_command(text: str, memory: dict) -> dict[str, Any] | None:
    stripped_text = text.strip()
    lowered_text = stripped_text.lower()

    if lowered_text == "/profile":
        reply = _build_profile_summary(memory)
        _save_exchange(memory, text, reply, "unknown", "profile", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "profile",
            "intent": "reflect",
            "reply": reply,
        }

    if not lowered_text.startswith("/forget"):
        return None

    parts = stripped_text.split(maxsplit=1)
    if len(parts) < 2:
        reply = "Utilise /forget suivi du champ a effacer, par exemple /forget likes."
        _save_exchange(memory, text, reply, "unknown", "profile", "precise", "clarify")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "profile",
            "intent": "clarify",
            "reply": reply,
        }

    field_name = _normalize_forget_field(parts[1])
    if not field_name:
        reply = "Champ inconnu. Tu peux effacer : name, city, job, likes, dislikes, projects, goals, important_people, habits ou tone."
        _save_exchange(memory, text, reply, "unknown", "profile", "precise", "clarify")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "profile",
            "intent": "clarify",
            "reply": reply,
        }

    forget_profile_field(memory, field_name)
    save_memory(memory)
    clear_waiting_flag(memory)

    reply = f"J'ai oublie le champ {field_name}."
    _save_exchange(memory, text, reply, "unknown", "profile", "precise", "reflect")
    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": "profile",
        "intent": "reflect",
        "reply": reply,
    }


def _handle_profile_question(text: str, memory: dict) -> dict[str, Any] | None:
    normalized = normalize_text(text)
    compact = _compact_simple_text(text)

    if compact in {
        "quijesuis",
        "quisuisje",
        "tusaisquijesuis",
    } or normalized in {
        "qui je suis",
        "qui suis je",
        "tu sais qui je suis",
    }:
        reply = _reply_with_self_summary(memory)
        _save_exchange(memory, text, reply, "unknown", "identity", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "identity",
            "intent": "reflect",
            "reply": reply,
        }

    if compact in {
        "oujhabite",
        "tusaisoujhabite",
        "dansquellevillejhabite",
        "ouestcequejhabite",
    } or (
        "habite" in normalized and ("ou" in normalized or "ville" in normalized or normalized.startswith("o "))
    ):
        reply = _reply_with_city(memory)
        _save_exchange(memory, text, reply, "unknown", "location", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "location",
            "intent": "reflect",
            "reply": reply,
        }

    if compact in {
        "quescequejaime",
        "questcequejaime",
        "tusaiscequejaime",
        "tusaiscequejaimebien",
    } or (
        "aime" in normalized and ("tu sais" in normalized or "qu est ce" in normalized or "que j aime" in normalized)
    ):
        reply = _reply_with_likes(memory)
        _save_exchange(memory, text, reply, "unknown", "preferences", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "preferences",
            "intent": "reflect",
            "reply": reply,
        }

    if compact in {
        "quelestmonmetier",
        "tusaismonmetier",
        "dansquoijetravaille",
        "oujetravaille",
    }:
        reply = _reply_with_job(memory)
        _save_exchange(memory, text, reply, "unknown", "work", "precise", "reflect")
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "work",
            "intent": "reflect",
            "reply": reply,
        }

    return None


def _extract_person_name_from_relation(value: str) -> str:
    clean_value = _clean_profile_statement_value(value)
    if not clean_value:
        return ""

    tokens = [token.strip(" .,!?:;\"'()[]{}") for token in clean_value.split() if token.strip()]
    if not tokens:
        return ""

    if len(tokens) >= 2 and tokens[1][:1].isupper():
        return f"{tokens[0]} {tokens[1]}".strip()

    return tokens[0]


def _split_personal_info_clauses(text: str) -> list[str]:
    compact_text = re.sub(r"\s+", " ", str(text or "").strip())
    if not compact_text:
        return []

    raw_chunks = re.split(r"[,;\n]+", compact_text)
    clauses: list[str] = []

    for raw_chunk in raw_chunks:
        chunk = raw_chunk.strip(" .!?")
        if not chunk:
            continue

        sub_chunks = re.split(
            r"\s+et\s+(?=(?:j(?:['’]|\s)|je\b|mon\b|ma\b|mes\b|moi\b))",
            chunk,
            flags=re.IGNORECASE,
        )

        for sub_chunk in sub_chunks:
            clause = sub_chunk.strip(" .!?")
            if clause:
                clauses.append(clause)

    return clauses


def _extract_personal_info_legacy(text: str) -> dict[str, str] | None:
    stripped_text = text.strip()
    if not stripped_text:
        return None

    patterns = (
        ("name", r"^je\s+m(?:['’]|\s)?appelle\s+(.+)$"),
        ("likes", r"^j(?:['’]|\s)?aime\s+(.+)$"),
        ("city", r"^j(?:['’]|\s)?habite\s+(.+)$"),
        ("city", r"^je\s+vis\s+(?:a|à)\s+(.+)$"),
        ("job", r"^je\s+travaille\s+(.+)$"),
        ("job", r"^mon\s+m(?:e|é)tier\s+(?:est|c(?:['’]|\s)?est)\s+(.+)$"),
    )

    for field, pattern in patterns:
        match = re.match(pattern, stripped_text, flags=re.IGNORECASE)
        if not match:
            continue

        value = _clean_profile_statement_value(match.group(1))
        if not value:
            return None

        if field == "name":
            value = _extract_declared_name(f"je m'appelle {value}", fallback_index=3)
        elif field == "likes":
            normalized_value = normalize_text(value)
            if normalized_value.startswith("bien "):
                value = _clean_profile_statement_value(value[5:])
            elif normalized_value.startswith("beaucoup "):
                value = _clean_profile_statement_value(value[9:])
        elif field == "job":
            value = re.sub(
                r"^(dans|en|comme)\s+",
                "",
                value,
                flags=re.IGNORECASE,
            )
            value = _clean_profile_statement_value(value)

        if value:
            return {
                "field": field,
                "value": value,
            }

    return None


def _build_personal_info_reply_legacy(field: str, value: str) -> tuple[str, str]:
    if field == "name":
        return f"Enchantee {value}. Je retiens ton prenom.", "identity"

    if field == "likes":
        if "rap" in normalize_text(value):
            return "Le rap a beaucoup de styles. Tu ecoutes quoi en ce moment ?", "preferences"
        return f"Je retiens que tu aimes {value}.", "preferences"

    if field == "city":
        return f"{value} a une vraie identite. J'en prends note.", "location"

    if field == "job":
        normalized_job = normalize_text(value)
        if "aide a domicile" in normalized_job or (
            "aide" in normalized_job and "domicile" in normalized_job
        ):
            return "C'est un metier humain et precieux. Je retiens ca.", "work"
        return f"Je retiens que ton travail concerne {value}.", "work"

    return "", "general"


def _handle_personal_info_legacy(text: str, memory: dict) -> dict[str, Any] | None:
    extracted_info = _extract_personal_info(text)
    if extracted_info is None:
        return None

    field = extracted_info["field"]
    value = extracted_info["value"]

    if field == "name":
        _save_name(memory, value)
        stored_value = _get_name(memory) or value
    elif field == "likes":
        add_profile_like(memory, value)
        stored_value = value
        save_memory(memory)
    elif field == "city":
        set_profile_city(memory, value)
        stored_value = value
        save_memory(memory)
    elif field == "job":
        set_profile_job(memory, value)
        stored_value = value
        save_memory(memory)
    else:
        return None

    reply, topic = _build_personal_info_reply(field, stored_value)
    if not reply:
        return None

    if reply.endswith("?"):
        set_last_bot_question(memory, reply, "general_followup")
    else:
        clear_waiting_flag(memory)

    _save_exchange(memory, text, reply, "positive", topic, "precise", "encourage")
    return {
        "emotion": "positive",
        "precision": "precise",
        "topic": topic,
        "intent": "encourage",
        "reply": reply,
    }


def _extract_personal_info(text: str) -> dict[str, str] | None:
    stripped_text = text.strip()
    if not stripped_text:
        return None

    patterns = (
        ("name", r"^je\s+m(?:['’]|\s)?appelle\s+(.+)$"),
        ("dislikes", r"^j(?:['’]|\s)?aime\s+pas\s+(.+)$"),
        ("dislikes", r"^je\s+d(?:e|é)teste\s+(.+)$"),
        ("likes", r"^j(?:['’]|\s)?aime\s+(.+)$"),
        ("city", r"^j(?:['’]|\s)?habite\s+(.+)$"),
        ("city", r"^je\s+vis\s+(?:a|à)\s+(.+)$"),
        ("job", r"^je\s+travaille\s+(.+)$"),
        ("job", r"^mon\s+m(?:e|é)tier\s+(?:est|c(?:['’]|\s)?est)\s+(.+)$"),
        ("projects", r"^je\s+veux\s+(?:creer|créer|lancer|developper|développer|faire|construire)\s+(.+)$"),
        ("goals", r"^je\s+veux\s+(.+)$"),
        ("important_people", r"^mon\s+(?:fils|garcon|garçon|enfant|frere|frère|soeur|sœur|fille|mari|femme|copine|copain|compagnon|compagne|pere|père|mere|mère|papa|maman)\s+s(?:['’]|\s)?appelle\s+(.+)$"),
        ("preferred_tone", r"^je\s+pr(?:e|é)f(?:e|è)re\s+un\s+ton\s+(.+)$"),
        ("preferred_tone", r"^je\s+pr(?:e|é)f(?:e|è)re\s+que\s+tu\s+parles\s+(.+)$"),
        ("habits", r"^j(?:['’]|\s)?ai\s+l(?:['’]|\s)?habitude\s+de\s+(.+)$"),
        ("habits", r"^je\s+fais\s+souvent\s+(.+)$"),
    )

    for field, pattern in patterns:
        match = re.match(pattern, stripped_text, flags=re.IGNORECASE)
        if not match:
            continue

        value = _clean_profile_statement_value(match.group(1))
        if not value:
            return None

        if field == "name":
            value = _extract_declared_name(f"je m'appelle {value}", fallback_index=3)
        elif field in {"likes", "dislikes"}:
            normalized_value = normalize_text(value)
            if normalized_value.startswith("bien "):
                value = _clean_profile_statement_value(value[5:])
            elif normalized_value.startswith("beaucoup "):
                value = _clean_profile_statement_value(value[9:])
            value = _strip_leading_article(value)
        elif field == "job":
            value = re.sub(r"^(dans|en|comme|chez)\s+", "", value, flags=re.IGNORECASE)
            value = _clean_profile_statement_value(value)
        elif field == "projects":
            value = _strip_leading_article(value)
        elif field == "goals":
            value = _clean_profile_statement_value(value)
        elif field == "important_people":
            value = _extract_person_name_from_relation(value)
        elif field == "preferred_tone":
            value = normalize_text(value).split(" ")[0].strip()
        elif field == "habits":
            value = _clean_profile_statement_value(value)

        if value:
            return {
                "field": field,
                "value": value,
            }

    return None


def _extract_personal_info_items(text: str) -> list[dict[str, str]]:
    clauses = _split_personal_info_clauses(text)
    if not clauses:
        return []

    extracted_items: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for clause in clauses:
        extracted_info = _extract_personal_info(clause)
        if extracted_info is None:
            continue

        field = str(extracted_info.get("field", "")).strip()
        value = str(extracted_info.get("value", "")).strip()
        if not field or not value:
            continue

        dedupe_key = (field, normalize_text(value))
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        extracted_items.append(
            {
                "field": field,
                "value": value,
            }
        )

    return extracted_items


def _build_personal_info_reply(field: str, value: str) -> tuple[str, str]:
    if field == "name":
        return f"Enchantee {value}. Je retiens ton prenom.", "identity"

    if field == "likes":
        if "rap" in normalize_text(value):
            return "Le rap a beaucoup de styles. Tu ecoutes quoi en ce moment ?", "preferences"
        return f"Je retiens que tu aimes {value}.", "preferences"

    if field == "dislikes":
        return f"Je retiens que tu n'aimes pas {value}.", "preferences"

    if field == "city":
        return f"{value} a une vraie identite. J'en prends note.", "location"

    if field == "job":
        normalized_job = normalize_text(value)
        if "aide a domicile" in normalized_job or ("aide" in normalized_job and "domicile" in normalized_job):
            return "C'est un metier humain et precieux. Je retiens ca.", "work"
        return f"Je retiens que ton travail concerne {value}.", "work"

    if field == "projects":
        return f"Je retiens ton projet autour de {value}.", "project"

    if field == "goals":
        return f"Je retiens que tu veux {value}.", "project"

    if field == "important_people":
        return f"Je retiens que {value} compte pour toi.", "family"

    if field == "preferred_tone":
        return f"D'accord. Je vais rester sur un ton {value}.", "communication"

    if field == "habits":
        return f"Je retiens cette habitude : {value}.", "daily_life"

    return "", "general"


def _store_personal_info(memory: dict, field: str, value: str) -> str:
    if field == "name":
        _save_name(memory, value)
        return _get_name(memory) or value

    if field == "likes":
        add_profile_like(memory, value)
    elif field == "dislikes":
        add_profile_dislike(memory, value)
    elif field == "city":
        set_profile_city(memory, value)
    elif field == "job":
        set_profile_job(memory, value)
    elif field == "projects":
        add_profile_project(memory, value)
    elif field == "goals":
        add_profile_goal(memory, value)
    elif field == "important_people":
        add_profile_person(memory, value)
    elif field == "preferred_tone":
        set_preferred_tone(memory, value)
    elif field == "habits":
        add_profile_habit(memory, value)
    else:
        return ""

    save_memory(memory)
    profile = get_profile(memory)
    current_value = profile.get(field)
    if isinstance(current_value, list):
        return value

    return str(current_value or value).strip()


def _handle_personal_info(text: str, memory: dict) -> dict[str, Any] | None:
    extracted_items = _extract_personal_info_items(text)
    if not extracted_items:
        return None

    replies: list[str] = []
    topics: list[str] = []

    for extracted_info in extracted_items:
        field = extracted_info["field"]
        stored_value = _store_personal_info(memory, field, extracted_info["value"])
        if not stored_value:
            continue

        reply, topic = _build_personal_info_reply(field, stored_value)
        if reply and reply not in replies:
            replies.append(reply)
        if topic:
            topics.append(topic)

    if not replies:
        return None

    reply = " ".join(replies)
    topic = topics[0] if topics else "profile"
    if len(set(topics)) > 1:
        topic = "profile"

    if reply.endswith("?"):
        set_last_bot_question(memory, reply, "general_followup")
    else:
        clear_waiting_flag(memory)

    _save_exchange(memory, text, reply, "positive", topic, "precise", "encourage")
    return {
        "emotion": "positive",
        "precision": "precise",
        "topic": topic,
        "intent": "encourage",
        "reply": reply,
    }


def _get_zoe_identity() -> dict[str, Any]:
    return load_zoe_identity()


def _reply_with_zoe_identity() -> str:
    zoe_identity = _get_zoe_identity()
    name = str(zoe_identity.get("name", "Zoe")).strip() or "Zoe"
    role = str(zoe_identity.get("role", "assistante intelligente")).strip() or "assistante intelligente"
    return f"Je m'appelle {name}. Je suis {role}."


def _reply_memory(memory: dict) -> str:
    profile = get_profile(memory)
    name = _get_name(memory)
    city = str(profile.get("city", "")).strip()
    job = str(profile.get("job", "")).strip()
    likes = profile.get("likes", [])
    last_emotion = memory.get("last_emotion", "unknown")
    last_topic = memory.get("last_topic", "general")
    parts: list[str] = []

    if name:
        parts.append(f"Je me souviens que tu t'appelles {name}.")

    if city:
        parts.append(f"Tu habites {city}.")

    if job:
        parts.append(f"Tu m'avais parle de ton travail dans {job}.")

    if isinstance(likes, list):
        clean_likes = [str(item).strip() for item in likes if str(item).strip()]
        if clean_likes:
            parts.append(f"Tu m'avais dit aimer {clean_likes[0]}.")

    if last_emotion != "unknown":
        parts.append(f"La derniere emotion que j'ai retenue, c'est {last_emotion}.")

    if last_topic != "general":
        parts.append(f"Le dernier sujet important que j'ai retenu, c'est {last_topic}.")

    if not parts:
        return "Je garde une memoire legere de nos echanges, mais elle est encore en train de se construire."

    return " ".join(parts)


def _remember_runtime_context(
    memory: dict,
    user_text: str,
    attached_image_url: str | None = None,
    attached_docx_url: str | None = None,
    attached_docx_path: str | None = None,
    attached_pdf_url: str | None = None,
    attached_pdf_path: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> None:
    get_session_context(memory)
    set_session_value(memory, "last_user_message", user_text)
    set_session_value(memory, "enabled_skills", get_enabled_skills(memory))

    if latitude is not None and longitude is not None:
        coordinates = {
            "latitude": latitude,
            "longitude": longitude,
        }
        set_session_value(memory, "last_coordinates", coordinates)
        add_trusted_fact(memory, "last_coordinates", coordinates)

        known_locations = memory.get("known_locations", [])
        if not isinstance(known_locations, list):
            known_locations = []

        already_known = any(
            isinstance(item, dict)
            and item.get("latitude") == latitude
            and item.get("longitude") == longitude
            for item in known_locations
        )
        if not already_known:
            known_locations.append(coordinates)
            memory["known_locations"] = known_locations[-10:]

    attachment_type = ""
    if (attached_image_url or "").strip():
        attachment_type = "image"
    elif (attached_docx_url or "").strip() or (attached_docx_path or "").strip():
        attachment_type = "docx"
    elif (attached_pdf_url or "").strip() or (attached_pdf_path or "").strip():
        attachment_type = "pdf"

    if attachment_type:
        set_session_value(memory, "last_attachment_type", attachment_type)


def _build_local_knowledge_reply(match: dict[str, Any]) -> str:
    source = str(match.get("source", "")).strip()
    payload = match.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}

    if source == "faq":
        return str(payload.get("answer", "")).strip()

    if source == "buildings":
        building_name = str(payload.get("name", "")).strip()
        description = str(payload.get("description", "")).strip()
        if building_name and description:
            return f"{building_name.capitalize()} : {description}"
        return description

    if source == "user_help":
        title = str(payload.get("title", "")).strip()
        description = str(payload.get("description", "")).strip()
        lines: list[str] = []

        if title and description:
            lines.append(f"{title} : {description}")
        elif title:
            lines.append(title)
        elif description:
            lines.append(description)

        skill_title = str(payload.get("skill_title", "")).strip()
        if skill_title:
            status = "active" if bool(payload.get("skill_enabled", True)) else "desactivee"
            lines.append(f"Capacite correspondante : {skill_title} ({status}).")

        enabled_skill_titles = payload.get("enabled_skill_titles", [])
        if isinstance(enabled_skill_titles, list) and enabled_skill_titles:
            lines.append("")
            lines.append("Capacites actives :")
            for item in enabled_skill_titles[:10]:
                clean_item = str(item).strip()
                if clean_item:
                    lines.append(f"- {clean_item}")

        examples = payload.get("examples", [])
        if isinstance(examples, list) and examples:
            lines.append("")
            lines.append("Exemples :")
            for item in examples[:3]:
                clean_item = str(item).strip()
                if clean_item:
                    lines.append(f"- {clean_item}")

        return "\n".join(lines).strip()

    return ""


def _build_local_knowledge_result(
    user_text: str,
    memory: dict,
) -> dict[str, Any] | None:
    local_match = route_local_knowledge(user_text, memory=memory)
    if local_match is None:
        return None

    reply = _build_local_knowledge_reply(local_match)
    if not reply.strip():
        return None

    zoe_identity = _get_zoe_identity()
    source = str(local_match.get("source", "knowledge")).strip() or "knowledge"

    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": source,
        "intent": "reflect",
        "reply": reply,
        "thought_summary": f"reponse locale chargee depuis {source}",
        "strategy": "local_knowledge",
        "tone": str(zoe_identity.get("tone", "informative")).strip() or "informative",
        "tool_type": "knowledge",
        "knowledge_source": source,
        "knowledge_confidence": local_match.get("confidence"),
    }


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
    attached_docx_url: str | None = None,
    attached_docx_path: str | None = None,
    attached_pdf_url: str | None = None,
    attached_pdf_path: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> str:
    text = normalize_text(user_message)
    has_attached_image = bool((attached_image_url or "").strip())
    has_attached_docx = bool((attached_docx_url or "").strip() or (attached_docx_path or "").strip())
    has_attached_pdf = bool((attached_pdf_url or "").strip() or (attached_pdf_path or "").strip())
    proximity_detected = should_use_proximity_search(
        user_message=text,
        latitude=latitude,
        longitude=longitude,
    )
    docx_analysis_detected = should_use_docx_analysis_tool(
        user_message=text,
        has_attached_docx=has_attached_docx,
    )
    docx_detected = should_use_docx_tool(text)
    pdf_analysis_detected = should_use_pdf_analysis_tool(
        user_message=text,
        has_attached_pdf=has_attached_pdf,
    )
    pdf_detected = should_use_pdf_tool(text)
    image_edit_detected = should_use_image_edit_tool(
        message=text,
        has_attached_image=has_attached_image,
    )
    image_analysis_detected = should_use_image_analysis_tool(
        message=text,
        has_attached_image=has_attached_image,
    )
    image_create_detected = should_use_image_tool(text)
    routed_preview = (
        "image_edit"
        if image_edit_detected
        else "image_analysis"
        if image_analysis_detected
        else "image_create"
        if image_create_detected
        else "text"
    )

    logger.info(
        "image-routing attached_image=%s attached_docx=%s attached_pdf=%s image_create=%s image_edit=%s image_analysis=%s proximity=%s docx_analysis=%s docx=%s pdf_analysis=%s pdf=%s route=%s source_image_provided=%s",
        has_attached_image,
        has_attached_docx,
        has_attached_pdf,
        image_create_detected,
        image_edit_detected,
        image_analysis_detected,
        proximity_detected,
        docx_analysis_detected,
        docx_detected,
        pdf_analysis_detected,
        pdf_detected,
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

    if proximity_detected:
        return INTENT_PROXIMITY_SEARCH

    if docx_analysis_detected:
        return INTENT_DOCX_ANALYSIS_REQUEST

    if pdf_analysis_detected:
        return INTENT_PDF_ANALYSIS_REQUEST

    if docx_detected:
        return INTENT_DOCX_REQUEST

    if pdf_detected:
        return INTENT_PDF_REQUEST

    if image_edit_detected:
        return INTENT_IMAGE_EDIT_REQUEST

    if image_analysis_detected:
        return INTENT_IMAGE_ANALYSIS_REQUEST

    if image_create_detected:
        return INTENT_IMAGE_REQUEST

    if should_use_web(text):
        return INTENT_WEB_SEARCH

    if _looks_like_creative_text_request(text) and not _looks_like_explicit_technical_code_request(text):
        return INTENT_CHAT

    if should_use_code_tool(text) and _looks_like_explicit_technical_code_request(text):
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
    if user_input.strip().startswith("/"):
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
        reply = generate_llm_reply(
            user_message=user_input,
            memory=memory,
            system_prompt=build_zoe_system_prompt(user_name=_get_name(memory)),
        )
        if not reply.strip():
            return None

        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "llm",
            "intent": "reflect",
            "reply": reply.strip(),
        }
    except Exception:
        return None


def _build_profile_memory_hint(user_input: str, memory: dict) -> str:
    normalized = normalize_text(user_input)
    profile = get_profile(memory)

    likes = profile.get("likes", [])
    if isinstance(likes, list):
        clean_likes = [str(item).strip() for item in likes if str(item).strip()]
        if clean_likes and any(term in normalized for term in {"musique", "rap", "chanson", "ecoute"}):
            return f"Tu m'avais dit aimer {clean_likes[0]}."

    city = str(profile.get("city", "")).strip()
    if city and any(term in normalized for term in {"ville", "habites", "habite", "chez toi", "quartier"}):
        return f"Tu habites {city} si je me souviens bien."

    job = str(profile.get("job", "")).strip()
    if job and any(term in normalized for term in {"travail", "metier", "boulot", "job"}):
        return f"Tu m'avais parle de ton travail dans {job}."

    projects = profile.get("projects", [])
    if isinstance(projects, list):
        clean_projects = [str(item).strip() for item in projects if str(item).strip()]
        if clean_projects and any(term in normalized for term in {"projet", "application", "appli"}):
            return f"Tu m'avais parle de ton projet autour de {clean_projects[0]}."

    return ""


def _merge_memory_hint(reply: str, memory_hint: str) -> str:
    clean_reply = str(reply or "").strip()
    clean_hint = str(memory_hint or "").strip()

    if not clean_hint:
        return clean_reply

    if clean_hint.lower() in clean_reply.lower():
        return clean_reply

    return f"{clean_hint} {clean_reply}".strip()


def _apply_session_humanity(reply: str, memory: dict, analysis: dict) -> str:
    clean_reply = str(reply or "").strip()
    if not clean_reply:
        return ""

    session_context = get_session_context(memory)
    mood = str(session_context.get("mood", "")).strip().lower()
    energy = str(session_context.get("energy", "")).strip().lower()
    emotion = str(analysis.get("emotion", "unknown")).strip().lower()

    if mood in {"sad", "stressed", "tired"} and not clean_reply.lower().startswith(("je suis la", "on peut", "je vois")):
        return f"Je suis la. {clean_reply}"

    if mood == "positive" and energy == "high" and emotion in {"positive", "joy"} and not clean_reply.lower().startswith("ca fait plaisir"):
        return f"Ca fait plaisir a entendre. {clean_reply}"

    return clean_reply


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

    profile_command_result = _handle_profile_command(text, memory)
    if profile_command_result is not None:
        return profile_command_result

    profile_question_result = _handle_profile_question(text, memory)
    if profile_question_result is not None:
        return profile_question_result

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

    if simple_intent == SIMPLE_INTENT_AI_NAME:
        reply = _reply_with_zoe_identity()
        _save_exchange(memory, text, reply, "positive", "identity", "precise", "reflect")
        return {
            "emotion": "positive",
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
            reply = f"D'accord, merci de me l'avoir dit. Je ne vais plus utiliser {wrong_name}."
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
        "ce n'est pas mon prã©nom",
        "ce n est pas mon prã©nom",
        "tu te trompes de prenom",
        "tu te trompes de prã©nom",
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
        reply = _reply_with_zoe_identity()
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
        reply = _reply_with_zoe_identity()
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
        "comment je m appelle",
        "comment je m appelles",
        "quel est mon nom",
        "c'est quoi mon nom",
        "c est quoi mon nom",
        "quel est mon prenom",
        "c'est quoi mon prenom",
        "c est quoi mon prenom",
        "tu connais mon prenom",
        "tu te souviens de mon prenom",
        "qui je suis",
        "qui suis je",
        "tu sais qui je suis",
        "tu sais mon nom",
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
        name = _extract_declared_name(text, fallback_index=3)
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
        name = _extract_declared_name(text, fallback_index=4)
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

    return None


def _handle_system_command(text: str, memory: dict) -> dict[str, Any] | None:
    plain_lower = normalize_text(text).strip(" .!?;,:")

    if plain_lower == "brain thinker":
        reply = "Mon cerveau avec reflexion est bien actif."
    elif plain_lower == "brain v5":
        reply = "Mon cerveau V5 simple est bien actif."
    else:
        return None

    _save_exchange(memory, text, reply, "positive", "system", "precise", "encourage")
    return {
        "emotion": "positive",
        "precision": "precise",
        "topic": "system",
        "intent": "encourage",
        "reply": reply,
    }


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
    attached_docx_url: str | None = None,
    attached_docx_path: str | None = None,
    attached_docx_name: str | None = None,
    attached_docx_mime_type: str | None = None,
    attached_pdf_url: str | None = None,
    attached_pdf_path: str | None = None,
    attached_pdf_name: str | None = None,
    attached_pdf_mime_type: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    search_radius_meters: int | None = None,
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
        "identity-context uid_present=%s account_key_present=%s attached_image=%s attached_docx=%s attached_pdf=%s location_provided=%s",
        bool(user_uid),
        bool(str(identity.get("account_key", "")).strip()),
        bool((attached_image_url or "").strip()),
        bool((attached_docx_url or "").strip() or (attached_docx_path or "").strip()),
        bool((attached_pdf_url or "").strip() or (attached_pdf_path or "").strip()),
        latitude is not None and longitude is not None,
    )
    _remember_runtime_context(
        memory=memory,
        user_text=text,
        attached_image_url=attached_image_url,
        attached_docx_url=attached_docx_url,
        attached_docx_path=attached_docx_path,
        attached_pdf_url=attached_pdf_url,
        attached_pdf_path=attached_pdf_path,
        latitude=latitude,
        longitude=longitude,
    )

    contextual_result = _handle_contextual_reply(text, memory)
    if contextual_result is not None:
        return contextual_result

    personal_info_result = _handle_personal_info(text, memory)
    if personal_info_result is not None:
        return personal_info_result

    direct_result = _direct_rules(text, memory)
    if direct_result is not None:
        return direct_result

    local_knowledge_result = _build_local_knowledge_result(text, memory)
    if local_knowledge_result is not None:
        _save_exchange(
            memory=memory,
            user_text=text,
            reply=local_knowledge_result["reply"],
            emotion=local_knowledge_result["emotion"],
            topic=local_knowledge_result["topic"],
            precision=local_knowledge_result["precision"],
            intent=local_knowledge_result["intent"],
        )
        return local_knowledge_result

    detected_intent = classify_intent(
        text,
        attached_image_url=attached_image_url,
        attached_docx_url=attached_docx_url,
        attached_docx_path=attached_docx_path,
        attached_pdf_url=attached_pdf_url,
        attached_pdf_path=attached_pdf_path,
        latitude=latitude,
        longitude=longitude,
    )
    logger.info(
        "intent-selected intent=%s attached_image=%s attached_docx=%s attached_pdf=%s source_image_provided=%s location_provided=%s",
        detected_intent,
        bool((attached_image_url or "").strip()),
        bool((attached_docx_url or "").strip() or (attached_docx_path or "").strip()),
        bool((attached_pdf_url or "").strip() or (attached_pdf_path or "").strip()),
        bool((attached_image_url or "").strip()),
        latitude is not None and longitude is not None,
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

    if detected_intent == INTENT_PROXIMITY_SEARCH:
        proximity_result = build_proximity_reply(
            user_message=text,
            latitude=latitude,
            longitude=longitude,
            search_radius_meters=search_radius_meters,
        )
        result = {
            "emotion": proximity_result.get("emotion", "unknown"),
            "precision": proximity_result.get("precision", "precise"),
            "topic": proximity_result.get("topic", "location"),
            "intent": proximity_result.get("intent", "clarify"),
            "reply": proximity_result["reply"],
            "thought_summary": "recherche de proximite activee",
            "strategy": "proximity_search",
            "tone": "practical",
            "tool_type": "proximity",
            "place_type": proximity_result.get("place_type"),
            "search_radius_meters": proximity_result.get("search_radius_meters"),
            "latitude": proximity_result.get("latitude"),
            "longitude": proximity_result.get("longitude"),
            "location_required": proximity_result.get("location_required"),
            "provider_status": proximity_result.get("provider_status"),
            "places": proximity_result.get("places"),
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

    if detected_intent == INTENT_DOCX_ANALYSIS_REQUEST:
        docx_result = analyze_docx_reply(
            user_message=text,
            docx_url=attached_docx_url,
            docx_path=attached_docx_path,
            docx_name=attached_docx_name,
            docx_mime_type=attached_docx_mime_type,
            conversation=_build_conversation_history(memory),
        )
        result = {
            "emotion": docx_result.get("emotion", "unknown"),
            "precision": docx_result.get("precision", "precise"),
            "topic": docx_result.get("topic", "docx"),
            "intent": docx_result.get("intent", "reflect"),
            "reply": docx_result["reply"],
            "thought_summary": "analyse de document word activee",
            "strategy": "docx_analysis",
            "tone": "informative",
            "tool_type": "docx",
            "docx_analysis_status": docx_result.get("docx_analysis_status"),
            "docx_summary": docx_result.get("docx_summary"),
            "docx_key_points": docx_result.get("docx_key_points"),
            "docx_source_name": docx_result.get("docx_source_name"),
            "docx_has_text": docx_result.get("docx_has_text"),
            "docx_question_answer": docx_result.get("docx_question_answer"),
            "docx_heading_titles": docx_result.get("docx_heading_titles"),
            "docx_paragraph_count": docx_result.get("docx_paragraph_count"),
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

    if detected_intent == INTENT_PDF_ANALYSIS_REQUEST:
        pdf_result = analyze_pdf_reply(
            user_message=text,
            pdf_url=attached_pdf_url,
            pdf_path=attached_pdf_path,
            pdf_name=attached_pdf_name,
            pdf_mime_type=attached_pdf_mime_type,
            conversation=_build_conversation_history(memory),
        )
        result = {
            "emotion": pdf_result.get("emotion", "unknown"),
            "precision": pdf_result.get("precision", "precise"),
            "topic": pdf_result.get("topic", "pdf"),
            "intent": pdf_result.get("intent", "reflect"),
            "reply": pdf_result["reply"],
            "thought_summary": "analyse de pdf activee",
            "strategy": "pdf_analysis",
            "tone": "informative",
            "tool_type": "pdf",
            "pdf_analysis_status": pdf_result.get("pdf_analysis_status"),
            "pdf_summary": pdf_result.get("pdf_summary"),
            "pdf_key_points": pdf_result.get("pdf_key_points"),
            "pdf_page_count": pdf_result.get("pdf_page_count"),
            "pdf_source_name": pdf_result.get("pdf_source_name"),
            "pdf_has_text": pdf_result.get("pdf_has_text"),
            "pdf_question_answer": pdf_result.get("pdf_question_answer"),
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

    if detected_intent == INTENT_DOCX_REQUEST:
        docx_result = build_docx_reply(
            user_message=text,
            conversation=_build_conversation_history(memory),
        )
        result = {
            "emotion": docx_result.get("emotion", "unknown"),
            "precision": docx_result.get("precision", "precise"),
            "topic": docx_result.get("topic", "docx"),
            "intent": docx_result.get("intent", "reflect"),
            "reply": docx_result["reply"],
            "thought_summary": "generation de document word activee",
            "strategy": "docx_generation",
            "tone": "practical",
            "tool_type": "docx",
            "docx_path": docx_result.get("docx_path"),
            "docx_url": docx_result.get("docx_url"),
            "docx_filename": docx_result.get("docx_filename"),
            "docx_mime_type": docx_result.get("docx_mime_type"),
            "docx_title": docx_result.get("docx_title"),
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

    if detected_intent == INTENT_PDF_REQUEST:
        pdf_result = build_pdf_reply(
            user_message=text,
            conversation=_build_conversation_history(memory),
        )
        result = {
            "emotion": pdf_result.get("emotion", "unknown"),
            "precision": pdf_result.get("precision", "precise"),
            "topic": pdf_result.get("topic", "pdf"),
            "intent": pdf_result.get("intent", "reflect"),
            "reply": pdf_result["reply"],
            "thought_summary": "generation de pdf activee",
            "strategy": "pdf_generation",
            "tone": "practical",
            "tool_type": "pdf",
            "pdf_path": pdf_result.get("pdf_path"),
            "pdf_url": pdf_result.get("pdf_url"),
            "pdf_filename": pdf_result.get("pdf_filename"),
            "pdf_mime_type": pdf_result.get("pdf_mime_type"),
            "pdf_title": pdf_result.get("pdf_title"),
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

    if detected_intent == INTENT_IMAGE_ANALYSIS_REQUEST:
        image_result = analyze_image_reply(
            user_message=text,
            image_url=attached_image_url,
            image_mime_type=attached_image_mime_type,
            conversation=_build_conversation_history(memory),
        )
        result = {
            "emotion": image_result.get("emotion", "unknown"),
            "precision": image_result.get("precision", "precise"),
            "topic": image_result.get("topic", "image"),
            "intent": image_result.get("intent", "reflect"),
            "reply": image_result["reply"],
            "thought_summary": "analyse d'image activee",
            "strategy": "image_analysis",
            "tone": "informative",
            "tool_type": "image",
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

    system_command_result = _handle_system_command(text, memory)
    if system_command_result is not None:
        return system_command_result

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
    reply = _merge_memory_hint(reply, _build_profile_memory_hint(text, memory))
    reply = _apply_session_humanity(reply, memory, analysis)
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
