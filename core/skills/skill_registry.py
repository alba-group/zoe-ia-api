from copy import deepcopy
from typing import Any


DEFAULT_SKILL_REGISTRY: dict[str, dict[str, Any]] = {
    "chat": {
        "title": "Conversation",
        "description": "Discussion generale et reponses naturelles.",
        "enabled_by_default": True,
        "category": "core",
    },
    "image_create": {
        "title": "Creation d'image",
        "description": "Generation d'images a partir d'une description.",
        "enabled_by_default": True,
        "category": "image",
    },
    "image_edit": {
        "title": "Modification d'image",
        "description": "Retouche et modification d'images existantes.",
        "enabled_by_default": True,
        "category": "image",
    },
    "image_analyze": {
        "title": "Analyse d'image",
        "description": "Description et analyse de contenus visuels.",
        "enabled_by_default": True,
        "category": "image",
    },
    "pdf_create": {
        "title": "Creation PDF",
        "description": "Generation de fichiers PDF a telecharger.",
        "enabled_by_default": True,
        "category": "document",
    },
    "pdf_analyze": {
        "title": "Analyse PDF",
        "description": "Lecture, resume et analyse de fichiers PDF.",
        "enabled_by_default": True,
        "category": "document",
    },
    "docx_create": {
        "title": "Creation Word",
        "description": "Generation de fichiers Word / DOCX.",
        "enabled_by_default": True,
        "category": "document",
    },
    "docx_analyze": {
        "title": "Analyse Word",
        "description": "Lecture, resume et analyse de fichiers Word / DOCX.",
        "enabled_by_default": True,
        "category": "document",
    },
    "gps_local_search": {
        "title": "Recherche locale",
        "description": "Recherche de lieux a proximite avec coordonnees GPS.",
        "enabled_by_default": True,
        "category": "location",
    },
    "web_search": {
        "title": "Recherche web",
        "description": "Recherche d'informations sur le web.",
        "enabled_by_default": True,
        "category": "search",
    },
    "code_generation": {
        "title": "Generation de code",
        "description": "Aide technique et generation de code.",
        "enabled_by_default": True,
        "category": "technical",
    },
}


def get_default_skill_flags() -> dict[str, bool]:
    return {
        skill_name: bool(metadata.get("enabled_by_default", True))
        for skill_name, metadata in DEFAULT_SKILL_REGISTRY.items()
    }


def skill_exists(skill_name: str) -> bool:
    return str(skill_name or "").strip() in DEFAULT_SKILL_REGISTRY


def get_skill_registry(memory: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    registry = deepcopy(DEFAULT_SKILL_REGISTRY)
    skill_flags = _normalize_skill_flags(memory.get("skills_enabled") if isinstance(memory, dict) else None)

    for skill_name, metadata in registry.items():
        metadata["enabled"] = skill_flags.get(
            skill_name,
            bool(metadata.get("enabled_by_default", True)),
        )

    return registry


def get_skill_metadata(
    skill_name: str,
    memory: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    clean_name = str(skill_name or "").strip()
    if not clean_name:
        return None

    registry = get_skill_registry(memory)
    metadata = registry.get(clean_name)
    if metadata is None:
        return None

    return deepcopy(metadata)


def is_skill_enabled(
    skill_name: str,
    memory: dict[str, Any] | None = None,
) -> bool:
    metadata = get_skill_metadata(skill_name, memory)
    if metadata is None:
        return False
    return bool(metadata.get("enabled", False))


def get_enabled_skills(memory: dict[str, Any] | None = None) -> list[str]:
    registry = get_skill_registry(memory)
    return [
        skill_name
        for skill_name, metadata in registry.items()
        if bool(metadata.get("enabled", False))
    ]


def _normalize_skill_flags(raw_value: Any) -> dict[str, bool]:
    normalized = get_default_skill_flags()
    if not isinstance(raw_value, dict):
        return normalized

    for skill_name, skill_value in raw_value.items():
        clean_name = str(skill_name or "").strip()
        if not clean_name:
            continue
        normalized[clean_name] = _coerce_bool(skill_value, normalized.get(clean_name, bool(skill_value)))

    return normalized


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "enabled", "active"}:
            return True
        if normalized in {"0", "false", "no", "off", "disabled", "inactive"}:
            return False

    return default
