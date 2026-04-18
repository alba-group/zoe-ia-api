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
            "riddle_question": None,
            "last_bot_question": None,
        }

    return memory["context"]


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
        "riddle_question": None,
        "last_bot_question": None,
    }


def start_riddle(memory: dict[str, Any], question: str, answer: str) -> None:
    """
    Active le mode devinette.
    """
    ctx = ensure_context(memory)
    ctx["mode"] = "riddle"
    ctx["last_question_type"] = "riddle"
    ctx["awaiting_user_reply"] = True
    ctx["riddle_question"] = question
    ctx["riddle_answer"] = answer
    ctx["last_bot_question"] = question


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
    ctx["last_bot_question"] = None


def set_last_bot_question(memory: dict[str, Any], question: str, question_type: str = "general") -> None:
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
    ctx = ensure_context(memory)
    return bool(ctx.get("awaiting_user_reply", False))


def is_riddle_mode(memory: dict[str, Any]) -> bool:
    ctx = ensure_context(memory)
    return ctx.get("mode") == "riddle"


def get_riddle_answer(memory: dict[str, Any]) -> str | None:
    ctx = ensure_context(memory)
    answer = ctx.get("riddle_answer", None)
    if isinstance(answer, str):
        return answer
    return None


def get_last_question_type(memory: dict[str, Any]) -> str | None:
    ctx = ensure_context(memory)
    qtype = ctx.get("last_question_type", None)
    if isinstance(qtype, str):
        return qtype
    return None 
