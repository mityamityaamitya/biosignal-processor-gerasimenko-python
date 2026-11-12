"""Каркас REST API сервера обработки биосигналов (вариант 4, ЭКГ).

На этом этапе описано только приложение и его метаданные: маршруты `/analyze` и
`/variant` добавляются на этапе интеграции вместе с клиентом тестирования.
"""

from __future__ import annotations

from fastapi import FastAPI

import config

app = FastAPI(
    title="Universal Bio-Signal Processing Server",
    description=(
        "REST API для фильтрации и извлечения параметров физиологических сигналов. "
        f"Вариант {config.VARIANT}: ЭКГ."
    ),
    version="0.1.0",
)
