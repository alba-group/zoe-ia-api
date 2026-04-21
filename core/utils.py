import json
from datetime import datetime
from pathlib import Path

from core.config import (
    DATA_DIR,
    DOCS_DIR,
    TESTS_DIR,
    DOCX_DIR,
    KNOWLEDGE_DIR,
    PERSONALITY_DIR,
    PDF_DIR,
    MEMORY_FILE,
    PROFILE_FILE,
    HISTORY_FILE,
    LOG_FILE,
    TIMEZONE,
)
from core.skills.skill_registry import get_default_skill_flags


def current_datetime_string() -> str:
    """
    Retourne la date et l'heure actuelle sous forme lisible.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_json_file(file_path: str, default_content) -> None:
    """
    Crée un fichier JSON s'il n'existe pas déjà.
    """
    path = Path(file_path)

    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_content, f, ensure_ascii=False, indent=2)


def ensure_text_file(file_path: str, default_content: str = "") -> None:
    """
    Crée un fichier texte s'il n'existe pas déjà.
    """
    path = Path(file_path)

    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        with open(path, "w", encoding="utf-8") as f:
            f.write(default_content)


def ensure_project_files() -> None:
    """
    Vérifie et crée les dossiers/fichiers essentiels du projet Zoe.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    TESTS_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    DOCX_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    PERSONALITY_DIR.mkdir(parents=True, exist_ok=True)

    ensure_json_file(
        MEMORY_FILE,
        {
            "history": [],
            "profile": {
                "name": "",
                "city": "",
                "job": "",
                "likes": [],
                "dislikes": [],
                "projects": [],
                "goals": [],
                "important_people": [],
                "habits": [],
                "preferred_tone": "",
                "last_update": "",
            },
            "last_emotion": "unknown",
            "last_topic": "general",
            "preferences": {},
            "skills_enabled": get_default_skill_flags(),
            "known_locations": [],
            "trusted_facts": {},
            "session_context": {
                "mood": "",
                "energy": "",
                "current_topic": "",
            },
            "long_term_memory": [],
        }
    )

    ensure_json_file(PROFILE_FILE, {})
    ensure_json_file(HISTORY_FILE, [])
    ensure_text_file(LOG_FILE, "")


def log_event(message: str) -> None:
    """
    Écrit un événement dans le fichier de logs.
    """
    timestamp = current_datetime_string()
    line = f"[{timestamp}] {message}\n"

    log_path = Path(LOG_FILE)
    if not log_path.parent.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def safe_read_json(file_path: str, default_value):
    """
    Lit un JSON proprement, sinon retourne une valeur par défaut.
    """
    path = Path(file_path)

    if not path.exists():
        return default_value

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_value


def safe_write_json(file_path: str, data) -> None:
    """
    Écrit un JSON proprement.
    """
    path = Path(file_path)

    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pretty_separator(size: int = 60, char: str = "=") -> str:
    """
    Retourne une ligne séparatrice.
    """
    return char * size


def normalize_user_text(text: str) -> str:
    """
    Nettoie un texte utilisateur simple.
    """
    return text.strip()


def get_timezone_name() -> str:
    """
    Retourne le fuseau configuré.
    """
    return TIMEZONE 
