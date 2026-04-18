from pathlib import Path
from typing import Any
import traceback

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.brain import process_user_message
from core.memory import load_memory, save_memory
from core.context import ensure_context


APP_TITLE = "Zoe IA API"
APP_VERSION = "1.0.1"


app = FastAPI(
    title=APP_TITLE,
    version=APP_VERSION,
    description="API locale pour piloter Zoe depuis Android ou une autre interface.",
)


BASE_DIR = Path(__file__).resolve().parent


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Message envoyé à Zoe")


class ChatResponse(BaseModel):
    ok: bool
    reply: str
    emotion: str = "unknown"
    precision: str = "vague"
    topic: str = "general"
    intent: str = "clarify"
    thought_summary: str = ""
    strategy: str = ""
    tone: str = ""


class MemoryResponse(BaseModel):
    ok: bool
    profile: dict[str, Any]
    last_emotion: str
    last_topic: str
    history_count: int


class GenericResponse(BaseModel):
    ok: bool
    message: str


def _safe_load_memory() -> dict[str, Any]:
    """
    Charge la mémoire Zoe avec sécurité.
    """
    try:
        memory = load_memory()
        if not isinstance(memory, dict):
            memory = {}
        ensure_context(memory)
        return memory
    except Exception:
        memory = {}
        ensure_context(memory)
        return memory


def _safe_save_memory(memory: dict[str, Any]) -> None:
    """
    Sauvegarde mémoire avec sécurité minimale.
    """
    ensure_context(memory)
    save_memory(memory)


@app.get("/", response_model=GenericResponse)
def root() -> GenericResponse:
    return GenericResponse(
        ok=True,
        message="API Zoe active."
    )


@app.get("/health", response_model=GenericResponse)
def health() -> GenericResponse:
    return GenericResponse(
        ok=True,
        message="Zoe fonctionne correctement."
    )


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    """
    Endpoint principal de discussion.
    """
    user_message = payload.message.strip()

    if not user_message:
        raise HTTPException(status_code=400, detail="Le message est vide.")

    try:
        memory = _safe_load_memory()
        result = process_user_message(user_message, memory)
        _safe_save_memory(memory)

        return ChatResponse(
            ok=True,
            reply=result.get("reply", "Je t'écoute."),
            emotion=result.get("emotion", "unknown"),
            precision=result.get("precision", "vague"),
            topic=result.get("topic", "general"),
            intent=result.get("intent", "clarify"),
            thought_summary=result.get("thought_summary", ""),
            strategy=result.get("strategy", ""),
            tone=result.get("tone", ""),
        )

    except Exception as e:
        print("\n========== ERREUR /chat ==========")
        print(f"Message reçu : {user_message!r}")
        print(f"Type erreur : {type(e).__name__}")
        print(f"Détail : {e}")
        traceback.print_exc()
        print("==================================\n")

        raise HTTPException(
            status_code=500,
            detail=f"Erreur serveur Zoe : {type(e).__name__}: {str(e)}"
        )


@app.get("/memory", response_model=MemoryResponse)
def get_memory() -> MemoryResponse:
    """
    Retourne un résumé mémoire.
    """
    try:
        memory = _safe_load_memory()
        profile = memory.get("profile", {})
        history = memory.get("history", [])

        return MemoryResponse(
            ok=True,
            profile=profile if isinstance(profile, dict) else {},
            last_emotion=str(memory.get("last_emotion", "unknown")),
            last_topic=str(memory.get("last_topic", "general")),
            history_count=len(history) if isinstance(history, list) else 0,
        )

    except Exception as e:
        print("\n========== ERREUR /memory ==========")
        print(f"Type erreur : {type(e).__name__}")
        print(f"Détail : {e}")
        traceback.print_exc()
        print("====================================\n")

        raise HTTPException(
            status_code=500,
            detail=f"Impossible de lire la mémoire : {type(e).__name__}: {str(e)}"
        )


@app.post("/clear", response_model=GenericResponse)
def clear_history() -> GenericResponse:
    """
    Vide uniquement l'historique et remet le contexte à zéro,
    sans supprimer le profil si tu veux garder le prénom.
    """
    try:
        memory = _safe_load_memory()

        memory["history"] = []
        memory["last_emotion"] = "unknown"
        memory["last_topic"] = "general"
        memory["context"] = {
            "mode": None,
            "last_question_type": None,
            "awaiting_user_reply": False,
            "riddle_answer": None,
            "riddle_question": None,
            "last_bot_question": None,
        }

        _safe_save_memory(memory)

        return GenericResponse(
            ok=True,
            message="Historique Zoe vidé."
        )

    except Exception as e:
        print("\n========== ERREUR /clear ==========")
        print(f"Type erreur : {type(e).__name__}")
        print(f"Détail : {e}")
        traceback.print_exc()
        print("===================================\n")

        raise HTTPException(
            status_code=500,
            detail=f"Impossible de vider l'historique : {type(e).__name__}: {str(e)}"
        ) 
