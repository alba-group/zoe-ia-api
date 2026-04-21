from typing import Any

from core.knowledge.knowledge_search import (
    search_building_category,
    search_faq,
    search_user_help,
)
from core.skills.skill_registry import get_enabled_skills, get_skill_metadata, is_skill_enabled


def route_local_knowledge(
    user_message: str,
    memory: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []

    user_help_match = search_user_help(user_message)
    if user_help_match is not None:
        payload = dict(user_help_match)
        skill_name = str(payload.get("skill", "")).strip()
        if skill_name:
            payload["skill_enabled"] = is_skill_enabled(skill_name, memory)
            skill_metadata = get_skill_metadata(skill_name, memory)
            if skill_metadata is not None:
                payload["skill_title"] = skill_metadata.get("title", skill_name)

        if payload.get("id") == "capabilities_overview":
            payload["enabled_skills"] = get_enabled_skills(memory)
            payload["enabled_skill_titles"] = [
                metadata.get("title", skill_name)
                for skill_name, metadata in (
                    (skill, get_skill_metadata(skill, memory) or {})
                    for skill in get_enabled_skills(memory)
                )
            ]

        candidates.append(
            {
                "source": "user_help",
                "match_type": "keyword",
                "confidence": _build_confidence(payload.get("score", 0), base=0.84),
                "payload": payload,
            }
        )

    faq_match = search_faq(user_message)
    if faq_match is not None:
        candidates.append(
            {
                "source": "faq",
                "match_type": "keyword",
                "confidence": _build_confidence(faq_match.get("score", 0), base=0.8),
                "payload": faq_match,
            }
        )

    building_match = search_building_category(user_message)
    if building_match is not None:
        candidates.append(
            {
                "source": "buildings",
                "match_type": "category",
                "confidence": _build_confidence(building_match.get("score", 0), base=0.78),
                "payload": building_match,
            }
        )

    if not candidates:
        return None

    return max(candidates, key=_sort_key)


def _build_confidence(score: Any, base: float) -> float:
    try:
        numeric_score = int(score)
    except Exception:
        numeric_score = 0

    confidence = base + min(numeric_score, 6) * 0.03
    return round(min(confidence, 0.99), 2)


def _sort_key(item: dict[str, Any]) -> tuple[float, int]:
    source_priority = {
        "user_help": 3,
        "faq": 2,
        "buildings": 1,
    }
    return (
        float(item.get("confidence", 0.0)),
        source_priority.get(str(item.get("source", "")), 0),
    )
