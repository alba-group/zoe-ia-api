import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import firebase_admin
from firebase_admin import credentials, storage

from core.config import (
    FIREBASE_SERVICE_ACCOUNT_FILE,
    FIREBASE_SERVICE_ACCOUNT_JSON,
    FIREBASE_STORAGE_BUCKET,
)

logger = logging.getLogger("zoe.firebase_storage")

_APP_NAME = "zoe-storage-app"


def _load_credentials():
    raw_json = (FIREBASE_SERVICE_ACCOUNT_JSON or "").strip()

    if raw_json:
        try:
            data = json.loads(raw_json)
            logger.info("firebase credentials loaded from JSON")
            return credentials.Certificate(data)
        except Exception as error:
            logger.exception("firebase credentials JSON invalid: %s", error)
            raise

    service_account_path = (
        FIREBASE_SERVICE_ACCOUNT_FILE
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    ).strip()

    if service_account_path:
        path_obj = Path(service_account_path)
        if not path_obj.exists():
            raise FileNotFoundError(
                f"Fichier service account introuvable: {service_account_path}"
            )
        logger.info("firebase credentials loaded from file")
        return credentials.Certificate(service_account_path)

    raise ValueError(
        "Aucun credential Firebase configure. "
        "Definis FIREBASE_SERVICE_ACCOUNT_JSON ou FIREBASE_SERVICE_ACCOUNT_FILE."
    )


def _get_app():
    try:
        return firebase_admin.get_app(_APP_NAME)
    except ValueError:
        app = firebase_admin.initialize_app(
            credential=_load_credentials(),
            options={"storageBucket": FIREBASE_STORAGE_BUCKET},
            name=_APP_NAME,
        )
        logger.info("firebase-storage initialized bucket=%s", FIREBASE_STORAGE_BUCKET)
        return app


def _slugify(value: str, fallback: str = "image") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug[:64] or fallback


def _storage_user_id(user_uid: str | None, account_key: str | None) -> str | None:
    clean_uid = (user_uid or "").strip()
    if clean_uid:
        return _slugify(clean_uid, fallback="user")

    raw = (account_key or "").strip()
    if raw.startswith("user_") and len(raw) > 5:
        user_key = raw[5:].split("_project_", 1)[0]
        return _slugify(user_key, fallback="user")

    return None


def build_generated_image_path(
    user_uid: str | None,
    account_key: str | None,
    prompt: str,
) -> str:
    user_id = _storage_user_id(user_uid=user_uid, account_key=account_key)
    if not user_id:
        raise ValueError(
            "Utilisateur non connecte. Impossible d'enregistrer l'image dans Firebase Storage."
        )

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    prompt_slug = _slugify(prompt, fallback="generated")
    file_name = f"generated_{timestamp}_{prompt_slug}.png"
    return f"images/{user_id}/{file_name}"


def upload_generated_image_bytes(
    image_bytes: bytes,
    user_uid: str | None,
    account_key: str | None,
    prompt: str,
) -> dict[str, str]:
    if not image_bytes:
        raise ValueError("Image bytes vides.")

    if not FIREBASE_STORAGE_BUCKET:
        raise ValueError("Bucket Firebase Storage non configure.")

    app = _get_app()
    bucket = storage.bucket(app=app)

    storage_path = build_generated_image_path(
        user_uid=user_uid,
        account_key=account_key,
        prompt=prompt,
    )

    blob = bucket.blob(storage_path)
    download_token = str(uuid.uuid4())

    logger.info(
        "firebase-storage upload start bucket=%s path=%s bytes=%s uid_present=%s",
        bucket.name,
        storage_path,
        len(image_bytes),
        bool((user_uid or "").strip()),
    )

    blob.metadata = {
        "firebaseStorageDownloadTokens": download_token,
    }
    blob.upload_from_string(image_bytes, content_type="image/png")
    blob.patch()

    download_url = (
        f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/"
        f"{quote(storage_path, safe='')}?alt=media&token={download_token}"
    )

    logger.info(
        "firebase-storage upload ok bucket=%s path=%s has_download_url=%s",
        bucket.name,
        storage_path,
        bool(download_url),
    )

    return {
        "storage_path": storage_path,
        "download_url": download_url,
        "bucket": bucket.name,
    }