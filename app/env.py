import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore

from app.config import LOCAL_ENV_FILE

logger = logging.getLogger(__name__)


def load_local_env() -> bool:
    """
    Загружает переменные из локального .env (только если файл существует).

    В Yandex Cloud Functions файл .env обычно отсутствует —
    там используются переменные окружения, заданные в консоли Yandex Cloud
    или секреты Yandex Lockbox, проброшенные в переменные окружения.
    Уже установленные переменные не перезаписываются.
    """
    if not LOCAL_ENV_FILE.exists():
        return False

    loaded = 0
    with LOCAL_ENV_FILE.open(encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            key, separator, value = line.partition("=")
            if not separator:
                continue

            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded += 1

    logger.info("Загружено переменных из %s: %s", LOCAL_ENV_FILE.name, loaded)
    return True


def is_dry_run() -> bool:
    return os.getenv("DRY_RUN", "").strip().lower() in {"1", "true", "yes", "on"}


def _load_service_account_info() -> dict[str, Any]:
    """
    Загружает JSON сервисного аккаунта Firebase.

    Источники (по приоритету):
    1. FIREBASE_SERVICE_ACCOUNT_JSON — JSON-строка (Yandex Cloud / Lockbox → env)
    2. FIREBASE_CREDENTIALS_FILE — путь к JSON-файлу (локальная разработка)
    """
    json_payload = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if json_payload:
        try:
            return json.loads(json_payload)
        except json.JSONDecodeError as exc:
            raise ValueError("FIREBASE_SERVICE_ACCOUNT_JSON содержит невалидный JSON") from exc

    credentials_file = os.getenv("FIREBASE_CREDENTIALS_FILE", "").strip()
    if credentials_file:
        path = Path(credentials_file)
        if not path.is_file():
            raise ValueError(f"FIREBASE_CREDENTIALS_FILE не найден: {credentials_file}")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("FIREBASE_CREDENTIALS_FILE содержит невалидный JSON") from exc

    raise ValueError(
        "Не заданы учётные данные Firebase: "
        "укажите FIREBASE_SERVICE_ACCOUNT_JSON или FIREBASE_CREDENTIALS_FILE"
    )


@lru_cache(maxsize=1)
def get_firebase_app() -> firebase_admin.App:
    if firebase_admin._apps:
        return firebase_admin.get_app()

    service_account_info = _load_service_account_info()
    cred = credentials.Certificate(service_account_info)
    app = firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin SDK инициализирован")
    return app


def get_firestore_client() -> firestore.Client:
    get_firebase_app()
    return firestore.client()
