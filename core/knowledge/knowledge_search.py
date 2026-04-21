from typing import Any

from core.analyzer import normalize_text
from core.knowledge.knowledge_loader import (
    load_buildings_knowledge,
    load_faq_knowledge,
    load_user_help_knowledge,
)


BUILDING_INFORMATION_MARKERS = (
    "c est quoi",
    "qu est ce qu un",
    "qu est ce qu une",
    "definition",
    "quel type de lieu",
    "que veut dire",
    "a quoi sert",
    "dis moi ce qu est",
    "explique moi ce qu est",
    "explique ce qu est",
)


def search_building_category(text: str) -> dict[str, Any] | None:
    normalized = _normalize_query(text)
    if not normalized or not _looks_like_building_information_request(normalized):
        return None

    knowledge = load_buildings_knowledge()
    best_match = _find_best_match(knowledge.get("categories", []), normalized)
    if best_match is None:
        return None

    return {
        "name": best_match["item"].get("name", ""),
        "description": best_match["item"].get("description", ""),
        "keywords": best_match["item"].get("keywords", []),
        "score": best_match["score"],
    }


def search_faq(text: str) -> dict[str, Any] | None:
    normalized = _normalize_query(text)
    if not normalized:
        return None

    knowledge = load_faq_knowledge()
    best_match = _find_best_match(knowledge.get("items", []), normalized)
    if best_match is None:
        return None

    return {
        "id": best_match["item"].get("id", ""),
        "question": best_match["item"].get("question", ""),
        "answer": best_match["item"].get("answer", ""),
        "keywords": best_match["item"].get("keywords", []),
        "score": best_match["score"],
    }


def search_user_help(text: str) -> dict[str, Any] | None:
    normalized = _normalize_query(text)
    if not normalized or not _looks_like_user_help_request(normalized):
        return None

    knowledge = load_user_help_knowledge()
    best_match = _find_best_match(knowledge.get("items", []), normalized)
    if best_match is None:
        return None

    payload = {
        "id": best_match["item"].get("id", ""),
        "title": best_match["item"].get("title", ""),
        "description": best_match["item"].get("description", ""),
        "keywords": best_match["item"].get("keywords", []),
        "examples": best_match["item"].get("examples", []),
        "score": best_match["score"],
    }

    skill = best_match["item"].get("skill", "")
    if skill:
        payload["skill"] = skill

    return payload


def _find_best_match(items: list[dict[str, Any]], normalized_text: str) -> dict[str, Any] | None:
    best_match: dict[str, Any] | None = None

    for item in items:
        keywords = item.get("keywords", [])
        score = _score_keywords(normalized_text, keywords)
        if score <= 0:
            continue

        if best_match is None or score > best_match["score"]:
            best_match = {
                "item": item,
                "score": score,
            }

    return best_match


def _score_keywords(text: str, keywords: Any) -> int:
    if not isinstance(keywords, list):
        return 0

    score = 0
    for keyword in keywords:
        normalized_keyword = _normalize_query(str(keyword))
        if normalized_keyword and normalized_keyword in text:
            score += max(1, len(normalized_keyword.split()))

    return score


def _looks_like_building_information_request(text: str) -> bool:
    return any(marker in text for marker in BUILDING_INFORMATION_MARKERS)


def _looks_like_user_help_request(text: str) -> bool:
    explicit_requests = {
        "aide",
        "help",
        "capacites",
        "capacites disponibles",
        "fonctions",
        "fonctions disponibles",
        "modules disponibles",
        "que peux tu faire",
        "que sais tu faire",
        "quelles sont tes capacites",
        "quelles sont tes fonctions",
    }
    if text in explicit_requests:
        return True

    request_prefixes = (
        "que peux tu faire",
        "que sais tu faire",
        "quelles sont tes capacites",
        "quelles sont tes fonctions",
        "quels sont tes modules",
        "modules disponibles",
        "comment ",
        "peux tu ",
        "tu peux ",
        "explique ",
        "montre ",
        "dis moi ",
        "aide moi ",
    )

    return any(text.startswith(prefix) for prefix in request_prefixes)


def _normalize_query(text: str) -> str:
    return normalize_text(text).replace("'", " ").strip()
