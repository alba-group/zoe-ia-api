from typing import Any


def ensure_context(memory: dict[str, Any]) -> dict[str, Any]:
    """
    Initialise le contexte vivant si absent.
    """
    if "context" not in memory or not isinstance(memory["context"], dict):
        memory["context"] = {
            "mode": None,
            "last_question_type": None,
            "awaiting_user_reply": False,
            "riddle_answer": None,
            "riddle_answers": [],
            "riddle_question": None,
            "last_bot_question": None,
            "quiz_title": None,
            "quiz_questions": [],
            "quiz_index": 0,
            "quiz_score": 0,
        }

    ctx = memory["context"]

    # Garde-fous si anciennes mémoires
    ctx.setdefault("mode", None)
    ctx.setdefault("last_question_type", None)
    ctx.setdefault("awaiting_user_reply", False)
    ctx.setdefault("riddle_answer", None)
    ctx.setdefault("riddle_answers", [])
    ctx.setdefault("riddle_question", None)
    ctx.setdefault("last_bot_question", None)
    ctx.setdefault("quiz_title", None)
    ctx.setdefault("quiz_questions", [])
    ctx.setdefault("quiz_index", 0)
    ctx.setdefault("quiz_score", 0)

    return ctx


def get_context(memory: dict[str, Any]) -> dict[str, Any]:
    """
    Retourne le contexte courant.
    """
    return ensure_context(memory)


def reset_context(memory: dict[str, Any]) -> None:
    """
    Réinitialise le contexte vivant.
    """
    memory["context"] = {
        "mode": None,
        "last_question_type": None,
        "awaiting_user_reply": False,
        "riddle_answer": None,
        "riddle_answers": [],
        "riddle_question": None,
        "last_bot_question": None,
        "quiz_title": None,
        "quiz_questions": [],
        "quiz_index": 0,
        "quiz_score": 0,
    }


def start_riddle(
    memory: dict[str, Any],
    question: str,
    answer: str,
    accepted_answers: list[str] | None = None,
) -> None:
    """
    Active le mode devinette.
    """
    ctx = ensure_context(memory)
    ctx["mode"] = "riddle"
    ctx["last_question_type"] = "riddle"
    ctx["awaiting_user_reply"] = True
    ctx["riddle_question"] = question
    ctx["riddle_answer"] = answer
    ctx["riddle_answers"] = accepted_answers or [answer]
    ctx["last_bot_question"] = question

    # reset quiz si besoin
    ctx["quiz_title"] = None
    ctx["quiz_questions"] = []
    ctx["quiz_index"] = 0
    ctx["quiz_score"] = 0


def close_riddle(memory: dict[str, Any]) -> None:
    """
    Ferme le mode devinette.
    """
    ctx = ensure_context(memory)
    ctx["mode"] = None
    ctx["last_question_type"] = None
    ctx["awaiting_user_reply"] = False
    ctx["riddle_question"] = None
    ctx["riddle_answer"] = None
    ctx["riddle_answers"] = []
    ctx["last_bot_question"] = None


def get_riddle_answer(memory: dict[str, Any]) -> str | None:
    """
    Retourne la réponse principale de la devinette en cours.
    """
    ctx = ensure_context(memory)
    answer = ctx.get("riddle_answer")
    if isinstance(answer, str):
        return answer
    return None


def get_riddle_answers(memory: dict[str, Any]) -> list[str]:
    """
    Retourne les réponses acceptées pour la devinette.
    """
    ctx = ensure_context(memory)
    answers = ctx.get("riddle_answers", [])
    if isinstance(answers, list):
        return [item for item in answers if isinstance(item, str) and item.strip()]
    return []


def is_riddle_mode(memory: dict[str, Any]) -> bool:
    """
    Indique si le mode devinette est actif.
    """
    ctx = ensure_context(memory)
    return ctx.get("mode") == "riddle"


def start_quiz(memory: dict[str, Any], title: str, questions: list[dict[str, Any]]) -> None:
    """
    Active le mode quiz.
    """
    ctx = ensure_context(memory)
    ctx["mode"] = "quiz"
    ctx["last_question_type"] = "quiz"
    ctx["awaiting_user_reply"] = True
    ctx["quiz_title"] = title
    ctx["quiz_questions"] = questions or []
    ctx["quiz_index"] = 0
    ctx["quiz_score"] = 0
    ctx["last_bot_question"] = title

    # reset riddle si besoin
    ctx["riddle_question"] = None
    ctx["riddle_answer"] = None
    ctx["riddle_answers"] = []


def close_quiz(memory: dict[str, Any]) -> None:
    """
    Ferme le mode quiz.
    """
    ctx = ensure_context(memory)
    ctx["mode"] = None
    ctx["last_question_type"] = None
    ctx["awaiting_user_reply"] = False
    ctx["quiz_title"] = None
    ctx["quiz_questions"] = []
    ctx["quiz_index"] = 0
    ctx["quiz_score"] = 0
    ctx["last_bot_question"] = None


def is_quiz_mode(memory: dict[str, Any]) -> bool:
    """
    Indique si le mode quiz est actif.
    """
    ctx = ensure_context(memory)
    return ctx.get("mode") == "quiz"


def get_quiz_title(memory: dict[str, Any]) -> str | None:
    """
    Retourne le titre du quiz.
    """
    ctx = ensure_context(memory)
    title = ctx.get("quiz_title")
    if isinstance(title, str):
        return title
    return None


def get_quiz_questions(memory: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Retourne la liste des questions du quiz.
    """
    ctx = ensure_context(memory)
    questions = ctx.get("quiz_questions", [])
    if isinstance(questions, list):
        return [item for item in questions if isinstance(item, dict)]
    return []


def get_quiz_index(memory: dict[str, Any]) -> int:
    """
    Retourne l'index courant du quiz.
    """
    ctx = ensure_context(memory)
    index = ctx.get("quiz_index", 0)
    if isinstance(index, int):
        return index
    return 0


def get_quiz_score(memory: dict[str, Any]) -> int:
    """
    Retourne le score actuel du quiz.
    """
    ctx = ensure_context(memory)
    score = ctx.get("quiz_score", 0)
    if isinstance(score, int):
        return score
    return 0


def get_quiz_total(memory: dict[str, Any]) -> int:
    """
    Retourne le nombre total de questions du quiz.
    """
    return len(get_quiz_questions(memory))


def get_quiz_question(memory: dict[str, Any]) -> dict[str, Any] | None:
    """
    Retourne la question courante du quiz.
    """
    questions = get_quiz_questions(memory)
    index = get_quiz_index(memory)

    if 0 <= index < len(questions):
        return questions[index]

    return None


def advance_quiz(memory: dict[str, Any], answered_correctly: bool) -> dict[str, Any] | None:
    """
    Fait avancer le quiz après une réponse.
    Retourne la question suivante, ou None si le quiz est terminé.
    """
    ctx = ensure_context(memory)

    if answered_correctly:
        current_score = get_quiz_score(memory)
        ctx["quiz_score"] = current_score + 1

    next_index = get_quiz_index(memory) + 1
    ctx["quiz_index"] = next_index

    questions = get_quiz_questions(memory)
    if 0 <= next_index < len(questions):
        return questions[next_index]

    return None


def set_last_bot_question(
    memory: dict[str, Any],
    question: str,
    question_type: str = "general",
) -> None:
    """
    Enregistre la dernière question posée par Zoe.
    """
    ctx = ensure_context(memory)
    ctx["last_bot_question"] = question
    ctx["last_question_type"] = question_type
    ctx["awaiting_user_reply"] = True


def clear_waiting_flag(memory: dict[str, Any]) -> None:
    """
    Indique que Zoe n'attend plus spécialement une réponse.
    """
    ctx = ensure_context(memory)
    ctx["awaiting_user_reply"] = False


def is_waiting_reply(memory: dict[str, Any]) -> bool:
    """
    Indique si Zoe attend une réponse utilisateur.
    """
    ctx = ensure_context(memory)
    return bool(ctx.get("awaiting_user_reply", False))


def get_last_question_type(memory: dict[str, Any]) -> str | None:
    """
    Retourne le type de la dernière question posée.
    """
    ctx = ensure_context(memory)
    qtype = ctx.get("last_question_type")
    if isinstance(qtype, str):
        return qtype
    return None 
