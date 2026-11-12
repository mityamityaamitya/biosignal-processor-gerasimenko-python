"""Детекторы: R-пики (Pan–Tompkins-подобный) и границы QRS."""

from __future__ import annotations

import numpy as np

import config
from biosignal.processing.models import QrsComplex
from biosignal.processing.signal_math import (
    derivative_energy,
    moving_average,
    odd_window_samples,
    samples_from_ms,
    sliding_window_max,
)


class RPeakDetector:
    """Поиск R-пиков по энергии первой производной.

    Шаги: центральная производная → энергия → сглаживание 80 мс → порог
    (30 % от локального максимума, но не ниже 5 % глобального) → локальные
    максимумы с рефрактерным периодом 200 мс → уточнение как ``argmax |y|``
    в окне ±40 мс.
    """

    def __init__(
        self,
        energy_window_ms: float = config.R_PEAK_ENERGY_WINDOW_MS,
        threshold_ratio: float = config.R_PEAK_ENERGY_THRESHOLD_RATIO,
        local_window_sec: float = config.R_PEAK_LOCAL_WINDOW_SEC,
        global_floor_ratio: float = config.R_PEAK_GLOBAL_FLOOR_RATIO,
        refine_window_ms: float = config.R_PEAK_REFINE_WINDOW_MS,
        refractory_ms: float = config.R_PEAK_REFRACTORY_MS,
        edge_guard_ms: float = config.R_PEAK_EDGE_GUARD_MS,
    ) -> None:
        self._energy_window_ms = energy_window_ms
        self._threshold_ratio = threshold_ratio
        self._local_window_sec = local_window_sec
        self._global_floor_ratio = global_floor_ratio
        self._refine_window_ms = refine_window_ms
        self._refractory_ms = refractory_ms
        self._edge_guard_ms = edge_guard_ms

    def detect(self, filtered: np.ndarray, fs: float) -> list[int]:
        """Возвращает отсортированные индексы R-пиков."""
        values = np.asarray(filtered, dtype=float)
        size = values.size
        if size < 3:
            return []

        energy = derivative_energy(values)
        smoothed = moving_average(energy, odd_window_samples(self._energy_window_ms, fs))
        global_max = float(smoothed.max())
        if global_max <= 0.0:
            return []

        half_local = samples_from_ms(self._local_window_sec * 1000.0, fs)
        local_max = sliding_window_max(smoothed, half_local)
        floor = self._global_floor_ratio * global_max
        refractory = samples_from_ms(self._refractory_ms, fs)
        guard = samples_from_ms(self._edge_guard_ms, fs)
        refine_half = samples_from_ms(self._refine_window_ms, fs)

        candidates: list[int] = []
        for i in range(1, size - 1):
            if i < guard or i > size - 1 - guard:
                continue
            value = float(smoothed[i])
            if value <= floor:
                continue
            if value <= self._threshold_ratio * float(local_max[i]):
                continue
            # Локальный максимум; плато допускается (сравнение нестрогое).
            if value < smoothed[i - 1] or value < smoothed[i + 1]:
                continue

            if candidates and i - candidates[-1] < refractory:
                # В пределах рефрактерного периода оставляем более сильный кандидат.
                if value > smoothed[candidates[-1]]:
                    candidates[-1] = i
                continue
            candidates.append(i)

        refined = {self._refine_peak(values, candidate, refine_half) for candidate in candidates}
        return sorted(refined)

    @staticmethod
    def _refine_peak(data: np.ndarray, candidate: int, half: int) -> int:
        """Уточняет вершину R как ``argmax |y|`` в окне ±half вокруг кандидата."""
        start = max(0, candidate - half)
        stop = min(data.size - 1, candidate + half)
        segment = np.abs(data[start : stop + 1])
        return start + int(np.argmax(segment))


class QrsBoundaryDetector:
    """Границы QRS по падению энергии первой производной ниже порога.

    Энергия — ``|Δ|``, сглаженная окном 20 мс (квадрат исказил бы смысл доли
    порога). Проход начинается с пропуска «мёртвой зоны» у вершины R, где
    производная близка к нулю. Инвариант ``onset < r ≤ offset`` гарантируется
    конструктивно, ширина ограничена физиологичными пределами.
    """

    def __init__(
        self,
        smoothing_ms: float = config.QRS_ENERGY_SMOOTHING_MS,
        threshold_ratio: float = config.QRS_ENERGY_THRESHOLD_RATIO,
        search_before_ms: float = config.QRS_SEARCH_BEFORE_MS,
        search_after_ms: float = config.QRS_SEARCH_AFTER_MS,
        min_width_ms: float = config.MIN_QRS_WIDTH_MS,
        max_width_ms: float = config.MAX_QRS_WIDTH_MS,
    ) -> None:
        self._smoothing_ms = smoothing_ms
        self._threshold_ratio = threshold_ratio
        self._search_before_ms = search_before_ms
        self._search_after_ms = search_after_ms
        self._min_width_ms = min_width_ms
        self._max_width_ms = max_width_ms

    def detect(self, filtered: np.ndarray, r_peaks: list[int], fs: float) -> list[QrsComplex]:
        """Возвращает границы комплексов для каждого R-пика."""
        values = np.asarray(filtered, dtype=float)
        size = values.size
        if size == 0 or not r_peaks:
            return []

        energy = self._smoothed_energy(values, fs)
        before = samples_from_ms(self._search_before_ms, fs)
        after = samples_from_ms(self._search_after_ms, fs)
        min_width = samples_from_ms(self._min_width_ms, fs)
        max_width = max(min_width, samples_from_ms(self._max_width_ms, fs))

        complexes: list[QrsComplex] = []
        for peak in r_peaks:
            r_peak = min(max(int(peak), 0), size - 1)
            window_start = max(0, r_peak - before)
            window_end = min(size - 1, r_peak + after)
            threshold = self._threshold_ratio * float(
                energy[window_start : window_end + 1].max()
            )

            onset = window_start
            left = r_peak
            while left >= window_start and energy[left] < threshold:
                left -= 1
            if left >= window_start:
                onset = left
                index = left - 1
                while index >= window_start and energy[index] >= threshold:
                    onset = index
                    index -= 1

            offset = window_end
            right = r_peak
            while right <= window_end and energy[right] < threshold:
                right += 1
            if right <= window_end:
                while right <= window_end and energy[right] >= threshold:
                    right += 1
                offset = min(right, window_end)

            onset, offset = self._clamp_boundaries(
                r_peak=r_peak,
                onset=onset,
                offset=offset,
                min_width=min_width,
                max_width=max_width,
                size=size,
            )
            complexes.append(
                QrsComplex(
                    r_peak_index=r_peak,
                    onset_index=onset,
                    offset_index=offset,
                )
            )
        return complexes

    def _smoothed_energy(self, values: np.ndarray, fs: float) -> np.ndarray:
        """Энергия первой разности ``|y[i] - y[i-1]|``, сглаженная окном."""
        difference = np.abs(np.diff(values, prepend=values[0]))
        return moving_average(difference, odd_window_samples(self._smoothing_ms, fs))

    @staticmethod
    def _clamp_boundaries(
        r_peak: int,
        onset: int,
        offset: int,
        min_width: int,
        max_width: int,
        size: int,
    ) -> tuple[int, int]:
        """Приводит границы к физиологичным пределам и инварианту ``onset < r ≤ offset``."""
        width = offset - onset
        if width < min_width or width > max_width:
            target = min_width if width < min_width else max_width
            half = target // 2
            onset = max(0, r_peak - half)
            offset = min(size - 1, onset + target)
            onset = max(0, offset - target)

        if onset >= r_peak:
            onset = max(0, r_peak - 1)
        if offset < r_peak:
            offset = min(size - 1, r_peak)
        return onset, offset
