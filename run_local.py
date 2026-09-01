"""Локальный запуск функции с загрузкой переменных из .env."""

from index import handler, load_local_env


def main() -> None:
    load_local_env()

    print("Локальный запуск корректировки цен Ozon...")
    result = handler({}, None)
    print("Результат:", result)


if __name__ == "__main__":
    main()
