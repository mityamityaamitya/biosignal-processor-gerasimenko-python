"""Фасад математического ядра (совместимость с шаблоном задания).

Реализация живёт в пакете ``biosignal.processing``: фильтры, детекторы,
признаки и конвейер разнесены по отдельным модулям. Здесь остаётся функция
``process_biosignal`` — центральная точка входа, которую ожидает шаблон, — и
реэкспорт компонентов для прямого использования.

Модуль не импортирует FastAPI/Flask/uvicorn: ядро тестируется отдельно от сети.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import config
from biosignal.processing import (
    ButterworthHighPassFilter,
    EcgPipeline,
    FeatureExtractor,
    MovingAverageFilter,
    ProcessingResult,
    QrsBoundaryDetector,
    QrsComplex,
    RPeakDetector,
    SignalFeatures,
)
from biosignal.processing.signal_math import MILLISECONDS_PER_SECOND

_DEFAULT_PIPELINE = EcgPipeline()


def _event_to_dict(complex_: QrsComplex, fs: float) -> dict[str, Any]:
    """Преобразует комплекс в элемент ``detected_events``."""
    return {
        "type": "QRS_COMPLEX",
        "r_peak_index": complex_.r_peak_index,
        "onset_index": complex_.onset_index,
        "offset_index": complex_.offset_index,
        "onset_time_ms": complex_.onset_index / fs * MILLISECONDS_PER_SECOND,
        "offset_time_ms": complex_.offset_index / fs * MILLISECONDS_PER_SECOND,
        "width_ms": complex_.width_ms(fs),
    }


def process_biosignal(
    raw_signal_list: list[float],
    fs: float = config.DEFAULT_SAMPLING_RATE_HZ,
) -> dict[str, Any]:
    """Центральная функция управления конвейером обработки.

    :param raw_signal_list: отсчёты исходного сигнала;
    :param fs: частота дискретизации, Гц;
    :returns: словарь с исходным и отфильтрованным сигналом, событиями и
        признаками (готов к сериализации в JSON);
    :raises ValueError: если сигнал короче двух отсчётов или ``fs <= 0``.
    """
    result: ProcessingResult = _DEFAULT_PIPELINE.process(raw_signal_list, fs)
    return {
        "raw_signal": result.raw_signal,
        "filtered_signal": result.filtered_signal,
        "detected_events": [_event_to_dict(complex_, fs) for complex_ in result.complexes],
        "calculated_features": asdict(result.features),
    }


__all__ = [
    "ButterworthHighPassFilter",
    "EcgPipeline",
    "FeatureExtractor",
    "MovingAverageFilter",
    "ProcessingResult",
    "QrsBoundaryDetector",
    "QrsComplex",
    "RPeakDetector",
    "SignalFeatures",
    "process_biosignal",
]
