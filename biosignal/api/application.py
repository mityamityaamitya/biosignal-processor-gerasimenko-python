"""Сборка FastAPI-приложения: маршруты и обработчики ошибок."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from biosignal.api.routes import analyze_router, variant_router
from biosignal.errors import SignalInputError


def create_app() -> FastAPI:
    """Создаёт и настраивает приложение."""
    app = FastAPI(
        title="Universal Bio-Signal Processing Server",
        description=(
            "REST API для фильтрации и извлечения параметров физиологических сигналов. "
            "Вариант 4: ЭКГ — сглаживание скользящим средним (окно 7), ФВЧ Баттерворта "
            "2-го порядка 0.5 Гц, границы QRS по падению энергии первой производной."
        ),
        version="1.0.0",
    )

    @app.exception_handler(SignalInputError)
    async def signal_input_error_handler(_: Request, error: SignalInputError) -> JSONResponse:
        """Единый формат ошибок: ``{"error": КОД, "errorDetails": {...}}``."""
        return JSONResponse(
            status_code=400,
            content={
                "error": error.code,
                "errorDetails": {"code": error.code, "details": error.details},
            },
        )

    app.include_router(analyze_router)
    app.include_router(variant_router)
    return app
