"""Локальный запуск функции с загрузкой переменных из .env."""

from app.env import load_local_env


def main() -> None:
    load_local_env()

    from index import handler

    print("Локальный запуск корректировки цен Ozon...")
    result = handler({}, None)
    print("Результат:", result)


if __name__ == "__main__":
    main()
