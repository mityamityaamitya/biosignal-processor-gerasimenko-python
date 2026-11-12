"""Расчёт признаков варианта 4."""

from __future__ import annotations

import numpy as np

from biosignal.processing.models import QrsComplex, SignalFeatures
from biosignal.processing.signal_math import MILLISECONDS_PER_SECOND

SECONDS_PER_MINUTE = 60.0


class FeatureExtractor:
    """Считает признаки по отфильтрованному сигналу и найденным комплексам.

    Все величины берутся по отфильтрованному сигналу: дрейф и тремор уже
    убраны, амплитуды сопоставимы между комплексами и участками записи.
    """

    def extract(
        self,
        filtered: np.ndarray,
        complexes: list[QrsComplex],
        fs: float,
    ) -> SignalFeatures:
        """Возвращает набор признаков варианта."""
        values = np.asarray(filtered, dtype=float)
        if values.size == 0:
            return SignalFeatures(
                mean_qrs_width_ms=None,
                max_peak_amplitude=None,
                mean_amplitude=None,
                std_amplitude=None,
                heart_rate_bpm=None,
                r_peak_count=0,
                qrs_count=0,
            )

        widths_ms = [complex_.width_ms(fs) for complex_ in complexes]
        mean_width = float(np.mean(widths_ms)) if widths_ms else None

        heart_rate = self._heart_rate(complexes, fs)
        qrs_count = sum(
            1
            for complex_ in complexes
            if complex_.onset_index < complex_.r_peak_index <= complex_.offset_index
        )

        return SignalFeatures(
            mean_qrs_width_ms=mean_width,
            max_peak_amplitude=float(values.max()),
            mean_amplitude=float(values.mean()),
            std_amplitude=float(values.std()),
            heart_rate_bpm=heart_rate,
            r_peak_count=len(complexes),
            qrs_count=qrs_count,
        )

    @staticmethod
    def _heart_rate(complexes: list[QrsComplex], fs: float) -> float | None:
        """ЧСС как ``60000 / mean(RR)``; ``None``, если комплексов меньше двух."""
        if len(complexes) < 2:
            return None
        r_peaks = np.asarray([complex_.r_peak_index for complex_ in complexes], dtype=float)
        rr_ms = np.diff(r_peaks) / fs * MILLISECONDS_PER_SECOND
        mean_rr = float(rr_ms.mean())
        if mean_rr <= 0.0:
            return None
        return SECONDS_PER_MINUTE * MILLISECONDS_PER_SECOND / mean_rr
