from typing import Any

from core.llm_client import create_llm_client


CODE_KEYWORDS = {
    "code",
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
    "backend",
    "frontend",
    "android",
    "compose",
    "jetpack compose",
    "fastapi",
    "base de donnees",
    "base de données",
}

TECHNICAL_SCRIPT_EXPRESSIONS = {
    "script python",
    "script javascript",
    "script js",
    "script kotlin",
    "script java",
    "script sql",
    "script html",
    "script css",
    "script php",
    "script c++",
    "script c#",
}

NON_CODE_SCRIPT_EXPRESSIONS = {
    "script de musique",
    "script musical",
    "script de chanson",
    "script de rap",
    "script video",
    "script vidéo",
    "script de clip",
    "script narratif",
    "script de presentation",
    "script de présentation",
    "script youtube",
    "script tiktok",
    "paroles",
    "chanson",
    "musique",
    "rap",
    "refrain",
    "couplet",
    "intro",
    "outro",
    "pont",
    "prompt",
    "prompt suno",
    "bio",
    "description",
    "texte",
    "poeme",
    "poésie",
    "poesie",
    "scenario",
    "scénario",
    "storytelling",
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


def _normalize(text: str) -> str:
    return (text or "").lower().strip()


def _looks_like_non_code_request(text: str) -> bool:
    if not text:
        return False

    return any(expr in text for expr in NON_CODE_SCRIPT_EXPRESSIONS)


def _looks_like_explicit_code_request(text: str) -> bool:
    if not text:
        return False

    if any(expr in text for expr in TECHNICAL_SCRIPT_EXPRESSIONS):
        return True

    return any(keyword in text for keyword in CODE_KEYWORDS)


def should_use_code_tool(user_message: str) -> bool:
    """
    Détecte si le message ressemble vraiment à une demande de code.
    """
    text = _normalize(user_message)

    if not text:
        return False

    # priorité absolue : si ça ressemble à une demande créative/textuelle,
    # on ne part pas en mode code
    if _looks_like_non_code_request(text):
        return False

    return _looks_like_explicit_code_request(text)


def detect_language(user_message: str) -> str:
    """
    Essaie de deviner le langage demandé.
    """
    text = _normalize(user_message)

    for hint, language in LANGUAGE_HINTS.items():
        if hint in text:
            return language

    # si la demande est code mais sans langage explicite,
    # on garde python comme fallback raisonnable
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
        "- ne produire que du contenu technique cohérent avec la demande\n"
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