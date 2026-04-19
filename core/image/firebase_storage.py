import json
import os
import urllib.parse
import uuid
from typing import Optional

import firebase_admin
from firebase_admin import credentials, storage


_FIREBASE_APP = None


def _get_storage_bucket_name() -> str:
    bucket = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError(
            "FIREBASE_STORAGE_BUCKET manquant. Exemple : zoe-ia-5d52f.firebasestorage.app"
        )
    return bucket


def _get_firebase_credential() -> credentials.Base:
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()

    if service_account_json:
        try:
            data = json.loads(service_account_json)
            return credentials.Certificate(data)
        except Exception as exc:
            raise RuntimeError(
                f"FIREBASE_SERVICE_ACCOUNT_JSON invalide : {exc}"
            ) from exc

    if service_account_path:
        if not os.path.exists(service_account_path):
            raise RuntimeError(
                f"GOOGLE_APPLICATION_CREDENTIALS introuvable : {service_account_path}"
            )
        return credentials.Certificate(service_account_path)

    raise RuntimeError(
        "Aucun secret Firebase trouvé. "
        "Définis FIREBASE_SERVICE_ACCOUNT_JSON ou GOOGLE_APPLICATION_CREDENTIALS."
    )


def get_firebase_app():
    global _FIREBASE_APP

    if _FIREBASE_APP is not None:
        return _FIREBASE_APP

    if firebase_admin._apps:
        _FIREBASE_APP = firebase_admin.get_app()
        return _FIREBASE_APP

    cred = _get_firebase_credential()
    bucket_name = _get_storage_bucket_name()

    _FIREBASE_APP = firebase_admin.initialize_app(
        cred,
        {
            "storageBucket": bucket_name,
        },
    )
    return _FIREBASE_APP


def get_storage_bucket():
    app = get_firebase_app()
    return storage.bucket(app=app)


def build_storage_path(
    uid: str,
    file_name: str,
    folder: str = "images",
) -> str:
    clean_uid = (uid or "").strip()
    clean_file_name = (file_name or "").strip()
    clean_folder = (folder or "").strip()

    if not clean_uid:
        raise ValueError("uid manquant pour le chemin Firebase Storage")

    if not clean_file_name:
        raise ValueError("file_name manquant pour le chemin Firebase Storage")

    if not clean_folder:
        clean_folder = "images"

    return f"{clean_folder}/{clean_uid}/{clean_file_name}"


def build_download_url(bucket_name: str, blob_name: str, token: str) -> str:
    encoded_blob_name = urllib.parse.quote(blob_name, safe="")
    return (
        f"https://firebasestorage.googleapis.com/v0/b/{bucket_name}/o/"
        f"{encoded_blob_name}?alt=media&token={token}"
    )


def upload_image_bytes(
    *,
    uid: str,
    image_bytes: bytes,
    file_name: str,
    content_type: str = "image/png",
    folder: str = "images",
    extra_metadata: Optional[dict] = None,
) -> dict:
    if not image_bytes:
        raise ValueError("image_bytes vide")

    bucket = get_storage_bucket()
    bucket_name = bucket.name

    blob_name = build_storage_path(
        uid=uid,
        file_name=file_name,
        folder=folder,
    )
    blob = bucket.blob(blob_name)

    download_token = str(uuid.uuid4())

    metadata = {
        "firebaseStorageDownloadTokens": download_token,
    }

    if extra_metadata:
        for key, value in extra_metadata.items():
            metadata[str(key)] = str(value)

    blob.metadata = metadata
    blob.upload_from_string(image_bytes, content_type=content_type)

    download_url = build_download_url(bucket_name, blob_name, download_token)

    return {
        "bucket": bucket_name,
        "path": blob_name,
        "download_url": download_url,
        "content_type": content_type,
    }


def upload_image_file(
    *,
    uid: str,
    local_file_path: str,
    file_name: str,
    content_type: str = "image/png",
    folder: str = "images",
    extra_metadata: Optional[dict] = None,
) -> dict:
    if not local_file_path:
        raise ValueError("local_file_path manquant")

    if not os.path.exists(local_file_path):
        raise FileNotFoundError(f"Fichier introuvable : {local_file_path}")

    with open(local_file_path, "rb") as f:
        image_bytes = f.read()

    return upload_image_bytes(
        uid=uid,
        image_bytes=image_bytes,
        file_name=file_name,
        content_type=content_type,
        folder=folder,
        extra_metadata=extra_metadata,
    ) 
