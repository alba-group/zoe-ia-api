import base64
import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from core.config import OPENAI_MAX_RETRIES, OPENAI_TIMEOUT_SECONDS


load_dotenv()


@dataclass
class LLMResult:
    text: str
    used_web: bool = False
    sources: list[dict[str, str]] = field(default_factory=list)
    raw_response: Any | None = None
    error: str | None = None


@dataclass
class ImageResult:
    ok: bool
    image_url: str = ""
    b64_json: str = ""
    revised_prompt: str = ""
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
        self.image_model = os.getenv("IMAGE_MODEL", "gpt-image-1").strip()

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY est vide dans le fichier .env")

        self.client = OpenAI(
            api_key=self.api_key,
            timeout=OPENAI_TIMEOUT_SECONDS,
            max_retries=OPENAI_MAX_RETRIES,
        )

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
            "Tu es un assistant expert en développement.\n"
            "Tu réponds uniquement à une demande technique explicite.\n"
            f"Langage demandé : {language}.\n"
            "Tu dois écrire un code propre, clair, complet, prêt à copier-coller.\n"
            "Tu peux ajouter de courts commentaires utiles si nécessaire.\n"
            "Tu ne produis ni paroles, ni texte créatif, ni bio, ni prompt artistique.\n"
            "Tu restes strictement technique et cohérent avec la demande.\n"
        )

        return self.ask(
            user_message=user_request,
            system_prompt=code_prompt,
            conversation=conversation,
            temperature=0.2,
        )

    def analyze_image(
        self,
        user_message: str,
        image_url: str | None = None,
        image_base64: str | None = None,
        image_mime_type: str | None = None,
        system_prompt: str = "",
        conversation: list[dict[str, str]] | None = None,
        temperature: float = 0.3,
    ) -> LLMResult:
        """
        Analyse une image avec un message texte associe.
        """
        try:
            image_input = self._build_image_input(
                image_url=image_url,
                image_base64=image_base64,
                image_mime_type=image_mime_type,
            )

            input_payload: list[dict[str, Any]] = []

            if system_prompt.strip():
                input_payload.append(
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": system_prompt.strip(),
                            }
                        ],
                    }
                )

            input_payload.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self._build_text_prompt(
                                user_message=user_message,
                                conversation=conversation,
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": image_input,
                        },
                    ],
                }
            )

            response = self.client.responses.create(
                model=self.model_name,
                input=input_payload,
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

    def generate_image(
        self,
        prompt: str,
        size: str = "1024x1024",
    ) -> ImageResult:
        """
        Génère une image via l'API image.
        Retourne soit une URL, soit du b64_json selon la réponse disponible.
        """
        try:
            response = self.client.images.generate(
                model=self.image_model,
                prompt=prompt.strip(),
                size=size,
            )

            image_url = ""
            b64_json = ""
            revised_prompt = ""

            data = getattr(response, "data", None) or []
            if data:
                first = data[0]

                image_url = getattr(first, "url", "") or ""
                b64_json = getattr(first, "b64_json", "") or ""
                revised_prompt = getattr(first, "revised_prompt", "") or ""

            return ImageResult(
                ok=bool(image_url or b64_json),
                image_url=image_url,
                b64_json=b64_json,
                revised_prompt=revised_prompt,
                raw_response=response,
                error=None,
            )

        except Exception as e:
            return ImageResult(
                ok=False,
                image_url="",
                b64_json="",
                revised_prompt="",
                raw_response=None,
                error=str(e),
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

    def _build_image_input(
        self,
        image_url: str | None = None,
        image_base64: str | None = None,
        image_mime_type: str | None = None,
    ) -> str:
        if image_base64:
            return self._build_base64_image_data_url(
                image_base64=image_base64,
                image_mime_type=image_mime_type,
            )

        cleaned_url = (image_url or "").strip()
        if cleaned_url.startswith(("http://", "https://", "data:image/")):
            return cleaned_url

        if cleaned_url:
            raise ValueError("Format d'image invalide.")

        raise ValueError("Aucune image exploitable fournie.")

    def _build_base64_image_data_url(
        self,
        image_base64: str,
        image_mime_type: str | None = None,
    ) -> str:
        raw_value = image_base64.strip()
        if not raw_value:
            raise ValueError("image_base64 vide")

        if raw_value.startswith("data:image/"):
            return raw_value

        clean_base64 = raw_value.split(",", 1)[-1].strip()
        if not clean_base64:
            raise ValueError("image_base64 vide")

        base64.b64decode(clean_base64, validate=True)

        mime_type = (image_mime_type or "image/jpeg").strip().lower()
        if not mime_type.startswith("image/"):
            mime_type = "image/jpeg"

        return f"data:{mime_type};base64,{clean_base64}"

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
    identity_part = ""
    if user_name.strip():
        identity_part = f"L'utilisateur s'appelle {user_name.strip()}. "

    return (
        "Tu es Zoé, une intelligence artificielle conversationnelle utile, naturelle, claire et empathique. "
        "Tu parles toujours en français. "
        f"{identity_part}"
        "Tu réponds avec naturel, intelligence et cohérence. "
        "Si tu ne sais pas, tu le dis honnêtement. "
        "Tu adaptes toujours le format de sortie à la vraie demande de l'utilisateur. "
        "Règle très importante : "
        "si l'utilisateur demande des paroles, une chanson, un rap, un refrain, un couplet, une intro, un pont, une outro, "
        "un prompt, une bio, une description, un texte, un scénario ou un script non technique, tu réponds en texte normal structuré et jamais en code. "
        "Le code ne doit être donné que si la demande est explicitement technique ou de développement : "
        "python, kotlin, java, html, css, javascript, sql, api, application, fonction, programme ou bug technique. "
        "Le mot 'script' seul ne veut pas automatiquement dire code. "
        "Si la demande est musicale ou créative, tu dois produire du texte exploitable directement, pas du Python. "
        "Si l'utilisateur demande des paroles structurées, utilise des balises propres comme [Intro], [Verse 1], [Chorus], [Bridge], [Outro]."
    )


def create_llm_client() -> LLMClient:
    return LLMClient()
