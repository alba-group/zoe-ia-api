import os
from typing import Optional

from openai import OpenAI

from core.firebase_storage import upload_image_bytes
from core.image_utils import (
    build_edit_prompt,
    build_image_prompt,
    content_type_for_png,
    decode_base64_image,
    safe_filename_from_prompt,
    should_create_image,
    should_edit_image,
    should_handle_image,
)


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def should_use_image_tool(message: str) -> bool:
    return should_handle_image(message)


def _generate_image_with_openai(prompt: str) -> dict:
    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024",
    )

    image_base64 = ""
    image_url = ""

    if hasattr(result, "data") and result.data and len(result.data) > 0:
        item = result.data[0]

        if hasattr(item, "b64_json") and item.b64_json:
            image_base64 = item.b64_json

        if hasattr(item, "url") and item.url:
            image_url = item.url

    return {
        "image_base64": image_base64,
        "image_url": image_url,
    }


def _edit_image_with_openai(
    prompt: str,
    input_image_bytes: bytes,
    input_mime_type: str = "image/png",
) -> dict:
    result = client.images.edit(
        model="gpt-image-1",
        image=[("input.png", input_image_bytes, input_mime_type)],
        prompt=prompt,
        size="1024x1024",
    )

    image_base64 = ""
    image_url = ""

    if hasattr(result, "data") and result.data and len(result.data) > 0:
        item = result.data[0]

        if hasattr(item, "b64_json") and item.b64_json:
            image_base64 = item.b64_json

        if hasattr(item, "url") and item.url:
            image_url = item.url

    return {
        "image_base64": image_base64,
        "image_url": image_url,
    }


def generate_image_reply(
    user_message: str,
    conversation=None,
    *,
    user_uid: Optional[str] = None,
    input_image_bytes: Optional[bytes] = None,
    input_mime_type: str = "image/png",
) -> dict:
    """
    Génération / modification image.

    Retourne :
    - reply
    - image_url
    - image_base64
    - storage_path
    """

    try:
        if should_edit_image(user_message):
            if not input_image_bytes:
                return {
                    "emotion": "unknown",
                    "precision": "precise",
                    "topic": "image",
                    "intent": "clarify",
                    "reply": "J'ai besoin d'une image envoyée pour pouvoir la modifier.",
                    "image_url": "",
                    "image_base64": "",
                    "storage_path": "",
                }

            prompt = build_edit_prompt(user_message, conversation)
            openai_result = _edit_image_with_openai(
                prompt=prompt,
                input_image_bytes=input_image_bytes,
                input_mime_type=input_mime_type,
            )
            success_reply = "Image modifiée avec succès."

        else:
            prompt = build_image_prompt(user_message, conversation)
            openai_result = _generate_image_with_openai(prompt=prompt)
            success_reply = "Image générée avec succès."

        image_base64 = openai_result.get("image_base64", "") or ""
        direct_image_url = openai_result.get("image_url", "") or ""

        final_image_url = ""
        storage_path = ""

        # Cas idéal : on reçoit le base64, on le transforme en PNG puis upload Firebase
        if image_base64:
            image_bytes = decode_base64_image(image_base64)

            if user_uid:
                file_name = safe_filename_from_prompt(prompt)
                upload_result = upload_image_bytes(
                    uid=user_uid,
                    image_bytes=image_bytes,
                    file_name=file_name,
                    content_type=content_type_for_png(),
                    folder="images",
                    extra_metadata={
                        "source": "openai",
                        "prompt": prompt[:300],
                    },
                )
                final_image_url = upload_result["download_url"]
                storage_path = upload_result["path"]
            else:
                # Fallback : pas d'UID disponible, on renvoie au moins le base64
                final_image_url = ""

        elif direct_image_url:
            final_image_url = direct_image_url

        else:
            return {
                "emotion": "unknown",
                "precision": "precise",
                "topic": "image",
                "intent": "clarify",
                "reply": "Je n'ai pas réussi à récupérer l'image générée.",
                "image_url": "",
                "image_base64": "",
                "storage_path": "",
            }

        return {
            "emotion": "positive",
            "precision": "precise",
            "topic": "image",
            "intent": "create" if not should_edit_image(user_message) else "edit",
            "reply": success_reply,
            "image_url": final_image_url,
            "image_base64": image_base64,
            "storage_path": storage_path,
        }

    except Exception as exc:
        print("IMAGE TOOL ERROR:", str(exc))
        return {
            "emotion": "unknown",
            "precision": "precise",
            "topic": "image",
            "intent": "clarify",
            "reply": "Je n'ai pas réussi à traiter l'image pour le moment.",
            "image_url": "",
            "image_base64": "",
            "storage_path": "",
        } 
