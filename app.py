"""REST API сервера обработки биосигналов (вариант 4, ЭКГ).

Модуль отвечает только за транспорт: валидацию запроса, вызов конвейера из
``signal_processor`` и сборку JSON-ответа. Никакой математики здесь нет.

Маршруты:
    POST /analyze  — загрузка файла сигнала и анализ (multipart/form-data);
    GET  /variant  — параметры варианта 4;
    GET  /docs     — Swagger UI;
    GET  /openapi.json — OpenAPI-схема.
"""

from __future__ import annotations

import math
import re
from typing import Annotated

import uvicorn
from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config
import signal_processor

# --- Модели ответа (одновременно документация Swagger) -----------------------


class QrsEvent(BaseModel):
    """Один обнаруженный QRS-комплекс."""

    type: str = Field(description="Тип события, для варианта 4 — QRS_COMPLEX")
    r_peak_index: int = Field(description="Индекс вершины R-пика")
    onset_index: int = Field(description="Индекс начала комплекса")
    offset_index: int = Field(description="Индекс окончания комплекса")
    onset_time_ms: float = Field(description="Время начала от начала записи, мс")
    offset_time_ms: float = Field(description="Время окончания от начала записи, мс")
    width_ms: float = Field(description="Ширина комплекса, мс")


class CalculatedFeatures(BaseModel):
    """Признаки варианта 4, рассчитанные по отфильтрованному сигналу."""

    mean_qrs_width_ms: float | None = Field(description="Средняя ширина QRS, мс")
    max_peak_amplitude: float | None = Field(description="Максимальная пиковая амплитуда (артефактный максимум)")
    mean_amplitude: float | None = Field(description="Среднее значение отфильтрованного сигнала")
    std_amplitude: float | None = Field(description="СКО отфильтрованного сигнала (по генеральной совокупности)")
    heart_rate_bpm: float | None = Field(description="ЧСС, BPM; null, если QRS меньше двух")
    r_peak_count: int = Field(description="Количество найденных R-пиков")
    qrs_count: int = Field(description="Количество корректных QRS-комплексов")


class AnalysisResponse(BaseModel):
    """Успешный ответ анализа."""

    status: str = Field(examples=[config.STATUS_SUCCESS])
    fs: float = Field(description="Частота дискретизации, Гц")
    variant: str = Field(description="Номер варианта задания")
    signal_length: int = Field(description="Количество отсчётов")
    raw_signal: list[float] = Field(description="Исходный сигнал")
    filtered_signal: list[float] = Field(description="Сигнал после фильтрации")
    detected_events: list[QrsEvent] = Field(description="Найденные QRS-комплексы")
    calculated_features: CalculatedFeatures = Field(description="Рассчитанные признаки")


class ErrorDetails(BaseModel):
    """Детали ошибки."""

    code: str = Field(description="Машиночитаемый код ошибки")
    details: str = Field(description="Человекочитаемое пояснение")


class ErrorResponse(BaseModel):
    """Тело ошибки (HTTP 400)."""

    error: str = Field(description="Код ошибки")
    errorDetails: ErrorDetails


class HighpassDescription(BaseModel):
    """Параметры ФВЧ варианта."""

    type: str
    order: int
    cutoff_hz: float
    zero_phase: bool


class FilteringDescription(BaseModel):
    """Параметры фильтрации варианта 4."""

    moving_average_window: int
    highpass: HighpassDescription


class QrsDetectionDescription(BaseModel):
    """Параметры детекции R-пиков и границ QRS."""

    energy_window_ms: float
    energy_threshold_ratio: float
    refractory_ms: float
    refine_window_ms: float
    qrs_energy_smoothing_ms: float
    qrs_energy_threshold_ratio: float
    qrs_search_before_ms: float
    qrs_search_after_ms: float


class VariantResponse(BaseModel):
    """Описание варианта 4."""

    variant: str
    title: str
    signal_type: str
    default_fs: float
    filtering: FilteringDescription
    qrs_detection: QrsDetectionDescription
    features: list[str]


# --- Приложение --------------------------------------------------------------

app = FastAPI(
    title="Universal Bio-Signal Processing Server",
    description=(
        "REST API для фильтрации и извлечения параметров физиологических сигналов. "
        "Вариант 4: ЭКГ — сглаживание скользящим средним (окно 7), ФВЧ Баттерворта "
        "2-го порядка 0.5 Гц, границы QRS по падению энергии первой производной."
    ),
    version="1.0.0",
)


class ApiError(Exception):
    """Ошибка валидации запроса с машиночитаемым кодом."""

    def __init__(self, code: str, details: str) -> None:
        super().__init__(details)
        self.code = code
        self.details = details


@app.exception_handler(ApiError)
async def api_error_handler(_: Request, error: ApiError) -> JSONResponse:
    """Единый формат ошибок: ``{"error": КОД, "errorDetails": {...}}``."""
    return JSONResponse(
        status_code=400,
        content={
            "error": error.code,
            "errorDetails": {"code": error.code, "details": error.details},
        },
    )


# --- Разбор файла ------------------------------------------------------------

_COLUMN_SPLIT = re.compile("[" + re.escape("".join(config.COLUMN_SEPARATORS)) + "]+")


def _decode(contents: bytes) -> str:
    try:
        return contents.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ApiError(
            config.ERROR_PARSE_ERROR,
            f"Файл не является текстом в кодировке UTF-8: {error}",
        ) from error


def _parse_rows(text: str) -> list[list[float]]:
    """Разбирает текст в строки чисел; пустые строки пропускаются."""
    rows: list[list[float]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        tokens = [token for token in _COLUMN_SPLIT.split(stripped) if token]
        try:
            rows.append([float(token) for token in tokens])
        except ValueError as error:
            raise ApiError(
                config.ERROR_PARSE_ERROR,
                f"Строка {line_number} не является числом: {stripped[:80]!r} ({error})",
            ) from error
    return rows


def _extract_column(rows: list[list[float]], column: int) -> list[float]:
    """Выбирает колонку сигнала из разобранных строк."""
    for line_number, row in enumerate(rows, start=1):
        if column >= len(row):
            raise ApiError(
                config.ERROR_INVALID_COLUMN,
                f"Колонка {column} отсутствует: в строке {line_number} "
                f"только {len(row)} колонок(и)",
            )
    return [row[column] for row in rows]


def _validate_extension(filename: str | None) -> None:
    name = (filename or "").lower()
    if not name.endswith(config.ALLOWED_FILE_EXTENSIONS):
        raise ApiError(
            config.ERROR_INVALID_FILE_FORMAT,
            "Неверный формат файла: разрешены только "
            + " и ".join(config.ALLOWED_FILE_EXTENSIONS),
        )


def _validate_sampling_rate(fs: float) -> None:
    if not math.isfinite(fs) or not (config.MIN_SAMPLING_RATE_HZ <= fs <= config.MAX_SAMPLING_RATE_HZ):
        raise ApiError(
            config.ERROR_INVALID_SAMPLING_RATE,
            f"Частота дискретизации должна лежать в диапазоне "
            f"{config.MIN_SAMPLING_RATE_HZ:g}…{config.MAX_SAMPLING_RATE_HZ:g} Гц, получено {fs}",
        )


def _round(value: float) -> float:
    return round(float(value), config.RESPONSE_DECIMAL_PLACES)


def _build_response(result: dict, fs: float) -> AnalysisResponse:
    """Округляет числа и собирает типизированный ответ."""
    features = result["calculated_features"]
    return AnalysisResponse(
        status=config.STATUS_SUCCESS,
        fs=fs,
        variant=config.VARIANT,
        signal_length=len(result["raw_signal"]),
        raw_signal=[_round(value) for value in result["raw_signal"]],
        filtered_signal=[_round(value) for value in result["filtered_signal"]],
        detected_events=[
            QrsEvent(
                type=event["type"],
                r_peak_index=event["r_peak_index"],
                onset_index=event["onset_index"],
                offset_index=event["offset_index"],
                onset_time_ms=_round(event["onset_time_ms"]),
                offset_time_ms=_round(event["offset_time_ms"]),
                width_ms=_round(event["width_ms"]),
            )
            for event in result["detected_events"]
        ],
        calculated_features=CalculatedFeatures(
            mean_qrs_width_ms=None if features["mean_qrs_width_ms"] is None else _round(features["mean_qrs_width_ms"]),
            max_peak_amplitude=None
            if features["max_peak_amplitude"] is None
            else _round(features["max_peak_amplitude"]),
            mean_amplitude=None if features["mean_amplitude"] is None else _round(features["mean_amplitude"]),
            std_amplitude=None if features["std_amplitude"] is None else _round(features["std_amplitude"]),
            heart_rate_bpm=None if features["heart_rate_bpm"] is None else _round(features["heart_rate_bpm"]),
            r_peak_count=features["r_peak_count"],
            qrs_count=features["qrs_count"],
        ),
    )


# --- Маршруты ----------------------------------------------------------------


@app.post(
    "/analyze",
    response_model=AnalysisResponse,
    summary="Обработать загруженный файл сигнала",
    responses={400: {"model": ErrorResponse, "description": "Ошибка валидации запроса"}},
)
async def analyze_signal(
    file: Annotated[
        UploadFile,
        File(description="Файл .txt или .csv с отсчётами сигнала (одно число на строку или несколько колонок)"),
    ],
    fs: Annotated[float, Query(description="Частота дискретизации сигнала, Гц")] = config.DEFAULT_SAMPLING_RATE_HZ,
    column: Annotated[int, Query(description="Индекс колонки с сигналом (с 0)")] = config.DEFAULT_COLUMN_INDEX,
) -> AnalysisResponse:
    """Фильтрует сигнал, находит QRS-комплексы и считает признаки варианта 4."""
    _validate_extension(file.filename)
    _validate_sampling_rate(fs)
    if column < 0:
        raise ApiError(config.ERROR_INVALID_COLUMN, f"Индекс колонки не может быть отрицательным: {column}")

    contents = await file.read()
    if not contents.strip():
        raise ApiError(config.ERROR_EMPTY_FILE, "Файл пуст или не содержит данных")

    rows = _parse_rows(_decode(contents))
    if not rows:
        raise ApiError(config.ERROR_EMPTY_FILE, "Файл не содержит ни одной строки с данными")

    raw_signal = _extract_column(rows, column)
    if len(raw_signal) < config.MIN_SIGNAL_SAMPLES:
        raise ApiError(
            config.ERROR_SIGNAL_TOO_SHORT,
            f"Сигнал слишком короткий: {len(raw_signal)} отсчётов, "
            f"нужно не меньше {config.MIN_SIGNAL_SAMPLES}",
        )

    try:
        result = signal_processor.process_biosignal(raw_signal, fs)
    except ValueError as error:
        raise ApiError(config.ERROR_SIGNAL_TOO_SHORT, str(error)) from error

    return _build_response(result, fs)


@app.get(
    "/variant",
    response_model=VariantResponse,
    summary="Параметры варианта 4",
)
async def get_variant() -> VariantResponse:
    """Возвращает параметры обработки, зафиксированные вариантом 4."""
    return VariantResponse(
        variant=config.VARIANT,
        title=config.VARIANT_TITLE,
        signal_type="ECG",
        default_fs=config.DEFAULT_SAMPLING_RATE_HZ,
        filtering=FilteringDescription(
            moving_average_window=config.MOVING_AVERAGE_WINDOW,
            highpass=HighpassDescription(
                type="butterworth",
                order=config.HIGHPASS_ORDER,
                cutoff_hz=config.HIGHPASS_CUTOFF_HZ,
                zero_phase=True,
            ),
        ),
        qrs_detection=QrsDetectionDescription(
            energy_window_ms=config.R_PEAK_ENERGY_WINDOW_MS,
            energy_threshold_ratio=config.R_PEAK_ENERGY_THRESHOLD_RATIO,
            refractory_ms=config.R_PEAK_REFRACTORY_MS,
            refine_window_ms=config.R_PEAK_REFINE_WINDOW_MS,
            qrs_energy_smoothing_ms=config.QRS_ENERGY_SMOOTHING_MS,
            qrs_energy_threshold_ratio=config.QRS_ENERGY_THRESHOLD_RATIO,
            qrs_search_before_ms=config.QRS_SEARCH_BEFORE_MS,
            qrs_search_after_ms=config.QRS_SEARCH_AFTER_MS,
        ),
        features=[
            "mean_qrs_width_ms",
            "max_peak_amplitude",
            "mean_amplitude",
            "std_amplitude",
            "heart_rate_bpm",
            "r_peak_count",
            "qrs_count",
        ],
    )


if __name__ == "__main__":
    uvicorn.run("app:app", host=config.SERVER_HOST, port=config.SERVER_PORT, reload=True)
