"""Сборка JSON-ответа из результата конвейера."""

from __future__ import annotations

import config
from biosignal.api.schemas import (
    AnalysisResponse,
    CalculatedFeatures,
    QrsEvent,
)
from biosignal.processing.models import ProcessingResult
from biosignal.processing.signal_math import MILLISECONDS_PER_SECOND


class AnalysisResponseBuilder:
    """Округляет числа и преобразует доменные модели в схемы ответа."""

    def build(self, result: ProcessingResult, fs: float) -> AnalysisResponse:
        """Собирает успешный ответ анализа."""
        features = result.features
        return AnalysisResponse(
            status=config.STATUS_SUCCESS,
            fs=fs,
            variant=config.VARIANT,
            signal_length=len(result.raw_signal),
            raw_signal=[self._round(value) for value in result.raw_signal],
            filtered_signal=[self._round(value) for value in result.filtered_signal],
            detected_events=[
                QrsEvent(
                    type="QRS_COMPLEX",
                    r_peak_index=complex_.r_peak_index,
                    onset_index=complex_.onset_index,
                    offset_index=complex_.offset_index,
                    onset_time_ms=self._round(
                        complex_.onset_index / fs * MILLISECONDS_PER_SECOND
                    ),
                    offset_time_ms=self._round(
                        complex_.offset_index / fs * MILLISECONDS_PER_SECOND
                    ),
                    width_ms=self._round(complex_.width_ms(fs)),
                )
                for complex_ in result.complexes
            ],
            calculated_features=CalculatedFeatures(
                mean_qrs_width_ms=self._optional(features.mean_qrs_width_ms),
                max_peak_amplitude=self._optional(features.max_peak_amplitude),
                mean_amplitude=self._optional(features.mean_amplitude),
                std_amplitude=self._optional(features.std_amplitude),
                heart_rate_bpm=self._optional(features.heart_rate_bpm),
                r_peak_count=features.r_peak_count,
                qrs_count=features.qrs_count,
            ),
        )

    @staticmethod
    def _round(value: float) -> float:
        return round(float(value), config.RESPONSE_DECIMAL_PLACES)

    def _optional(self, value: float | None) -> float | None:
        return None if value is None else self._round(value)
