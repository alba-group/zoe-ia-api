import os
from pathlib import Path

from dotenv import load_dotenv


# Charge les variables du fichier .env
load_dotenv()


# =========================
# CHEMINS PRINCIPAUX
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = BASE_DIR / "core"
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
TESTS_DIR = BASE_DIR / "tests"


# =========================
# FICHIERS DATA
# =========================
MEMORY_FILE = str(DATA_DIR / "memory.json")
PROFILE_FILE = str(DATA_DIR / "profile.json")
HISTORY_FILE = str(DATA_DIR / "history.json")
LOG_FILE = str(DATA_DIR / "logs.txt")


# =========================
# INFOS APPLICATION
# =========================
APP_NAME = os.getenv("APP_NAME", "Zoe")
APP_VERSION = os.getenv("APP_VERSION", "1.0")
LANGUAGE = os.getenv("LANGUAGE", "fr")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Paris")


# =========================
# DEBUG / LOGS
# =========================
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


# =========================
# MÉMOIRE
# =========================
HISTORY_LIMIT = int(os.getenv("MEMORY_LIMIT", "10"))


# =========================
# OPENAI / IA
# =========================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5.2")


# =========================
# VALIDATIONS MINIMALES
# =========================
def validate_config() -> None:
    """
    Vérifie la configuration minimale du projet.
    """
    if not OPENAI_API_KEY:
        print(
            "Attention : OPENAI_API_KEY est vide. "
            "Zoe ne pourra pas utiliser l'IA en ligne tant que la clé n'est pas ajoutée dans le fichier .env."
        ) 
