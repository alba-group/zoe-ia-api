from typing import Any

from core.llm_client import create_llm_client


CODE_KEYWORDS = {
    "code",
    "script",
    "fonction",
    "programme",
    "fichier",
    "classe",
    "application",
    "app",
    "python",
    "kotlin",
    "java",
    "html",
    "css",
    "javascript",
    "js",
    "sql",
    "php",
    "c++",
    "c#",
    "api",
    "bug",
    "corrige",
    "corriger",
    "débogue",
    "debug",
    "algo",
    "algorithme",
}


LANGUAGE_HINTS = {
    "python": "python",
    "kotlin": "kotlin",
    "java": "java",
    "html": "html",
    "css": "css",
    "javascript": "javascript",
    "js": "javascript",
    "sql": "sql",
    "php": "php",
    "c++": "cpp",
    "c#": "csharp",
}


def should_use_code_tool(user_message: str) -> bool:
    """
    Détecte si le message ressemble à une demande de code.
    """
    text = user_message.lower().strip()

    if not text:
        return False

    for keyword in CODE_KEYWORDS:
        if keyword in text:
            return True

    return False


def detect_language(user_message: str) -> str:
    """
    Essaie de deviner le langage demandé.
    """
    text = user_message.lower().strip()

    for hint, language in LANGUAGE_HINTS.items():
        if hint in text:
            return language

    return "python"


def build_code_prompt(user_message: str, language: str) -> str:
    """
    Construit une consigne plus propre pour le moteur de génération de code.
    """
    return (
        f"Demande utilisateur : {user_message}\n\n"
        f"Langage demandé : {language}\n\n"
        "Consignes :\n"
        "- écrire un code propre, clair et complet\n"
        "- ajouter des commentaires utiles seulement si nécessaire\n"
        "- éviter le blabla inutile\n"
        "- donner un résultat prêt à copier-coller\n"
        "- si la demande est ambiguë, faire l'interprétation la plus logique\n"
    )


def generate_code_reply(
    user_message: str,
    conversation: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Génère une réponse orientée code via llm_client.py
    """
    client = create_llm_client()
    language = detect_language(user_message)
    prompt = build_code_prompt(user_message, language)

    result = client.generate_code(
        user_request=prompt,
        language=language,
        conversation=conversation,
    )

    if result.error:
        return {
            "ok": False,
            "language": language,
            "reply": (
                "Je n'ai pas réussi à générer le code pour le moment. "
                f"Détail : {result.error}"
            ),
            "error": result.error,
        }

    return {
        "ok": True,
        "language": language,
        "reply": result.text.strip(),
        "error": None,
    }


def build_code_result(
    user_message: str,
    conversation: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Retourne un dictionnaire prêt à être utilisé dans brain.py
    """
    code_result = generate_code_reply(
        user_message=user_message,
        conversation=conversation,
    )

    if not code_result["ok"]:
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "code",
            "intent": "clarify",
            "reply": code_result["reply"],
            "language": code_result["language"],
        }

    return {
        "emotion": "positive",
        "precision": "precise",
        "topic": "code",
        "intent": "reflect",
        "reply": code_result["reply"],
        "language": code_result["language"],
    } 
