"""Pydantic-схемы запросов и ответов (одновременно документация Swagger)."""

from __future__ import annotations

from pydantic import BaseModel, Field

import config


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
    max_peak_amplitude: float | None = Field(
        description="Максимальная пиковая амплитуда (артефактный максимум)"
    )
    mean_amplitude: float | None = Field(description="Среднее значение отфильтрованного сигнала")
    std_amplitude: float | None = Field(
        description="СКО отфильтрованного сигнала (по генеральной совокупности)"
    )
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
