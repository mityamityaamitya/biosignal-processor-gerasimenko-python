"""Модели данных конвейера обработки ЭКГ."""

from __future__ import annotations

from dataclasses import dataclass

from biosignal.processing.signal_math import MILLISECONDS_PER_SECOND


@dataclass(frozen=True)
class QrsComplex:
    """Найденный QRS-комплекс.

    ``onset`` — последний отсчёт выше порога слева от R, ``offset`` — первый
    отсчёт ниже порога справа; ширина равна ``offset − onset``.
    """

    r_peak_index: int
    onset_index: int
    offset_index: int

    @property
    def width_samples(self) -> int:
        """Ширина комплекса в отсчётах."""
        return self.offset_index - self.onset_index

    def width_ms(self, fs: float) -> float:
        """Ширина комплекса в миллисекундах."""
        return self.width_samples / fs * MILLISECONDS_PER_SECOND


@dataclass(frozen=True)
class SignalFeatures:
    """Признаки варианта 4, рассчитанные по отфильтрованному сигналу."""

    mean_qrs_width_ms: float | None
    max_peak_amplitude: float | None
    mean_amplitude: float | None
    std_amplitude: float | None
    heart_rate_bpm: float | None
    r_peak_count: int
    qrs_count: int


@dataclass(frozen=True)
class ProcessingResult:
    """Результат полного конвейера обработки."""

    raw_signal: list[float]
    filtered_signal: list[float]
    complexes: list[QrsComplex]
    features: SignalFeatures
