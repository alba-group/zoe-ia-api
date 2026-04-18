import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


@dataclass
class LLMResult:
    text: str
    used_web: bool = False
    sources: list[dict[str, str]] = field(default_factory=list)
    raw_response: Any | None = None
    error: str | None = None


class LLMClient:
    """
    Client OpenAI simple et robuste pour Zoe.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model_name = os.getenv("MODEL_NAME", "gpt-4o-mini").strip()
        self.web_enabled = os.getenv("WEB_ENABLED", "false").strip().lower() == "true"

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY est vide dans le fichier .env")

        self.client = OpenAI(api_key=self.api_key)

    def ask(
        self,
        user_message: str,
        system_prompt: str = "",
        conversation: list[dict[str, str]] | None = None,
        temperature: float = 0.7,
    ) -> LLMResult:
        """
        Réponse normale sans recherche web.
        """
        try:
            full_prompt = self._build_text_prompt(
                user_message=user_message,
                system_prompt=system_prompt,
                conversation=conversation,
            )

            response = self.client.responses.create(
                model=self.model_name,
                input=full_prompt,
                temperature=temperature,
            )

            return LLMResult(
                text=self._extract_output_text(response),
                used_web=False,
                sources=[],
                raw_response=response,
                error=None,
            )

        except Exception as e:
            return LLMResult(
                text="",
                used_web=False,
                sources=[],
                raw_response=None,
                error=str(e),
            )

    def ask_with_web(
        self,
        user_message: str,
        system_prompt: str = "",
        conversation: list[dict[str, str]] | None = None,
        temperature: float = 0.5,
    ) -> LLMResult:
        """
        Réponse avec recherche web.
        """
        if not self.web_enabled:
            return LLMResult(
                text="La recherche web est désactivée dans le fichier .env.",
                used_web=False,
                sources=[],
                raw_response=None,
                error="WEB_ENABLED=false",
            )

        try:
            full_prompt = self._build_text_prompt(
                user_message=user_message,
                system_prompt=system_prompt,
                conversation=conversation,
            )

            response = self.client.responses.create(
                model=self.model_name,
                input=full_prompt,
                temperature=temperature,
                tools=[{"type": "web_search_preview"}],
            )

            return LLMResult(
                text=self._extract_output_text(response),
                used_web=True,
                sources=[],
                raw_response=response,
                error=None,
            )

        except Exception as e:
            return LLMResult(
                text="",
                used_web=False,
                sources=[],
                raw_response=None,
                error=str(e),
            )

    def generate_code(
        self,
        user_request: str,
        language: str = "python",
        conversation: list[dict[str, str]] | None = None,
    ) -> LLMResult:
        """
        Génération de code.
        """
        code_prompt = (
            f"Tu es un assistant expert en développement.\n"
            f"Tu dois écrire du code propre, complet, prêt à copier-coller.\n"
            f"Langage demandé : {language}.\n"
            f"Réponds uniquement avec le code et quelques commentaires utiles si nécessaire.\n"
        )

        return self.ask(
            user_message=user_request,
            system_prompt=code_prompt,
            conversation=conversation,
            temperature=0.2,
        )

    def _build_text_prompt(
        self,
        user_message: str,
        system_prompt: str = "",
        conversation: list[dict[str, str]] | None = None,
    ) -> str:
        """
        Construit un prompt texte simple et stable.
        """
        parts: list[str] = []

        if system_prompt.strip():
            parts.append(f"[SYSTEM]\n{system_prompt.strip()}")

        if conversation:
            parts.append("[HISTORIQUE]")
            for msg in conversation:
                role = msg.get("role", "user").strip().lower()
                content = msg.get("content", "").strip()
                if not content:
                    continue

                if role == "assistant":
                    parts.append(f"Zoé : {content}")
                else:
                    parts.append(f"Utilisateur : {content}")

        parts.append("[MESSAGE ACTUEL]")
        parts.append(f"Utilisateur : {user_message.strip()}")
        parts.append("Zoé :")

        return "\n\n".join(parts)

    def _extract_output_text(self, response: Any) -> str:
        """
        Extraction robuste du texte.
        """
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        texts: list[str] = []

        for item in getattr(response, "output", []) or []:
            content = getattr(item, "content", None)
            if not content:
                continue

            for part in content:
                txt = getattr(part, "text", None)
                if isinstance(txt, str) and txt.strip():
                    texts.append(txt.strip())

        return "\n".join(texts).strip()


def build_zoe_system_prompt(user_name: str = "") -> str:
    if user_name.strip():
        return (
            f"Tu es Zoé, une intelligence artificielle conversationnelle utile, naturelle et empathique. "
            f"Tu parles toujours en français. "
            f"L'utilisateur s'appelle {user_name.strip()}. "
            f"Tu réponds avec clarté, naturel et intelligence. "
            f"Si tu ne sais pas, tu le dis honnêtement. "
            f"Quand on te demande du code, tu donnes un vrai code prêt à copier-coller."
        )

    return (
        "Tu es Zoé, une intelligence artificielle conversationnelle utile, naturelle et empathique. "
        "Tu parles toujours en français. "
        "Tu réponds avec clarté, naturel et intelligence. "
        "Si tu ne sais pas, tu le dis honnêtement. "
        "Quand on te demande du code, tu donnes un vrai code prêt à copier-coller."
    )


def create_llm_client() -> LLMClient:
    return LLMClient() 
