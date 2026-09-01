import json
import logging

import requests

from app.pipeline import run_price_adjustment

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def handler(event, context):
    try:
        result = run_price_adjustment()
        payload = {
            "statusCode": 200,
            "body": result.body,
            "status": result.status,
            "updated_count": result.updated_count,
            "task_ids": result.task_ids,
        }
        logger.info("Завершение handler: %s", json.dumps(payload, ensure_ascii=False))
        return payload

    except ValueError as exc:
        logger.error("Ошибка конфигурации: %s", exc)
        return {"statusCode": 500, "body": str(exc), "status": "error"}

    except requests.RequestException as exc:
        logger.error("Сетевая ошибка при работе с Ozon API: %s", exc)
        return {"statusCode": 502, "body": f"Ошибка Ozon API: {exc}", "status": "error"}

    except Exception as exc:
        logger.exception("Непредвиденная ошибка: %s", exc)
        return {"statusCode": 500, "body": f"Внутренняя ошибка: {exc}", "status": "error"}
