"""Конвейер обработки ЭКГ: фильтрация → детекция → признаки."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

import config
from biosignal.processing.detectors import QrsBoundaryDetector, RPeakDetector
from biosignal.processing.features import FeatureExtractor
from biosignal.processing.filters import ButterworthHighPassFilter, MovingAverageFilter
from biosignal.processing.models import ProcessingResult


class EcgPipeline:
    """Оркестратор этапов варианта 4.

    Компоненты внедряются через конструктор, поэтому любой этап можно заменить
    (например, в тестах) без изменения остальных.
    """

    def __init__(
        self,
        moving_average_filter: MovingAverageFilter | None = None,
        high_pass_filter: ButterworthHighPassFilter | None = None,
        r_peak_detector: RPeakDetector | None = None,
        qrs_boundary_detector: QrsBoundaryDetector | None = None,
        feature_extractor: FeatureExtractor | None = None,
    ) -> None:
        self._moving_average = moving_average_filter or MovingAverageFilter()
        self._high_pass = high_pass_filter or ButterworthHighPassFilter()
        self._r_peak_detector = r_peak_detector or RPeakDetector()
        self._qrs_boundary_detector = qrs_boundary_detector or QrsBoundaryDetector()
        self._feature_extractor = feature_extractor or FeatureExtractor()

    def process(
        self,
        raw_signal: Sequence[float] | np.ndarray,
        fs: float = config.DEFAULT_SAMPLING_RATE_HZ,
    ) -> ProcessingResult:
        """Выполняет полный цикл обработки сигнала.

        :raises ValueError: если сигнал короче двух отсчётов или ``fs <= 0``.
        """
        raw = np.asarray(raw_signal, dtype=float)
        if raw.size < 2:
            raise ValueError("Для обработки нужно минимум 2 отсчёта")
        if not math.isfinite(fs) or fs <= 0.0:
            raise ValueError("Частота дискретизации должна быть положительной")

        smoothed = self._moving_average.apply(raw)
        filtered = self._high_pass.apply(smoothed, fs)

        r_peaks = self._r_peak_detector.detect(filtered, fs)
        complexes = self._qrs_boundary_detector.detect(filtered, r_peaks, fs)
        features = self._feature_extractor.extract(filtered, complexes, fs)

        return ProcessingResult(
            raw_signal=raw.tolist(),
            filtered_signal=filtered.tolist(),
            complexes=complexes,
            features=features,
        )
