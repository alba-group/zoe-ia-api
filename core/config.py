import os
from pathlib import Path

BASE_DIR = Path(file).resolve().parent.parent
CORE_DIR = BASE_DIR / "core"
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
TESTS_DIR = BASE_DIR / "tests"

MEMORY_FILE = str(DATA_DIR / "memory.json")
PROFILE_FILE = str(DATA_DIR / "profile.json")
HISTORY_FILE = str(DATA_DIR / "history.json")
LOG_FILE = str(DATA_DIR / "logs.txt")

def _env_bool(name: str, default: bool) -> bool:
value = os.getenv(name)
if value is None:
return default
return value.strip().lower() in {"1", "true", "yes", "on"}

def _env_int(name: str, default: int, minimum: int | None = None) -> int:
raw_value = os.getenv(name, str(default)).strip()
try:
parsed = int(raw_value)
except ValueError:
parsed = default

if minimum is not None:
    return max(parsed, minimum)
return parsed
def _env_float(name: str, default: float, minimum: float | None = None) -> float:
raw_value = os.getenv(name, str(default)).strip()
try:
parsed = float(raw_value)
except ValueError:
parsed = default

if minimum is not None:
    return max(parsed, minimum)
return parsed
APP_NAME = os.getenv("APP_NAME", "Zoe IA").strip() or "Zoe IA"
APP_VERSION = os.getenv("APP_VERSION", "1.1.0").strip() or "1.1.0"

API_TITLE = os.getenv("API_TITLE", "Zoe IA API").strip() or "Zoe IA API"
API_DESCRIPTION = (
os.getenv(
"API_DESCRIPTION",
"API FastAPI de Zoe IA pour Android et clients compatibles.",
).strip()
or "API FastAPI de Zoe IA pour Android et clients compatibles."
)

LANGUAGE = os.getenv("LANGUAGE", "fr").strip() or "fr"
TIMEZONE = os.getenv("TIMEZONE", "Europe/Paris").strip() or "Europe/Paris"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO"

DEBUG = _env_bool("DEBUG", False)

HISTORY_LIMIT = _env_int("MEMORY_LIMIT", 12, minimum=4)
LLM_HISTORY_LIMIT = _env_int("LLM_HISTORY_LIMIT", 6, minimum=2)
MAX_USER_MESSAGE_LENGTH = _env_int("MAX_USER_MESSAGE_LENGTH", 1500, minimum=128)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini").strip() or "gpt-4o-mini"
IMAGE_MODEL_NAME = os.getenv("IMAGE_MODEL_NAME", "gpt-image-1").strip() or "gpt-image-1"
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1024x1024").strip() or "1024x1024"

OPENAI_TIMEOUT_SECONDS = _env_float("OPENAI_TIMEOUT_SECONDS", 20.0, minimum=5.0)
OPENAI_MAX_RETRIES = _env_int("OPENAI_MAX_RETRIES", 1, minimum=0)
CHAT_TIMEOUT_SECONDS = _env_float("CHAT_TIMEOUT_SECONDS", 25.0, minimum=5.0)

WEB_ENABLED = _env_bool("WEB_ENABLED", False)

FIREBASE_STORAGE_BUCKET = (
os.getenv("FIREBASE_STORAGE_BUCKET", "zoe-ia-5d52f.firebasestorage.app").strip()
or "zoe-ia-5d52f.firebasestorage.app"
)
FIREBASE_SERVICE_ACCOUNT_FILE = os.getenv("FIREBASE_SERVICE_ACCOUNT_FILE", "").strip()
FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()

API_RATE_LIMIT_WINDOW_SECONDS = _env_int(
"API_RATE_LIMIT_WINDOW_SECONDS",
60,
minimum=5,
)
API_RATE_LIMIT_MAX_REQUESTS = _env_int(
"API_RATE_LIMIT_MAX_REQUESTS",
20,
minimum=1,
)
API_SPAM_REPEAT_WINDOW_SECONDS = _env_int(
"API_SPAM_REPEAT_WINDOW_SECONDS",
120,
minimum=5,
)
API_SPAM_REPEAT_MAX = _env_int(
"API_SPAM_REPEAT_MAX",
3,
minimum=1,
)

def validate_config() -> list[str]:
warnings: list[str] = []

if not OPENAI_API_KEY:
    warnings.append("OPENAI_API_KEY est vide : les fonctions IA distantes ne seront pas disponibles.")

if not FIREBASE_STORAGE_BUCKET:
    warnings.append("FIREBASE_STORAGE_BUCKET est vide : l'upload Firebase Storage ne fonctionnera pas.")

return warnings
