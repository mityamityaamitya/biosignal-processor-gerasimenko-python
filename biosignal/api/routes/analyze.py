"""Маршрут POST /analyze."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile

import config
from biosignal.api.dependencies import (
    get_parser,
    get_pipeline,
    get_response_builder,
    get_validator,
)
from biosignal.api.response import AnalysisResponseBuilder
from biosignal.api.schemas import AnalysisResponse, ErrorResponse
from biosignal.errors import SignalInputError
from biosignal.io import AnalysisRequestValidator, SignalTextParser
from biosignal.processing import EcgPipeline

router = APIRouter(tags=["analysis"])


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    summary="Обработать загруженный файл сигнала",
    responses={400: {"model": ErrorResponse, "description": "Ошибка валидации запроса"}},
)
async def analyze_signal(
    file: Annotated[
        UploadFile,
        File(
            description="Файл .txt или .csv с отсчётами сигнала "
            "(одно число на строку или несколько колонок)"
        ),
    ],
    pipeline: Annotated[EcgPipeline, Depends(get_pipeline)],
    parser: Annotated[SignalTextParser, Depends(get_parser)],
    validator: Annotated[AnalysisRequestValidator, Depends(get_validator)],
    builder: Annotated[AnalysisResponseBuilder, Depends(get_response_builder)],
    fs: Annotated[float, Query(description="Частота дискретизации сигнала, Гц")] = (
        config.DEFAULT_SAMPLING_RATE_HZ
    ),
    column: Annotated[int, Query(description="Индекс колонки с сигналом (с 0)")] = (
        config.DEFAULT_COLUMN_INDEX
    ),
) -> AnalysisResponse:
    """Фильтрует сигнал, находит QRS-комплексы и считает признаки варианта 4."""
    validator.validate_filename(file.filename)
    validator.validate_sampling_rate(fs)
    validator.validate_column(column)

    rows = parser.parse(await file.read())
    raw_signal = parser.extract_column(rows, column)
    validator.validate_signal_length(len(raw_signal))

    try:
        result = pipeline.process(raw_signal, fs)
    except ValueError as error:
        raise SignalInputError(config.ERROR_SIGNAL_TOO_SHORT, str(error)) from error

    return builder.build(result, fs)
