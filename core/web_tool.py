from typing import Any

from core.llm_client import create_llm_client, build_zoe_system_prompt


WEB_KEYWORDS = {
    "météo",
    "meteo",
    "temps",
    "actualité",
    "actu",
    "news",
    "cherche",
    "recherche",
    "recherche-moi",
    "recherche moi",
    "trouve",
    "qui est",
    "c'est qui",
    "prix",
    "cours",
    "bitcoin",
    "horaire",
    "horaires",
    "adresse",
    "site officiel",
    "youtube",
    "google",
}


def should_use_web(user_message: str) -> bool:
    """
    Détecte si le message ressemble à une demande de recherche web.
    """
    text = user_message.lower().strip()

    if not text:
        return False

    for keyword in WEB_KEYWORDS:
        if keyword in text:
            return True

    return False


def format_sources(sources: list[dict[str, str]]) -> str:
    """
    Formate les sources en texte lisible.
    """
    if not sources:
        return ""

    lines = []
    for index, source in enumerate(sources[:5], start=1):
        title = source.get("title", "").strip() or "Source"
        domain = source.get("domain", "").strip() or source.get("url", "").strip()
        lines.append(f"{index}. {title} — {domain}")

    return "\n".join(lines)


def search_web(
    user_message: str,
    user_name: str = "",
    conversation: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Lance une vraie recherche web via le client OpenAI.
    """
    client = create_llm_client()

    system_prompt = (
        build_zoe_system_prompt(user_name=user_name)
        + " Quand tu utilises le web, réponds clairement, simplement, en français."
    )

    result = client.ask_with_web(
        user_message=user_message,
        system_prompt=system_prompt,
        conversation=conversation,
    )

    return {
        "ok": result.error is None,
        "text": result.text if result.text else "",
        "used_web": result.used_web,
        "sources": result.sources,
        "sources_text": format_sources(result.sources),
        "error": result.error,
    }


def build_web_reply(
    user_message: str,
    user_name: str = "",
    conversation: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Retourne une réponse prête à être utilisée dans brain.py.
    """
    web_result = search_web(
        user_message=user_message,
        user_name=user_name,
        conversation=conversation,
    )

    if not web_result["ok"]:
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "web",
            "intent": "clarify",
            "reply": (
                "Je n'ai pas réussi à faire la recherche web pour le moment. "
                f"Détail : {web_result['error']}"
            ),
            "sources": [],
            "used_web": False,
        }

    reply_text = web_result["text"].strip()

    if web_result["sources_text"]:
        reply_text += "\n\nSources :\n" + web_result["sources_text"]

    return {
        "emotion": "unknown",
        "precision": "precise",
        "topic": "web",
        "intent": "clarify",
        "reply": reply_text,
        "sources": web_result["sources"],
        "used_web": web_result["used_web"],
    } 
