import logging

import requests

from app.pipeline import run_price_adjustment

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def handler(event, context):
    try:
        body = run_price_adjustment()
        return {"statusCode": 200, "body": body}

    except ValueError as exc:
        logging.error("Ошибка конфигурации: %s", exc)
        return {"statusCode": 500, "body": str(exc)}

    except requests.RequestException as exc:
        logging.error("Сетевая ошибка при работе с Ozon API: %s", exc)
        return {"statusCode": 502, "body": f"Ошибка Ozon API: {exc}"}

    except Exception as exc:
        logging.exception("Непредвиденная ошибка: %s", exc)
        return {"statusCode": 500, "body": f"Внутренняя ошибка: {exc}"}
