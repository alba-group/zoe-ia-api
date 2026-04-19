import asyncio
import logging
import time
import traceback
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.brain import process_user_message
from core.config import (
    API_DESCRIPTION,
    API_RATE_LIMIT_MAX_REQUESTS,
    API_RATE_LIMIT_WINDOW_SECONDS,
    API_SPAM_REPEAT_MAX,
    API_SPAM_REPEAT_WINDOW_SECONDS,
    API_TITLE,
    APP_VERSION,
    CHAT_TIMEOUT_SECONDS,
    DEBUG,
    MAX_USER_MESSAGE_LENGTH,
    MODEL_NAME,
    OPENAI_API_KEY,
    validate_config,
)
from core.memory import apply_identity_context, clear_memory, get_memory_stats, load_memory, save_memory
from core.utils import ensure_project_files, log_event


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zoe")


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        ...,
        min_length=1,
        max_length=MAX_USER_MESSAGE_LENGTH,
        description="Message utilisateur envoye a Zoe.",
        examples=["Salut Zoe"],
    )
    uid: str | None = Field(
        default=None,
        max_length=128,
        description="UID Firebase Auth de l'utilisateur connecte, si disponible.",
    )
    account_key: str | None = Field(
        default=None,
        max_length=120,
        description="Identite stable du compte ou de la session locale.",
    )
    user_name: str | None = Field(
        default=None,
        max_length=80,
        description="Nom fiable du compte actuellement connecte, si disponible.",
    )
    attached_image_url: str | None = Field(
        default=None,
        max_length=3000,
        description="URL de l'image jointe actuellement envoyee avec le message.",
    )
    attached_image_mime_type: str | None = Field(
        default=None,
        max_length=80,
        description="Type MIME de l'image jointe, si disponible.",
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = " ".join(value.split()).strip()
        if not cleaned:
            raise ValueError("Le message est vide.")
        return cleaned

    @field_validator("uid", "account_key", "user_name", "attached_image_url", "attached_image_mime_type")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        cleaned = " ".join(value.split()).strip()
        return cleaned or None


class ChatResponse(BaseModel):
    ok: bool = True
    reply: str
    emotion: str = "unknown"
    precision: str = "vague"
    topic: str = "general"
    intent: str = "clarify"
    thought_summary: str = ""
    strategy: str = ""
    tone: str = ""
    tool_type: str | None = None
    image_base64: str | None = None
    image_url: str | None = None
    image_mime_type: str | None = None
    image_prompt: str | None = None
    language: str | None = None


class MemoryResponse(BaseModel):
    ok: bool = True
    profile: dict[str, Any]
    last_emotion: str
    last_topic: str
    history_count: int


class GenericResponse(BaseModel):
    ok: bool = True
    message: str


class VersionResponse(BaseModel):
    ok: bool = True
    name: str
    version: str
    model: str
    llm_configured: bool


class StatsResponse(BaseModel):
    ok: bool = True
    history_count: int
    recent_history_count: int
    profile_fields: int
    last_emotion: str
    last_topic: str
    rate_limit_window_seconds: int
    rate_limit_max_requests: int


class ErrorResponse(BaseModel):
    ok: bool = False
    message: str
    request_id: str | None = None
    errors: list[dict[str, Any]] | None = None


class RequestGuard:
    def __init__(
        self,
        rate_limit_window_seconds: int,
        rate_limit_max_requests: int,
        repeat_window_seconds: int,
        repeat_max: int,
    ) -> None:
        self.rate_limit_window_seconds = rate_limit_window_seconds
        self.rate_limit_max_requests = rate_limit_max_requests
        self.repeat_window_seconds = repeat_window_seconds
        self.repeat_max = repeat_max
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._messages: dict[str, deque[tuple[float, str]]] = defaultdict(deque)

    def check(self, client_key: str, message: str | None = None) -> None:
        now = time.monotonic()
        requests = self._requests[client_key]

        while requests and now - requests[0] > self.rate_limit_window_seconds:
            requests.popleft()

        if len(requests) >= self.rate_limit_max_requests:
            raise HTTPException(
                status_code=429,
                detail="Trop de requetes. Reessaie dans un instant.",
            )

        requests.append(now)

        if not message:
            return

        normalized_message = " ".join(message.lower().split())
        messages = self._messages[client_key]

        while messages and now - messages[0][0] > self.repeat_window_seconds:
            messages.popleft()

        repeated_count = sum(
            1
            for _, existing_message in messages
            if existing_message == normalized_message
        )

        if repeated_count >= self.repeat_max:
            raise HTTPException(
                status_code=429,
                detail="Message repete trop souvent. Attends un instant avant de recommencer.",
            )

        messages.append((now, normalized_message))


request_guard = RequestGuard(
    rate_limit_window_seconds=API_RATE_LIMIT_WINDOW_SECONDS,
    rate_limit_max_requests=API_RATE_LIMIT_MAX_REQUESTS,
    repeat_window_seconds=API_SPAM_REPEAT_WINDOW_SECONDS,
    repeat_max=API_SPAM_REPEAT_MAX,
)


def get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def get_client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    client = request.client.host if request.client else None
    return client or "unknown"


def safe_load_memory() -> dict[str, Any]:
    try:
        return load_memory()
    except Exception:
        logger.exception("Impossible de charger la memoire")
        print(traceback.format_exc())
        raise


def process_chat_message(
    user_message: str,
    uid: str | None = None,
    account_key: str | None = None,
    user_name: str | None = None,
    attached_image_url: str | None = None,
    attached_image_mime_type: str | None = None,
) -> dict[str, Any]:
    memory = safe_load_memory()
    return process_user_message(
        user_message,
        memory,
        identity={
            "user_uid": uid or "",
            "account_key": account_key or "",
            "user_name": user_name or "",
        },
        attached_image_url=attached_image_url or "",
        attached_image_mime_type=attached_image_mime_type or "",
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_project_files()

    for warning in validate_config():
        logger.warning(warning)

    logger.info("Demarrage de %s %s", API_TITLE, APP_VERSION)
    log_event("Demarrage API FastAPI.")
    yield
    logger.info("Arret de %s", API_TITLE)
    log_event("Arret API FastAPI.")


app = FastAPI(
    title=API_TITLE,
    version=APP_VERSION,
    description=API_DESCRIPTION,
    debug=DEBUG,
    lifespan=lifespan,
    contact={"name": "Zoe IA API"},
    openapi_tags=[
        {"name": "Core", "description": "Endpoints principaux de disponibilite et version."},
        {"name": "Chat", "description": "Discussion avec Zoe IA."},
        {"name": "Memory", "description": "Lecture et remise a zero de la memoire locale."},
        {"name": "Ops", "description": "Informations d'exploitation et statistiques simples."},
    ],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "Erreur non geree | rid=%s | method=%s | path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        print(traceback.format_exc())
        raise

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    response.headers["X-Request-ID"] = request_id

    logger.info(
        "rid=%s method=%s path=%s status=%s duration_ms=%.2f ip=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        get_client_key(request),
    )

    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [
        {
            "field": ".".join(str(item) for item in error.get("loc", [])[1:]),
            "message": error.get("msg", "Valeur invalide."),
        }
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            message="Requete invalide.",
            request_id=get_request_id(request),
            errors=errors,
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            message=str(exc.detail),
            request_id=get_request_id(request),
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Erreur serveur non geree")
    print(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            message=str(exc),
            request_id=get_request_id(request),
        ).model_dump(),
    )


@app.get("/", response_model=GenericResponse, tags=["Core"], summary="Accueil API")
async def root() -> GenericResponse:
    return GenericResponse(message="API Zoe active.")


@app.get("/ping", response_model=GenericResponse, tags=["Core"], summary="Ping rapide")
async def ping() -> GenericResponse:
    return GenericResponse(message="pong")


@app.get("/health", response_model=GenericResponse, tags=["Core"], summary="Etat de sante")
async def health(request: Request) -> GenericResponse:
    request_guard.check(get_client_key(request))
    return GenericResponse(message="Zoe fonctionne correctement.")


@app.get("/version", response_model=VersionResponse, tags=["Ops"], summary="Version du service")
async def version(request: Request) -> VersionResponse:
    request_guard.check(get_client_key(request))
    return VersionResponse(
        name=API_TITLE,
        version=APP_VERSION,
        model=MODEL_NAME,
        llm_configured=bool(OPENAI_API_KEY),
    )


@app.get("/stats", response_model=StatsResponse, tags=["Ops"], summary="Statistiques simples")
async def stats(request: Request) -> StatsResponse:
    request_guard.check(get_client_key(request))
    memory = safe_load_memory()
    stats_payload = get_memory_stats(memory)

    return StatsResponse(
        history_count=stats_payload["history_count"],
        recent_history_count=stats_payload["recent_history_count"],
        profile_fields=stats_payload["profile_fields"],
        last_emotion=stats_payload["last_emotion"],
        last_topic=stats_payload["last_topic"],
        rate_limit_window_seconds=API_RATE_LIMIT_WINDOW_SECONDS,
        rate_limit_max_requests=API_RATE_LIMIT_MAX_REQUESTS,
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"], summary="Envoyer un message a Zoe")
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    try:
        request_guard.check(get_client_key(request), payload.message)
        logger.info(
            "chat payload uid_present=%s account_key_present=%s attached_image=%s attached_image_mime_type=%s",
            bool(payload.uid),
            bool(payload.account_key),
            bool(payload.attached_image_url),
            payload.attached_image_mime_type or "",
        )

        result = await asyncio.wait_for(
            asyncio.to_thread(
                process_chat_message,
                payload.message,
                payload.uid,
                payload.account_key,
                payload.user_name,
                payload.attached_image_url,
                payload.attached_image_mime_type,
            ),
            timeout=CHAT_TIMEOUT_SECONDS,
        )

        return ChatResponse(
            reply=result.get("reply", "Je t'ecoute."),
            emotion=result.get("emotion", "unknown"),
            precision=result.get("precision", "vague"),
            topic=result.get("topic", "general"),
            intent=result.get("intent", "clarify"),
            thought_summary=result.get("thought_summary", ""),
            strategy=result.get("strategy", ""),
            tone=result.get("tone", ""),
            tool_type=result.get("tool_type"),
            image_base64=result.get("image_base64"),
            image_url=result.get("image_url"),
            image_mime_type=result.get("image_mime_type"),
            image_prompt=result.get("image_prompt"),
            language=result.get("language"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Erreur /chat")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory", response_model=MemoryResponse, tags=["Memory"], summary="Resume memoire")
async def get_memory(
    request: Request,
    account_key: str | None = Query(default=None),
    user_name: str | None = Query(default=None),
) -> MemoryResponse:
    request_guard.check(get_client_key(request))
    memory = safe_load_memory()
    if account_key or user_name:
        apply_identity_context(
            memory=memory,
            account_key=account_key or "",
            user_name=user_name or "",
        )
        save_memory(memory)
    history = memory.get("history", [])
    profile = memory.get("profile", {})

    return MemoryResponse(
        profile=profile if isinstance(profile, dict) else {},
        last_emotion=str(memory.get("last_emotion", "unknown")) or "unknown",
        last_topic=str(memory.get("last_topic", "general")) or "general",
        history_count=len(history) if isinstance(history, list) else 0,
    )


def clear_chat_history() -> None:
    clear_memory(preserve_profile=True)


@app.post("/clear", response_model=GenericResponse, tags=["Memory"], summary="Vider l'historique")
async def clear(request: Request) -> GenericResponse:
    request_guard.check(get_client_key(request))
    clear_chat_history()
    return GenericResponse(message="Historique Zoe vide.")


@app.post(
    "/reset-memory",
    response_model=GenericResponse,
    tags=["Memory"],
    summary="Reinitialiser entierement la memoire",
)
async def reset_memory_endpoint(request: Request) -> GenericResponse:
    request_guard.check(get_client_key(request))
    clear_memory(preserve_profile=False)
    return GenericResponse(message="Memoire Zoe reinitialisee.")
