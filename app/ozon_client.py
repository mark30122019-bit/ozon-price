import logging
import os
from typing import Any

import requests

from app.config import OZON_API_BASE_URL

logger = logging.getLogger(__name__)


class OzonClient:
    def __init__(self, client_id: str, api_key: str) -> None:
        self.client_id = client_id
        self.api_key = api_key

    @classmethod
    def from_env(cls) -> "OzonClient":
        client_id = os.getenv("OZON_CLIENT_ID")
        api_key = os.getenv("OZON_API_KEY")

        if not client_id or not api_key:
            raise ValueError("Переменные окружения OZON_CLIENT_ID и OZON_API_KEY обязательны")

        return cls(client_id, api_key)

    def _headers(self) -> dict[str, str]:
        return {
            "Client-Id": self.client_id,
            "Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    def post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{OZON_API_BASE_URL}{endpoint}"

        try:
            response = requests.post(url, headers=self._headers(), json=payload, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.error("Ошибка запроса к Ozon API (%s): %s", endpoint, exc)
            if getattr(exc, "response", None) is not None:
                logger.error("Ответ Ozon: %s", exc.response.text)
            raise
