"""Фильтры конвейера: скользящее среднее и ФВЧ Баттерворта с нулевой фазой."""

from __future__ import annotations

import numpy as np
from scipy import signal as scipy_signal

import config
from biosignal.processing.signal_math import moving_average


class MovingAverageFilter:
    """Центрированное скользящее среднее по окну ``window`` отсчётов."""

    def __init__(self, window: int = config.MOVING_AVERAGE_WINDOW) -> None:
        if window < 1:
            raise ValueError(f"Размер окна должен быть положительным, получено {window}")
        self._window = window

    @property
    def window(self) -> int:
        """Размер окна, отсчётов."""
        return self._window

    def apply(self, data: np.ndarray) -> np.ndarray:
        """Возвращает сглаженный сигнал."""
        return moving_average(data, self._window)


class ButterworthHighPassFilter:
    """ФВЧ Баттерворта с нулевой фазой (двойной проход ``filtfilt``).

    Двойной проход удваивает эффективный порядок и обнуляет фазовый набег,
    поэтому вершина R не смещается. ``padlen`` не меньше ``3·fs``: полюс 0,5 Гц
    близок к единичной окружности, и при коротком паддинге переходный процесс
    на первых отсчётах порождает ложный R-пик. ``padtype="even"`` — отражение
    с реверсом без повтора крайнего отсчёта, как в эталонной реализации.
    """

    def __init__(
        self,
        cutoff_hz: float = config.HIGHPASS_CUTOFF_HZ,
        order: int = config.HIGHPASS_ORDER,
        padding_seconds: float = config.FILTFILT_PADDING_SECONDS,
        min_padding_samples: int = config.FILTFILT_MIN_PADDING_SAMPLES,
    ) -> None:
        if cutoff_hz <= 0:
            raise ValueError(f"Частота среза должна быть положительной, получено {cutoff_hz}")
        if order < 1:
            raise ValueError(f"Порядок фильтра должен быть положительным, получено {order}")
        self._cutoff_hz = cutoff_hz
        self._order = order
        self._padding_seconds = padding_seconds
        self._min_padding_samples = min_padding_samples

    @property
    def cutoff_hz(self) -> float:
        """Частота среза, Гц."""
        return self._cutoff_hz

    @property
    def order(self) -> int:
        """Порядок фильтра."""
        return self._order

    def coefficients(self, fs: float) -> tuple[np.ndarray, np.ndarray]:
        """Коэффициенты ``b`` и ``a`` для заданной частоты дискретизации."""
        if fs <= 0:
            raise ValueError(f"Частота дискретизации должна быть положительной, получено {fs}")
        if self._cutoff_hz >= fs / 2.0:
            raise ValueError(
                f"Частота среза {self._cutoff_hz} Гц должна быть меньше Найквиста {fs / 2.0} Гц"
            )
        return scipy_signal.butter(
            self._order,
            self._cutoff_hz,
            btype="high",
            fs=fs,
        )

    def apply(self, data: np.ndarray, fs: float) -> np.ndarray:
        """Возвращает отфильтрованный сигнал."""
        values = np.asarray(data, dtype=float)
        if values.size < 2:
            return values.copy()

        b, a = self.coefficients(fs)
        padding = max(self._min_padding_samples, int(self._padding_seconds * fs))
        padding = min(padding, values.size - 1)
        return scipy_signal.filtfilt(b, a, values, padlen=padding, padtype="even")
