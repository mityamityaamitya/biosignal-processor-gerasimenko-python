"""Точка входа REST API сервера обработки биосигналов (вариант 4, ЭКГ).

Файл намеренно тонкий: приложение собирается фабрикой из пакета ``biosignal``,
а здесь остаются только объект ``app`` для uvicorn и запуск для разработки.
"""

from __future__ import annotations

import uvicorn

import config
from biosignal.api.application import create_app

app = create_app()


if __name__ == "__main__":
    uvicorn.run("app:app", host=config.SERVER_HOST, port=config.SERVER_PORT, reload=True)
