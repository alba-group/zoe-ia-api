from typing import Any

from core.llm_client import create_llm_client


# Mots-clés forts : vraie intention de développement
STRONG_CODE_KEYWORDS = {
    "code",
    "script",
    "fonction",
    "programme",
    "classe",
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
    "algo",
    "algorithme",
}

# Expressions explicites qui montrent clairement une demande de code
CODE_PHRASES = {
    "écris un code",
    "ecris un code",
    "écris moi un code",
    "ecris moi un code",
    "écris-moi un code",
    "ecris-moi un code",
    "écris un script",
    "ecris un script",
    "écris moi un script",
    "ecris moi un script",
    "écris-moi un script",
    "ecris-moi un script",
    "génère un code",
    "genere un code",
    "génère moi un code",
    "genere moi un code",
    "génère un script",
    "genere un script",
    "génère moi un script",
    "genere moi un script",
    "crée un script",
    "cree un script",
    "crée moi un script",
    "cree moi un script",
    "développe un code",
    "developpe un code",
    "fais un code",
    "fais moi un code",
    "fais-moi un code",
    "corrige ce code",
    "corrige mon code",
    "debug ce code",
    "débogue ce code",
    "debloque ce code",
}

# Mots / phrases qui doivent empêcher le mode code
NON_CODE_PATTERNS = {
    "comment tu t'appelles",
    "tu t'appelles comment",
    "quel est ton nom",
    "c'est quoi ton prénom",
    "qui es-tu",
    "tu es qui",
    "tu es quoi",
    "comment je m'appelle",
    "tu connais mon prénom",
    "tu te souviens de mon prénom",
    "c'est quoi mon prénom",
    "je m'appelle pas",
    "je ne m'appelle pas",
    "ce n'est pas mon prénom",
    "c'est pas mon prénom",
    "tu te trompes de prénom",
    "salut",
    "bonjour",
    "bonsoir",
    "coucou",
    "merci",
    "ça va",
    "ca va",
    "je t'aime",
    "je suis triste",
    "j'ai besoin de parler",
    "appelle",
    "appel",
    "contacte",
    "message à",
    "sms à",
    "écris à",
    "ecris à",
    "calendrier",
    "événement",
    "evenement",
    "rendez-vous",
    "rappel",
    "note",
    "bloc-notes",
    "bloc notes",
    "keep",
    "image",
    "dessine",
    "génère une image",
    "genere une image",
    "photo de",
    "illustration de",
    "météo",
    "meteo",
    "cherche",
    "recherche",
    "qui est",
    "c'est qui",
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


def _normalize_text(value: str) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().lower().split())


def should_use_code_tool(user_message: str) -> bool:
    """
    Détecte uniquement les vraies demandes de code.
    Le mode code doit être strict pour éviter d'avaler
    les messages normaux de conversation.
    """
    text = _normalize_text(user_message)

    if not text:
        return False

    # 1. Protection forte : si le message ressemble à du chat normal,
    #    à une action téléphone, web, image, prénom, etc. => pas de code
    for blocked in NON_CODE_PATTERNS:
        if blocked in text:
            return False

    # 2. Si une phrase explicite de code est trouvée => oui
    for phrase in CODE_PHRASES:
        if phrase in text:
            return True

    # 3. Si mot-clé fort + verbe d'action lié au code => oui
    action_words = {
        "écris", "ecris", "génère", "genere", "crée", "cree",
        "développe", "developpe", "fais", "corrige", "corriger",
        "debug", "débogue", "debloque",
    }

    contains_strong_keyword = any(keyword in text for keyword in STRONG_CODE_KEYWORDS)
    contains_action_word = any(word in text for word in action_words)

    if contains_strong_keyword and contains_action_word:
        return True

    # 4. Si le message commence directement par un langage ou une demande de code
    direct_prefixes = (
        "python ",
        "kotlin ",
        "java ",
        "html ",
        "css ",
        "javascript ",
        "js ",
        "sql ",
        "php ",
        "c++ ",
        "c# ",
        "code ",
        "script ",
    )

    if text.startswith(direct_prefixes):
        return True

    return False


def detect_language(user_message: str) -> str:
    """
    Essaie de deviner le langage demandé.
    """
    text = _normalize_text(user_message)

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
