import logging
import os

from app.config import LOCAL_ENV_FILE

logger = logging.getLogger(__name__)


def load_local_env() -> bool:
    """
    Загружает переменные из локального .env (только если файл существует).

    В Yandex Cloud Functions файл .env обычно отсутствует —
    там используются переменные окружения, заданные в консоли Yandex Cloud.
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
