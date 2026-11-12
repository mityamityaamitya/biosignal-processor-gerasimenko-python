"""Маршрут GET /variant."""

from __future__ import annotations

from fastapi import APIRouter

import config
from biosignal.api.schemas import (
    FilteringDescription,
    HighpassDescription,
    QrsDetectionDescription,
    VariantResponse,
)

router = APIRouter(tags=["variant"])


@router.get(
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
